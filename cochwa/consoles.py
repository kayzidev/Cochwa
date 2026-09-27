"""Registre des consoles — base de la logique multiconsole.

PS2 : recherche (IA + MiNERVA), bibliothèque et lancement.
Switch : bibliothèque locale et lancement (Ryubing) ; la recherche Switch
attend son provider — ne pas en ajouter un sans identification des dumps
(pas d'équivalent Redump branché pour l'instant).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Console:
    id: str
    name: str
    enabled: bool = False
    rom_extensions: tuple[str, ...] = ()
    roms_dir: str = ""  # dossier ROMs par défaut (tilde autorisée)
    launcher: str = ""  # script de lancement par défaut
    emulator: str = ""
    emulator_url: str = ""
    disc_based: bool = False  # images CD/DVD : CUE/CHD, conversion, datfile


CONSOLES = (
    Console(
        "ps2",
        "PlayStation 2",
        enabled=True,
        rom_extensions=(".iso", ".chd", ".cue", ".bin"),
        roms_dir="~/Games/roms/ps2",
        launcher="~/Games/scripts/pcsx2/launch.sh",
        emulator="PCSX2",
        emulator_url="https://pcsx2.net/",
        disc_based=True,
    ),
    Console(
        "switch",
        "Switch",
        enabled=True,
        rom_extensions=(".nsp", ".xci", ".nca"),
        roms_dir="~/Games/roms/switch",
        launcher="~/Games/scripts/ryujinx/launch.sh",
        emulator="Ryubing (fork Ryujinx)",
        emulator_url="https://git.ryujinx.app/Ryubing/Canary/releases",
    ),
)

DEFAULT_CONSOLE = CONSOLES[0]


def get(console_id):
    """Retourne la console correspondant à l'identifiant, ou None."""
    return next((c for c in CONSOLES if c.id == console_id), None)
