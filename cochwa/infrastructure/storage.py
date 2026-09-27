"""Écritures atomiques et confinement des chemins sur Linux."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath


def confined_path(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or "\x00" in name
        or relative.is_absolute()
        or any(part in {"", ".", ".."} for part in name.split("/"))
    ):
        raise ValueError(f"Chemin distant interdit : {name!r}")
    root = Path(root).absolute()
    if root.is_symlink():
        raise ValueError("Le dossier cible ne doit pas être un lien symbolique")
    candidate = root.joinpath(*relative.parts)
    for path in [candidate, *candidate.parents]:
        if path == root.parent:
            break
        if path.is_symlink():
            raise ValueError(f"Lien symbolique interdit : {path}")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError("Chemin hors destination")
    return candidate


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"Lien symbolique interdit : {path}")
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_json(path: Path, data) -> None:
    atomic_write(path, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode())


@contextmanager
def file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Une autre tâche utilise déjà cette destination") from exc
        yield
    finally:
        os.close(fd)
