"""Tests des fonctionnalités P1/P2/P3 : dédupplication, variantes SGDB,
durées lisibles, export CSV, doublons, catalogue dynamique, conversion masse."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from romget.api.steamgriddb import _title_variants
from romget.config import Config
from romget.gui.games_data import (
    catalog_entries,
    recommended_entries,
    recommended_pool,
    top_entries,
)
from romget.models import IAGame
from romget.services.conversion import convert_all_chd
from romget.services.index import LibraryIndex
from romget.services.library import InstalledGame, export_csv
from romget.services.search import _dedupe
from romget.util import human_duration


def game(title, size, identifier="id"):
    return IAGame(identifier, title, title, [{"name": "x.iso", "size": size}], "x.iso", size)


class DedupeTests(unittest.TestCase):
    def test_near_identical_duplicates_removed(self):
        games = [game("Game (Europe)", 1000, "a"), game("Game (Europe)", 1040, "b")]
        self.assertEqual(len(_dedupe(games)), 1)

    def test_variants_preserved(self):
        # Régions différentes : titres nettoyés distincts → conservées.
        games = [game("Game (Europe)", 1000, "a"), game("Game (USA)", 1010, "b")]
        self.assertEqual(len(_dedupe(games)), 2)
        # Même titre mais tailles très différentes → conservés.
        games = [game("Game (Europe)", 1000, "a"), game("Game (Europe)", 2000, "b")]
        self.assertEqual(len(_dedupe(games)), 2)


class TitleVariantTests(unittest.TestCase):
    def test_variants_strip_region_and_the(self):
        self.assertEqual(
            _title_variants("The Getaway (Europe) (En,Fr,De)"),
            [
                "The Getaway (Europe) (En,Fr,De)",
                "The Getaway",
                "Getaway (Europe) (En,Fr,De)",
                "Getaway",
            ],
        )

    def test_variants_deduped(self):
        self.assertEqual(_title_variants("Gran Turismo 4"), ["Gran Turismo 4"])


class HumanDurationTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(human_duration(45), "45 s")
        self.assertEqual(human_duration(200), "3 min 20 s")
        self.assertEqual(human_duration(3720), "1 h 02 min")


class ExportCsvTests(unittest.TestCase):
    def test_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            games = [
                InstalledGame("Game A", [Path("/roms/a/a.iso")], 1000, "Vérifié", Path("/roms/a")),
                InstalledGame("Game B", [Path("/roms/b.chd")], 2000, "Importé", Path("/roms")),
            ]
            target = Path(tmp) / "out.csv"
            export_csv(games, target)
            rows = target.read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(rows[0], "titre;taille_octets;taille;statut;dossier;fichiers")
            self.assertEqual(len(rows), 3)
            self.assertIn("Game A", rows[1])


class DuplicatesTests(unittest.TestCase):
    def test_duplicates_grouped_by_md5(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = LibraryIndex(Path(tmp) / "idx.sqlite3")
            datfile = Mock()
            datfile.lookup_title_by_md5.return_value = None
            with patch("romget.services.index.checksum", side_effect=["aaa", "aaa", "bbb"]):
                for name in ("a.iso", "b.iso", "c.iso"):
                    path = Path(tmp) / name
                    path.write_bytes(b"x")
                    index.verify(path, datfile=datfile)
            groups = index.duplicates()
            self.assertEqual(len(groups), 1)
            self.assertEqual(len(groups["aaa"]), 2)


class CatalogTests(unittest.TestCase):
    def test_entries_have_title_and_genre(self):
        entries = catalog_entries()
        self.assertGreaterEqual(len(entries), 150)
        for entry in entries:
            self.assertTrue(entry["title"])
            self.assertTrue(entry.get("genre"))

    def test_top_sorted_by_score_desc(self):
        entries = top_entries()
        self.assertGreaterEqual(len(entries), 50)
        scores = [e["score"] for e in entries]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertGreaterEqual(scores[0], 90)

    def test_recommended_pool_is_100_and_distinct_from_top(self):
        pool = recommended_pool()
        self.assertEqual(len(pool), 100)
        top_titles = {e["title"] for e in top_entries()}
        self.assertFalse(top_titles & {e["title"] for e in pool})

    def test_recommended_rotation_deterministic(self):
        first = [e["title"] for e in recommended_entries(day="20260927")]
        second = [e["title"] for e in recommended_entries(day="20260927")]
        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 20)
        # Un autre jour donne une autre sélection.
        other = [e["title"] for e in recommended_entries(day="20260928")]
        self.assertNotEqual(first, other)

    def test_user_catalog_extends(self):
        with tempfile.TemporaryDirectory() as tmp:
            user_file = Path(tmp) / "catalog_ps2.json"
            user_file.write_text(
                json.dumps({"games": [{"title": "Custom Game (Europe)", "genre": "Test"}]})
            )
            with (
                patch("romget.gui.games_data.USER_CATALOG", user_file),
                patch.dict("romget.gui.games_data._cache", {"entries": None, "mtime": 0.0}),
            ):
                titles = [e["title"] for e in catalog_entries()]
            self.assertIn("Custom Game (Europe)", titles)


class IaCollectionsConfigTests(unittest.TestCase):
    def test_ia_collections_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text('[providers.ia_redump]\nia_collections = ["redump", "fav-user"]\n')
            config = Config.load(path)
            self.assertEqual(config.providers["ia_redump"].ia_collections, ["redump", "fav-user"])

    def test_ia_collections_rejects_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text('[providers.ia_redump]\nia_collections = "redump"\n')
            with self.assertRaises(ValueError):
                Config.load(path)


class ConvertAllTests(unittest.TestCase):
    def test_targets_only_iso_cue_without_chd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            iso = root / "a.iso"
            iso.write_bytes(b"x")
            cue = root / "b.cue"
            cue.write_bytes(b"x")
            done = root / "c.iso"
            done.write_bytes(b"x")
            (root / "c.chd").write_bytes(b"x")
            games = [InstalledGame("G", [iso, cue, done], 3, "Importé", root)]
            with patch("romget.services.conversion.convert_chd") as convert:
                report = convert_all_chd(games)
            self.assertEqual(len(report["converted"]), 2)
            self.assertEqual(report["failed"], [])
            # CUE en mode CD, ISO en mode DVD par défaut.
            kinds = {c.args[0].name: c.args[1] for c in convert.call_args_list}
            self.assertEqual(kinds, {"a.iso": "dvd", "b.cue": "cd"})


if __name__ == "__main__":
    unittest.main()
