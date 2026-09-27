"""Extraction d'archives ROM (.rar/.zip/.7z) après téléchargement.

Utilise 7z (p7zip, dispo sur Fedora) ou unar en fallback.
L'archive est conservée jusqu'à vérification que l'extraction a produit
au moins une image disque reconnue, puis supprimée.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from cochwa.util import is_archive, is_iso_like


def _extractor():
    """Retourne la commande d'extraction disponible, ou None."""
    if shutil.which("7z"):
        return "7z"
    if shutil.which("unar"):
        return "unar"
    return None


def _list_iso_entries(tool: str, archive: Path) -> list[str]:
    """Liste les entrées images disque d'une archive (chemins relatifs)."""
    if tool == "7z":
        # -ba : sortie brute "chemin" seul, une entrée par ligne
        result = subprocess.run(
            ["7z", "l", "-ba", str(archive)],
            capture_output=True,
            text=True,
            timeout=300,
        )
    else:
        result = subprocess.run(
            ["unar", "-l", str(archive)],
            capture_output=True,
            text=True,
            timeout=300,
        )
    if result.returncode != 0:
        return []
    entries = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if tool == "unar" and line.endswith(")"):  # ligne "name (size)"
            line = line.rsplit(" (", 1)[0]
        if line and is_iso_like(line):
            entries.append(line)
    return entries


def extract_archive(archive: Path, dest_dir: Path, cancel=None) -> list[Path]:
    """Extrait une archive dans dest_dir. Retourne les images disque extraites.

    Lève ValueError si aucun extracteur n'est disponible, si l'extraction
    échoue, ou si aucune image disque n'est produite.
    """
    tool = _extractor()
    if tool is None:
        raise ValueError("Aucun extracteur disponible (installer p7zip : sudo dnf install p7zip)")
    archive = Path(archive)
    dest_dir = Path(dest_dir)
    # Liste les images attendues AVANT extraction (le mtime extrait peut être
    # celui d'origine du fichier, on ne peut pas s'y fier pour détecter).
    expected = _list_iso_entries(tool, archive)
    if tool == "7z":
        args = ["7z", "x", "-y", f"-o{dest_dir}", str(archive)]
    else:  # unar
        args = ["unar", "-f", "-o", str(dest_dir), str(archive)]
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=3600,  # 1h max pour les grosses archives DVD9
    )
    if result.returncode != 0:
        raise ValueError(f"Extraction échouée : {(result.stderr or result.stdout)[:200]}")
    # Vérifie que les images listées existent bien après extraction ;
    # fallback : scan du dossier si le listing a échoué.
    extracted = [dest_dir / e for e in expected if (dest_dir / e).is_file()]
    if not extracted:
        extracted = [p for p in dest_dir.rglob("*") if p.is_file() and is_iso_like(p.name)]
    if not extracted:
        raise ValueError("Aucune image disque (.iso/.bin/.cue/.chd) dans l'archive")
    return extracted


def extract_if_archive(path: Path, dest_dir: Path, cancel=None) -> list[Path]:
    """Extrait path si c'est une archive, puis supprime l'archive.

    Retourne la liste des images disque extraites, ou [] si path n'est
    pas une archive.
    """
    path = Path(path)
    if not is_archive(path.name):
        return []
    extracted = extract_archive(path, dest_dir, cancel)
    # Suppression seulement après extraction réussie
    path.unlink()
    return extracted
