import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cochwa.cli import main
from cochwa.config import Config
from cochwa.models import IAGame


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
        with patch("cochwa.cli.SearchService.item", return_value=game):
            code, out, err = self.call("download", "fixture")
        self.assertEqual(code, 2)
        self.assertIn("--file", err)
        self.assertFalse((self.root / "state/jobs.sqlite3").exists())

    def test_dry_run_no_queue_or_rom_written(self):
        game = IAGame("fixture", "Game", "Game", [{"name": "disc.iso", "size": 6}], "disc.iso", 6)
        with patch("cochwa.cli.SearchService.item", return_value=game):
            code, out, err = self.call("download", "fixture", "--file", "disc.iso", "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["total_size"], 6)
        self.assertFalse((self.root / "state/jobs.sqlite3").exists())

    def test_iso_conversion_without_media_fails_before_download(self):
        game = IAGame("fixture", "Game", "Game", [{"name": "disc.iso", "size": 6}], "disc.iso", 6)
        with patch("cochwa.cli.SearchService.item", return_value=game):
            code, out, err = self.call("download", "fixture", "--file", "disc.iso", "--chd")
        self.assertEqual(code, 2)
        self.assertIn("--media", err)


if __name__ == "__main__":
    unittest.main()


class CliConsoleTests(unittest.TestCase):
    """M4 : --console sur list/play/doctor."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.switch = self.root / "switch"
        self.switch.mkdir()
        (self.switch / "Game [0100ABCD][v0].nsp").write_bytes(b"rom")
        (self.root / "Game PS2.iso").write_bytes(b"rom")
        self.config = self.root / "config.toml"
        Config(
            ps2_dir=self.root,
            switch_dir=self.switch,
            state_dir=self.root / "state",
            source=self.config,
        ).save()

    def call(self, *args):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = main(["--config", str(self.config), "--json", *args])
        return code, output.getvalue(), error.getvalue()

    def test_list_console_switch(self):
        code, out, _ = self.call("list", "--console", "switch")
        self.assertEqual(code, 0)
        titles = [g["title"] for g in json.loads(out)]
        self.assertEqual(titles, ["Game [0100ABCD][v0]"])

    def test_list_console_default_is_ps2(self):
        code, out, _ = self.call("list")
        self.assertEqual(code, 0)
        titles = [g["title"] for g in json.loads(out)]
        self.assertIn("Game PS2", titles)

    def test_list_console_unconfigured(self):
        cfg = Config.load(self.config)
        cfg.switch_dir = None
        cfg.save()
        code, _, err = self.call("list", "--console", "switch")
        self.assertEqual(code, 2)
        self.assertIn("non configurée", json.loads(err)["error"])

    def test_doctor_reports_each_console(self):
        code, out, _ = self.call("doctor")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(set(data["consoles"]), {"ps2", "switch"})
        self.assertTrue(data["consoles"]["switch"]["configured"])
        self.assertTrue(data["consoles"]["switch"]["rom_directory_exists"])
        self.assertFalse(data["consoles"]["switch"]["launcher_exists"])
        # Clés historiques PS2 conservées.
        self.assertEqual(data["rom_directory"], str(self.root))
        self.assertNotIn("steamgrid_api_key", data)

    def test_doctor_console_filter(self):
        code, out, _ = self.call("doctor", "--console", "switch")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(set(data["consoles"]), {"switch"})
