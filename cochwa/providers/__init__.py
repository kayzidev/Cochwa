"""Providers disponibles — registry dynamique.

CONTRACT: pour ajouter une console au moteur de recherche
==========================================================
1. Définir la console dans consoles.py (entrée CONSOLES avec SearchProfile)
2. Enregistrer un ou plusieurs providers dans CONSOLE_PROVIDERS ci-dessous
3. Activer les providers concernés dans la config utilisateur

Le moteur de recherche résout automatiquement les providers compatibles avec
la console via le registre CONSOLE_PROVIDERS, sans toucher SearchService.
"""

from __future__ import annotations

from cochwa.providers.base import Provider
from cochwa.providers.ia_redump import IARedumpProvider
from cochwa.providers.minerva import MinervaProvider
from cochwa.providers.ia_switch import SwitchArchiveProvider

# Registry global : nom -> classe
PROVIDERS: dict[str, type[Provider]] = {
    "ia_redump": IARedumpProvider,
    "minerva": MinervaProvider,
    "ia_switch": SwitchArchiveProvider,
}

# Mapping console.id -> liste de noms de providers compatibles.
# La clé doit correspondre à Console.id dans consoles.py.
CONSOLE_PROVIDERS: dict[str, list[str]] = {
    "ps2": ["ia_redump", "minerva"],
    "switch": ["ia_switch"],
}


def register_provider(name: str, cls: type[Provider]) -> None:
    """Enregistre un provider dans le registre global (usage interne / tests)."""
    PROVIDERS[name] = cls


def get_provider(name: str, config) -> Provider | None:
    """Instancie un provider par nom, ou None si inconnu/désactivé."""
    cls = PROVIDERS.get(name)
    if cls is None:
        return None
    return cls(config)


def get_console_providers(console_id: str) -> list[str]:
    """Retourne la liste des noms de providers enregistrés pour une console."""
    return CONSOLE_PROVIDERS.get(console_id, [])


def list_provider_names() -> list[str]:
    return list(PROVIDERS.keys())
