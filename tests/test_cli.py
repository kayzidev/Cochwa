import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from romget.cli import main
from romget.config import Config
from romget.models import IAGame


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "config.toml"
        Config(ps2_dir=self.root, state_dir=self.root / "state", source=self.config).save()

    def call(self, *args):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = main(["--config", str(self.config), "--json", *args])
        return code, output.getvalue(), error.getvalue()

    def test_doctor_json_no_key(self):
        code, out, err = self.call("doctor")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertNotIn("steamgrid_api_key", data)
        self.assertFalse(data["artwork_key_configured"])

    def test_bad_config_is_structured_error(self):
        self.config.write_text("[broken")
        code, out, err = self.call("doctor")
        self.assertEqual(code, 2)
        self.assertFalse(out)
        self.assertIn("error", json.loads(err))

    def test_download_requires_selection(self):
        game = IAGame("fixture", "Game", "Game", [{"name": "disc.iso", "size": 6}], "disc.iso", 6)
        with patch("romget.cli.SearchService.item", return_value=game):
            code, out, err = self.call("download", "fixture")
        self.assertEqual(code, 2)
        self.assertIn("--file", err)
        self.assertFalse((self.root / "state/jobs.sqlite3").exists())

    def test_dry_run_no_queue_or_rom_written(self):
        game = IAGame("fixture", "Game", "Game", [{"name": "disc.iso", "size": 6}], "disc.iso", 6)
        with patch("romget.cli.SearchService.item", return_value=game):
            code, out, err = self.call("download", "fixture", "--file", "disc.iso", "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["total_size"], 6)
        self.assertFalse((self.root / "state/jobs.sqlite3").exists())

    def test_iso_conversion_without_media_fails_before_download(self):
        game = IAGame("fixture", "Game", "Game", [{"name": "disc.iso", "size": 6}], "disc.iso", 6)
        with patch("romget.cli.SearchService.item", return_value=game):
            code, out, err = self.call("download", "fixture", "--file", "disc.iso", "--chd")
        self.assertEqual(code, 2)
        self.assertIn("--media", err)


if __name__ == "__main__":
    unittest.main()
