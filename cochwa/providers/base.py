"""Contrat d'une source distante ; aucun cache global imposé aux providers."""

from typing import Protocol

from cochwa.models import IAGame, SearchResult


class Provider(Protocol):
    name: str
    display_name: str

    def search(
        self,
        query: str,
        *,
        page: int = 1,
        limit: int = 20,
        verified_only: bool = False,
        region: str = "",
        language: str = "",
        cancel=None,
    ) -> SearchResult: ...

    def item(self, identifier: str, datfile=None) -> IAGame: ...
