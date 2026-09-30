"""Jaquettes avec cache atomique, bornes mémoire et absence temporairement mémorisée."""

from __future__ import annotations

import hashlib
import io
import json
import threading
import time
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote

from PIL import Image

from cochwa.config import DEFAULT_CACHE_DIR
from cochwa.infrastructure.http import get_json, session
from cochwa.infrastructure.storage import atomic_write, write_json
from cochwa.util import artwork_search_title

SGDB_API = "https://www.steamgriddb.com/api/v2"
IA_METADATA_URL = "https://archive.org/metadata/{identifier}"
IA_DOWNLOAD_URL = "https://archive.org/download/{identifier}/{name}"
CACHE_DIR = DEFAULT_CACHE_DIR / "covers"
_locks = [threading.Lock() for _ in range(16)]


def cover_cache_lock(path):
    """Verrou partagé entre téléchargement automatique et choix manuel."""
    return _locks[int(Path(path).stem[:2], 16) % len(_locks)]


# Seuils du match assoupli SGDB : titre suffisamment long (les titres courts
# sont trop ambigus), similarité élevée, et meilleur résultat nettement
# devant le second (sinon rejet — une mauvaise jaquette est pire qu'aucune).
_SGDB_SIMILARITY = 0.85
_SGDB_MIN_TITLE_LEN = 8
_SGDB_MIN_MARGIN = 0.05


def _similarity(a, b):
    return SequenceMatcher(None, a.casefold(), b.casefold()).ratio()


def search_grids(api_key, game_title, dimensions="600x900"):
    if not api_key:
        return []
    headers = {"Authorization": f"Bearer {api_key}"}
    games = get_json(
        f"{SGDB_API}/search/autocomplete/{quote(game_title, safe='')}", headers=headers
    ).get("data", [])
    if not games:
        return []
    exact = next((g for g in games if g.get("name", "").casefold() == game_title.casefold()), None)
    if exact is None:
        # Match assoupli strict : titre long, très proche, et sans concurrent
        # proche — évite de choisir silencieusement une suite ("Game" → "Game 2").
        if len(game_title.strip()) < _SGDB_MIN_TITLE_LEN:
            return []
        scored = sorted(
            ((_similarity(game_title, g.get("name", "")), g) for g in games),
            key=lambda t: t[0],
            reverse=True,
        )
        best_ratio, best = scored[0]
        second_ratio = scored[1][0] if len(scored) > 1 else 0.0
        if best_ratio < _SGDB_SIMILARITY or best_ratio - second_ratio < _SGDB_MIN_MARGIN:
            return []
        game = best
    else:
        game = exact
    return (
        get_json(
            f"{SGDB_API}/grids/game/{game['id']}",
            headers=headers,
            params={"dimensions": dimensions, "types": "static"},
        ).get("data", [])
        or []
    )


def _fetch_image(url, max_bytes=12 * 1024**2, portrait=False):
    """Télécharge une image avec borne mémoire. Retourne les bytes PNG.

    Si portrait=True, rejette les images paysage/carrées ou trop petites
    (évite d'afficher le logo générique archive.org comme jaquette).
    """
    if not url.startswith("https://"):
        raise ValueError("URL jaquette non sécurisée")
    content = bytearray()
    with session().get(url, timeout=(10, 20), stream=True) as response:
        response.raise_for_status()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content) > max_bytes:
                raise ValueError("Jaquette trop volumineuse")
    with Image.open(io.BytesIO(content)) as img:
        if img.width * img.height > 20_000_000:
            raise ValueError("Dimensions jaquette excessives")
        if portrait and (img.width >= img.height or img.height < 250):
            raise ValueError("Image générique (pas une jaquette)")
        img.thumbnail((600, 900))
        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, "PNG")
    return buffer.getvalue()


# Extensions image et indices de nommage d'une jaquette dans les fichiers IA.
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
_COVER_NAME_HINTS = ("front", "cover", "boxart", "box_art", "jaquette", "sleeve")


def _ia_metadata(identifier, cache_dir, ttl=86400):
    """Métadonnées IA avec cache disque (24 h) pour éviter les requêtes répétées."""
    key = hashlib.sha256(identifier.encode()).hexdigest()
    path = Path(cache_dir) / "metadata" / f"ia-{key}.json"
    try:
        saved = json.loads(path.read_text())
        if time.time() - saved["time"] < ttl:
            return saved["data"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    data = get_json(IA_METADATA_URL.format(identifier=quote(identifier, safe="")))
    try:
        write_json(path, {"time": time.time(), "data": data})
    except OSError:
        pass
    return data


def _ia_cover_url(identifier, cache_dir):
    """URL d'un fichier image ressemblant à une jaquette, ou None.

    Les métadonnées de l'item sont inspectées d'abord : sans fichier image
    dont le nom évoque une jaquette, on ne tente pas services/img, qui ne
    sert presque toujours que le logo générique archive.org (requête gaspillée).
    """
    try:
        data = _ia_metadata(identifier, cache_dir)
    except (OSError, ValueError):
        return None
    candidates = []
    for raw in data.get("files", []):
        name = raw.get("name", "")
        if not isinstance(name, str) or not name.lower().endswith(_IMAGE_EXTENSIONS):
            continue
        base = name.rsplit(".", 1)[0].casefold().replace("-", "_").replace(" ", "_")
        for priority, hint in enumerate(_COVER_NAME_HINTS):
            if hint in base:
                candidates.append((priority, name))
                break
    if not candidates:
        return None
    name = min(candidates)[1]
    return IA_DOWNLOAD_URL.format(identifier=quote(identifier, safe=""), name=quote(name))


# Durée du cache négatif (aucune jaquette trouvée) : 24 h. Le cache positif
# (covers/<hash>.png) est permanent — une jaquette n'est jamais re-téléchargée.
NEGATIVE_TTL = 86400


def cover_cache_path(cache_dir, platform, title):
    """Cache versionné par plateforme et titre de recherche normalisé."""
    identity = f"v2\0{platform or ''}\0{artwork_search_title(title).casefold()}"
    key = hashlib.sha256(identity.encode()).hexdigest()
    return Path(cache_dir) / f"{key}.png"


def _title_variants(title):
    """Variantes de titre pour le match SGDB, de la plus précise à la plus large.

    Sans région/parenthèses, puis sans « The » initial (SGDB liste souvent
    « X, The » ou sans article).
    """
    cleaned = artwork_search_title(title)
    variants = [cleaned]
    base = cleaned.split("(")[0].strip()
    if base and base != variants[0]:
        variants.append(base)
    for variant in list(variants):
        if variant.casefold().startswith("the "):
            variants.append(variant[4:].strip())
    seen = set()
    return [v for v in variants if v and not (v.casefold() in seen or seen.add(v.casefold()))]


def download_cover(
    api_key, game_title, cache_path=None, cache_dir=None, ia_identifier=None, platform=None
):
    """Télécharge la jaquette d'un jeu.

    Ordre : cache local → SteamGridDB (avec variantes de titre) → jaquette
    dans les fichiers de l'item IA (fallback si ia_identifier fourni et qu'un
    fichier image pertinent existe).
    """
    path = (
        Path(cache_path)
        if cache_path
        else cover_cache_path(cache_dir or CACHE_DIR, platform, game_title)
    )
    negative = path.with_suffix(".missing.json")
    with cover_cache_lock(path):
        if path.exists():
            try:
                with Image.open(path) as img:
                    img.verify()
                return path
            except (OSError, ValueError):
                pass
        try:
            if time.time() - json.loads(negative.read_text())["at"] < NEGATIVE_TTL:
                return None
        except (OSError, ValueError, KeyError):
            pass

        # 1. SteamGridDB — essai du titre puis de ses variantes.
        if api_key:
            grids = []
            for variant in _title_variants(game_title):
                grids = search_grids(api_key, variant)
                if grids:
                    break
            if grids:
                url = grids[0].get("url", "")
                try:
                    atomic_write(path, _fetch_image(url, portrait=True))
                    try:
                        write_json(path.with_suffix(".source.json"), {"source": "sgdb"})
                    except OSError:
                        pass
                    negative.unlink(missing_ok=True)
                    return path
                except (ValueError, OSError):
                    pass  # tente le fallback IA

        # 2. Fallback : jaquette dans les fichiers de l'item IA (portrait
        # seulement). Sans fichier image pertinent, aucune requête image
        # n'est tentée — services/img ne sert que le logo générique.
        if ia_identifier:
            url = _ia_cover_url(ia_identifier, cache_dir or CACHE_DIR)
            if url:
                try:
                    atomic_write(path, _fetch_image(url, portrait=True))
                    try:
                        write_json(path.with_suffix(".source.json"), {"source": "ia"})
                    except OSError:
                        pass
                    negative.unlink(missing_ok=True)
                    return path
                except (ValueError, OSError):
                    pass

        write_json(negative, {"at": time.time()})
        return None
