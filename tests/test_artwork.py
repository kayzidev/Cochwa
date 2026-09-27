import tempfile
import unittest
from unittest.mock import patch

from cochwa.api.steamgriddb import _ia_cover_url, download_cover, search_grids


class ArtworkTests(unittest.TestCase):
    def test_autocomplete_term_is_in_path(self):
        with patch(
            "cochwa.api.steamgriddb.get_json",
            side_effect=[
                {"data": [{"id": 42, "name": "Game #1"}]},
                {"data": [{"url": "https://cdn.example/image.png"}]},
            ],
        ) as request:
            result = search_grids("fixture-key", "Game #1")
        self.assertEqual(len(result), 1)
        self.assertTrue(
            request.call_args_list[0].args[0].endswith("/search/autocomplete/Game%20%231")
        )
        self.assertEqual(
            request.call_args_list[0].kwargs["headers"], {"Authorization": "Bearer fixture-key"}
        )

    def test_ambiguous_game_does_not_choose_sequel(self):
        with patch(
            "cochwa.api.steamgriddb.get_json",
            return_value={"data": [{"id": 1, "name": "Game 2"}, {"id": 2, "name": "Game 3"}]},
        ) as request:
            self.assertEqual(search_grids("fixture", "Game"), [])
        self.assertEqual(request.call_count, 1)

    def test_ia_cover_url_picks_cover_like_file(self):
        metadata = {
            "files": [
                {"name": "game.iso"},
                {"name": "screenshot_gameplay.png"},
                {"name": "Game Front Cover.jpg"},
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            with patch("cochwa.api.steamgriddb.get_json", return_value=metadata):
                url = _ia_cover_url("some-item", tmp)
        self.assertIsNotNone(url)
        self.assertIn("some-item", url)
        self.assertTrue(url.endswith("Game%20Front%20Cover.jpg"))

    def test_ia_cover_url_none_without_cover_like_file(self):
        metadata = {"files": [{"name": "game.iso"}, {"name": "ingame_01.png"}]}
        with tempfile.TemporaryDirectory() as tmp:
            with patch("cochwa.api.steamgriddb.get_json", return_value=metadata):
                self.assertIsNone(_ia_cover_url("some-item", tmp))

    def test_no_ia_request_when_no_cover_candidate(self):
        # Sans fichier jaquette dans les métadonnées, aucune requête image
        # ne doit être tentée (services/img ne sert que le logo générique).
        metadata = {"files": [{"name": "game.iso"}]}
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("cochwa.api.steamgriddb.get_json", return_value=metadata),
                patch("cochwa.api.steamgriddb._fetch_image") as fetch,
            ):
                result = download_cover("", "Some Game", cache_dir=tmp, ia_identifier="item")
            self.assertIsNone(result)
            fetch.assert_not_called()
