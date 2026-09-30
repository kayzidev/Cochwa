"""Recherche et mise en cache des métadonnées de jeux IGDB."""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher

from cochwa.infrastructure.http import session
from cochwa.infrastructure.storage import write_json
from cochwa.services.relevance import normalized

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
API_URL = "https://api.igdb.com/v4/games"
METADATA_TTL = 30 * 24 * 60 * 60
NEGATIVE_TTL = 24 * 60 * 60

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

    def _query(self, body):
        response = session().post(
            API_URL,
            data=body,
            headers={
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {self._access_token()}",
                "Accept": "application/json",
                "Content-Type": "text/plain",
            },
            timeout=(10, 25),
        )
        response.raise_for_status()
        return response.json()

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
