"""Tests du registre provider et résolution dynamique (lot L2).

Prouve que l'ajout d'une console = CONSOLES + SearchProfile + register provider(s),
sans modifier SearchService ni l'orchestration existante.
"""

import unittest
from unittest.mock import Mock, patch

from cochwa.config import Config
from cochwa.consoles import Console, SearchProfile
from cochwa.models import SearchResult
from cochwa.providers import CONSOLE_PROVIDERS, register_provider
from cochwa.services.search import SearchService


class StubConsoleProvider:
    """Provider fictif pour tester la résolution sans impacter le produit."""

    name = "stub_console"
    display_name = "Stub Console Provider"

    def __init__(self, config):
        self.config = config

    def search(
        self,
        query,
        *,
        page=1,
        limit=20,
        verified_only=False,
        region="",
        language="",
        cancel=None,
    ):
        """Retourne un résultat stub pour prouver la résolution."""
        return SearchResult(
            page=page,
            games=[],
            total_items=1,
            source_totals={"stub_console": 1},
        )

    def item(self, identifier, datfile=None):
        return None


class SearchRegistryTests(unittest.TestCase):
    """Tests de résolution provider via registre pour multi-console évolutif."""

    def test_ps2_providers_resolved_from_registry(self):
        """PS2 doit résoudre ia_redump + minerva via le registre."""
        from cochwa.providers import get_console_providers

        providers = get_console_providers("ps2")
        self.assertEqual(set(providers), {"ia_redump", "minerva"})

    def test_switch_providers_resolved_from_registry(self):
        """Switch doit résoudre ia_switch via le registre."""
        from cochwa.providers import get_console_providers

        providers = get_console_providers("switch")
        self.assertEqual(providers, ["ia_switch"])

    def test_stub_console_provider_registration(self):
        """Un provider fictif peut être enregistré sans modifier SearchService."""
        # Enregistrer le provider stub
        register_provider("stub_console", StubConsoleProvider)

        # Enregistrer temporairement la console stub
        original = CONSOLE_PROVIDERS.copy()
        CONSOLE_PROVIDERS["stub_console_test"] = ["stub_console"]

        try:
            from cochwa.providers import get_console_providers

            providers = get_console_providers("stub_console_test")
            self.assertEqual(providers, ["stub_console"])
        finally:
            # Cleanup : retirer la console stub du registre
            CONSOLE_PROVIDERS.clear()
            CONSOLE_PROVIDERS.update(original)

    def test_search_service_resolves_providers_dynamically(self):
        """SearchService doit résoudre les providers via le registre, pas en dur."""
        config = Mock(spec=Config)
        config.providers = {
            "stub_console": Mock(enabled=True),
        }

        # Enregistrer le provider et la console stub
        register_provider("stub_console", StubConsoleProvider)
        original_providers = CONSOLE_PROVIDERS.copy()
        CONSOLE_PROVIDERS["stub_test"] = ["stub_console"]

        # Créer un SearchProfile stub
        stub_profile = SearchProfile(
            other_platform_terms=("other",),
            console_collection=r"stub",
            other_collection=r"not_stub",
        )

        # Mock la console stub dans consoles.get()
        stub_console = Console(
            id="stub_test",
            name="Stub Console",
            search_profile=stub_profile,
        )

        try:
            with patch("cochwa.services.search.consoles.get", return_value=stub_console):
                service = SearchService(config)
                result = service.search("test query", platform="stub_test")

                # Vérifier que le provider stub a été appelé
                self.assertEqual(result.source_totals.get("stub_console"), 1)
                self.assertEqual(result.total_items, 1)
        finally:
            # Cleanup
            CONSOLE_PROVIDERS.clear()
            CONSOLE_PROVIDERS.update(original_providers)

    def test_ps2_and_switch_behavior_unchanged(self):
        """PS2 et Switch doivent continuer de fonctionner après refactoring."""
        config = Mock(spec=Config)
        config.providers = {
            "ia_redump": Mock(enabled=True),
            "minerva": Mock(enabled=True),
            "ia_switch": Mock(enabled=True),
        }

        service = SearchService(config)

        # Mock les méthodes de recherche pour éviter les appels réseau
        with (
            patch.object(service._ia, "search") as mock_ia_search,
            patch("cochwa.services.search.MinervaProvider") as mock_minerva_cls,
            patch("cochwa.services.search.SwitchArchiveProvider") as mock_switch_cls,
        ):
            mock_ia_search.return_value = SearchResult(page=1)
            mock_minerva_instance = Mock()
            mock_minerva_instance.search.return_value = SearchResult(page=1)
            mock_minerva_cls.return_value = mock_minerva_instance

            mock_switch_instance = Mock()
            mock_switch_instance.search.return_value = SearchResult(page=1)
            mock_switch_cls.return_value = mock_switch_instance

            # Test PS2
            result_ps2 = service.search("test", platform="ps2")
            self.assertEqual(result_ps2.page, 1)
            mock_ia_search.assert_called()

            # Test Switch
            result_switch = service.search("test", platform="switch")
            self.assertEqual(result_switch.page, 1)
            mock_switch_instance.search.assert_called()

    def test_unknown_platform_raises_error(self):
        """Une plateforme inconnue doit lever une erreur claire."""
        config = Mock(spec=Config)
        service = SearchService(config)

        with self.assertRaises(ValueError) as ctx:
            service.search("test", platform="unknown")

        self.assertIn("Plateforme inconnue", str(ctx.exception))

    def test_platform_without_providers_raises_error(self):
        """Une plateforme sans providers enregistrés doit lever une erreur."""
        config = Mock(spec=Config)

        # Mock une console sans providers
        empty_console = Console(
            id="empty_test",
            name="Empty Console",
            search_profile=SearchProfile(
                other_platform_terms=(),
                console_collection=r"empty",
                other_collection=r"other",
            ),
        )

        with patch("cochwa.services.search.consoles.get", return_value=empty_console):
            service = SearchService(config)

            with self.assertRaises(ValueError) as ctx:
                service.search("test", platform="empty_test")

            self.assertIn("Aucun provider enregistré", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
