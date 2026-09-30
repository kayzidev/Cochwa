from unittest.mock import patch

import pytest

from cochwa.config import Config
from cochwa.services.collections import CollectionStore
from cochwa.services.emulator_filters import PLATFORMS, filter_emulators
from cochwa.services.emulators import EmulatorRegistry, catalog


def test_emulator_facets_combine_on_the_same_platform_and_sort_by_brand():
    items = catalog()
    assert {platform for item in items for platform in item["platforms"]} <= PLATFORMS.keys()
    assert [
        item["id"] for item in filter_emulators(items, manufacturer="Sony", processor="128 bits")
    ] == ["pcsx2"]
    assert [
        item["id"] for item in filter_emulators(items, manufacturer="Microsoft", processor="x86")
    ] == ["xemu"]
    assert "ares" in {
        item["id"]
        for item in filter_emulators(
            items, manufacturer="Nintendo", decade=1990, processor="64 bits"
        )
    }
    assert "ares" not in {
        item["id"]
        for item in filter_emulators(items, manufacturer="Sega", decade=1990, processor="64 bits")
    }
    assert [item["id"] for item in filter_emulators(items, platform="GameCube")] == ["dolphin"]
    assert [item["id"] for item in filter_emulators(items)[:3]] == ["mame", "xemu", "xenia"]


def test_emulator_manual_path_roundtrip_and_shell_free_launch(tmp_path):
    path = tmp_path / "PCSX2 $(echo nope) with spaces"
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o700)
    config = Config(state_dir=tmp_path / "state", launcher=tmp_path / "missing")
    registry = EmulatorRegistry(config)
    with patch("cochwa.services.emulators.shutil.which", return_value=None):
        with patch("cochwa.services.emulators.subprocess.Popen") as process:
            registry.set_path("pcsx2", path)
            detected = next(e for e in EmulatorRegistry(config).detect() if e["id"] == "pcsx2")
            assert detected["command"] == [str(path)]
            process.assert_not_called()
            registry.open("pcsx2")
            assert process.call_args.args[0] == [str(path)]
            assert not process.call_args.kwargs.get("shell")
        path.unlink()
        assert not next(e for e in registry.detect() if e["id"] == "pcsx2")["ready"]
        with pytest.raises(FileNotFoundError):
            registry.open("pcsx2")


def test_invalid_executable_and_corrupt_registry_preserved(tmp_path):
    registry = EmulatorRegistry(Config(state_dir=tmp_path))
    path = tmp_path / "not-executable"
    path.write_text("data")
    with pytest.raises(ValueError):
        registry.set_path("pcsx2", path)
    path.chmod(0o700)
    registry.path.write_text("{broken")
    with pytest.raises(ValueError):
        registry.set_path("pcsx2", path)
    assert registry.path.read_text() == "{broken"


def test_configured_launcher_never_opened_without_a_game(tmp_path):
    launcher = tmp_path / "game.sh"
    launcher.write_text('#!/bin/sh\nexec pcsx2 "$1"')
    registry = EmulatorRegistry(Config(state_dir=tmp_path, launcher=launcher))
    with patch("cochwa.services.emulators.shutil.which", return_value=None):
        row = next(e for e in registry.detect() if e["id"] == "pcsx2")
        assert row["configured"] and not row["command"]
        with pytest.raises(FileNotFoundError):
            registry.open("pcsx2")


def test_flatpak_detection_uses_installed_deployment(tmp_path):
    registry = EmulatorRegistry(Config(state_dir=tmp_path, launcher=tmp_path / "absent"))
    deployment = tmp_path / ".local/share/flatpak/app/org.DolphinEmu.dolphin-emu/current/active"
    deployment.mkdir(parents=True)
    with (
        patch("cochwa.services.emulators.Path.home", return_value=tmp_path),
        patch(
            "cochwa.services.emulators.shutil.which",
            side_effect=lambda n: "/usr/bin/flatpak" if n == "flatpak" else None,
        ),
    ):
        row = next(e for e in registry.detect() if e["id"] == "dolphin")
        assert row["command"] == ["/usr/bin/flatpak", "run", "org.DolphinEmu.dolphin-emu"]


def test_collections_persist_independently_and_delete_only_references(tmp_path):
    rom = tmp_path / "Game.iso"
    rom.write_bytes(b"untouched")
    store = CollectionStore(tmp_path)
    ps2 = store.save("Favoris", "ps2", ["Game", "Game"])
    switch = store.save("Favoris", "switch", ["Mario"])
    with pytest.raises(ValueError):
        store.save(" favoris ", "ps2", [])
    store.save("À terminer", "ps2", ["Game"], ps2["id"])
    store.remove(switch["id"])
    assert CollectionStore(tmp_path).read() == [dict(ps2, name="À terminer")]
    assert rom.read_bytes() == b"untouched"


def test_corrupt_collections_not_overwritten(tmp_path):
    store = CollectionStore(tmp_path)
    store.path.write_text("[{}]")
    with pytest.raises(ValueError):
        store.save("New", "ps2", [])
    assert store.path.read_text() == "[{}]"
