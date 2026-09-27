"""Registre des consoles — base de la logique multiconsole.

PS2 : recherche (IA + MiNERVA), bibliothèque et lancement.
Switch : recherche IA (NSP/XCI), bibliothèque locale et lancement (Ryubing).
Le SearchProfile ci-dessous concentre la stratégie de pertinence plateforme :
le provider Internet Archive est réutilisable en lui passant un autre profil.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchProfile:
    """Stratégie de pertinence plateforme pour la recherche distante.

    Toute la connaissance « qu'est-ce qui n'est PAS cette console » vit ici :
    le provider Internet Archive est ainsi réutilisable pour une autre console
    en lui passant simplement un autre profil.
    """

    # Marqueurs des AUTRES plateformes dans titres/identifiers — exclus.
    # Comparés après normalisation, avec espaces autour (évite les faux positifs).
    other_platform_terms: tuple[str, ...]
    console_collection: str  # regex : collection IA signalant CETTE console
    other_collection: str  # regex : collection IA signalant une autre console
    # Regex titre hérité ambigu (ex. « PlayStation » seul = PS1) ; None sinon.
    legacy_title_pattern: str | None = None


_PS2_PROFILE = SearchProfile(
    other_platform_terms=(
        "ps vita",
        "psvita",
        "vita",
        "ps3",
        "ps4",
        "ps5",
        "playstation 4",
        "playstation 5",
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
        "pc",
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
    ),
    console_collection=r"playstation[_ ]?2|\bps2\b",
    other_collection=(
        r"playstation[_ ]?(?![_ ]?2\b)|\bpsx\b|\bpsp\b|xbox|gamecube|nintendo|sega|dreamcast|saturn"
    ),
    # « PlayStation » seul (sans « 2 ») désigne la PS1 : « Tekken 3 (PlayStation) ».
    legacy_title_pattern=r"\bplaystation\b(?!\s*2\b)",
)

_SWITCH_PROFILE = SearchProfile(
    other_platform_terms=(
        "ps2",
        "ps3",
        "ps4",
        "ps5",
        "playstation",
        "psp",
        "ps vita",
        "psvita",
        "vita",
        "psx",
        "xbox",
        "gamecube",
        "game cube",
        "wii",
        "wiiu",
        "wii u",
        "dreamcast",
        "n64",
        "game boy",
        "gba",
        "nds",
        "nintendo ds",
        "3ds",
        "snes",
        "megadrive",
        "genesis",
        "saturn",
        "mame",
        "pc game",
        "windows",
        "dos",
    ),
    console_collection=r"nintendo[_ -]?switch|\bnsw\b",
    other_collection=(
        r"playstation|\bps[1-5x]\b|\bpsp\b|xbox|gamecube|sega|dreamcast|saturn|\bwii\b"
    ),
)


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
    short_name: str = ""
    disc_based: bool = False  # images CD/DVD : CUE/CHD, conversion, datfile
    log_name: str = ""  # nom du journal dans state_dir (défaut : id)
    search_profile: SearchProfile | None = None  # None = recherche non branchée


CONSOLES = (
    Console(
        "ps2",
        "PlayStation 2",
        short_name="PS2",
        enabled=True,
        rom_extensions=(".iso", ".chd", ".cue", ".bin"),
        roms_dir="~/Games/roms/ps2",
        launcher="~/Games/scripts/pcsx2/launch.sh",
        emulator="PCSX2",
        emulator_url="https://pcsx2.net/",
        disc_based=True,
        log_name="pcsx2",  # nom historique du journal
        search_profile=_PS2_PROFILE,
    ),
    Console(
        "switch",
        "Switch",
        short_name="Switch",
        enabled=True,
        rom_extensions=(".nsp", ".xci", ".nca"),
        roms_dir="~/Games/roms/switch",
        launcher="~/Games/scripts/ryujinx/launch.sh",
        emulator="Ryubing (fork Ryujinx)",
        emulator_url="https://git.ryujinx.app/Ryubing/Canary/releases",
        log_name="switch",
        search_profile=_SWITCH_PROFILE,  # défini, non câblé à l'UI (provider à venir)
    ),
)

DEFAULT_CONSOLE = CONSOLES[0]


def get(console_id):
    """Retourne la console correspondant à l'identifiant, ou None."""
    return next((c for c in CONSOLES if c.id == console_id), None)
