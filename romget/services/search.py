"""Recherche paginée commune ; cache metadata et identification par fichier."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from difflib import SequenceMatcher, get_close_matches
from urllib.parse import quote

from romget.api.redump import get_datfile
from romget.infrastructure.http import get_json
from romget.infrastructure.storage import write_json
from romget.models import IAGame, SearchResult
from romget.providers.minerva import MinervaProvider
from romget.services.relevance import (
    dedupe,
    is_unrequested_asset,
    matches_filters,
    relevant,
    tokens,
)
from romget.util import extract_main_rom, is_rom_or_archive

SEARCH_URL = "https://archive.org/advancedsearch.php"
_METADATA_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="metadata")
_CACHE_LOCKS = [threading.Lock() for _ in range(32)]

# Taille minimale d'un item pour être pré-filtré (100 MB) — élimine cheats/assets
# sans appel metadata grâce au champ item_size d'advancedsearch.
MIN_ITEM_SIZE = 100 * 1024 * 1024

# Mots-clés dépriorisés dans les titres (démos, assets, outils) — pas exclus,
# mais relégués en fin de liste.
_LOW_PRIORITY_TERMS = (
    "cheat",
    "action replay",
    "gameshark",
    "codebreaker",
    "code breaker",
    "trailer",
    "soundtrack",
    "press kit",
    "press disc",
    "art disc",
    "promo",
    "demo disc",
    "kiosk",
    "trade demo",
    "preview",
)

# Marqueurs d'autres plateformes dans les titres/identifiers — exclus de la
# recherche PS2 (un item "God of War Collection PS Vita" n'est pas une ROM PS2).
# Comparés après normalisation (underscores/tirets → espaces), avec espaces
# autour pour éviter les faux positifs ("eps3" ne matche pas "ps3").
_OTHER_PLATFORM_TERMS = (
    "ps vita",
    "psvita",
    "vita",
    "ps3",
    "playstation 3",
    "psp",
    "ps1",
    "psx",
    "playstation 1",
    "ps one",
    "psone",
    "playstation classic",
    "xbox",
    "gamecube",
    "game cube",
    "wii",
    "dreamcast",
    "switch",
    "pc game",
    "windows",
    "dos",
    "n64",
    "game boy",
    "gba",
    "nds",
    "nintendo ds",
    "megadrive",
    "genesis",
    "snes",
    "saturn",
    "mame",
    "3ds",
    "wiiu",
    "wii u",
)

# « PlayStation » seul (sans « 2 ») désigne la PS1 : « Tekken 3 (PlayStation) ».
# Le lookahead négatif protège « PlayStation 2 ».
_PS1_PATTERN = re.compile(r"\bplaystation\b(?!\s*2\b)", re.IGNORECASE)

# Collections IA : signal fiable de plateforme quand elles sont renseignées.
_PS2_COLLECTION = re.compile(r"playstation[_ ]?2|\bps2\b", re.IGNORECASE)
_OTHER_CONSOLE_COLLECTION = re.compile(
    r"playstation[_ ]?(?![_ ]?2\b)|\bpsx\b|\bpsp\b|xbox|gamecube|nintendo|sega|dreamcast|saturn",
    re.IGNORECASE,
)


def _normalize(text):
    """Normalise un titre/identifier pour la détection de plateforme."""
    return " " + " ".join(re.sub(r"[^a-z0-9]+", " ", text.casefold()).split()) + " "


def _matches_other_platform(title, identifier, collections=()):
    haystack = _normalize(title) + _normalize(identifier)
    if any(f" {term} " in haystack for term in _OTHER_PLATFORM_TERMS):
        return True
    if _PS1_PATTERN.search(haystack):
        return True
    # Collections IA renseignées, aucune PS2, au moins une autre console.
    cols = [collections] if isinstance(collections, str) else list(collections or [])
    if cols and not any(_PS2_COLLECTION.search(c) for c in cols):
        return any(_OTHER_CONSOLE_COLLECTION.search(c) for c in cols)
    return False


def literal(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


_dedupe = dedupe


class SearchService:
    def __init__(self, config):
        self.config = config

    def search(
        self,
        query,
        *,
        page=1,
        limit=20,
        verified_only=False,
        region="",
        language="",
        cancel=None,
        source="all",
    ):
        query = query.strip()
        if page < 1 or not 1 <= limit <= 100:
            raise ValueError("Page ≥ 1 et limite entre 1 et 100 requises")
        if source not in {"all", "ia_redump", "minerva"}:
            raise ValueError("Source inconnue")
        if not query:
            return SearchResult(page=page)
        methods = {"ia_redump": self._search_ia, "minerva": MinervaProvider(self.config).search}
        selected = [
            name
            for name in methods
            if source in {"all", name}
            and self.config.providers.get(name)
            and self.config.providers[name].enabled
        ]
        if not selected:
            raise ValueError("Aucune source sélectionnée active")
        options = dict(
            page=page,
            limit=limit,
            verified_only=verified_only,
            region=region,
            language=language,
            cancel=cancel,
        )
        result = SearchResult(page=page)
        failures = []
        # Pool séparé : ne pas bloquer les workers metadata avec leurs parents.
        with ThreadPoolExecutor(max_workers=len(selected)) as pool:
            futures = {name: pool.submit(methods[name], query, **options) for name in selected}
            for name, future in futures.items():
                try:
                    part = future.result()
                except Exception as exc:
                    failures.append(name)
                    result.warnings.append(f"{name} indisponible ({type(exc).__name__})")
                    continue
                result.games.extend(part.games)
                result.total_items += part.total_items
                result.has_more |= part.has_more
                result.source_totals.update(part.source_totals)
                result.warnings.extend(part.warnings)
                result.suggestions.extend(part.suggestions)
        if cancel and cancel.is_set():
            return SearchResult(page=page)
        if len(failures) == len(selected):
            raise RuntimeError("Toutes les sources sélectionnées sont indisponibles ; réessayer")
        result.games = _dedupe(result.games)
        result.suggestions = list(dict.fromkeys(result.suggestions)) if not result.games else []
        return result

    def _cached(self, url, params=None, ttl=3600):
        key = hashlib.sha256(json.dumps([url, params], sort_keys=True).encode()).hexdigest()
        path = self.config.cache_dir / "metadata" / f"{key}.json"
        # Serializing cache misses prevents duplicate requests across tabs.
        with _CACHE_LOCKS[int(key[:2], 16) % len(_CACHE_LOCKS)]:
            try:
                saved = json.loads(path.read_text())
                if time.time() - saved["time"] < ttl:
                    return saved["data"]
            except (OSError, ValueError, KeyError, TypeError):
                pass
            data = get_json(url, params=params)
            try:
                write_json(path, {"time": time.time(), "data": data})
            except OSError:
                pass
            return data

    def item(self, identifier, datfile=None):
        if identifier.startswith("minerva-"):
            raise ValueError("MiNERVA : ouvrir la fiche source avec un client torrent externe")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", identifier):
            raise ValueError("Identifiant IA invalide")
        data = self._cached("https://archive.org/metadata/" + quote(identifier, safe=""))
        if data.get("is_dark"):
            raise ValueError("Item non accessible")
        title = data.get("metadata", {}).get("title") or identifier
        if isinstance(title, list):
            title = " / ".join(str(x) for x in title)
        datfile = datfile or get_datfile(self.config.cache_dir, self.config.datfile_url)
        files = []
        for raw in data.get("files", []):
            name = raw.get("name", "")
            # Images disque directes ou archives contenant une ROM.
            # Les .pkg (PS2 Classics PSN) sont exclus : incompatibles PCSX2.
            if not isinstance(name, str) or not is_rom_or_archive(name):
                continue
            if str(raw.get("private", "")).lower() in {"true", "1"}:
                continue
            try:
                size = int(raw.get("size", 0))
            except (TypeError, ValueError):
                continue
            if size <= 0:
                continue
            md5 = (raw.get("md5") or "").lower()
            recognized = datfile.lookup_title_by_md5(md5) if md5 else None
            files.append(
                {
                    "name": name,
                    "size": size,
                    "md5": md5,
                    "sha1": raw.get("sha1") or "",
                    "title": recognized or "",
                    "identification": "hash" if recognized else "unknown",
                }
            )
        titles = {f["title"] for f in files if f["title"]}
        # Seules les images disque directes peuvent matcher le hash Redump ;
        # une archive (.rar/.zip/.7z) a le hash de l'archive, pas du contenu.
        images = [f for f in files if not f["name"].lower().endswith(".cue")]
        all_identified = bool(images) and all(f["title"] for f in images)
        identification = (
            "hash" if all_identified else ("title" if datfile.is_ps2_title(title) else "unknown")
        )
        clean = next(iter(titles)) if len(titles) == 1 and all_identified else title
        return IAGame(
            identifier,
            title,
            clean,
            files,
            extract_main_rom([f["name"] for f in files]),
            sum(f["size"] for f in files),
            all_identified,
            identification,
        )

    def _search_ia(
        self, query, *, page=1, limit=20, verified_only=False, region="", language="", cancel=None
    ):
        query = query.strip()
        if not query:
            return SearchResult(page=page)
        if page < 1 or not 1 <= limit <= 100:
            raise ValueError("Page ≥ 1 et limite entre 1 et 100 requises")
        provider = self.config.providers.get("ia_redump")
        if provider and not provider.enabled:
            raise ValueError("Provider IA désactivé dans la configuration")
        # Quoted tokens prevent the user text from becoming Solr operators.
        terms = " AND ".join(literal(word) for word in query.split())
        serial = bool(re.fullmatch(r"[A-Za-z]{4}[- _]?\d{5}", query))
        fields = f"title:({terms}) OR identifier:({terms}) OR subject:({terms})"
        if serial:
            fields += f" OR description:({terms})"
        # item_size filter eliminates cheats/assets before metadata calls.
        q = f"({fields}) AND mediatype:software AND item_size:[{MIN_ITEM_SIZE} TO *]"
        data = self._cached(
            SEARCH_URL,
            {
                "q": q,
                "fl[]": ["identifier", "title", "item_size", "downloads", "collection"],
                "rows": limit,
                "page": page,
                "output": "json",
                # Popular items first: good dumps are downloaded more often.
                "sort[]": "downloads desc",
            },
            300,
        )
        response = data.get("response")
        if not isinstance(response, dict):
            raise ValueError("Réponse recherche IA invalide")
        datfile = get_datfile(self.config.cache_dir, self.config.datfile_url)
        result = SearchResult(total_items=int(response.get("numFound", 0)), page=page)
        result.has_more = page * limit < result.total_items
        result.source_totals = {"ia_redump": result.total_items}
        if datfile.status != "fresh":
            result.warnings.append("Index Redump périmé ou indisponible : identification limitée")
        # Pré-filtre par titre/identifier : exclut les items d'autres plateformes
        # avant les appels metadata (vitesse + pertinence).
        docs = []
        for d in response.get("docs", []):
            ident = d.get("identifier")
            if not ident:
                continue
            title = d.get("title") or ""
            if isinstance(title, list):
                title = " ".join(str(x) for x in title)
            if _matches_other_platform(title, ident, d.get("collection")):
                continue
            docs.append(d)
        futures = [_METADATA_POOL.submit(self.item, d["identifier"], datfile) for d in docs]
        failures = 0
        for future in futures:
            if cancel and cancel.is_set():
                for other in futures:
                    other.cancel()
                return SearchResult(page=page)
            try:
                game = future.result()
            except Exception:
                failures += 1
                continue
            if not game.files or _matches_other_platform(game.ia_title, game.identifier):
                continue
            if is_unrequested_asset(query, game.ia_title):
                continue
            # Tous les filtres doivent être satisfaits par la même édition.
            candidates = []
            for file in game.files:
                file_title = file.get("title") or file["name"]
                if _matches_other_platform(file_title, ""):
                    continue
                if is_unrequested_asset(query, file_title):
                    continue
                if verified_only and file.get("identification") != "hash":
                    continue
                generic = bool(
                    re.fullmatch(
                        r"(?:game|disc|disk|track|image|rom|part|x)[ _.-]*[0-9]*(?:\.[a-z0-9]+)?",
                        file["name"],
                        re.I,
                    )
                )
                if not (
                    relevant(query, file_title)
                    or (generic and relevant(query, game.clean_title))
                    or (
                        serial
                        and re.sub(r"[^a-z0-9]", "", query.casefold())
                        in re.sub(r"[^a-z0-9]", "", file_title.casefold())
                    )
                ):
                    continue
                # Le titre du fichier prime pour les régions explicites : un pack
                # « Europe + USA » ne doit pas faire passer un fichier USA en Europe.
                filter_text = file_title
                if not re.search(r"\b(europe|usa|japan|pal|eur|jpn)\b", file_title, re.I):
                    filter_text += " " + game.clean_title
                if matches_filters(filter_text, region, language):
                    candidates.append(file)
            if not candidates:
                continue
            game = replace(
                game,
                files=candidates,
                main_rom=extract_main_rom([f["name"] for f in candidates]),
                total_size=sum(f["size"] for f in candidates),
            )
            result.games.append(game)
        if failures:
            result.warnings.append(f"{failures} item(s) inaccessible(s) ; résultats partiels")
        if failures and failures == len(futures):
            raise RuntimeError("Impossible de charger les métadonnées IA ; réessayer")

        # Popularité par identifier (récupérée via fl[]=downloads dans la query).
        downloads = {
            d.get("identifier"): int(d.get("downloads") or 0)
            for d in response.get("docs", [])
            if d.get("identifier")
        }
        # Collections IA par identifier — les collections de confiance
        # (providers.ia_redump.ia_collections) reçoivent un bonus au classement.
        trusted = set(provider.ia_collections) if provider else set()
        doc_collections = {}
        for d in response.get("docs", []):
            if not d.get("identifier"):
                continue
            cols = d.get("collection") or []
            doc_collections[d["identifier"]] = {
                str(c) for c in (cols if isinstance(cols, list) else [cols])
            }

        def rank(game):
            title = game.clean_title.casefold()
            ident = game.identifier.casefold()
            similarity = SequenceMatcher(None, query.casefold(), title).ratio()
            # Cheats/démos/assets relégués en fin de liste (pas exclus).
            low_priority = any(term in title for term in _LOW_PRIORITY_TERMS)
            # Prototypes/betas dépriorisés par rapport aux versions finales
            # (détection dans le titre ET l'identifier : "GodofWarIIFeb22007prototype").
            is_prototype = (
                "prototype" in title or "prototype" in ident or "beta" in title or "alpha" in title
            )
            popularity = downloads.get(game.identifier, 0)
            # Score composite : similarité dominante, popularité en appoint,
            # bonus pour les dumps identifiés par hash Redump et pour les
            # collections IA de confiance configurées.
            score = (
                similarity * 0.65
                + min(popularity / 50000, 1.0) * 0.25
                + (0.10 if game.identification == "hash" else 0.0)
                + (0.05 if trusted & doc_collections.get(game.identifier, set()) else 0.0)
            )
            base_title = re.split(r"[([]", game.clean_title)[0]
            exact = tokens(query) == tokens(base_title)
            return (
                low_priority,  # False (jeux) avant True (cheats/démos)
                is_prototype,  # versions finales avant prototypes
                not exact,
                -score,  # meilleur score d'abord
                game.clean_title,
                game.identifier,
            )

        result.games.sort(key=rank)
        result.games = _dedupe(result.games)
        if not result.games:
            titles = {
                t.split("(")[0].strip().casefold(): t.split("(")[0].strip() for t in datfile.titles
            }
            result.suggestions = [
                titles[t] for t in get_close_matches(query.casefold(), titles, n=3, cutoff=0.65)
            ]
        return result
