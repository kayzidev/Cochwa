"""Contrat d'une source distante ; aucun cache global imposé aux providers."""

from typing import Protocol

from romget.models import IAGame


class Provider(Protocol):
    name: str
    display_name: str
    platform: str

    def search(self, query: str, limit: int = 20) -> list[IAGame]: ...
    def find_by_id(self, game_id: str) -> IAGame: ...
