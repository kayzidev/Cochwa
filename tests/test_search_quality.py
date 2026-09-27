import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from romget.config import Config, ProviderConfig
from romget.models import IAGame, SearchResult
from romget.providers.minerva import CatalogParser, MinervaProvider
from romget.services.jobs import JobStore
from romget.services.relevance import dedupe, is_unrequested_asset, relevant
from romget.services.search import SearchService, _matches_other_platform


def game(identifier, title, filename=None, md5="", size=1000):
    name = filename or title + ".iso"
    return IAGame(identifier, title, title, [{"name": name, "size": size, "md5": md5}], name, size)


class QualityTests(unittest.TestCase):
    def test_sequels_and_whole_tokens(self):
        for query, title in [
            ("Final Fantasy X", "Final Fantasy X-2"),
            ("Final Fantasy X", "Final Fantasy X2"),
            ("God of War II", "God of War III"),
            ("Gran Turismo 4", "Gran Turismo 3 (Rev 4)"),
            ("tekken", "Tekkenette"),
        ]:
            with self.subTest(title=title):
                self.assertFalse(relevant(query, title))
        self.assertTrue(relevant("final fantasy 10", "Final Fantasy X (Europe)"))
        self.assertTrue(relevant("gran turismo 4", "Gran Turismo 4 Spec II (Europe)"))
        self.assertTrue(relevant("final fantasy", "Final Fantasy X-2"))
        self.assertTrue(relevant("okami", "Ōkami (USA)"))

    def test_assets_excluded_unless_explicitly_requested(self):
        self.assertTrue(is_unrequested_asset("tekken", "Action Replay for Tekken 4"))
        self.assertTrue(is_unrequested_asset("Gran Turismo 4", "GT4 texture pack"))
        self.assertFalse(is_unrequested_asset("texture pack", "GT4 texture pack"))
        self.assertFalse(is_unrequested_asset("undercover", "Need for Speed Undercover"))

    def test_platform_string_collection_and_arcade_title(self):
        self.assertTrue(_matches_other_platform("God of War 2 PC Gamehayvai", "id"))
        self.assertTrue(_matches_other_platform("Game", "id", "sony_playstation"))
        self.assertFalse(_matches_other_platform("Arcade Classics (PS2)", "id"))

    def test_hash_duplicates_keep_alternate_source(self):
        a = game("a", "Title A", md5="a" * 32)
        b = game("b", "Title B", md5="a" * 32)
        result = dedupe([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].alternatives[0]["identifier"], "b")
        self.assertEqual(a.alternatives, [])
        self.assertEqual(len(dedupe(result + [b])[0].alternatives), 1)

    def test_different_hashes_and_discs_preserved(self):
        a = game("a", "Game", md5="a" * 32)
        b = game("b", "Game", md5="b" * 32)
        self.assertEqual(len(dedupe([a, b])), 2)
        a = game("a", "Game", "Game (Disc 1).iso")
        b = game("b", "Game", "Game (Disc 2).iso")
        self.assertEqual(len(dedupe([a, b])), 2)
        b.files.append({"name": "bonus.iso", "size": 1})
        self.assertEqual(len(dedupe([a, b])), 2)

    def test_revision_directories_are_not_discarded(self):
        a = game("a", "Game", "Rev1/game.iso")
        b = game("b", "Game", "Rev2/game.iso")
        self.assertEqual(len(dedupe([a, b])), 2)

    def test_exact_names_sizes_and_region_required_without_hash(self):
        a = game("a", "Game (Europe)")
        b = game("b", "Game (Europe)")
        self.assertEqual(len(dedupe([a, b])), 1)
        self.assertEqual(len(dedupe([a, game("c", "Game (USA)")])), 2)
        self.assertEqual(len(dedupe([a, game("d", "Game (Europe)", size=1040)])), 2)

    def test_pack_does_not_match_tags_or_other_edition_filters(self):
        service = SearchService(Config(providers={"ia_redump": ProviderConfig("ia_redump")}))
        pack = game("pack", "PS2 Europe French Collection")
        pack.files = [
            {"name": "Gran Turismo 4 (USA) (En).iso", "size": 20},
            {"name": "Gran Turismo 4 (Europe) (En,Fr).iso", "size": 30},
            {"name": "Gran Turismo 3 (Europe) (En,Fr).iso", "size": 40},
            {"name": "Gran Turismo 4 textures.zip", "size": 10},
        ]
        data = {"response": {"numFound": 1, "docs": [{"identifier": "pack", "title": "PS2 pack"}]}}
        index = Mock(status="fresh", titles=[])
        with (
            patch.object(service, "_cached", return_value=data),
            patch.object(service, "item", return_value=pack),
            patch("romget.services.search.get_datfile", return_value=index),
        ):
            result = service.search("gran turismo 4", region="Europe", language="Fr")
            empty = service.search("god of war")
        self.assertEqual([f["size"] for f in result.games[0].files], [30])
        self.assertEqual(result.games[0].total_size, 30)
        self.assertEqual(len(pack.files), 4)
        self.assertEqual(empty.games, [])

    def test_provider_failure_does_not_hide_other_results(self):
        service = SearchService(Config())
        with (
            patch.object(service, "_search_ia", side_effect=OSError("offline")),
            patch.object(
                MinervaProvider,
                "search",
                return_value=SearchResult(
                    games=[game("b", "Game")], total_items=1, source_totals={"minerva": 1}
                ),
            ),
        ):
            result = service.search("Game")
        self.assertEqual(len(result.games), 1)
        self.assertIn("ia_redump", result.warnings[0])
        self.assertEqual(result.source_totals, {"minerva": 1})

    def test_both_failed_is_not_empty_success(self):
        with (
            patch.object(SearchService, "_search_ia", side_effect=OSError),
            patch.object(MinervaProvider, "search", side_effect=ValueError),
        ):
            with self.assertRaises(RuntimeError):
                SearchService(Config()).search("Game")

    def test_source_selection_and_disabled(self):
        config = Config()
        config.providers["minerva"].enabled = False
        with (
            patch.object(SearchService, "_search_ia", return_value=SearchResult()) as ia,
            patch.object(MinervaProvider, "search") as minerva,
        ):
            SearchService(config).search("Game")
            ia.assert_called_once()
            minerva.assert_not_called()
            with self.assertRaises(ValueError):
                SearchService(config).search("Game", source="minerva")


class MinervaTests(unittest.TestCase):
    def test_parser_uses_only_numeric_item_links_and_rom_names(self):
        parser = CatalogParser()
        parser.feed(
            '<a href="/rom?id=12">Game &amp; More (Europe).zip</a>'
            '<a href="javascript:void(0)">Magnet</a>'
            '<a href="https://evil.test/rom?id=13">Bad.iso</a>'
            '<a href="/rom?id=14">notes.txt</a>'
            '<a href="/rom?id=15">../../bad.iso</a>'
        )
        self.assertEqual(parser.entries, {"12": "Game & More (Europe).zip"})

    def test_catalog_cached_and_paginated(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(
                providers={"ia_redump": ProviderConfig("ia_redump", options={"cache_dir": tmp})}
            )
            provider = MinervaProvider(config)
            with patch(
                "romget.providers.minerva.fetch_catalog",
                return_value={"1": "Game (Europe) (En,Fr).zip", "2": "Game (USA).zip"},
            ) as fetch:
                first = provider.search("Game", limit=1)
                second = provider.search("Game", page=2, limit=1)
                filtered = provider.search("Game", region="Europe", language="Fr")
            fetch.assert_called_once()
            self.assertTrue(first.has_more)
            self.assertFalse(second.has_more)
            self.assertNotEqual(first.games[0].identifier, second.games[0].identifier)
            self.assertEqual(filtered.total_items, 1)
            self.assertTrue(filtered.games[0].external)
            self.assertEqual(filtered.games[0].files, [])
            with self.assertRaises(ValueError):
                JobStore(Path(tmp) / "state").add(filtered.games[0], [], Path(tmp))

    def test_verified_only_skips_unknown_hashes_without_fetch(self):
        with patch.object(MinervaProvider, "catalog") as fetch:
            result = MinervaProvider(Config()).search("Game", verified_only=True)
        fetch.assert_not_called()
        self.assertEqual(result.games, [])
