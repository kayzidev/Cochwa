"""File persistante, un transfert actif, pause/reprise et verrou interprocessus."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from cochwa import consoles
from cochwa.infrastructure.storage import confined_path, file_lock, write_json
from cochwa.services.download import DownloadCancelled, checksum, download
from cochwa.services.extraction import extract_if_archive
from cochwa.services.library import cue_files
from cochwa.util import is_archive, sanitize_dirname


class JobStore:
    def __init__(self, state_dir):
        self.directory = Path(state_dir)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "jobs.sqlite3"
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, payload TEXT NOT NULL,
                status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
                total INTEGER NOT NULL, error TEXT NOT NULL DEFAULT '', updated REAL NOT NULL)""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def add(self, game, names, root):
        if game.external or game.source not in {"ia_redump", "ia_switch"}:
            raise ValueError("Cette source utilise un téléchargement externe ; ouvrir sa fiche")
        if not Path(root).is_dir():
            raise FileNotFoundError(
                "Dossier ROMs absent ; vérifier le montage avant de télécharger"
            )
        selected = [f for f in game.files if f["name"] in names]
        if not selected or len(set(names)) != len(selected):
            raise ValueError("Sélection de fichiers invalide")
        for f in selected:
            confined_path(Path(root), f["name"])
        if not any(not f["name"].lower().endswith(".cue") for f in selected):
            raise ValueError("Sélectionner aussi les pistes BIN du CUE")
        key = hashlib.sha256(
            json.dumps(
                [
                    str(Path(root).resolve()),
                    game.identifier,
                    sorted(
                        (f["name"], f["size"], f.get("md5", ""), f.get("sha1", ""))
                        for f in selected
                    ),
                ]
            ).encode()
        ).hexdigest()[:20]
        titles = {f.get("title") for f in selected if f.get("title")}
        title = next(iter(titles)) if len(titles) == 1 else game.clean_title
        destination = Path(root) / (sanitize_dirname(title) + " [" + key[:8] + "]")
        payload = {
            "identifier": game.identifier,
            "platform": game.platform,
            "title": title,
            "files": selected,
            "root": str(root),
            "destination": str(destination),
        }
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO jobs(id,title,payload,status,total,updated) VALUES(?,?,?,?,?,?)",
                (
                    key,
                    title,
                    json.dumps(payload),
                    "queued",
                    sum(f["size"] for f in selected),
                    time.time(),
                ),
            )
            db.execute(
                "UPDATE jobs SET status='queued',error='',updated=? WHERE id=? AND status='completed'",
                (time.time(), key),
            )
        return key

    def list(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY updated,id")]

    def update(self, job_id, **fields):
        if not fields.keys() <= {"status", "progress", "error"}:
            raise ValueError("Champ de tâche invalide")
        fields["updated"] = time.time()
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET "
                + ",".join(f"{k}=?" for k in fields)
                + " WHERE id=? AND status != 'removing'",
                (*fields.values(), job_id),
            )

    def remove(self, job_id):
        """Retire la tâche ; laisse un marqueur pour arrêter un worker actif."""
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET status='removing',updated=? WHERE id=? AND status='running'",
                (time.time(), job_id),
            )
            db.execute("DELETE FROM jobs WHERE id=? AND status!='removing'", (job_id,))

    def removal_requested(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            return row is None or row["status"] == "removing"

    def finish_removal(self, job_id):
        with self.connect() as db:
            db.execute("DELETE FROM jobs WHERE id=? AND status='removing'", (job_id,))

    def resume(self, job_id):
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET status='queued',error='',updated=? WHERE id=? AND status IN ('paused','failed','cancelled')",
                (time.time(), job_id),
            )


class DownloadManager:
    def __init__(self, store, notify=None, datfile=None):
        self.store = store
        self.notify = notify or (lambda *args: None)
        # Callable optionnel retournant le datfile Redump — utilisé pour
        # identifier par hash le contenu extrait des archives.
        self.datfile = datfile
        self.stop_event = threading.Event()
        self.cancel_event = threading.Event()
        self.active = None
        self._requested = "paused"
        self._thread = None
        self._guard = threading.Lock()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self.stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="downloads")
        self._thread.start()

    def pause(self, job_id, cancel=False):
        with self._guard:
            state = "cancelled" if cancel else "paused"
            if self.active == job_id:
                self._requested = state
                self.cancel_event.set()
            else:
                with self.store.connect() as db:
                    db.execute(
                        "UPDATE jobs SET status=?,updated=? WHERE id=? AND (status='queued' OR (? AND status='paused'))",
                        (state, time.time(), job_id, cancel),
                    )

    def remove(self, job_id):
        with self._guard:
            self.store.remove(job_id)
            if self.active == job_id:
                self.cancel_event.set()
        self.notify("jobs", job_id)

    def close(self):
        self.stop_event.set()
        self.cancel_event.set()

    def _run(self):
        try:
            with file_lock(self.store.directory / "queue.lock"):
                with self.store.connect() as db:
                    db.execute(
                        "UPDATE jobs SET status='paused',error='Interruption précédente' WHERE status='running'"
                    )
                    db.execute("DELETE FROM jobs WHERE status='removing'")
                while not self.stop_event.is_set():
                    queued = next((r for r in self.store.list() if r["status"] == "queued"), None)
                    if queued is None:
                        self.stop_event.wait(0.3)
                        continue
                    with self._guard:
                        if self.stop_event.is_set():
                            break
                        # A pause may have arrived after taking the snapshot.
                        with self.store.connect() as db:
                            changed = db.execute(
                                "UPDATE jobs SET status='running',error='' WHERE id=? AND status='queued'",
                                (queued["id"],),
                            ).rowcount
                        if not changed:
                            continue
                        self.active = queued["id"]
                        self.cancel_event.clear()
                        self._requested = "paused"
                    try:
                        self._execute(queued)
                        self.store.update(
                            queued["id"], status="completed", progress=queued["total"]
                        )
                    except DownloadCancelled:
                        self.store.update(queued["id"], status=self._requested)
                    except Exception as exc:
                        self.store.update(queued["id"], status="failed", error=str(exc))
                    finally:
                        self.store.finish_removal(queued["id"])
                        self.notify("jobs", queued["id"])
                        with self._guard:
                            self.active = None
        except Exception as exc:
            self.notify("error", str(exc))

    def _execute(self, job):
        payload = json.loads(job["payload"])
        root = Path(payload["root"])
        if not root.is_dir():
            raise FileNotFoundError("Disque ou dossier ROMs indisponible")
        destination = confined_path(root, Path(payload["destination"]).name)
        destination.mkdir(exist_ok=True)
        with file_lock(destination / ".cochwa.lock"):
            pending = destination / ".cochwa.pending.json"
            write_json(pending, {"job_id": job["id"], "files": payload["files"]})
            completed = 0
            last = 0
            files = payload["files"]
            # CUE first, then validate that its referenced tracks are explicitly selected.
            ordered = sorted(files, key=lambda f: not f["name"].lower().endswith(".cue"))
            for item in ordered:

                def progress(written, total):
                    nonlocal last
                    if self.store.removal_requested(job["id"]):
                        raise DownloadCancelled()
                    now = time.monotonic()
                    if now - last > 0.2 or written == total:
                        self.store.update(job["id"], progress=completed + written)
                        self.notify("progress", job["id"])
                        last = now

                dest = download(
                    payload["identifier"],
                    item["name"],
                    destination,
                    size=item["size"],
                    md5=item.get("md5", ""),
                    sha1=item.get("sha1", ""),
                    progress=progress,
                    cancel=self.cancel_event,
                )
                if dest.suffix.lower() == ".cue":
                    selected = {confined_path(destination, f["name"]) for f in files}
                    refs = [
                        confined_path(dest.parent, a or b)
                        for a, b in cue_files(dest.read_text(errors="replace"))
                    ]
                    if not refs or not set(refs) <= selected:
                        raise ValueError(
                            "Le CUE référence des pistes non sélectionnées ; sélectionner tous ses BIN"
                        )
                item["mtime_ns"] = dest.stat().st_mtime_ns
                completed += item["size"]
            # Extraction des archives après téléchargement complet.
            # L'archive est supprimée seulement si une image disque est produite,
            # et le manifeste est mis à jour pour pointer vers les fichiers extraits.
            extracted_titles = []
            final_files = []
            for item in files:
                path = destination / item["name"]
                if path.is_file() and is_archive(path.name):
                    extracted = extract_if_archive(path, destination, self.cancel_event)
                    extracted_titles.extend(p.name for p in extracted)
                    for p in extracted:
                        stat = p.stat()
                        entry = {
                            "name": str(p.relative_to(destination)),
                            "size": stat.st_size,
                            "mtime_ns": stat.st_mtime_ns,
                            "extracted_from": item["name"],
                        }
                        # Identification Redump du contenu extrait : le hash de
                        # l'archive ne vaut rien, celui du fichier extrait si.
                        # Réservé aux consoles à disques (datfile Redump PS2).
                        platform = consoles.get(payload.get("platform", "ps2"))
                        if self.datfile and platform and platform.disc_based:
                            digest = checksum(p, cancel=self.cancel_event)
                            entry["md5"] = digest
                            recognized = self.datfile().lookup_title_by_md5(digest)
                            if recognized:
                                entry["title"] = recognized
                        final_files.append(entry)
                else:
                    final_files.append(item)
            write_json(
                destination / ".romget.json",
                {
                    "schema": 1,
                    "title": payload["title"],
                    "identifier": payload["identifier"],
                    "files": final_files,
                    "extracted": extracted_titles,
                },
            )
            pending.unlink(missing_ok=True)
