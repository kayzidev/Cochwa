"""Préréglages SRM générés : manifestes par console, aperçu et fusion sauvegardée.

Contrat : SteamGridDB/steam-rom-manager ManualParser et schéma v29.
Aucun changement de Steam ni arrêt de processus lors de l'installation.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from cochwa.consoles import CONSOLES
from cochwa.infrastructure.storage import atomic_write, file_lock
from cochwa.services.library import scan
from cochwa.util import switch_content_type


def detect_srm_directory():
    home = Path.home()
    candidates = [
        home / ".var/app/com.steamgriddb.steam-rom-manager/config/steam-rom-manager/userData",
        Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "steam-rom-manager/userData",
        Path(os.environ.get("APPDATA", home)) / "steam-rom-manager/userData",
        home / "Library/Application Support/steam-rom-manager/userData",
    ]
    return next((p for p in candidates if (p / "userConfigurations.json").is_file()), None)


def detect_steam_directory():
    home = Path.home()
    candidates = [
        home / ".steam/steam",
        home / ".local/share/Steam",
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Steam",
        home / "Library/Application Support/Steam",
    ]
    return next((p.resolve() for p in candidates if (p / "userdata").is_dir()), None)


def process_running(name):
    if sys.platform == "win32":
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, check=True
        )
        return any(
            line.lower().startswith(f'"{name.lower()}.exe"') for line in result.stdout.splitlines()
        )
    result = subprocess.run(["pgrep", "-x", name], capture_output=True, check=False)
    if result.returncode not in {0, 1}:
        raise RuntimeError("Impossible de vérifier les processus en cours")
    return result.returncode == 0


def ensure_srm_closed():
    if shutil.which("flatpak"):
        result = subprocess.run(
            ["flatpak", "ps", "--columns=application"], capture_output=True, text=True, check=False
        )
        if "com.steamgriddb.steam-rom-manager" in result.stdout:
            raise RuntimeError(
                "Fermez Steam ROM Manager avant d’installer ou synchroniser les préréglages."
            )
    if process_running("steam-rom-manager") or process_running("steam-rom-manag"):
        raise RuntimeError("Fermez Steam ROM Manager puis réessayez.")


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _json(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()


def _quote_arg(path):
    text = str(path)
    if any(c in text for c in ('"', "\n", "\r", "\x00")):
        raise ValueError("Un chemin contient un caractère incompatible avec les arguments Steam")
    if os.name != "nt":
        text = text.replace("\\", "\\\\").replace("$", "\\$").replace("`", "\\`")
    return '"' + text + '"'


def _preset(console, manifest_dir, steam_dir):
    return {
        "version": 29,
        "parserType": "Manual",
        "parserId": f"cochwa-{console.id}",
        "configTitle": f"Cochwa — {console.name}",
        "group": "Cochwa",
        "disabled": False,
        "steamDirectory": str(steam_dir),
        "romDirectory": "",
        "steamCategories": ["Cochwa", console.name],
        "parserInputs": {"manualManifests": str(manifest_dir)},
        "executable": {"path": "", "shortcutPassthrough": False, "appendArgsToExecutable": False},
        "executableArgs": "",
        "executableModifier": '"${exePath}"',
        "startInDirectory": "",
        "titleModifier": "${title}",
        "imagePool": "${fuzzyTitle}",
        "onlineImageQueries": ["${fuzzyTitle}"],
        "imageProviders": ["sgdb"],
        "imageProviderAPIs": {},
        "userAccounts": {"specifiedAccounts": ["Global"]},
        "titleFromVariable": {
            "limitToGroups": [],
            "caseInsensitiveVariables": False,
            "skipFileIfVariableWasNotFound": False,
        },
        "sortAsFromVariable": {"limitToGroups": []},
        "fuzzyMatch": {
            "use": True,
            "replaceDiacritics": True,
            "removeCharacters": True,
            "removeBrackets": False,
        },
        "steamInputEnabled": "1",
        "drmProtect": False,
        "controllers": {},
        **{
            k: dict.fromkeys(("tall", "long", "hero", "logo", "icon"))
            for k in ("defaultImage", "localImages", "overlayImages")
        },
    }


@dataclass
class SRMPlan:
    directory: Path
    original_digest: str
    configurations: list
    manifests: dict
    summaries: list[str]
    overlaps: list[str]
    overlap_ids: list[str]


def prepare(config, directory, steam_dir, console_ids):
    """Lecture seule : prépare exactement le contenu montré avant installation."""
    directory, steam_dir = (
        Path(directory).expanduser().absolute(),
        Path(steam_dir).expanduser().absolute(),
    )
    if not (steam_dir / "userdata").is_dir():
        raise ValueError("Choisissez le dossier Steam contenant userdata.")
    target = directory / "userConfigurations.json"
    original = target.read_bytes() if target.exists() else b"[]"
    existing = json.loads(original)
    if not isinstance(existing, list) or not all(isinstance(c, dict) for c in existing):
        raise ValueError(
            "Format SRM incompatible : userConfigurations.json doit contenir une liste."
        )
    known = {c.id: c for c in CONSOLES}
    if not console_ids or any(c not in known for c in console_ids):
        raise ValueError("Sélectionnez au moins une console prise en charge.")
    configurations = [dict(c) for c in existing]
    manifests, summaries, overlaps, overlap_ids = {}, [], [], []
    revision = uuid.uuid4().hex[:12]
    for console_id in dict.fromkeys(console_ids):
        console = known[console_id]
        root = config.roms_dir(console)
        launcher = config.launcher_for(console)
        if root is None or not root.is_dir():
            raise ValueError(f"{console.name} : configurez un dossier de jeux existant.")
        if (
            launcher is None
            or not launcher.is_file()
            or (os.name != "nt" and not os.access(launcher, os.X_OK))
        ):
            raise ValueError(f"{console.name} : configurez un lanceur exécutable.")
        roots = [root]
        if (
            console.disc_based
            and config.download_dir
            and config.download_dir.resolve() != root.resolve()
        ):
            roots.append(config.download_dir)
        entries, seen = [], set()
        for folder in roots:
            for game in scan(folder, extensions=console.rom_extensions):
                paths = sorted(
                    game.paths,
                    key=lambda p: (
                        {".chd": 0, ".cue": 1, ".iso": 2}.get(p.suffix.lower(), 3),
                        str(p),
                    ),
                )
                if not paths:
                    continue
                selected = paths[0]
                # Pas de DLC/mise à jour Switch transformé en raccourci autonome.
                if console_id == "switch" and (
                    selected.suffix.lower() == ".nca"
                    or switch_content_type(selected.name) != "game"
                ):
                    continue
                if selected.resolve() in seen:
                    continue
                seen.add(selected.resolve())
                entries.append(
                    {
                        "title": game.title,
                        "target": str(launcher.resolve()),
                        "startIn": str(launcher.resolve().parent),
                        "launchOptions": _quote_arg(selected.resolve()),
                        "appendArgsToExecutable": False,
                    }
                )
        manifest_dir = directory / "cochwa" / revision / console_id
        manifests[manifest_dir / "games.json"] = entries
        generated = _preset(console, manifest_dir, steam_dir)
        configurations = [c for c in configurations if c.get("parserId") != generated["parserId"]]
        configurations.append(generated)
        summaries.append(f"{console.name} : {len(entries)} jeu(x) · {launcher.name}")
        for parser in existing:
            if not parser.get("disabled") and not str(parser.get("parserId", "")).startswith(
                "cochwa-"
            ):
                old_root = parser.get("romDirectory", "")
                if old_root and Path(old_root).expanduser().resolve() in {
                    p.resolve() for p in roots
                }:
                    overlaps.append(str(parser.get("configTitle", "Parseur personnel")))
                    if parser.get("parserId"):
                        overlap_ids.append(parser["parserId"])
    return SRMPlan(
        directory, _digest(original), configurations, manifests, summaries, overlaps, overlap_ids
    )


def install(plan, disable_overlaps=False):
    ensure_srm_closed()
    plan.directory.mkdir(parents=True, exist_ok=True)
    target = plan.directory / "userConfigurations.json"
    with file_lock(plan.directory / ".cochwa-srm.lock"):
        current = target.read_bytes() if target.exists() else b"[]"
        if _digest(current) != plan.original_digest:
            raise RuntimeError("SRM a changé depuis l’aperçu. Préparez un nouvel aperçu.")
        backup = plan.directory / f"userConfigurations.cochwa-backup-{uuid.uuid4().hex[:12]}.json"
        atomic_write(backup, current)
        for path, games in plan.manifests.items():
            atomic_write(path, _json(games))
        configurations = [dict(c) for c in plan.configurations]
        if disable_overlaps:
            for parser in configurations:
                if parser.get("parserId") in plan.overlap_ids:
                    parser["disabled"] = True
        atomic_write(target, _json(configurations))
    return backup


def synchronize(config):
    """Commande officielle SRM add ; tous les parseurs activés participent."""
    ensure_srm_closed()
    if process_running("steam"):
        raise RuntimeError("Fermez Steam manuellement, puis relancez la synchronisation.")
    executable = shutil.which("steam-rom-manager")
    command = [executable, "add"] if executable else ["flatpak", "run", config.srm_flatpak, "add"]
    if not executable and not shutil.which("flatpak"):
        raise RuntimeError(
            "Steam ROM Manager introuvable : installez SRM ou utilisez l’export des préréglages."
        )
    result = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError(
            "SRM n’a pas terminé la synchronisation : " + (result.stderr or result.stdout)[-1200:]
        )
    return "Synchronisation SRM terminée. Vous pouvez rouvrir Steam."
