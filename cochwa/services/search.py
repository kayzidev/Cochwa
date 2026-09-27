"""Recherche paginée multi-sources : orchestration, isolation des pannes, dédup.

La connaissance plateforme (termes exclus, collections IA, datfile) vit dans
les providers ; cette couche choisit les sources compatibles avec la plateforme.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from cochwa.api.redump import get_datfile
from cochwa.models import SearchResult
from cochwa.providers.ia_ps2_search import PS2SearchProvider
from cochwa.providers.ia_ps2_search import _matches_other_platform as _matches_other_platform
from cochwa.providers.ia_ps2_search import literal as literal
from cochwa.providers.minerva import MinervaProvider
from cochwa.services.relevance import dedupe

_dedupe = dedupe  # compat : historiquement ré-exporté d'ici


class SearchService(PS2SearchProvider):
    @staticmethod
    def _get_datfile(*args):
        return get_datfile(*args)

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
        platform="ps2",
    ):
        query = query.strip()
        if page < 1 or not 1 <= limit <= 100:
            raise ValueError("Page ≥ 1 et limite entre 1 et 100 requises")
        if platform not in {"ps2", "switch"}:
            raise ValueError("Plateforme inconnue")
        from cochwa.providers.ia_switch import SwitchArchiveProvider

        methods = (
            {"ia_switch": SwitchArchiveProvider(self._cached).search}
            if platform == "switch"
            else {"ia_redump": self._search_ia, "minerva": MinervaProvider(self.config).search}
        )
        if source != "all" and source not in methods:
            raise ValueError("Source incompatible avec la plateforme")
        if not query:
            return SearchResult(page=page)
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
