"""Pont threads → GUI : remplace le Dispatcher Tkinter par des signaux Qt.

Les workers (recherche, jaquettes, scan, conversions) ne touchent jamais les
widgets ; les résultats arrivent par connexions en file (thread GUI).
"""

from __future__ import annotations

import json
import time

from PySide6.QtCore import QObject, QThreadPool, Signal


class _Task(QObject):
    success = Signal(object)
    error = Signal(str)

    def __init__(self, work):
        super().__init__()
        self._work = work

    def run(self):
        try:
            self.success.emit(self._work())
        except Exception as exc:
            self.error.emit(str(exc))


class Worker(QObject):
    """Soumet des callables au pool ; les callbacks sont livrés dans le thread GUI."""

    def __init__(self, parent=None, threads=4):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(threads)
        self._tasks = set()

    def submit(self, work, on_success=None, on_error=None):
        task = _Task(work)
        self._tasks.add(task)  # garde la référence jusqu'à livraison
        if on_success:
            task.success.connect(on_success)
        task.error.connect(on_error or (lambda message: None))
        task.success.connect(lambda *_: self._tasks.discard(task))
        task.error.connect(lambda *_: self._tasks.discard(task))
        self.pool.start(task.run)


class CoverService(QObject):
    """Jaquettes isolées par plateforme et titre normalisé."""

    loaded = Signal(str, str, object)  # plateforme, titre de recherche, chemin ou None

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.results = {}  # (plateforme, titre) -> Path ou None
        self.pending = set()
        self.fallback_urls = {}
        self.sources = {}
        self.generation = 0
        self.worker = Worker(self)

    def invalidate(self):
        """Relance les recherches après changement de clé sans perdre les choix manuels."""
        self.generation += 1
        manual = {key for key, source in self.sources.items() if source == "manual"}
        self.results = {key: value for key, value in self.results.items() if key in manual}
        self.sources = {key: "manual" for key in manual}
        self.pending.clear()
        self.fallback_urls.clear()

    @staticmethod
    def _saved_source(path):
        try:
            return json.loads(path.with_suffix(".source.json").read_text()).get("source", "")
        except (OSError, ValueError, AttributeError):
            return ""

    def request(self, title, platform, ia_identifier=None):
        from cochwa.api.steamgriddb import download_cover
        from cochwa.util import artwork_search_title

        base = artwork_search_title(title)
        key = (platform, base)
        if key in self.results or key in self.pending:
            return
        from cochwa.api.steamgriddb import cover_cache_path

        cached = cover_cache_path(self.config.cache_dir / "covers", platform, base)
        if cached.is_file():
            from PIL import Image

            try:
                with Image.open(cached) as image:
                    image.verify()
            except (OSError, ValueError):
                pass
            else:
                self.results[key] = cached
                self.sources[key] = self._saved_source(cached) or "sgdb_or_ia"
                self.loaded.emit(platform, base, cached)
                return
        if not self.config.steamgrid_api_key and not ia_identifier:
            self.results[key] = None
            return
        self.pending.add(key)
        generation = self.generation

        def work():
            try:
                path = download_cover(
                    self.config.steamgrid_api_key,
                    base,
                    cache_dir=self.config.cache_dir / "covers",
                    ia_identifier=ia_identifier,
                    platform=platform,
                )
                return path
            except Exception:
                return None

        def deliver(path):
            if generation != self.generation:
                return
            self.pending.discard(key)
            fallback = self.fallback_urls.pop(key, "")
            if self.sources.get(key) != "manual":
                self.results[key] = path
                if path:
                    self.sources[key] = self._saved_source(path) or "sgdb_or_ia"
                self.loaded.emit(platform, base, path)
            if fallback:
                self.request_igdb_cover(base, fallback, platform)

        self.worker.submit(work, deliver)

    def request_igdb_cover(self, title, url, platform):
        """La jaquette IGDB validée par plateforme prime sur le match textuel."""
        from cochwa.util import artwork_search_title

        base = artwork_search_title(title)
        key = (platform, base)
        if not url.startswith("https://images.igdb.com/igdb/image/upload/"):
            return
        if self.sources.get(key) in {"manual", "igdb"}:
            return
        from cochwa.api.steamgriddb import cover_cache_path

        cached = cover_cache_path(self.config.cache_dir / "covers", platform, base)
        saved_source = self._saved_source(cached) if cached.is_file() else ""
        if saved_source in {"manual", "igdb"}:
            self.results[key] = cached
            self.sources[key] = saved_source
            self.loaded.emit(platform, base, cached)
            return
        if key in self.pending:
            self.fallback_urls[key] = url
            return
        self.pending.add(key)
        generation = self.generation

        def work():
            from cochwa.api.steamgriddb import _fetch_image, cover_cache_lock, cover_cache_path
            from cochwa.infrastructure.storage import atomic_write, write_json

            path = cover_cache_path(self.config.cache_dir / "covers", platform, base)
            data = _fetch_image(url, portrait=True)
            with cover_cache_lock(path):
                if self._saved_source(path) != "manual":
                    atomic_write(path, data)
                    try:
                        write_json(path.with_suffix(".source.json"), {"source": "igdb"})
                    except OSError:
                        pass
            return path

        def deliver(path):
            if generation != self.generation:
                return
            self.pending.discard(key)
            if path and self.sources.get(key) != "manual":
                self.results[key] = path
                self.sources[key] = "igdb"
                self.loaded.emit(platform, base, path)
            elif key not in self.results:
                self.results[key] = None
                self.loaded.emit(platform, base, None)

        self.worker.submit(work, deliver, lambda _: deliver(None))


class GameMetadataService(QObject):
    """Enrichissement IGDB asynchrone, partagé entre cartes et fiches."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        from cochwa.services.igdb import IGDBClient

        self.client = IGDBClient(config)
        self.worker = Worker(self, threads=1)
        self.cache = {}
        self.pending = {}

    def configure(self, client_id, client_secret):
        self.client.configure(client_id, client_secret)
        self.cache.clear()

    def request(self, title, platform, callback=None):
        if not self.client.configured:
            if callback:
                callback(None)
            return
        key = (platform, title.casefold().strip())
        if key in self.cache:
            if callback:
                callback(self.cache[key])
            return
        if key in self.pending:
            if callback:
                self.pending[key].append(callback)
            return
        self.pending[key] = [callback] if callback else []

        def deliver(metadata):
            callbacks = self.pending.pop(key, [])
            self.cache[key] = metadata
            for done in callbacks:
                done(metadata)

        self.worker.submit(
            lambda: self.client.enrich(title, platform), deliver, lambda _: deliver(None)
        )


class GameCatalogService(QObject):
    """Synchronise les catalogues complets IGDB hors du thread graphique."""

    updated = Signal(object)
    failed = Signal(str)

    def __init__(self, config, consoles, parent=None):
        super().__init__(parent)
        from cochwa.services.igdb import IGDBClient

        self.config = config
        self.consoles = consoles
        self.client = IGDBClient(config)
        self.worker = Worker(self, threads=1)
        self.busy = False
        self._last_auto_attempt = {}

    @property
    def configured(self):
        return self.client.configured

    def configure(self, client_id, client_secret):
        changed = (self.client.client_id, self.client.client_secret) != (
            client_id.strip(),
            client_secret.strip(),
        )
        self.client.configure(client_id, client_secret)
        if changed:
            self._last_auto_attempt.clear()

    def refresh_all(self, consoles=None):
        if self.busy:
            return False
        if not self.configured:
            self.failed.emit("Configurez Twitch Client ID et Client Secret dans Paramètres.")
            return False
        self.busy = True
        requested = set(consoles) if consoles is not None else None
        enabled = [
            console
            for console in self.consoles
            if console.enabled and (requested is None or console.id in requested)
        ]

        def work():
            result = {"updated": {}, "errors": {}}
            for console in enabled:
                try:
                    self.client.sync_catalog(console.id, console.name)
                    result["updated"][console.id] = True
                except Exception as exc:
                    result["errors"][console.id] = f"{type(exc).__name__}: {exc}"
            return result

        def done(result):
            self.busy = False
            from cochwa.catalog import clear_catalog_cache

            clear_catalog_cache()
            self.updated.emit(result)

        def fail(message):
            self.busy = False
            self.failed.emit(message)

        self.worker.submit(work, done, fail)
        return True

    def refresh_if_stale(self):
        from cochwa.catalog import has_igdb_catalog
        from cochwa.services.igdb import CATALOG_TTL

        if not self.configured or self.busy:
            return False
        now = time.time()
        stale = []
        for console in self.consoles:
            if not console.enabled:
                continue
            path = self.config.cache_dir / "catalogs" / f"igdb-{console.id}.json"
            if not has_igdb_catalog(console.id, self.config.cache_dir):
                stale.append(console.id)
                continue
            try:
                saved = float(json.loads(path.read_text())["time"])
            except (OSError, ValueError, KeyError, TypeError):
                stale.append(console.id)
                continue
            if now - saved >= CATALOG_TTL:
                stale.append(console.id)
        # Un échec réseau ne doit pas relancer le même gros catalogue à chaque
        # visite des Paramètres. Le bouton manuel reste toujours disponible.
        stale = [
            platform
            for platform in stale
            if now - self._last_auto_attempt.get(platform, 0) >= 30 * 60
        ]
        if not stale:
            return False
        if self.refresh_all(stale):
            self._last_auto_attempt.update({platform: now for platform in stale})
            return True
        return False
