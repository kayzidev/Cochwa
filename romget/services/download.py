"""Transfert reprenable : .part, Range contrôlé, empreinte et publication atomique."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
import time
from pathlib import Path
from urllib.parse import quote

import requests

from romget.infrastructure.http import session
from romget.infrastructure.storage import confined_path, file_lock, write_json


class DownloadCancelled(Exception):
    pass


def checksum(path: Path, algorithm="md5", cancel=None):
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            if cancel and cancel.is_set():
                raise DownloadCancelled("Opération interrompue")
            digest.update(chunk)
    return digest.hexdigest()


def verified(path, size, digest="", algorithm="md5", cancel=None):
    return (
        path.is_file()
        and (not size or path.stat().st_size == size)
        and (not digest or checksum(path, algorithm, cancel) == digest.lower())
    )


def download(
    identifier, filename, root, *, size, md5="", sha1="", progress=None, cancel=None, client=None
):
    """Ne remplace jamais un fichier final non reconnu. Retourne le chemin publié."""
    if not identifier or "/" in identifier or "\\" in identifier:
        raise ValueError("Identifiant source invalide")
    if size <= 0:
        raise ValueError("Taille distante positive requise")
    algorithm, digest = ("sha1", sha1) if sha1 else ("md5", md5)
    if digest and not re.fullmatch(r"[0-9a-fA-F]{" + str(40 if sha1 else 32) + "}", digest):
        raise ValueError("Empreinte distante invalide")
    root = Path(root)
    dest = confined_path(root, filename)
    part = confined_path(root, filename + ".part")
    meta = confined_path(root, filename + ".part.json")
    lock = confined_path(root, filename + ".lock")
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://archive.org/download/{quote(identifier, safe='')}/{quote(filename, safe='/')}"
    identity = {"url": url, "size": size, "digest": digest, "algorithm": algorithm}
    cancel = cancel or threading.Event()
    with file_lock(lock):
        if dest.exists():
            if digest and verified(dest, size, digest, algorithm, cancel):
                if progress:
                    progress(size, size)
                return dest
            raise FileExistsError(f"Fichier existant non validé, conservé : {dest}")
        old = {}
        if meta.exists():
            try:
                old = json.loads(meta.read_text())
            except (ValueError, OSError):
                pass
        if not isinstance(old, dict):
            old = {}
        same = all(old.get(k) == v for k, v in identity.items())
        if part.exists() and (not same or part.stat().st_size > size):
            # Preserve unidentified fragments for manual recovery.
            os.replace(part, part.with_name(part.name + f".saved-{time.time_ns()}"))
        if part.exists() and part.stat().st_size == size:
            if digest and verified(part, size, digest, algorithm, cancel):
                os.replace(part, dest)
                if meta.exists():
                    meta.unlink()
                return dest
            if not digest:
                os.replace(part, part.with_name(part.name + f".saved-{time.time_ns()}"))
            else:
                os.replace(part, part.with_name(part.name + f".invalid-{time.time_ns()}"))
                raise ValueError(
                    "Empreinte incorrecte ; fragment isolé, réessayer pour repartir de zéro"
                )
        if part.exists() and not digest and (not old.get("etag") or old["etag"].startswith("W/")):
            # Size alone cannot establish that the remote object is still the same version.
            os.replace(part, part.with_name(part.name + f".saved-{time.time_ns()}"))
        initial = part.stat().st_size if part.exists() else 0
        if shutil.disk_usage(dest.parent).free < size - initial + 16 * 1024 * 1024:
            raise OSError("Espace disque insuffisant")
        client = client or session()
        for attempt in range(3):
            if cancel.is_set():
                raise DownloadCancelled("Téléchargement interrompu")
            initial = part.stat().st_size if part.exists() else 0
            headers = {"Accept-Encoding": "identity"}
            if initial:
                headers["Range"] = f"bytes={initial}-"
                validator = old.get("etag") or old.get("last_modified")
                if validator:
                    headers["If-Range"] = validator
            try:
                with client.get(url, headers=headers, stream=True, timeout=(10, 30)) as response:
                    response.raise_for_status()
                    if response.headers.get("Content-Encoding", "identity") != "identity":
                        raise ValueError("Encodage incompatible avec la reprise par octets")
                    if response.status_code == 206:
                        match = re.fullmatch(
                            r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", "")
                        )
                        if (
                            not match
                            or int(match[1]) != initial
                            or int(match[3]) != size
                            or int(match[2]) != size - 1
                        ):
                            raise ValueError("Content-Range incohérent ; fragment conservé")
                        if (
                            old.get("etag")
                            and response.headers.get("ETag")
                            and old["etag"] != response.headers["ETag"]
                        ):
                            raise ValueError("La version distante a changé ; fragment conservé")
                        mode = "ab"
                    elif response.status_code == 200:
                        initial, mode = 0, "wb"
                    else:
                        raise ValueError(f"Réponse inattendue : HTTP {response.status_code}")
                    length = response.headers.get("Content-Length")
                    if length is not None and int(length) != size - initial:
                        raise ValueError("Taille HTTP différente des métadonnées")
                    old = {
                        **identity,
                        "etag": response.headers.get("ETag", ""),
                        "last_modified": response.headers.get("Last-Modified", ""),
                    }
                    if old["etag"].startswith("W/"):
                        old["etag"] = ""
                    write_json(meta, old)
                    flags = (
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_NOFOLLOW
                        | (os.O_APPEND if mode == "ab" else os.O_TRUNC)
                    )
                    fd = os.open(part, flags, 0o600)
                    written = initial
                    with os.fdopen(fd, mode) as stream:
                        for chunk in response.iter_content(chunk_size=512 * 1024):
                            if cancel.is_set():
                                raise DownloadCancelled("Téléchargement interrompu")
                            if not chunk:
                                continue
                            if written + len(chunk) > size:
                                raise ValueError("Réponse plus grande que prévu")
                            stream.write(chunk)
                            written += len(chunk)
                            if progress:
                                progress(written, size)
                        stream.flush()
                        os.fsync(stream.fileno())
                if not verified(part, size, digest, algorithm, cancel):
                    os.replace(part, part.with_name(part.name + f".invalid-{time.time_ns()}"))
                    raise ValueError(
                        "Taille ou empreinte incorrecte ; fragment isolé, fichier non publié"
                    )
                if cancel.is_set():
                    raise DownloadCancelled("Téléchargement interrompu")
                os.replace(part, dest)
                meta.unlink(missing_ok=True)
                return dest
            except (
                requests.ConnectionError,
                requests.Timeout,
                requests.exceptions.ChunkedEncodingError,
            ):
                if attempt == 2:
                    raise
                if cancel.wait(0.5 * (attempt + 1)):
                    raise DownloadCancelled("Téléchargement interrompu")
    raise RuntimeError("Transfert inachevé")
