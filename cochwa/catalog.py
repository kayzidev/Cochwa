"""Catalogue local et cache IGDB par plateforme.

Source packagée : ``cochwa/data/catalog_ps2.json``. Extension utilisateur
possible via ``~/.config/cochwa/catalog_ps2.json`` (même schéma ; une entrée
dont le titre existe déjà remplace l'entrée packagée, sinon elle s'ajoute) —
le catalogue évolue donc sans toucher au code.

Les titres sont matchés contre le datfile Redump PS2 (lookup MD5) et
recherchés sur Internet Archive au clic (recherche à la demande).
"""

from __future__ import annotations

import json
import random
import time
from importlib import resources

from cochwa.config import DEFAULT_CONFIG_DIR
from cochwa.consoles import get as get_console

USER_CATALOG = DEFAULT_CONFIG_DIR / "catalog_ps2.json"

_cache = {"entries": None, "mtime": None}
_platform_caches = {}
_igdb_status_cache = {}


def clear_catalog_cache():
    """Force la relecture des catalogues après une synchronisation."""
    _cache.update(entries=None, mtime=None)
    _platform_caches.clear()
    _igdb_status_cache.clear()


def _load_packaged(platform="ps2"):
    try:
        text = (
            resources.files("cochwa.data").joinpath(f"catalog_{platform}.json").read_text("utf-8")
        )
        return json.loads(text).get("games", [])
    except (FileNotFoundError, ModuleNotFoundError):
        return []


def _valid_entry(entry):
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("title"), str)
        and entry["title"].strip()
        and isinstance(entry.get("genre", ""), str)
        and (
            "score" not in entry
            or entry["score"] is None
            or (isinstance(entry["score"], (int, float)) and not isinstance(entry["score"], bool))
        )
    )


def _catalog_files(platform, cache_dir=None):
    user = USER_CATALOG if platform == "ps2" else DEFAULT_CONFIG_DIR / f"catalog_{platform}.json"
    remote = None
    if cache_dir is not None:
        remote = cache_dir / "catalogs" / f"igdb-{platform}.json"
    return user, remote


def has_igdb_catalog(platform="ps2", cache_dir=None):
    """Un ancien catalogue complet reste utilisable pendant son actualisation."""
    _, remote = _catalog_files(platform, cache_dir)
    if not remote:
        return False
    try:
        stamp = remote.stat()
        cached = _igdb_status_cache.get(remote)
        signature = (stamp.st_mtime_ns, stamp.st_size)
        if cached and cached[0] == signature:
            return cached[1]
        data = json.loads(remote.read_text())
        valid = (
            isinstance(data, dict)
            and isinstance(data.get("games"), list)
            and len({entry["title"].casefold() for entry in data["games"] if _valid_entry(entry)})
            >= 20
        )
        _igdb_status_cache[remote] = (signature, valid)
        return valid
    except (OSError, ValueError, KeyError, TypeError):
        return False


def catalog_entries(platform="ps2", cache_dir=None):
    """Entrées du catalogue (packagées + extension utilisateur), rechargées
    si le fichier utilisateur change."""
    console = get_console(platform)
    if console is None:
        raise ValueError("Plateforme inconnue")
    user_catalog, remote_catalog = _catalog_files(platform, cache_dir)
    key = (platform, str(cache_dir) if cache_dir is not None else "default")
    cache = (
        _cache
        if key == ("ps2", "default")
        else _platform_caches.setdefault(key, {"entries": None, "mtime": None})
    )
    mtimes = []
    for path in (user_catalog, remote_catalog):
        try:
            mtimes.append(path.stat().st_mtime if path else 0.0)
        except OSError:
            mtimes.append(0.0)
    if cache["entries"] is not None and mtimes == cache["mtime"]:
        return cache["entries"]
    merged = {}
    for entry in _load_packaged(platform):
        if _valid_entry(entry):
            copied = dict(entry)
            if platform == "ps2" and type(copied.get("score")) is int:
                copied.setdefault("metacritic_score", copied["score"])
                copied.setdefault("score_source", "Metacritic · catalogue local")
            merged[copied["title"].casefold()] = copied
    user_entries = []
    try:
        data = json.loads(user_catalog.read_text())
        user_entries = [e for e in data.get("games", []) if _valid_entry(e)]
    except (OSError, ValueError, TypeError):
        pass
    for entry in user_entries:
        merged[entry["title"].casefold()] = dict(entry)
    if remote_catalog and has_igdb_catalog(platform, cache_dir):
        try:
            data = json.loads(remote_catalog.read_text())
            for entry in data.get("games", []):
                if not _valid_entry(entry):
                    continue
                key = entry["title"].casefold()
                prior = merged.get(key, {})
                merged[key] = {**prior, **entry}
        except (OSError, ValueError, TypeError):
            pass
    cache["entries"] = list(merged.values())
    cache["mtime"] = mtimes
    return cache["entries"]


def top_entries(platform="ps2", cache_dir=None):
    """Tous les jeux notés par les critiques IGDB, sinon le Top local historique."""
    entries = catalog_entries(platform, cache_dir)
    igdb_scored = [
        e
        for e in entries
        if e.get("source") == "IGDB" and type(e.get("critic_score")) in (int, float)
    ]
    if igdb_scored:
        return sorted(
            igdb_scored,
            key=lambda e: (
                -float(e["critic_score"]),
                -int(e.get("critic_rating_count") or 0),
                e["title"].casefold(),
            ),
        )
    local = [
        e for e in entries if type(e.get("metacritic_score")) is int or type(e.get("score")) is int
    ]
    if local:
        return sorted(
            local,
            key=lambda e: (
                -int(e.get("metacritic_score", e.get("score", 0))),
                e["title"].casefold(),
            ),
        )
    return sorted(
        (e for e in entries if e.get("top_rank")),
        key=lambda e: (e.get("top_rank", 0), e["title"].casefold()),
    )


def top_titles():
    return [e["title"] for e in top_entries()]


def genres(platform="ps2", cache_dir=None):
    """Genres présents dans le catalogue, triés (pour le filtre de l'onglet Top)."""
    return sorted(
        {e.get("genre", "") for e in catalog_entries(platform, cache_dir) if e.get("genre")}
    )


def recommended_pool(platform="ps2", cache_dir=None):
    """Candidats recommandés ; une sélection de 20 à 30 est affichée."""
    entries = catalog_entries(platform, cache_dir)
    if has_igdb_catalog(platform, cache_dir):
        remote = [e for e in entries if e.get("source") == "IGDB"]
        if len(remote) >= 20:
            return remote
        # Les entrées locales complètent un catalogue IGDB encore parcellaire.
        return remote + [e for e in entries if e.get("source") != "IGDB"]
    return [e for e in entries if e.get("recommended")]


def recommended_entries(count=30, day=None, platform="ps2", cache_dir=None):
    """Sélection variée, au plus 30 jeux, depuis le catalogue local ou IGDB."""
    pool = recommended_pool(platform, cache_dir)
    if has_igdb_catalog(platform, cache_dir):
        remaining = sorted(
            pool,
            key=lambda e: (
                -float(e.get("rating") or 0),
                -float(e.get("score") or 0),
                -int(e.get("rating_count") or 0),
                -int(e.get("hypes") or 0),
                e["title"].casefold(),
            ),
        )
        # Round-robin par genre pour que la sélection ne soit pas monopolisée
        # par les RPG ou les jeux d'action.
        buckets = {}
        for entry in remaining:
            buckets.setdefault(entry.get("genre") or "Autres", []).append(entry)
        pool = []
        while any(buckets.values()):
            for genre in sorted(buckets):
                if buckets[genre]:
                    pool.append(buckets[genre].pop(0))
    else:
        day = time.strftime("%Y%m%d") if day is None else day
        random.Random(str(day)).shuffle(pool)
        if len(pool) < 20:
            known = {entry["title"].casefold() for entry in pool}
            extras = [
                e
                for e in catalog_entries(platform, cache_dir)
                if e["title"].casefold() not in known
            ]
            extras.sort(
                key=lambda e: (
                    -int(e.get("metacritic_score", e.get("score", e.get("top_rank", 0))) or 0),
                    e["title"].casefold(),
                )
            )
            pool.extend(extras)
    desired = min(30, max(20, int(count)))
    return pool[: min(desired, len(pool))]


# Compatibilité avec l'ancienne API (listes statiques).
TOP_PS2 = top_titles()
RECOMMENDED_PS2 = [e["title"] for e in recommended_entries()]
TOP_BY_CONSOLE = {"PS2": TOP_PS2}
