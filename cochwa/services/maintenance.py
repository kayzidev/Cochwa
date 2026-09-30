"""Purge bornée et spécifique aux sources des caches.

Les jaquettes positives (covers/<hash>.png) restent permanentes — choix de
design : une jaquette n'est jamais re-téléchargée. Appelé au démarrage de la
GUI et du CLI ; ne lève jamais d'exception (la purge est best-effort).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from cochwa.api.steamgriddb import NEGATIVE_TTL
from cochwa.services.igdb import METADATA_TTL as IGDB_TTL
from cochwa.services.igdb import NEGATIVE_TTL as IGDB_NEGATIVE_TTL

# Les fichiers hashés non préfixés viennent du provider IA (TTL d'appel 1 h).
METADATA_TTL = 3600
IA_COVER_METADATA_TTL = 24 * 60 * 60


def _purge(directory, pattern, timestamp_key, ttl, now, *, excluded_prefixes=(), negative_ttl=None):
    """Supprime les fichiers JSON de `directory` plus vieux que `ttl` (ou illisibles)."""
    removed = 0
    if not directory.is_dir():
        return removed
    for path in directory.glob(pattern):
        if not path.is_file():
            continue
        if path.name.startswith(excluded_prefixes):
            continue
        try:
            data = json.loads(path.read_text())
            stamp = float(data[timestamp_key])
            effective_ttl = negative_ttl if negative_ttl and not data.get("data") else ttl
            expired = now - stamp >= effective_ttl
        except (OSError, ValueError, KeyError, TypeError):
            expired = True  # fichier illisible : inutilisable, on purge
        if not expired:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def purge_expired_caches(cache_dir, now=None):
    """Purge les caches expirés sous `cache_dir` ; retourne les compteurs."""
    now = time.time() if now is None else now
    cache_dir = Path(cache_dir)
    return {
        "metadata": _purge(
            cache_dir / "metadata",
            "*.json",
            "time",
            METADATA_TTL,
            now,
            excluded_prefixes=("ia-", "igdb-"),
        ),
        "ia_cover_metadata": _purge(
            cache_dir / "metadata", "ia-*.json", "time", IA_COVER_METADATA_TTL, now
        ),
        "igdb_metadata": _purge(
            cache_dir / "metadata",
            "igdb-*.json",
            "time",
            IGDB_TTL,
            now,
            negative_ttl=IGDB_NEGATIVE_TTL,
        ),
        # La synchronisation IGDB remplace atomiquement le catalogue. Garder
        # l'ancienne copie évite un Top vide si le réseau échoue au démarrage.
        "catalogs": 0,
        "negative_covers": _purge(cache_dir / "covers", "*.missing.json", "at", NEGATIVE_TTL, now),
    }


def purge_quietly(cache_dir):
    """Purge sans jamais interrompre le démarrage de l'application."""
    try:
        return purge_expired_caches(cache_dir)
    except OSError:
        return {"metadata": 0, "negative_covers": 0}
