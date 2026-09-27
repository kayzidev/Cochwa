"""Identifications locales persistantes, invalidées par taille et date de modification."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from cochwa.services.download import checksum


class LibraryIndex:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS verified_files (
                path TEXT PRIMARY KEY, size INTEGER, mtime INTEGER, md5 TEXT, title TEXT)""")
            # Scan incrémental : dernier résultat de scan par (racine, extensions),
            # invalidé par le snapshot (path, size, mtime_ns) de la racine.
            db.execute("""CREATE TABLE IF NOT EXISTS scan_cache (
                root TEXT, extensions TEXT, snapshot TEXT, result TEXT,
                PRIMARY KEY (root, extensions))""")

    def records(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            return {row["path"]: dict(row) for row in db.execute("SELECT * FROM verified_files")}

    def verify(self, path, datfile, cancel=None):
        path = Path(path).resolve()
        before = path.stat()
        digest = checksum(path, cancel=cancel)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Le fichier a changé pendant sa vérification")
        title = datfile.lookup_title_by_md5(digest)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO verified_files VALUES(?,?,?,?,?)",
                (str(path), after.st_size, after.st_mtime_ns, digest, title),
            )
        return {
            "path": str(path),
            "md5": digest,
            "redump_title": title,
            "status": "hash_recognized" if title else "unknown",
        }

    def cached_scan(self, root, extensions):
        """(snapshot, résultat JSON) du dernier scan de cette racine, ou None."""
        key_extensions = ",".join(sorted(extensions))
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute(
                "SELECT snapshot, result FROM scan_cache WHERE root=? AND extensions=?",
                (str(root), key_extensions),
            ).fetchone()
            return (row[0], row[1]) if row else None

    def store_scan(self, root, extensions, snapshot, result_json):
        """Mémorise le résultat d'un scan et le snapshot qui l'a produit."""
        key_extensions = ",".join(sorted(extensions))
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO scan_cache VALUES(?,?,?,?)",
                (str(root), key_extensions, snapshot, result_json),
            )

    def duplicates(self):
        """Groupes de fichiers distincts partageant le même hash MD5.

        Ne couvre que les fichiers déjà vérifiés (présents dans l'index).
        Retourne {md5: [paths]} pour les hash présents en plusieurs exemplaires.
        """
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                """SELECT md5 FROM verified_files
                   WHERE md5 != '' GROUP BY md5 HAVING COUNT(DISTINCT path) > 1"""
            ).fetchall()
            return {
                row["md5"]: [
                    r["path"]
                    for r in db.execute(
                        "SELECT path FROM verified_files WHERE md5=? ORDER BY path",
                        (row["md5"],),
                    )
                ]
                for row in rows
            }
