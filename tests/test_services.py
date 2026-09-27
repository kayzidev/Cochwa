import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from cochwa.api.redump import RedumpDatfile
from cochwa.config import Config
from cochwa.models import IAGame
from cochwa.providers.ia_redump import IARedumpProvider
from cochwa.services.jobs import JobStore
from cochwa.services.library import scan
from cochwa.services.search import SearchService, _matches_other_platform, literal


class ServicesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_custom_config_created_and_persistent(self):
        path = self.root / "nested/config.toml"
        cfg = Config.load(path)
        self.assertTrue(path.exists())
        self.assertEqual(cfg.steamgrid_api_key, "")
        cfg.ps2_dir = self.root / "roms"
        cfg.save()
        self.assertEqual(Config.load(path).ps2_dir, cfg.ps2_dir)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_download_dir_optional_and_persistent(self):
        path = self.root / "config.toml"
        cfg = Config.load(path)
        # Par défaut : téléchargements dans le dossier PS2.
        self.assertIsNone(cfg.download_dir)
        self.assertEqual(cfg.download_path, cfg.ps2_dir)
        cfg.download_dir = self.root / "incoming"
        cfg.save()
        loaded = Config.load(path)
        self.assertEqual(loaded.download_dir, cfg.download_dir)
        self.assertEqual(loaded.download_path, cfg.download_dir)
        # Retour à « vide = dossier PS2 » : la clé est retirée du TOML.
        loaded.download_dir = None
        loaded.save()
        self.assertIsNone(Config.load(path).download_dir)

    def test_switch_dir_and_launcher_optional_and_persistent(self):
        from cochwa.consoles import get

        switch = get("switch")
        path = self.root / "config.toml"
        cfg = Config.load(path)
        # Par défaut : console Switch non configurée.
        self.assertIsNone(cfg.switch_dir)
        self.assertIsNone(cfg.switch_launcher)
        self.assertIsNone(cfg.roms_dir(switch))
        self.assertIsNone(cfg.launcher_for(switch))
        cfg.switch_dir = self.root / "switch"
        cfg.switch_launcher = self.root / "ryujinx" / "launch.sh"
        cfg.save()
        loaded = Config.load(path)
        self.assertEqual(loaded.switch_dir, cfg.switch_dir)
        self.assertEqual(loaded.switch_launcher, cfg.switch_launcher)
        self.assertEqual(loaded.roms_dir(switch), cfg.switch_dir)
        self.assertEqual(loaded.launcher_for(switch), cfg.switch_launcher)
        # La PS2 reste sur les champs historiques.
        self.assertEqual(loaded.roms_dir(get("ps2")), loaded.ps2_dir)
        self.assertEqual(loaded.launcher_for(get("ps2")), loaded.launcher)
        # Retour à « non configuré » : les clés sont retirées du TOML.
        loaded.switch_dir = None
        loaded.switch_launcher = None
        loaded.save()
        reloaded = Config.load(path)
        self.assertIsNone(reloaded.switch_dir)
        self.assertIsNone(reloaded.switch_launcher)

    def test_config_preserves_extra_options(self):
        path = self.root / "config.toml"
        path.write_text('[custom]\nfoo="bar"\n')
        Config.load(path).save()
        import tomllib

        self.assertEqual(tomllib.loads(path.read_text())["custom"]["foo"], "bar")

    def test_expired_cache_survives_network_failure(self):
        path = self.root / "redump.json"
        path.write_text(
            json.dumps({"saved_at": 0, "md5_to_title": {"abc": "Game"}, "titles": ["Game"]})
        )
        index = RedumpDatfile(path)
        with patch.object(index, "_download_and_parse", side_effect=OSError("offline")) as call:
            self.assertTrue(index.load())
            self.assertTrue(index.load())
        self.assertEqual(call.call_count, 1)
        self.assertEqual(index.status, "stale")

    def test_library_ignores_empty_and_partial(self):
        (self.root / "empty").mkdir()
        (self.root / "x.iso.part").write_bytes(b"partial")
        (self.root / "zero.iso").touch()
        (self.root / "Game.iso").write_bytes(b"image")
        result = scan(self.root)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, "Game")

    def test_cue_tracks_one_playable_disc(self):
        (self.root / "Game.cue").write_text('FILE "track.bin" BINARY\nTRACK 01 MODE2/2352\n')
        (self.root / "track.bin").write_bytes(b"bytes")
        result = scan(self.root)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].paths[0].suffix, ".cue")

    def test_title_does_not_become_verified_hash(self):
        service = SearchService(Config())
        metadata = {
            "metadata": {"title": "Known title"},
            "files": [{"name": "game.iso", "size": "20", "md5": "unrecognized"}],
        }
        index = Mock()
        index.lookup_title_by_md5.return_value = None
        index.is_ps2_title.return_value = True
        with patch.object(IARedumpProvider, "_cached", return_value=metadata):
            game = service.item("fixture", index)
        self.assertFalse(game.is_ps2)
        self.assertEqual(game.identification, "title")

    def test_mixed_pack_not_renamed_as_single_game(self):
        service = SearchService(Config())
        index = Mock()
        index.lookup_title_by_md5.side_effect = ["Game A", None]
        index.is_ps2_title.return_value = False
        data = {
            "metadata": {"title": "Pack"},
            "files": [
                {"name": "a.iso", "size": 1, "md5": "a"},
                {"name": "b.iso", "size": 2, "md5": "b"},
            ],
        }
        with patch.object(IARedumpProvider, "_cached", return_value=data):
            game = service.item("fixture", index)
        self.assertEqual(game.clean_title, "Pack")
        self.assertFalse(game.is_ps2)

    def test_jobs_deduplicate_selection(self):
        store = JobStore(self.root / "state")
        game = IAGame("id", "Game", "Game", [{"name": "x.iso", "size": 20}], "x.iso", 20)
        a = store.add(game, ["x.iso"], self.root)
        b = store.add(game, ["x.iso"], self.root)
        self.assertEqual(a, b)
        self.assertEqual(len(store.list()), 1)

    def test_jobs_reject_missing_mount(self):
        game = IAGame("id", "G", "G", [{"name": "x.iso", "size": 20}], "x.iso", 20)
        with self.assertRaises(FileNotFoundError):
            JobStore(self.root / "state").add(game, ["x.iso"], self.root / "missing")

    def test_solr_literal(self):
        self.assertEqual(literal('a" OR *:*'), '"a\\" OR *:*"')

    def test_playstation_alone_is_ps1_not_ps2(self):
        self.assertTrue(_matches_other_platform("Tekken 3 (PlayStation)", "tekken3_ps1"))
        self.assertFalse(_matches_other_platform("Gran Turismo 4 (PlayStation 2)", "gt4_ps2"))

    def test_collections_signal_platform(self):
        self.assertTrue(
            _matches_other_platform("Some Game", "some_game", ["sony_playstation", "retoroms"])
        )
        self.assertFalse(_matches_other_platform("Some Game", "some_game", ["sony_playstation2"]))
        # Collections non concluantes : pas d'exclusion sur ce seul signal.
        self.assertFalse(_matches_other_platform("Some Game", "some_game", ["retoroms"]))


if __name__ == "__main__":
    unittest.main()
