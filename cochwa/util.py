"""Utilitaires : sanitization de noms de fichiers/dossiers, tailles lisible."""

from __future__ import annotations

import re
from pathlib import Path

# Caractères interdits dans les noms de fichiers Linux/Windows
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_dirname(name: str) -> str:
    """Nettoie un nom de jeu pour en faire un nom de dossier valide.

    Préserve les parenthèses (important pour SRM fuzzyMatch) mais enlève
    les caractères interdits et tronque les noms trop longs.
    """
    name = name.strip()
    name = _INVALID_CHARS.sub("_", name)
    # Pas de point en fin de nom (problème Windows)
    name = name.rstrip(". ")
    # Tronque à 180 chars (limite filesystem ~255)
    while len(name.encode("utf-8")) > 180:
        name = name[:-1]
    name = name.rstrip()
    return name or "Unknown"


def clean_rom_title(name: str) -> str:
    """Titre affichable : retire les tags de dumps Switch.

    Supprime les groupes « [0100…][v0][US] » et les tags de site entre
    parenthèses (« (nsw2u.xyz) » — présence d'un point = domaine).
    """
    cleaned = re.sub(r"\s*\[[^\]]*\]", "", name)
    cleaned = re.sub(r"\s*\([^)]*\.[^)]*\)", "", cleaned)
    return cleaned.strip() or name


_DUMP_BRACKET = re.compile(
    r"(?:[0-9a-f]{16}|[A-Z]{2,5}[-_ ]?\d{3,}|v\d+(?:\.\d+)*|"
    r"PS\d|PSX|SWITCH|NSW|BASE|UPD|UPDATE|DLC|"
    r"USA|US|EUR|EU|JPN|JP|WORLD|ASIA|"
    r"REV(?:ISION)?[ ._-]*[A-Z0-9]+|DISC[ ._-]*\d+(?:[ ._-]*OF[ ._-]*\d+)?|"
    r"[A-Z](?:-[A-Z]){2,}|[A-Za-z0-9-]+\.(?:com|net|org|xyz|ws))",
    re.I,
)
_REGION_WORDS = {
    "usa",
    "united states",
    "europe",
    "australia",
    "japan",
    "world",
    "asia",
    "korea",
    "france",
    "germany",
    "italy",
    "spain",
    "uk",
}
_LANGUAGE_CODES = {
    "en",
    "fr",
    "de",
    "es",
    "it",
    "pt",
    "ja",
    "jp",
    "ko",
    "zh",
    "nl",
    "ru",
    "pl",
    "sv",
    "no",
    "da",
    "fi",
    "tr",
    "cs",
    "hu",
}


def _language_tag(value: str) -> bool:
    parts = [part.strip().casefold() for part in value.split(",")]
    return bool(parts) and all(part in _LANGUAGE_CODES for part in parts)


def artwork_search_title(name: str) -> str:
    """Titre commun de recherche d'images, sans métadonnées de dump.

    Préserve les éditions et les années significatives, indépendamment de la
    console ; les noms de fichiers et les titres affichés restent distincts.
    """

    def square(match):
        value = match.group(1).strip()
        return "" if _DUMP_BRACKET.fullmatch(value) or _language_tag(value) else match.group(0)

    def round_bracket(match):
        value = match.group(1).strip()
        lower = value.casefold()
        regions = {part.strip() for part in lower.split(",")}
        languages = _language_tag(value)
        disc = re.fullmatch(r"(?:disc|disk|cd)[ ._-]*\d+(?:[ ._-]*of[ ._-]*\d+)?", value, re.I)
        revision = re.fullmatch(r"(?:rev(?:ision)?|rerelease)[ ._-]*[A-Z0-9]*", value, re.I)
        domain = re.search(r"\b[\w-]+\.(?:com|net|org|xyz|ws)\b", lower)
        if regions <= _REGION_WORDS or languages or disc or revision or domain:
            return ""
        return match.group(0)

    cleaned = re.sub(r"\s*\[([^\]]*)\]", square, name.strip())
    cleaned = re.sub(r"\s*\(([^()]*)\)", round_bracket, cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_")
    return cleaned or name.strip()


def human_size(num_bytes: int) -> str:
    """Convertit un nombre d'octets en taille lisible."""
    size = float(num_bytes)
    for unit in ("o", "Kio", "Mio", "Gio", "Tio"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} Pio"


def human_duration(seconds: float) -> str:
    """Convertit une durée en secondes en texte lisible (« 3 min 20 s »)."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {seconds:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


def ensure_dir(path: Path) -> Path:
    """Crée le dossier si nécessaire, retourne le chemin."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_iso_like(filename: str) -> bool:
    """Retourne True si le fichier est une image disque PS2."""
    return filename.lower().endswith((".iso", ".bin", ".chd", ".cue"))


# Archives pouvant contenir une ROM (extraction requise après téléchargement).
ARCHIVE_EXTENSIONS = (".rar", ".zip", ".7z")


def is_archive(filename: str) -> bool:
    """Retourne True si le fichier est une archive susceptible de contenir une ROM."""
    return filename.lower().endswith(ARCHIVE_EXTENSIONS)


def is_rom_or_archive(filename: str) -> bool:
    """Retourne True pour une image disque ou une archive contenant une ROM.

    Exclut les .pkg (PS2 Classics PSN, incompatibles PCSX2).
    """
    return is_iso_like(filename) or is_archive(filename)


def extract_main_rom(filenames: list[str]) -> str | None:
    """Parmi une liste de fichiers d'un item IA, retourne le fichier ROM principal.

    Priorise .iso > .cue (avec pistes) > .chd > .bin seul > archive.
    """
    lower = {f.lower(): f for f in filenames}
    if any(f.endswith(".iso") for f in lower):
        return next(f for f in filenames if f.lower().endswith(".iso"))
    bins = [f for f in filenames if f.lower().endswith(".bin")]
    cues = [f for f in filenames if f.lower().endswith(".cue")]
    if bins and cues:
        # Le CUE décrit les pistes et constitue le point de lancement.
        return cues[0]
    if any(f.endswith(".chd") for f in lower):
        return next(f for f in filenames if f.lower().endswith(".chd"))
    if bins:
        return bins[0]
    # Archive : prend la plus grosse (souvent la ROM compressée)
    archives = [f for f in filenames if is_archive(f)]
    if archives:
        return archives[0]
    return None


def switch_content_type(filename):
    """Distingue les tags de contenu Switch sans assimiler une version à une MAJ."""
    import re

    name = Path(filename).stem
    if re.search(r"\[(?:update|upd)(?:\]|\s)", name, re.I):
        return "update"
    if re.search(r"\[dlc(?:\]|\s)", name, re.I):
        return "dlc"
    title_id = re.search(r"\[([0-9a-f]{16})\]|^([0-9a-f]{16})$", name, re.I)
    if title_id and int(title_id[1] or title_id[2], 16) & 0xFFF == 0x800:
        return "update"
    return "game"
