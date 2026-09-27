"""Providers disponibles — registry dynamique."""

from cochwa.providers.base import Provider
from cochwa.providers.ia_redump import IARedumpProvider

# Registry : nom -> classe
PROVIDERS: dict[str, type[Provider]] = {
    "ia_redump": IARedumpProvider,
}


def get_provider(name: str, config) -> Provider | None:
    """Instancie un provider par nom, ou None si inconnu/désactivé."""
    cls = PROVIDERS.get(name)
    if cls is None:
        return None
    return cls(config)


def list_provider_names() -> list[str]:
    return list(PROVIDERS.keys())
