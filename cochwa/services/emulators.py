"""Catalogue officiel et détection locale passive : aucun binaire exécuté au scan."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

from cochwa.infrastructure.storage import file_lock, write_json


def catalog():
    return json.loads(files("cochwa.data").joinpath("emulators.json").read_text())


def executable(path):
    return bool(path and Path(path).is_file() and os.access(path, os.X_OK))


class EmulatorRegistry:
    def __init__(self, config):
        self.config = config
        self.path = config.state_dir / "emulators.json"

    def _read(self):
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text())
        if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
            raise ValueError("Registre des émulateurs invalide ; fichier conservé.")
        return data

    def set_path(self, emulator_id, path):
        if emulator_id not in {e["id"] for e in catalog()}:
            raise ValueError("Émulateur inconnu")
        path = Path(path).expanduser().absolute()
        if not executable(path):
            raise ValueError("Choisissez un fichier exécutable (binaire, AppImage ou script).")
        with file_lock(self.path.with_suffix(".lock")):
            data = self._read()
            data[emulator_id] = str(path)
            write_json(self.path, data)

    def clear_path(self, emulator_id):
        with file_lock(self.path.with_suffix(".lock")):
            data = self._read()
            data.pop(emulator_id, None)
            write_json(self.path, data)

    def detect(self):
        custom = self._read()
        results = []
        flatpak = shutil.which("flatpak")
        for item in catalog():
            row = dict(item, command=[], origin="", configured=False, custom=False)
            selected = custom.get(item["id"])
            if selected:
                row.update(custom=True, origin=selected)
                if executable(selected):
                    row["command"] = [selected]
            else:
                for name in item["executables"]:
                    path = shutil.which(name)
                    if path:
                        row.update(command=[path], origin=path)
                        break
                if not row["command"] and flatpak:
                    for app_id in item["flatpaks"]:
                        roots = (
                            Path.home() / ".local/share/flatpak/app",
                            Path("/var/lib/flatpak/app"),
                        )
                        if any((root / app_id / "current/active").is_dir() for root in roots):
                            row.update(
                                command=[flatpak, "run", app_id], origin=f"Flatpak · {app_id}"
                            )
                            break
            launcher = self.config.console_launchers.get(item["integration"])
            # Un script de jeu configuré n'est pas exécuté sans ROM.
            if (
                launcher
                and Path(launcher).is_file()
                and (executable(launcher) or Path(launcher).suffix == ".sh")
            ):
                row["configured"] = True
                if not row["origin"]:
                    row["origin"] = f"Lanceur Cochwa · {launcher}"
            row["ready"] = bool(row["command"] or row["configured"])
            results.append(row)
        return results

    def open(self, emulator_id):
        item = next(e for e in self.detect() if e["id"] == emulator_id)
        if not item["command"]:
            raise FileNotFoundError("Ajoutez un exécutable pour ouvrir cet émulateur.")
        # Liste d'arguments : aucun shell, aucune commande issue d'un champ libre.
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        with (self.config.state_dir / f"emulator-{emulator_id}.log").open("ab") as log:
            return subprocess.Popen(item["command"], stdout=log, stderr=log, start_new_session=True)
