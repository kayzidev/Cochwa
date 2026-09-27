from unittest.mock import patch

import pytest

from cochwa.config import Config
from cochwa.models import SearchResult
from cochwa.providers.ia_redump import IARedumpProvider
from cochwa.providers.ia_switch import SwitchArchiveProvider
from cochwa.services.search import SearchService


def test_switch_item_selects_only_matching_accessible_formats():
    data = {
        "metadata": {"title": "A Switch pack"},
        "files": [
            {"name": "Mario (USA).nsp", "size": "100", "md5": "a" * 32},
            {"name": "Mario (Europe).iso", "size": "100"},
            {"name": "Mario.exe", "size": "100"},
            {"name": "../../Mario.xci", "size": "100"},
            {"name": "Mario.xci", "size": "100", "private": True},
            {"name": "Zelda.nsp", "size": "100"},
        ],
    }
    provider = SwitchArchiveProvider(lambda *a, **k: data)
    game = provider.item("fixture", "mario")
    assert game.platform == "switch" and not game.external
    assert [f["name"] for f in game.files] == ["Mario (USA).nsp"]
    assert "Redump" not in game.label
    assert provider.item("fixture", "mario", region="Europe") is None


def test_explicit_switch_archive_is_external_not_download_job():
    provider = SwitchArchiveProvider(
        lambda *a, **k: {
            "metadata": {"title": "Mario Switch"},
            "files": [{"name": "Mario.xci.rar", "size": "100"}],
        }
    )
    game = provider.item("fixture", "mario")
    assert game.external
    assert game.files == []
    assert game.source_reference()["url"] == "https://archive.org/details/fixture"


def test_switch_search_does_not_call_ps2_sources():
    service = SearchService(Config())
    with (
        patch.object(SwitchArchiveProvider, "search", return_value=SearchResult()) as switch,
        patch.object(IARedumpProvider, "search") as ps2,
    ):
        service.search("mario", platform="switch")
        switch.assert_called_once()
        ps2.assert_not_called()
    with pytest.raises(ValueError, match="incompatible"):
        service.search("mario", platform="switch", source="minerva")


def test_switch_catalog_is_separate_and_does_not_fabricate_scores():
    from cochwa.catalog import recommended_entries, top_entries

    top = top_entries("switch")
    assert top and all("score" not in e for e in top)
    assert [e["top_rank"] for e in top] == list(range(1, len(top) + 1))
    assert recommended_entries(platform="switch") != recommended_entries(platform="ps2")


def test_switch_updates_are_not_offered_as_base_games():
    files = [
        {"name": "Mario [0100000000010000][v0].nsp", "size": "100"},
        {"name": "Mario [0100000000010800][v123].nsp", "size": "80"},
        {"name": "Mario [DLC].nsp", "size": "50"},
        {"name": "0100152000022800.nsp", "size": "100"},
    ]
    provider = SwitchArchiveProvider(
        lambda *a, **k: {"metadata": {"title": "Mario Switch"}, "files": files}
    )
    game = provider.item("fixture", "mario")
    assert len(game.files) == 1
    assert game.files[0]["content_type"] == "game"
