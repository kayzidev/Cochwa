"""Tests d'intégration réseau réels — marqués slow, hors CI par défaut.

Lancement manuel :
    ROMGET_NETWORK_TESTS=1 .venv/bin/python -m unittest tests.test_integration_network -v

Nécessite un accès Internet. Aucune clé API requise pour la recherche IA ;
le test SteamGridDB est sauté si aucune clé n'est configurée localement.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from romget.api.steamgriddb import _ia_cover_url, search_grids
from romget.config import DEFAULT_CACHE_DIR, Config, ProviderConfig
from romget.services.search import SearchService

NETWORK = os.environ.get("ROMGET_NETWORK_TESTS") == "1"


@unittest.skipUnless(NETWORK, "tests réseau désactivés (ROMGET_NETWORK_TESTS=1 pour activer)")
class NetworkIntegrationTests(unittest.TestCase):
    """Sondes réelles Internet Archive / SteamGridDB — lentes par nature."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="romget-net-")
        cache = Path(self.tmp.name)
        # Réutilise le datfile Redump local si présent (évite un téléchargement).
        old = DEFAULT_CACHE_DIR / "ps2_datfile.json"
        if old.exists():
            shutil.copyfile(old, cache / "ps2_datfile.json")
        self.config = Config(
            providers={"ia_redump": ProviderConfig("ia_redump", options={"cache_dir": str(cache)})}
        )
        self.service = SearchService(self.config)

    def tearDown(self):
        self.tmp.cleanup()

    def test_real_ia_search_returns_ps2_results(self):
        result = self.service.search("gran turismo 4", limit=5)
        self.assertGreater(result.total_items, 0)
        self.assertTrue(result.games, "aucun jeu exploitable retourné")
        for game in result.games:
            self.assertTrue(game.files, f"{game.identifier} sans fichier ROM")
        # Le filtre plateforme ne doit laisser passer aucune autre console.
        for game in result.games:
            haystack = (game.ia_title + " " + game.identifier).casefold()
            self.assertNotIn("ps vita", haystack)
            self.assertNotIn("psp", haystack)

    def test_real_ia_item_metadata(self):
        result = self.service.search("gran turismo 4", limit=3)
        self.assertTrue(result.games)
        game = result.games[0]
        self.assertTrue(game.identifier)
        self.assertGreater(game.total_size, 0)
        self.assertIn(game.identification, ("hash", "title", "unknown"))

    def test_real_ia_cover_probe_is_safe(self):
        # Sans clé SGDB : la sonde jaquette IA ne doit jamais lever d'erreur,
        # qu'un fichier jaquette existe ou non dans l'item.
        result = self.service.search("gran turismo 4", limit=3)
        self.assertTrue(result.games)
        url = _ia_cover_url(result.games[0].identifier, self.config.cache_dir)
        if url is not None:
            self.assertTrue(url.startswith("https://archive.org/download/"))

    def test_real_sgdb_search_if_key_configured(self):
        config = Config.load()
        if not config.steamgrid_api_key:
            self.skipTest("aucune clé SteamGridDB configurée")
        grids = search_grids(config.steamgrid_api_key, "Gran Turismo 4")
        self.assertTrue(grids, "SGDB ne retourne aucune jaquette pour Gran Turismo 4")
        self.assertTrue(grids[0].get("url", "").startswith("https://"))


if __name__ == "__main__":
    unittest.main()
