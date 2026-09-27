"""Conversion conservatrice : aucune suppression des sources."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from romget.infrastructure.storage import file_lock
from romget.services.download import DownloadCancelled


def _run_command(command, cancel=None):
    if cancel is None:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    with tempfile.TemporaryFile(mode="w+") as output:
        process = subprocess.Popen(command, stdout=output, stderr=output, text=True)
        try:
            while process.poll() is None:
                if cancel.wait(0.1):
                    raise DownloadCancelled("Conversion interrompue ; sources conservées")
            if process.returncode:
                output.seek(0)
                raise subprocess.CalledProcessError(
                    process.returncode, command, stderr=output.read()[-1000:]
                )
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def convert_chd(source: Path, media: str | None = None, cancel=None) -> Path:
    source = Path(source)
    if source.suffix.lower() not in {".iso", ".cue"} or not source.is_file():
        raise ValueError("Choisir un fichier ISO ou CUE existant")
    if source.suffix.lower() == ".cue":
        media = "cd"
    if media not in {"cd", "dvd"}:
        raise ValueError("Préciser le support ISO : cd ou dvd (aucune déduction par taille)")
    executable = shutil.which("chdman")
    if not executable:
        raise RuntimeError("chdman introuvable ; installer les outils MAME")
    if cancel and cancel.is_set():
        raise DownloadCancelled("Conversion interrompue")
    sources = [source]
    if source.suffix.lower() == ".cue":
        from romget.services.library import cue_tracks

        sources.extend(cue_tracks(source))
        if len(sources) == 1:
            raise ValueError("CUE sans piste")
    stamps = [(path, path.stat().st_size, path.stat().st_mtime_ns) for path in sources]
    if shutil.disk_usage(source.parent).free < sum(size for _, size, _ in stamps) + 16 * 1024**2:
        raise OSError("Espace insuffisant pour conserver les originaux et le CHD")
    target = source.with_suffix(".chd")
    temporary = target.with_name(target.name + ".converting")
    with file_lock(target.with_name(target.name + ".lock")):
        if target.exists() or target.is_symlink() or temporary.exists() or temporary.is_symlink():
            raise FileExistsError("Sortie CHD ou conversion partielle déjà présente ; conservée")
        try:
            _run_command(
                [executable, "create" + media, "-i", str(source), "-o", str(temporary)], cancel
            )
            _run_command([executable, "verify", "-i", str(temporary)], cancel)
            if any(
                (path.stat().st_size, path.stat().st_mtime_ns) != (size, mtime)
                for path, size, mtime in stamps
            ):
                raise ValueError("Une source a changé pendant la conversion ; sortie non publiée")
            if cancel and cancel.is_set():
                raise DownloadCancelled("Conversion interrompue ; sources conservées")
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise RuntimeError("CHD vide ou absent")
            os.replace(temporary, target)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Échec chdman : {exc.stderr[-1000:]} ; sources conservées") from exc
    return target


def convert_all_chd(games, media="dvd", cancel=None, progress=None):
    """Convertit en CHD tous les ISO/CUE sans CHD existant parmi games.

    Les CUE sont convertis en mode CD (pistes audio), les ISO avec le média
    indiqué (dvd par défaut — majoritaire sur PS2). Les originaux sont
    conservés. Retourne un rapport {"converted": [...], "failed": [...]}.
    """
    targets = []
    for game in games:
        for path in game.paths:
            path = Path(path)
            if path.suffix.lower() in {".iso", ".cue"} and not path.with_suffix(".chd").exists():
                targets.append(path)
    report = {"converted": [], "failed": []}
    for index, path in enumerate(targets, 1):
        if cancel and cancel.is_set():
            raise DownloadCancelled("Conversion de masse interrompue ; sources conservées")
        if progress:
            progress(index, len(targets), path.name)
        try:
            convert_chd(path, "cd" if path.suffix.lower() == ".cue" else media, cancel=cancel)
            report["converted"].append(str(path))
        except Exception as exc:
            report["failed"].append(f"{path.name} : {exc}")
    return report
