"""Purge bornée des caches : metadata IA expirées et marqueurs négatifs SGDB.

Les jaquettes positives (covers/<hash>.png) restent permanentes — choix de
design : une jaquette n'est jamais re-téléchargée. Appelé au démarrage de la
GUI et du CLI ; ne lève jamais d'exception (la purge est best-effort).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from cochwa.api.steamgriddb import NEGATIVE_TTL

# TTL maximal des réponses IA mises en cache (metadata 1 h, recherches 5 min) :
# un fichier plus vieux que ce seuil est expiré pour tous les appelants.
METADATA_TTL = 3600


def _purge(directory, pattern, timestamp_key, ttl, now):
    """Supprime les fichiers JSON de `directory` plus vieux que `ttl` (ou illisibles)."""
    removed = 0
    if not directory.is_dir():
        return removed
    for path in directory.glob(pattern):
        if not path.is_file():
            continue
        try:
            stamp = float(json.loads(path.read_text())[timestamp_key])
            expired = now - stamp >= ttl
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
        "metadata": _purge(cache_dir / "metadata", "*.json", "time", METADATA_TTL, now),
        "negative_covers": _purge(cache_dir / "covers", "*.missing.json", "at", NEGATIVE_TTL, now),
    }


def purge_quietly(cache_dir):
    """Purge sans jamais interrompre le démarrage de l'application."""
    try:
        return purge_expired_caches(cache_dir)
    except OSError:
        return {"metadata": 0, "negative_covers": 0}
