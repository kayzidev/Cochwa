"""Catalogue PS2 MiNERVA : recherche locale, ouverture externe des fiches torrent.

Le catalogue HTML est public ; l'API de recherche n'est pas utilisée car ses
réponses n'ont pas pu être validées. Aucune empreinte torrent n'est traitée
comme une empreinte Redump, aucune taille arrondie comme une taille vérifiable.
"""

import json
import re
import threading
import time
from html.parser import HTMLParser

from cochwa.infrastructure.http import session
from cochwa.infrastructure.storage import write_json
from cochwa.models import IAGame, SearchResult
from cochwa.services.relevance import is_unrequested_asset, matches_filters, relevant, tokens
from cochwa.util import is_rom_or_archive

CATALOG_URL = "https://minerva-archive.org/browse/Redump/Sony%20-%20PlayStation%202/"
_LOCK = threading.Lock()


class CatalogParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.entries = {}
        self.identifier = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            match = re.fullmatch(r"/rom\?id=(\d+)", dict(attrs).get("href", ""))
            self.identifier = match[1] if match else None
            self.parts = []

    def handle_data(self, data):
        if self.identifier is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.identifier is not None:
            name = "".join(self.parts).strip()
            if name and is_rom_or_archive(name) and "/" not in name and "\\" not in name:
                self.entries[self.identifier] = name
            self.identifier = None


def fetch_catalog():
    parser = CatalogParser()
    body = bytearray()
    with session().get(CATALOG_URL, timeout=(10, 25), stream=True) as response:
        response.raise_for_status()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body) > 16 * 1024**2:
                raise ValueError("Catalogue MiNERVA trop volumineux")
    parser.feed(body.decode("utf-8"))
    if not parser.entries:
        raise ValueError("Catalogue MiNERVA vide ou format modifié")
    return parser.entries


class MinervaProvider:
    name = "minerva"
    display_name = "MiNERVA — catalogue PS2, torrents externes"
    platform = "ps2"

    def __init__(self, config):
        self.path = config.cache_dir / "sources" / "minerva-ps2-v1.json"

    def catalog(self):
        with _LOCK:
            try:
                saved = json.loads(self.path.read_text())
                entries = saved["entries"]
                if (
                    time.time() - saved["time"] < 86400
                    and isinstance(entries, dict)
                    and entries
                    and all(
                        re.fullmatch(r"\d+", k) and isinstance(v, str) for k, v in entries.items()
                    )
                ):
                    return entries
            except (OSError, ValueError, KeyError, TypeError):
                pass
            entries = fetch_catalog()
            try:
                write_json(self.path, {"time": time.time(), "entries": entries})
            except OSError:
                pass
            return entries

    def search(
        self, query, *, page=1, limit=20, verified_only=False, region="", language="", cancel=None
    ):
        if verified_only or (cancel and cancel.is_set()):
            return SearchResult(page=page, source_totals={"minerva": 0})
        matches = []
        for identifier, name in self.catalog().items():
            title = name.rsplit(".", 1)[0]
            if (
                relevant(query, title)
                and not is_unrequested_asset(query, title)
                and matches_filters(title, region, language)
            ):
                matches.append((identifier, title))
        matches.sort(
            key=lambda row: (
                bool(re.search(r"\b(demo|beta|prototype|preview)\b", row[1], re.I)),
                tokens(query) != tokens(re.split(r"[([]", row[1])[0]),
                row[1].casefold(),
                row[0],
            )
        )
        start = (page - 1) * limit
        games = [
            IAGame(
                "minerva-" + identifier,
                title,
                title,
                [],
                None,
                0,
                source="minerva",
                source_url="https://minerva-archive.org/rom?id=" + identifier,
                external=True,
            )
            for identifier, title in matches[start : start + limit]
        ]
        return SearchResult(
            games=games,
            total_items=len(matches),
            page=page,
            has_more=start + limit < len(matches),
            source_totals={"minerva": len(matches)},
        )
