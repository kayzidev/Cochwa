import hashlib
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cochwa.infrastructure.storage import file_lock
from cochwa.models import IAGame
from cochwa.services.download import DownloadCancelled
from cochwa.services.jobs import DownloadManager, JobStore
from cochwa.services.library import scan


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = JobStore(self.root / "state")
        self.game = IAGame(
            "fixture",
            "Game",
            "Game",
            [{"name": "disc.iso", "size": 6, "md5": hashlib.md5(b"abcdef").hexdigest()}],
            "disc.iso",
            6,
        )
        self.id = self.store.add(self.game, ["disc.iso"], self.root)

    def row(self):
        return self.store.list()[0]

    def wait(self, condition):
        deadline = time.monotonic() + 3
        while not condition():
            if time.monotonic() > deadline:
                self.fail("worker timeout")
            time.sleep(0.01)

    def test_complete_persists_manifest_and_library_identity(self):
        def fake(identifier, name, root, **kwargs):
            path = root / name
            path.write_bytes(b"abcdef")
            kwargs["progress"](6, 6)
            return path

        manager = DownloadManager(self.store)
        with patch("cochwa.services.jobs.download", side_effect=fake):
            manager.start()
            self.wait(lambda: self.row()["status"] == "completed")
            manager.close()
            manager._thread.join(2)
        dest = Path(json.loads(self.row()["payload"])["destination"])
        self.assertTrue((dest / ".romget.json").exists())
        games = scan(self.root)
        self.assertEqual(games[0].title, "Game")
        self.assertEqual(games[0].status, "Vérifié")

    def test_pause_and_resume_persist(self):
        entered = threading.Event()

        def slow(*args, **kwargs):
            entered.set()
            kwargs["cancel"].wait(2)
            raise DownloadCancelled()

        manager = DownloadManager(self.store)
        with patch("cochwa.services.jobs.download", side_effect=slow):
            manager.start()
            self.assertTrue(entered.wait(2))
            manager.pause(self.id)
            self.wait(lambda: self.row()["status"] == "paused")
            manager.close()
            manager._thread.join(2)
        self.store.resume(self.id)
        self.assertEqual(self.row()["status"], "queued")

    def test_lock_prevents_second_manager(self):
        errors = []
        with file_lock(self.store.directory / "queue.lock"):
            manager = DownloadManager(self.store, lambda kind, msg: errors.append(msg))
            manager.start()
            manager._thread.join(2)
        self.assertTrue(errors)
        self.assertEqual(self.row()["status"], "queued")

    def test_missing_cue_track_fails_before_bin_download(self):
        files = [{"name": "disc.cue", "size": 24}, {"name": "wrong.bin", "size": 20}]
        game = IAGame("cue", "Cue", "Cue", files, "disc.cue", 44)
        job = self.store.add(game, [f["name"] for f in files], self.root)
        row = next(r for r in self.store.list() if r["id"] == job)
        manager = DownloadManager(self.store)

        def fake(identifier, name, root, **kwargs):
            path = root / name
            path.write_text('FILE "missing.bin" BINARY\n')
            return path

        with patch("cochwa.services.jobs.download", side_effect=fake) as call:
            with self.assertRaises(ValueError):
                manager._execute(row)
        self.assertEqual(call.call_count, 1)


if __name__ == "__main__":
    unittest.main()
