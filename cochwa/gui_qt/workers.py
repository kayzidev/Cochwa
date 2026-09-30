"""Pont threads → GUI : remplace le Dispatcher Tkinter par des signaux Qt.

Les workers (recherche, jaquettes, scan, conversions) ne touchent jamais les
widgets ; les résultats arrivent par connexions en file (thread GUI).
"""

from __future__ import annotations

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
    """Jaquettes via le service existant ; cache mémoire + disque, dédup par titre de base."""

    loaded = Signal(str, object)  # titre de base, chemin ou None

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.results = {}  # titre de base -> Path ou None (cache négatif inclus)
        self.pending = set()
        self.fallback_urls = {}
        self.worker = Worker(self)

    def request(self, title, ia_identifier=None):
        from cochwa.api.steamgriddb import download_cover

        base = title.split("(")[0].strip()
        if base in self.results or base in self.pending:
            return
        if not self.config.steamgrid_api_key and not ia_identifier:
            self.results[base] = None
            return
        self.pending.add(base)

        def work():
            try:
                path = download_cover(
                    self.config.steamgrid_api_key,
                    base,
                    cache_dir=self.config.cache_dir / "covers",
                    ia_identifier=ia_identifier,
                )
                return path
            except Exception:
                return None

        def deliver(path):
            self.pending.discard(base)
            fallback = self.fallback_urls.pop(base, "")
            if not path and fallback:
                self.request_igdb_cover(base, fallback)
                return
            self.results[base] = path
            self.loaded.emit(base, path)

        self.worker.submit(work, deliver)

    def request_igdb_cover(self, title, url):
        """Télécharge une image IGDB après validation du match par le client."""
        base = title.split("(")[0].strip()
        if not url.startswith("https://images.igdb.com/igdb/image/upload/"):
            return
        if self.results.get(base):
            return
        if base in self.pending:
            self.fallback_urls[base] = url
            return
        self.pending.add(base)

        def work():
            from hashlib import sha256

            from cochwa.api.steamgriddb import _fetch_image
            from cochwa.infrastructure.storage import atomic_write

            key = sha256(base.casefold().encode()).hexdigest()
            path = self.config.cache_dir / "covers" / f"{key}.png"
            atomic_write(path, _fetch_image(url, portrait=True))
            return path

        def deliver(path):
            self.pending.discard(base)
            self.results[base] = path
            self.loaded.emit(base, path)

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

    @property
    def configured(self):
        return self.client.configured

    def configure(self, client_id, client_secret):
        self.client.configure(client_id, client_secret)

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
        from cochwa.services.igdb import CATALOG_TTL

        if not self.configured or self.busy:
            return False
        now = time.time()
        stale = []
        for console in self.consoles:
            if not console.enabled:
                continue
            path = self.config.cache_dir / "catalogs" / f"igdb-{console.id}.json"
            try:
                saved = path.stat().st_mtime
            except OSError:
                stale.append(console.id)
                continue
            if now - saved >= CATALOG_TTL:
                stale.append(console.id)
        return self.refresh_all(stale) if stale else False
