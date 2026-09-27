"""Catalogue PS2 : titres Redump exacts, genres et recommandations dynamiques.

Source packagée : ``romget/data/catalog_ps2.json``. Extension utilisateur
possible via ``~/.config/romget/catalog_ps2.json`` (même schéma ; une entrée
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

from romget.config import DEFAULT_CONFIG_DIR

USER_CATALOG = DEFAULT_CONFIG_DIR / "catalog_ps2.json"

_cache = {"entries": None, "mtime": 0.0}


def _load_packaged():
    text = resources.files("romget.data").joinpath("catalog_ps2.json").read_text("utf-8")
    return json.loads(text).get("games", [])


def _valid_entry(entry):
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("title"), str)
        and entry["title"].strip()
        and isinstance(entry.get("genre", ""), str)
        and ("score" not in entry or type(entry["score"]) is int)
    )


def catalog_entries():
    """Entrées du catalogue (packagées + extension utilisateur), rechargées
    si le fichier utilisateur change."""
    user_mtime = 0.0
    user_entries = []
    try:
        user_mtime = USER_CATALOG.stat().st_mtime
        data = json.loads(USER_CATALOG.read_text())
        user_entries = [e for e in data.get("games", []) if _valid_entry(e)]
    except (OSError, ValueError):
        user_mtime = 0.0
    if _cache["entries"] is not None and user_mtime == _cache["mtime"]:
        return _cache["entries"]
    merged = {e["title"]: dict(e) for e in _load_packaged() if _valid_entry(e)}
    for entry in user_entries:
        merged[entry["title"]] = dict(entry)
    _cache["entries"] = list(merged.values())
    _cache["mtime"] = user_mtime
    return _cache["entries"]


def top_entries():
    """Le vrai top des jeux PS2 les mieux notés : entrées avec score,
    triées par score décroissant (Metacritic indicatif)."""
    return sorted(
        (e for e in catalog_entries() if type(e.get("score")) is int),
        key=lambda e: (-e["score"], e["title"].casefold()),
    )


def top_titles():
    return [e["title"] for e in top_entries()]


def genres():
    """Genres présents dans le catalogue, triés (pour le filtre de l'onglet Top)."""
    return sorted({e.get("genre", "") for e in catalog_entries() if e.get("genre")})


def recommended_pool():
    """Les 100 jeux recommandés — ensemble distinct du Top (découverte)."""
    return [e for e in catalog_entries() if e.get("recommended")]


def recommended_entries(count=20, day=None):
    """Sélection du jour parmi les 100 recommandés — rotation quotidienne
    déterministe (même graine pour un jour donné)."""
    pool = recommended_pool()
    if day is None:
        day = time.strftime("%Y%m%d")
    shuffled = list(pool)
    random.Random(str(day)).shuffle(shuffled)
    return shuffled[:count]


# Compatibilité avec l'ancienne API (listes statiques).
TOP_PS2 = top_titles()
RECOMMENDED_PS2 = [e["title"] for e in recommended_entries()]
TOP_BY_CONSOLE = {"PS2": TOP_PS2}
