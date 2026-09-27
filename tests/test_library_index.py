import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from romget.infrastructure.storage import write_json
from romget.services.index import LibraryIndex
from romget.services.library import scan


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_mixed_managed_and_imported_library(self):
        directory = self.root / "A"
        directory.mkdir()
        managed = directory / "disc.iso"
        managed.write_bytes(b"abcdef")
        write_json(
            directory / ".romget.json",
            {
                "title": "A",
                "files": [
                    {
                        "name": "disc.iso",
                        "size": 6,
                        "md5": hashlib.md5(b"abcdef").hexdigest(),
                        "mtime_ns": managed.stat().st_mtime_ns,
                    }
                ],
            },
        )
        imported = self.root / "Z.iso"
        imported.write_bytes(b"local")
        index = LibraryIndex(self.root / "state/library.sqlite3")
        datfile = Mock()
        datfile.lookup_title_by_md5.return_value = "Z Redump"
        index.verify(imported, datfile)
        games = scan(self.root, index)
        self.assertEqual(len(games), 2)
        self.assertEqual(games[1].status, "Hash local reconnu Redump")
        imported.write_bytes(b"changed")
        self.assertEqual(scan(self.root, index)[1].status, "Importé — non vérifié")

    def test_pending_download_is_not_playable(self):
        directory = self.root / "A"
        directory.mkdir()
        (directory / "disc.iso").write_bytes(b"complete first disc")
        write_json(directory / ".romget.pending.json", {"job_id": "fixture"})
        self.assertEqual(scan(self.root), [])

    def test_nested_managed_files_stay_one_game(self):
        directory = self.root / "Game"
        (directory / "disc1").mkdir(parents=True)
        (directory / "disc2").mkdir()
        files = []
        for name in ["disc1/a.iso", "disc2/b.iso"]:
            path = directory / name
            path.write_bytes(b"image")
            files.append({"name": name, "size": 5, "mtime_ns": path.stat().st_mtime_ns})
        write_json(directory / ".romget.json", {"title": "Managed title", "files": files})
        games = scan(self.root)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].title, "Managed title")
        self.assertEqual(len(games[0].paths), 2)

    def test_corrupt_manifest_does_not_crash_scan(self):
        (self.root / "Game.iso").write_bytes(b"image")
        (self.root / ".romget.json").write_text("[1,2]")
        self.assertIn("invalide", scan(self.root)[0].status)
