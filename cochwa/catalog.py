"""Catalogue PS2 : titres Redump exacts, genres et recommandations dynamiques.

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

USER_CATALOG = DEFAULT_CONFIG_DIR / "catalog_ps2.json"

_cache = {"entries": None, "mtime": 0.0}
_platform_caches = {}


def _load_packaged(platform="ps2"):
    text = resources.files("cochwa.data").joinpath(f"catalog_{platform}.json").read_text("utf-8")
    return json.loads(text).get("games", [])


def _valid_entry(entry):
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("title"), str)
        and entry["title"].strip()
        and isinstance(entry.get("genre", ""), str)
        and ("score" not in entry or type(entry["score"]) is int)
    )


def catalog_entries(platform="ps2"):
    """Entrées du catalogue (packagées + extension utilisateur), rechargées
    si le fichier utilisateur change."""
    if platform not in {"ps2", "switch"}:
        raise ValueError("Plateforme inconnue")
    cache = (
        _cache
        if platform == "ps2"
        else _platform_caches.setdefault(platform, {"entries": None, "mtime": 0.0})
    )
    user_catalog = (
        USER_CATALOG if platform == "ps2" else DEFAULT_CONFIG_DIR / f"catalog_{platform}.json"
    )
    user_mtime = 0.0
    user_entries = []
    try:
        user_mtime = user_catalog.stat().st_mtime
        data = json.loads(user_catalog.read_text())
        user_entries = [e for e in data.get("games", []) if _valid_entry(e)]
    except (OSError, ValueError):
        user_mtime = 0.0
    if cache["entries"] is not None and user_mtime == cache["mtime"]:
        return cache["entries"]
    merged = {e["title"]: dict(e) for e in _load_packaged(platform) if _valid_entry(e)}
    for entry in user_entries:
        merged[entry["title"]] = dict(entry)
    cache["entries"] = list(merged.values())
    cache["mtime"] = user_mtime
    return cache["entries"]


def top_entries(platform="ps2"):
    """Le vrai top des jeux PS2 les mieux notés : entrées avec score,
    triées par score décroissant (Metacritic indicatif)."""
    return sorted(
        (e for e in catalog_entries(platform) if type(e.get("score")) is int or e.get("top_rank")),
        key=lambda e: (e.get("top_rank", -e.get("score", 0)), e["title"].casefold()),
    )


def top_titles():
    return [e["title"] for e in top_entries()]


def genres(platform="ps2"):
    """Genres présents dans le catalogue, triés (pour le filtre de l'onglet Top)."""
    return sorted({e.get("genre", "") for e in catalog_entries(platform) if e.get("genre")})


def recommended_pool(platform="ps2"):
    """Les 100 jeux recommandés — ensemble distinct du Top (découverte)."""
    return [e for e in catalog_entries(platform) if e.get("recommended")]


def recommended_entries(count=20, day=None, platform="ps2"):
    """Sélection du jour parmi les 100 recommandés — rotation quotidienne
    déterministe (même graine pour un jour donné)."""
    pool = recommended_pool(platform)
    if day is None:
        day = time.strftime("%Y%m%d")
    shuffled = list(pool)
    random.Random(str(day)).shuffle(shuffled)
    return shuffled[:count]


# Compatibilité avec l'ancienne API (listes statiques).
TOP_PS2 = top_titles()
RECOMMENDED_PS2 = [e["title"] for e in recommended_entries()]
TOP_BY_CONSOLE = {"PS2": TOP_PS2}
