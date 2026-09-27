"""Recherche Switch IA : formats NSP/XCI directs, jamais de validation Redump."""

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import PurePosixPath
from urllib.parse import quote

from cochwa.models import IAGame, SearchResult
from cochwa.services.relevance import is_unrequested_asset, matches_filters, relevant
from cochwa.util import switch_content_type


class SwitchArchiveProvider:
    def __init__(self, cached):
        self.cached = cached

    def item(self, identifier, query, region="", language=""):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", identifier):
            return None
        data = self.cached("https://archive.org/metadata/" + quote(identifier, safe=""))
        if data.get("is_dark"):
            return None
        title = data.get("metadata", {}).get("title") or identifier
        if isinstance(title, list):
            title = " / ".join(map(str, title))
        files = []
        archives = []
        for raw in data.get("files", []):
            name = raw.get("name", "")
            path = PurePosixPath(name)
            # Les archives génériques, exécutables, NSZ et NCA isolés ne sont pas
            # assimilés à des jeux jouables. Aucun pack inconnu n'est téléchargé.
            archive = any(
                name.lower().endswith(rom + ext)
                for rom in (".nsp", ".xci")
                for ext in (".zip", ".7z", ".rar")
            )
            if (
                (path.suffix.lower() not in {".nsp", ".xci"} and not archive)
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in name
            ):
                continue
            if raw.get("private") or raw.get("viruscheck") == "failed":
                continue
            size = int(raw.get("size") or 0)
            if size <= 0:
                continue
            content_type = switch_content_type(name)
            if content_type != "game" and not re.search(
                r"\b(update|upd|dlc|mise à jour)\b", query, re.I
            ):
                continue
            label = path.stem
            generic = label.casefold() in {"game", "rom", "dump"} or bool(
                re.fullmatch(r"[0-9a-f]{16}", label, re.I)
            )
            match_title = title if generic else label
            if (
                not relevant(query, match_title)
                or is_unrequested_asset(query, match_title)
                or not matches_filters(match_title, region, language)
            ):
                continue
            if archive:
                archives.append(name)
                continue
            file = {"name": name, "size": size, "content_type": content_type}
            for key, length in (("md5", 32), ("sha1", 40)):
                digest = str(raw.get(key) or "")
                if re.fullmatch(rf"[a-fA-F0-9]{{{length}}}", digest):
                    file[key] = digest.lower()
            files.append(file)
        if not files:
            if archives:
                return IAGame(
                    identifier,
                    title,
                    title,
                    [],
                    None,
                    0,
                    platform="switch",
                    source="ia_switch",
                    identification="archive",
                    external=True,
                )
            return None
        return IAGame(
            identifier,
            title,
            title,
            files,
            files[0]["name"],
            sum(f["size"] for f in files),
            platform="switch",
            source="ia_switch",
            identification="source_checksum"
            if all(f.get("md5") or f.get("sha1") for f in files)
            else "unknown",
        )

    def search(
        self, query, *, page=1, limit=20, verified_only=False, region="", language="", cancel=None
    ):
        if verified_only:
            return SearchResult(
                page=page,
                warnings=[
                    "Redump concerne la PS2 ; aucun fichier Switch n’est certifié par Redump."
                ],
            )
        escaped = '"' + query.replace("\\", "\\\\").replace('"', '\\"') + '"'
        data = self.cached(
            "https://archive.org/advancedsearch.php",
            params={
                "q": f"mediatype:software AND (title:({escaped}) OR subject:({escaped})) AND (title:(switch) OR subject:(switch))",
                "output": "json",
                "rows": limit,
                "page": page,
                "fl[]": ["identifier", "title"],
                "sort[]": "downloads desc",
            },
        )["response"]
        total = int(data.get("numFound", 0))
        result = SearchResult(
            page=page,
            total_items=total,
            has_more=page * limit < total,
            source_totals={"ia_switch": total},
        )
        failures = 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(self.item, d.get("identifier", ""), query, region, language)
                for d in data.get("docs", [])
                if not (cancel and cancel.is_set())
            ]
            for future in futures:
                if cancel and cancel.is_set():
                    return SearchResult(page=page)
                try:
                    game = future.result()
                    if game:
                        result.games.append(game)
                except Exception:
                    failures += 1
        if futures and failures == len(futures):
            raise RuntimeError("Métadonnées Switch inaccessibles ; réessayer")
        if failures:
            result.warnings.append(f"{failures} fiche(s) inaccessible(s)")
        if not result.games:
            result.warnings.append(
                "Aucun NSP/XCI direct accessible sur cette page ; les fichiers privés sont exclus."
            )
        return result
