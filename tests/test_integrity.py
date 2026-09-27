import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from romget.infrastructure.storage import confined_path, write_json
from romget.services.conversion import convert_chd
from romget.services.download import DownloadCancelled, download


class Response:
    def __init__(self, body=b"abcdef", status=200, headers=None):
        self.body = body
        self.status_code = status
        self.headers = {"Content-Length": str(len(body)), **(headers or {})}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, **kwargs):
        yield self.body


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.md5 = hashlib.md5(b"abcdef").hexdigest()

    def call(self, response, **kwargs):
        client = Mock()
        client.get.return_value = response
        return download(
            "fixture", "disc.iso", self.root, size=6, md5=self.md5, client=client, **kwargs
        )

    def seed(self, body=b"abc"):
        (self.root / "disc.iso.part").write_bytes(body)
        write_json(
            self.root / "disc.iso.part.json",
            {
                "url": "https://archive.org/download/fixture/disc.iso",
                "size": 6,
                "digest": self.md5,
                "algorithm": "md5",
                "etag": '"v1"',
            },
        )

    def test_server_ignores_range_restarts(self):
        self.seed()
        target = self.call(Response())
        self.assertEqual(target.read_bytes(), b"abcdef")
        self.assertFalse((self.root / "disc.iso.part").exists())

    def test_206_correct_offset(self):
        self.seed()
        target = self.call(Response(b"def", 206, {"Content-Range": "bytes 3-5/6"}))
        self.assertEqual(target.read_bytes(), b"abcdef")

    def test_206_wrong_offset_preserves_fragment(self):
        self.seed()
        with self.assertRaises(ValueError):
            self.call(Response(b"def", 206, {"Content-Range": "bytes 2-4/6"}))
        self.assertEqual((self.root / "disc.iso.part").read_bytes(), b"abc")
        self.assertFalse((self.root / "disc.iso").exists())

    def test_etag_changed(self):
        self.seed()
        with self.assertRaises(ValueError):
            self.call(Response(b"def", 206, {"Content-Range": "bytes 3-5/6", "ETag": '"v2"'}))

    def test_wrong_hash_not_published(self):
        with self.assertRaises(ValueError):
            self.call(Response(b"XXXXXX"))
        self.assertFalse((self.root / "disc.iso").exists())

    def test_short_response_not_published(self):
        with self.assertRaises(ValueError):
            self.call(Response(b"abc", headers={"Content-Length": "6"}))
        self.assertFalse((self.root / "disc.iso").exists())

    def test_wrong_existing_preserved(self):
        dest = self.root / "disc.iso"
        dest.write_bytes(b"XXXXXX")
        with self.assertRaises(FileExistsError):
            self.call(Response())
        self.assertEqual(dest.read_bytes(), b"XXXXXX")

    def test_verified_existing_reused(self):
        dest = self.root / "disc.iso"
        dest.write_bytes(b"abcdef")
        client = Mock()
        self.assertEqual(
            download("fixture", "disc.iso", self.root, size=6, md5=self.md5, client=client), dest
        )
        client.get.assert_not_called()

    def test_complete_fragment_promoted_without_416(self):
        self.seed(b"abcdef")
        target = self.call(Response(status=416))
        self.assertEqual(target.read_bytes(), b"abcdef")

    def test_416_partial_not_published(self):
        import requests

        self.seed()
        with self.assertRaises(requests.HTTPError):
            self.call(Response(status=416))
        self.assertFalse((self.root / "disc.iso").exists())

    def test_path_escape_rejected(self):
        for name in [
            "../outside.iso",
            "/tmp/out.iso",
            "a/../../out.iso",
            "a\\out.iso",
            "a/./b.iso",
        ]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                confined_path(self.root, name)

    def test_symlink_rejected(self):
        (self.root / "disc.iso.part").symlink_to(self.root / "victim")
        with self.assertRaises(ValueError):
            self.call(Response())

    def test_low_space(self):
        with patch("romget.services.download.shutil.disk_usage", return_value=Mock(free=0)):
            with self.assertRaises(OSError):
                self.call(Response())

    def test_cancel_keeps_no_final(self):
        import threading

        event = threading.Event()
        event.set()
        with self.assertRaises(DownloadCancelled):
            self.call(Response(), cancel=event)

    def test_nested_file_and_url_encoding(self):
        client = Mock()
        client.get.return_value = Response()
        path = download(
            "fixture", "sub/disc #?.iso", self.root, size=6, md5=self.md5, client=client
        )
        self.assertEqual(path.read_bytes(), b"abcdef")
        self.assertIn("disc%20%23%3F.iso", client.get.call_args.args[0])

    def test_stream_interruption_resumes_without_duplication(self):
        import requests

        class Interrupted(Response):
            def iter_content(self, **kwargs):
                yield b"abc"
                raise requests.ConnectionError("interrupted")

        client = Mock()
        client.get.side_effect = [
            Interrupted(),
            Response(b"def", 206, {"Content-Range": "bytes 3-5/6"}),
        ]
        target = download("fixture", "disc.iso", self.root, size=6, md5=self.md5, client=client)
        self.assertEqual(target.read_bytes(), b"abcdef")
        self.assertEqual(client.get.call_args_list[1].kwargs["headers"]["Range"], "bytes=3-")

    def test_bad_fragment_is_quarantined_and_retry_can_restart(self):
        with self.assertRaises(ValueError):
            self.call(Response(b"XXXXXX"))
        self.assertEqual(len(list(self.root.glob("disc.iso.part.invalid-*"))), 1)
        self.assertEqual(self.call(Response()).read_bytes(), b"abcdef")

    def test_resume_without_hash_or_etag_restarts(self):
        (self.root / "disc.iso.part").write_bytes(b"abc")
        write_json(
            self.root / "disc.iso.part.json",
            {
                "url": "https://archive.org/download/fixture/disc.iso",
                "size": 6,
                "digest": "",
                "algorithm": "md5",
            },
        )
        client = Mock()
        client.get.return_value = Response()
        target = download("fixture", "disc.iso", self.root, size=6, client=client)
        self.assertEqual(target.read_bytes(), b"abcdef")
        self.assertNotIn("Range", client.get.call_args.kwargs["headers"])

    def test_conversion_keeps_all_discs(self):
        for name in ["disc1.iso", "disc2.iso", "other.bin"]:
            (self.root / name).write_bytes(b"original")

        def run(cmd, **kwargs):
            if "-o" in cmd:
                Path(cmd[cmd.index("-o") + 1]).write_bytes(b"chd")

        with (
            patch("romget.services.conversion.shutil.which", return_value="/fake/chdman"),
            patch("romget.services.conversion.subprocess.run", side_effect=run) as proc,
        ):
            target = convert_chd(self.root / "disc1.iso", "dvd")
        self.assertTrue(target.exists())
        self.assertTrue(
            all((self.root / n).exists() for n in ["disc1.iso", "disc2.iso", "other.bin"])
        )
        self.assertEqual(proc.call_args_list[0].args[0][1], "createdvd")
        self.assertEqual(proc.call_args_list[1].args[0][1], "verify")

    def test_conversion_requires_media(self):
        source = self.root / "cd.iso"
        source.write_bytes(b"original")
        with self.assertRaises(ValueError):
            convert_chd(source)

    def test_conversion_verification_failure_preserves_source(self):
        import subprocess

        source = self.root / "dvd.iso"
        source.write_bytes(b"original")

        def run(cmd, **kwargs):
            if "-o" in cmd:
                Path(cmd[cmd.index("-o") + 1]).write_bytes(b"bad")
            else:
                raise subprocess.CalledProcessError(1, cmd, stderr="bad CHD")

        with (
            patch("romget.services.conversion.shutil.which", return_value="/fake/chdman"),
            patch("romget.services.conversion.subprocess.run", side_effect=run),
        ):
            with self.assertRaises(RuntimeError):
                convert_chd(source, "dvd")
        self.assertEqual(source.read_bytes(), b"original")
        self.assertFalse(source.with_suffix(".chd").exists())


if __name__ == "__main__":
    unittest.main()
