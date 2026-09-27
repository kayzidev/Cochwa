"""Inventaire local et lancement ; aucune identification par simple dossier."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cochwa.consoles import DEFAULT_CONSOLE
from cochwa.infrastructure.storage import confined_path, write_json
from cochwa.services.download import checksum
from cochwa.util import human_size


def cue_files(text):
    return re.findall(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+\S+', text, re.I | re.M)


def cue_tracks(path):
    return [
        confined_path(path.parent, a or b) for a, b in cue_files(path.read_text(errors="replace"))
    ]


@dataclass
class InstalledGame:
    title: str
    paths: list[Path]
    size: int
    status: str
    directory: Path

    def to_dict(self):
        return {
            "title": self.title,
            "paths": [str(p) for p in self.paths],
            "size": self.size,
            "status": self.status,
            "directory": str(self.directory),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["title"],
            [Path(p) for p in data["paths"]],
            data["size"],
            data["status"],
            Path(data["directory"]),
        )


def _snapshot(root, index=None):
    """Empreinte (path, size, mtime_ns) de tous les fichiers de la racine.

    Toute addition/suppression/modification invalide le scan mis en cache.
    Le contenu de l'index (fichiers vérifiés) est inclus : une vérification
    Redump change les statuts — mais pas l'écriture du cache lui-même.
    """
    digest = hashlib.sha256()
    index_file = Path(index.path).resolve() if index else None
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if index_file and path.resolve() == index_file:
                continue  # l'écriture du cache ne doit pas s'auto-invalider
            try:
                stat = path.lstat()
            except OSError:
                continue
            digest.update(f"{path}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
    if index:
        records = index.records()
        digest.update(json.dumps(sorted(records.items()), default=str).encode())
    return digest.hexdigest()


def scan(root: Path, index=None, extensions=None):
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"Dossier ROMs introuvable : {root}")
    extensions = {e.lower() for e in (extensions or DEFAULT_CONSOLE.rom_extensions)}
    snapshot = _snapshot(root, index) if index else None
    if index:
        cached = index.cached_scan(root, extensions)
        if cached and cached[0] == snapshot:
            return [InstalledGame.from_dict(g) for g in json.loads(cached[1])]
    index_records = index.records() if index else {}
    groups = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in extensions:
            continue
        if any(p.is_symlink() for p in path.parents if p.is_relative_to(root)):
            continue
        if path.stat().st_size == 0 or path.with_name(path.name + ".part").exists():
            continue
        ancestors = [p for p in path.parents if p.is_relative_to(root)]
        if any((p / ".cochwa.pending.json").exists() for p in ancestors):
            continue
        owner = next((p for p in ancestors if (p / ".romget.json").is_file()), path.parent)
        groups.setdefault(owner, []).append(path)
    result = []
    for directory, files in groups.items():
        tracked = set()
        broken = set()
        for cue in [p for p in files if p.suffix.lower() == ".cue"]:
            try:
                tracks = cue_tracks(cue)
                tracked.update(tracks)
                if not tracks or not all(p.is_file() and p.stat().st_size > 0 for p in tracks):
                    broken.add(cue)
            except (OSError, ValueError):
                broken.add(cue)
        paths = [p for p in files if p not in tracked and p not in broken]
        # Prefer a converted copy without hiding the existence of other discs.
        paths = [
            p for p in paths if p.suffix.lower() == ".chd" or p.with_suffix(".chd") not in paths
        ]
        if not paths:
            continue
        manifest = {}
        invalid_manifest = False
        try:
            manifest = json.loads((directory / ".romget.json").read_text())
            if not isinstance(manifest, dict) or not isinstance(manifest.get("files", []), list):
                raise ValueError("Manifeste invalide")
            if not all(isinstance(f, dict) for f in manifest.get("files", [])):
                raise ValueError("Fichiers du manifeste invalides")
        except (OSError, ValueError):
            invalid_manifest = (directory / ".romget.json").exists()
            manifest = {}
        entries = [paths] if directory != root else [[p] for p in paths]
        for playable in entries:
            title = manifest.get("title") or (
                directory.name if directory != root else playable[0].stem
            )
            status = "Importé — non vérifié"
            if manifest:
                records = manifest.get("files", [])
                valid = bool(records)
                for item in records:
                    try:
                        p = confined_path(directory, item["name"])
                        valid = (
                            valid
                            and p.stat().st_size == item["size"]
                            and p.stat().st_mtime_ns == item.get("mtime_ns")
                        )
                    except (OSError, ValueError, KeyError):
                        valid = False
                status = (
                    (
                        "Vérifié"
                        if all(f.get("md5") or f.get("sha1") for f in records)
                        else "Taille contrôlée"
                    )
                    if valid
                    else "À revérifier"
                )
            if not manifest and len(playable) == 1:
                entry = index_records.get(str(playable[0].resolve()))
                stat = playable[0].stat()
                if entry and (entry["size"], entry["mtime"]) == (stat.st_size, stat.st_mtime_ns):
                    if entry["title"]:
                        status = "Hash local reconnu Redump"
                    else:
                        status = "Hash calculé — non référencé"
            if invalid_manifest:
                status = "Manifeste invalide — à vérifier"
            if broken:
                status = "Disque incomplet"
            size = (
                sum(p.stat().st_size for p in files)
                if directory != root
                else playable[0].stat().st_size
                + (
                    sum(p.stat().st_size for p in cue_tracks(playable[0]))
                    if playable[0].suffix.lower() == ".cue"
                    else 0
                )
            )
            result.append(InstalledGame(title, playable, size, status, directory))
    ordered = sorted(result, key=lambda g: g.title.casefold())
    if index:
        index.store_scan(root, extensions, snapshot, json.dumps([g.to_dict() for g in ordered]))
    return ordered


def verify_manifest(directory: Path, cancel=None):
    path = directory / ".romget.json"
    if not path.exists():
        raise ValueError("Pas de manifeste ; utiliser Redump pour identifier une ROM importée")
    data = json.loads(path.read_text())
    results = []
    for item in data["files"]:
        target = confined_path(directory, item["name"])
        algorithm = "sha1" if item.get("sha1") else "md5"
        expected = item.get(algorithm)
        ok = target.is_file() and target.stat().st_size == item["size"]
        if ok and expected:
            ok = checksum(target, algorithm, cancel=cancel) == expected
        results.append({"file": item["name"], "ok": ok, "level": "hash" if expected else "size"})
        if ok:
            item["mtime_ns"] = target.stat().st_mtime_ns
    if all(r["ok"] for r in results):
        write_json(path, data)
    return results


def export_csv(games, path):
    """Exporte la bibliothèque en CSV (séparateur « ; », compatible tableurs FR)."""
    import csv

    with open(path, "w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["titre", "taille_octets", "taille", "statut", "dossier", "fichiers"])
        for game in games:
            writer.writerow(
                [
                    game.title,
                    game.size,
                    human_size(game.size),
                    game.status,
                    str(game.directory),
                    " | ".join(str(p) for p in game.paths),
                ]
            )
    return Path(path)


def launch(path, config, console=None):
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError("ROM absente ou vide")
    launcher = config.launcher_for(console or DEFAULT_CONSOLE)
    if not launcher:
        name = (console or DEFAULT_CONSOLE).name
        raise FileNotFoundError(f"Lanceur {name} non configuré (onglet Paramètres)")
    if not launcher.is_file():
        raise FileNotFoundError(f"Lanceur introuvable : {launcher}")
    config.state_dir.mkdir(parents=True, exist_ok=True)
    log_name = (console or DEFAULT_CONSOLE).log_name or (console or DEFAULT_CONSOLE).id
    log_path = config.state_dir / f"{log_name}.log"
    command = (
        ["bash", str(launcher), str(path)]
        if launcher.suffix == ".sh"
        else [str(launcher), str(path)]
    )
    with log_path.open("ab") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)
    return process, log_path
