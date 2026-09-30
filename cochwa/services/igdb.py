"""Recherche et mise en cache des métadonnées de jeux IGDB."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher

from cochwa.infrastructure.http import session
from cochwa.infrastructure.storage import write_json
from cochwa.services.relevance import normalized

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
API_URL = "https://api.igdb.com/v4/games"
API_ROOT = "https://api.igdb.com/v4"
METADATA_TTL = 30 * 24 * 60 * 60
NEGATIVE_TTL = 24 * 60 * 60
CATALOG_TTL = 30 * 24 * 60 * 60
_REQUEST_LOCK = threading.Lock()
_TOKEN_LOCK = threading.Lock()
_NEXT_API_REQUEST = 0.0

_FIELDS = ",".join(
    (
        "id",
        "name",
        "slug",
        "summary",
        "storyline",
        "first_release_date",
        "release_dates.human",
        "release_dates.platform.name",
        "release_dates.release_region.name",
        "game_type.name",
        "genres.name",
        "platforms.name",
        "involved_companies.company.name",
        "involved_companies.developer",
        "involved_companies.publisher",
        "game_modes.name",
        "player_perspectives.name",
        "themes.name",
        "game_engines.name",
        "franchises.name",
        "collections.name",
        "age_ratings.organization.name",
        "age_ratings.rating_category.rating",
        "total_rating",
        "total_rating_count",
        "hypes",
        "aggregated_rating",
        "aggregated_rating_count",
        "cover.image_id",
        "websites.url",
    )
)

_PLATFORM_ALIASES = {
    "ps2": {"playstation 2"},
    "switch": {"nintendo switch", "switch"},
}


def _names(items):
    return sorted({item["name"] for item in items if isinstance(item, dict) and item.get("name")})


def _unique(values):
    return sorted({value for value in values if value})


def _release_date(timestamp):
    if not isinstance(timestamp, (int, float)):
        return ""
    try:
        return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return ""


def _metadata(game):
    companies = game.get("involved_companies", [])
    developers = []
    publishers = []
    for involved in companies:
        name = (involved.get("company") or {}).get("name", "")
        if involved.get("developer"):
            developers.append(name)
        if involved.get("publisher"):
            publishers.append(name)

    release_dates = []
    for release in game.get("release_dates", []):
        human = release.get("human")
        platform = (release.get("platform") or {}).get("name", "")
        region = (release.get("release_region") or {}).get("name", "")
        if human:
            release_dates.append({"date": human, "platform": platform, "region": region})

    ratings = []
    for rating in game.get("age_ratings", []):
        organization = (rating.get("organization") or {}).get("name", "")
        value = (rating.get("rating_category") or {}).get("rating", "")
        if organization or value:
            ratings.append({"organization": organization, "rating": value})

    cover_id = (game.get("cover") or {}).get("image_id")
    slug = game.get("slug", "")
    return {
        "id": game.get("id"),
        "name": game.get("name", ""),
        "url": f"https://www.igdb.com/games/{slug}" if slug else "https://www.igdb.com/",
        "summary": game.get("summary", ""),
        "storyline": game.get("storyline", ""),
        "release_date": _release_date(game.get("first_release_date")),
        "release_dates": release_dates,
        "game_type": (game.get("game_type") or {}).get("name", ""),
        "platforms": _names(game.get("platforms", [])),
        "genres": _names(game.get("genres", [])),
        "developers": _unique(developers),
        "publishers": _unique(publishers),
        "modes": _names(game.get("game_modes", [])),
        "perspectives": _names(game.get("player_perspectives", [])),
        "themes": _names(game.get("themes", [])),
        "engines": _names(game.get("game_engines", [])),
        "franchises": _names(game.get("franchises", [])),
        "collections": _names(game.get("collections", [])),
        "age_ratings": ratings,
        "rating": game.get("total_rating"),
        "rating_count": game.get("total_rating_count"),
        "critic_rating": game.get("aggregated_rating"),
        "critic_rating_count": game.get("aggregated_rating_count"),
        "cover_url": (
            f"https://images.igdb.com/igdb/image/upload/t_cover_big/{cover_id}.jpg"
            if cover_id
            else ""
        ),
        "websites": _unique([site.get("url", "") for site in game.get("websites", [])]),
        "source": "IGDB",
    }


class IGDBClient:
    """Client Twitch Client Credentials + IGDB v4, avec cache de 30 jours."""

    def __init__(self, config):
        self.config = config
        self.client_id = config.igdb_client_id.strip()
        self.client_secret = config.igdb_client_secret.strip()
        self._token = ""
        self._token_expiry = 0

    def configure(self, client_id, client_secret):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self._token = ""
        self._token_expiry = 0

    @property
    def configured(self):
        return bool(self.client_id and self.client_secret)

    def _access_token(self):
        if self._token and time.time() < self._token_expiry:
            return self._token
        with _TOKEN_LOCK:
            if self._token and time.time() < self._token_expiry:
                return self._token
            response = session().post(
                TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=(10, 20),
            )
            response.raise_for_status()
            payload = response.json()
            self._token = payload["access_token"]
            self._token_expiry = time.time() + max(60, int(payload.get("expires_in", 3600)) - 60)
            return self._token

    def _query(self, body, endpoint="games"):
        global _NEXT_API_REQUEST
        with _REQUEST_LOCK:
            for attempt in range(3):
                delay = _NEXT_API_REQUEST - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                response = session().post(
                    f"{API_ROOT}/{endpoint}",
                    data=body,
                    headers={
                        "Client-ID": self.client_id,
                        "Authorization": f"Bearer {self._access_token()}",
                        "Accept": "application/json",
                        "Content-Type": "text/plain",
                    },
                    timeout=(10, 25),
                )
                retry_after = response.headers.get("Retry-After", "")
                if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                    try:
                        backoff = max(0.26, min(30.0, float(retry_after)))
                    except ValueError:
                        backoff = 0.5 * (2**attempt)
                    _NEXT_API_REQUEST = time.monotonic() + backoff
                    continue
                _NEXT_API_REQUEST = time.monotonic() + 0.26
                break
        response.raise_for_status()
        return response.json()

    def _platform_id(self, platform, platform_name=None):
        aliases = {
            "ps2": ("PlayStation 2", "PS2"),
            "switch": ("Nintendo Switch", "Switch"),
        }.get(platform, (platform_name or platform,))
        candidates = {}
        for alias in aliases:
            query = alias.replace("\\", "\\\\").replace('"', '\\"')
            for item in self._query(
                f'fields id,name,alternative_name,slug; search "{query}"; limit 20;',
                endpoint="platforms",
            ):
                candidates[item.get("id")] = item
            for item in candidates.values():
                names = [item.get("name", ""), item.get("alternative_name", "")]
                if any(normalized(name) == normalized(alias) for name in names):
                    return item["id"]
        if platform_name:
            for item in candidates.values():
                if normalized(item.get("name", "")) == normalized(platform_name):
                    return item["id"]
        raise ValueError(f"Plateforme IGDB introuvable : {platform_name or platform}")

    def fetch_platform_catalog(self, platform, platform_name=None):
        """Charge le catalogue principal d'une plateforme par pages de 500 jeux."""
        if not self.configured:
            raise ValueError("Configurez les identifiants Twitch/IGDB dans Paramètres.")
        platform_id = self._platform_id(platform, platform_name)
        rows = []
        last_id = 0
        fields = (
            "id,name,slug,summary,storyline,first_release_date,game_type.name,"
            "genres.name,platforms.name,total_rating,total_rating_count,"
            "aggregated_rating,aggregated_rating_count,hypes,cover.image_id,websites.url"
        )
        while True:
            body = (
                f"fields {fields}; where platforms = {platform_id} & version_parent = null "
                f"& game_type = 0 & id > {last_id}; sort id asc; limit 500;"
            )
            page = self._query(body)
            if not page:
                break
            rows.extend(entry for game in page if (entry := _catalog_entry(game)))
            last_id = page[-1]["id"]
            if len(page) < 500:
                break
        return rows

    def sync_catalog(self, platform, platform_name=None):
        """Rafraîchit le cache de catalogue sur disque, sans toucher à la GUI."""
        rows = self.fetch_platform_catalog(platform, platform_name)
        path = self.config.cache_dir / "catalogs" / f"igdb-{platform}.json"
        saved = {"time": time.time(), "platform": platform, "source": "IGDB", "games": rows}
        write_json(path, saved)
        return {"platform": platform, "updated_at": saved["time"]}

    def enrich(self, title, platform=""):
        """Retourne le meilleur match probable ou None si le titre est incertain."""
        if not self.configured or not title.strip():
            return None
        search_title = re.split(r"\s+\(", title.strip(), maxsplit=1)[0].strip()
        search_title = search_title or title.strip()
        key = hashlib.sha256(f"{platform}\0{search_title.casefold()}".encode()).hexdigest()
        cache = self.config.cache_dir / "metadata" / f"igdb-{key}.json"
        try:
            cached = json.loads(cache.read_text())
            ttl = METADATA_TTL if cached.get("data") else NEGATIVE_TTL
            if time.time() - cached["time"] < ttl:
                return cached.get("data")
        except (OSError, ValueError, KeyError, TypeError):
            pass

        escaped = search_title.replace("\\", "\\\\").replace('"', '\\"')
        query = f'fields {_FIELDS}; search "{escaped}"; where version_parent = null; limit 10;'
        games = self._query(query)
        target_platforms = _PLATFORM_ALIASES.get(platform, set())
        wanted = normalized(search_title)
        ranked = []
        for game in games:
            candidate = normalized(game.get("name", ""))
            if not candidate:
                continue
            similarity = SequenceMatcher(None, wanted, candidate).ratio()
            platforms = {normalized(name) for name in _names(game.get("platforms", []))}
            platform_matches = not target_platforms or bool(
                platforms & {normalized(name) for name in target_platforms}
            )
            # Prefer a platform match, but tolerate incomplete IGDB platform tags
            # when the name is an exact match.
            score = similarity + (0.15 if platform_matches else -0.15)
            ranked.append((score, similarity, platform_matches, game))

        ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
        chosen = None
        if ranked:
            score, similarity, platform_matches, game = ranked[0]
            if similarity >= 0.84 and (platform_matches or similarity >= 0.98):
                chosen = _metadata(game)
        write_json(cache, {"time": time.time(), "data": chosen})
        return chosen


def _catalog_entry(game):
    if not game.get("id") or not game.get("name"):
        return None
    metadata = _metadata(game)
    genres = metadata["genres"]
    critic = metadata.get("critic_rating")
    return {
        "igdb_id": game["id"],
        "title": metadata["name"],
        "genre": genres[0] if genres else "",
        "genres": genres,
        "score": round(critic) if critic is not None else None,
        "critic_score": critic,
        "score_source": "IGDB · critiques" if critic is not None else "",
        "critic_rating_count": metadata.get("critic_rating_count") or 0,
        "rating": metadata.get("rating"),
        "rating_count": metadata.get("rating_count") or 0,
        "hypes": game.get("hypes") or 0,
        "release_date": metadata.get("release_date", ""),
        "igdb_url": metadata.get("url", ""),
        "cover_url": metadata.get("cover_url", ""),
        "summary": metadata.get("summary", ""),
        "source": "IGDB",
    }
