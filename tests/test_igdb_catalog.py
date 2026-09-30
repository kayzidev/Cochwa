"""Contrat du catalogue IGDB : couverture, classement et copie de secours."""

import json
import time
from unittest.mock import patch

import pytest

from cochwa.catalog import (
    clear_catalog_cache,
    has_igdb_catalog,
    recommended_entries,
    top_entries,
)
from cochwa.config import Config, ProviderConfig
from cochwa.services.igdb import CATALOG_TTL, IGDBClient
from cochwa.services.maintenance import purge_expired_caches


def test_switch_catalog_sync_populates_all_scored_games_and_keeps_stale_copy(tmp_path):
    cache = tmp_path / "cache"
    config = Config(
        igdb_client_id="test-id",
        igdb_client_secret="test-secret",
        providers={"ia_redump": ProviderConfig("ia_redump", options={"cache_dir": str(cache)})},
    )
    client = IGDBClient(config)
    queries = []

    def fake_query(body, endpoint="games"):
        queries.append((endpoint, body))
        if endpoint == "game_types":
            return [
                {"id": 11, "type": "main_game"},
                {"id": 12, "type": "dlc_addon"},
                {"id": 13, "type": "remake"},
                {"id": 14, "type": "remaster"},
            ]
        return [
            {
                "id": index,
                "name": f"Switch Game {index:02d}",
                "aggregated_rating": 90 - index / 10,
                "aggregated_rating_count": 5 + index,
                "genres": [{"name": "Adventure"}],
            }
            for index in range(1, 76)
        ]

    with (
        patch.object(client, "_platform_id", return_value=130),
        patch.object(client, "_query", side_effect=fake_query),
    ):
        client.sync_catalog("switch", "Nintendo Switch")
    assert "game_type = (11,13,14)" in queries[1][1]
    assert "game_type = 0" not in queries[1][1]
    assert len(top_entries("switch", cache)) == 75
    assert all(entry["source"] == "IGDB" for entry in top_entries("switch", cache))
    recommendation = recommended_entries(platform="switch", cache_dir=cache)
    assert 20 <= len(recommendation) <= 30
    assert len({entry["title"] for entry in recommendation}) == len(recommendation)

    path = cache / "catalogs" / "igdb-switch.json"
    saved = json.loads(path.read_text())
    saved["time"] = time.time() - CATALOG_TTL - 10
    path.write_text(json.dumps(saved))
    clear_catalog_cache()
    purge_expired_caches(cache)
    assert path.exists() and has_igdb_catalog("switch", cache)
    assert len(top_entries("switch", cache)) == 75

    with patch.object(client, "fetch_platform_catalog", return_value=[{"title": "Partial"}]):
        with pytest.raises(ValueError, match="incomplet"):
            client.sync_catalog("switch")
    assert len(json.loads(path.read_text())["games"]) == 75


def test_packaged_recommendations_meet_range_without_credentials():
    for platform in ("ps2", "switch"):
        entries = recommended_entries(platform=platform)
        assert 20 <= len(entries) <= 30
        assert len({entry["title"].casefold() for entry in entries}) == len(entries)


def test_enrichment_rejects_same_title_on_wrong_platform(tmp_path):
    config = Config(
        igdb_client_id="test-id",
        igdb_client_secret="test-secret",
        providers={"ia_redump": ProviderConfig("ia_redump", options={"cache_dir": str(tmp_path)})},
    )
    client = IGDBClient(config)
    same_name_wrong_console = {
        "id": 100,
        "name": "Shared Game",
        "platforms": [{"name": "PlayStation 2"}],
        "cover": {"image_id": "bad-cover"},
    }
    with patch.object(client, "_query", return_value=[same_name_wrong_console]):
        assert client.enrich("Shared Game", "switch") is None
