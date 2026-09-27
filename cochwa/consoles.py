"""Registre des consoles — base de la future logique multiconsole.

Seule la PS2 est implémentée (recherche, bibliothèque, lancement). Les autres
entrées sont des emplacements réservés exposés à l'UI (sélecteur de console)
sans aucune logique derrière : ne pas ajouter de provider tant que l'entrée
n'est pas marquée ``enabled``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Console:
    id: str
    name: str
    enabled: bool = False


CONSOLES = (
    Console("ps2", "PlayStation 2", enabled=True),
    # Prochaine console à implémenter — sélecteur UI uniquement pour l'instant.
    Console("switch", "Switch"),
)

DEFAULT_CONSOLE = CONSOLES[0]


def get(console_id):
    """Retourne la console correspondant à l'identifiant, ou None."""
    return next((c for c in CONSOLES if c.id == console_id), None)
