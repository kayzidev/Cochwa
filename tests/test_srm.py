import json
import struct
from pathlib import Path
from unittest.mock import patch

import pytest

from cochwa.config import Config
from cochwa.services import srm
from cochwa.services.steam_shortcuts import read_shortcuts


def _write_shortcuts(path, games):
    def field(name, value):
        return b"\x01" + name.encode() + b"\0" + str(value).encode() + b"\0"

    payload = b"\x00shortcuts\0"
    for index, game in enumerate(games):
        payload += b"\x00" + str(index).encode() + b"\0"
        payload += b"\x02appid\0" + struct.pack("<I", 0xA0000000 + index)
        payload += field("appname", game["title"])
        payload += field("exe", f'"{game["target"]}"')
        payload += field("LaunchOptions", game["launchOptions"])
        payload += b"\x08"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload + b"\x08\x08")


@pytest.fixture
def setup(tmp_path):
    ps2 = tmp_path / "ps2"
    switch = tmp_path / "switch"
    steam = tmp_path / "Steam"
    for p in (ps2, switch, steam / "userdata"):
        p.mkdir(parents=True)
    for name in ("Grand Tour (Europe).iso", "Grand Tour (Europe).chd", "Grand Tour (Spec II).iso"):
        (ps2 / name).write_bytes(b"rom")
    (switch / "Game [010018E011D92000][v0][US](nsw2u.com).nsp").write_bytes(b"rom")
    (switch / "Game [UPD].nsp").write_bytes(b"update")
    (steam / "config").mkdir()
    (steam / "config" / "loginusers.vdf").write_text(
        '"users"\n{\n\t"76561198042463546"\n\t{\n\t\t"AccountName"\t\t"player1"\n\t}\n}\n'
    )
    launcher = tmp_path / "launch.sh"
    launcher.write_text("#!/bin/sh\nexit 0\n")
    launcher.chmod(0o755)
    config = Config(
        ps2_dir=ps2,
        switch_dir=switch,
        launcher=launcher,
        switch_launcher=launcher,
        state_dir=tmp_path / "state",
    )
    directory = tmp_path / "srm" / "userData"
    directory.mkdir(parents=True)
    return config, directory, steam


def test_plan_preserves_editions_prefers_chd_and_skips_switch_updates(setup):
    config, directory, steam = setup
    plan = srm.prepare(config, directory, steam, ["ps2", "switch"])
    assert not (directory / "userConfigurations.json").exists()
    ps2, switch = list(plan.manifests.values())
    assert len(ps2) == 2
    assert any('Grand Tour (Europe).chd"' in p["launchOptions"] for p in ps2)
    assert any(p["title"] == "Grand Tour" for p in ps2)
    assert any("Spec II" in p["title"] for p in ps2)
    assert len(switch) == 1
    assert switch[0]["title"] == "Game"
    assert "[010018E011D92000]" in switch[0]["launchOptions"]
    assert all(p["target"] == str(config.launcher) for p in ps2 + switch)
    assert plan.configurations[1]["steamCategories"] == ["Cochwa", "Switch"]
    assert plan.configurations[1]["imageProviders"] == ["sgdb"]
    assert plan.configurations[1]["imageProviderAPIs"]["sgdb"]["imageMotionTypes"] == ["static"]


def test_install_is_idempotent_and_preserves_personal_parser_with_backup(setup):
    config, directory, steam = setup
    target = directory / "userConfigurations.json"
    personal = {
        "parserId": "mine",
        "configTitle": "My parser",
        "disabled": False,
        "romDirectory": str(config.ps2_dir),
    }
    target.write_text(json.dumps([personal]))
    plan = srm.prepare(config, directory, steam, ["ps2"])
    assert plan.overlap_ids == ["mine"]
    with patch.object(srm, "ensure_srm_closed"):
        backup = srm.install(plan)
        again = srm.prepare(config, directory, steam, ["ps2"])
        srm.install(again)
    saved = json.loads(target.read_text())
    assert len(saved) == 2
    assert saved[0] == personal
    assert json.loads(backup.read_text()) == [personal]
    assert Path(saved[1]["parserInputs"]["manualManifests"]).joinpath("games.json").is_file()


def test_overlaps_disabled_only_on_explicit_choice(setup):
    config, directory, steam = setup
    target = directory / "userConfigurations.json"
    target.write_text(json.dumps([{"parserId": "mine", "romDirectory": str(config.ps2_dir)}]))
    plan = srm.prepare(config, directory, steam, ["ps2"])
    with patch.object(srm, "ensure_srm_closed"):
        srm.install(plan, disable_overlaps=True)
    assert json.loads(target.read_text())[0]["disabled"] is True


def test_concurrent_srm_change_is_not_overwritten(setup):
    config, directory, steam = setup
    plan = srm.prepare(config, directory, steam, ["ps2"])
    target = directory / "userConfigurations.json"
    target.write_text('[{"configTitle":"new"}]')
    with patch.object(srm, "ensure_srm_closed"), pytest.raises(RuntimeError, match="changé"):
        srm.install(plan)
    assert json.loads(target.read_text()) == [{"configTitle": "new"}]


def test_invalid_root_fails_instead_of_erasing_manifest(setup):
    config, directory, steam = setup
    config.switch_dir = directory / "absent"
    with pytest.raises(ValueError, match="Switch"):
        srm.prepare(config, directory, steam, ["switch"])
    assert not (directory / "userConfigurations.json").exists()


def test_sync_refuses_running_steam(setup):
    config, directory, steam = setup
    plan = srm.prepare(config, directory, steam, ["ps2"])
    with (
        patch.object(srm, "ensure_srm_closed"),
        patch.object(srm, "process_running", return_value=True),
        patch.object(srm, "_run_srm_add") as run,
        pytest.raises(RuntimeError, match="Fermez Steam"),
    ):
        srm.synchronize(config, plan)
    run.assert_not_called()


def test_sync_verifies_steam_shortcuts_and_artwork(setup):
    config, directory, steam = setup
    plan = srm.prepare(config, directory, steam, ["switch"])
    with patch.object(srm, "ensure_srm_closed"):
        srm.install(plan)
    shortcut_file = steam / "userdata" / "123" / "config" / "shortcuts.vdf"
    game = next(iter(plan.manifests.values()))[0]

    def add(*_args, **_kwargs):
        _write_shortcuts(shortcut_file, [game])
        (shortcut_file.parent / "grid" / f"{0xA0000000}p.png").parent.mkdir(exist_ok=True)
        (shortcut_file.parent / "grid" / f"{0xA0000000}p.png").write_bytes(b"image")

    with (
        patch.object(srm, "ensure_srm_closed"),
        patch.object(srm, "process_running", return_value=False),
        patch.object(srm, "detect_srm_directory", return_value=directory),
        patch.object(srm.shutil, "which", return_value="/usr/bin/steam-rom-manager"),
        patch.object(srm, "_run_srm_add", side_effect=add) as command,
    ):
        result = srm.synchronize(config, plan)
    assert result.expected == 1
    assert result.added == 1
    assert result.artwork == 1
    assert "1 jeu" in result.message
    assert read_shortcuts(shortcut_file)[0]["appname"] == "Game"
    command.assert_called_once()


def test_sync_rejects_silent_success_without_shortcuts(setup):
    config, directory, steam = setup
    plan = srm.prepare(config, directory, steam, ["switch"])
    with patch.object(srm, "ensure_srm_closed"):
        srm.install(plan)
    with (
        patch.object(srm, "ensure_srm_closed"),
        patch.object(srm, "process_running", return_value=False),
        patch.object(srm, "detect_srm_directory", return_value=directory),
        patch.object(srm.shutil, "which", return_value="/usr/bin/steam-rom-manager"),
        patch.object(srm, "_run_srm_add"),
        pytest.raises(RuntimeError, match="absents de Steam"),
    ):
        srm.synchronize(config, plan)


def test_sync_refuses_modified_parser_before_running_srm(setup):
    config, directory, steam = setup
    plan = srm.prepare(config, directory, steam, ["switch"])
    with patch.object(srm, "ensure_srm_closed"):
        srm.install(plan)
    target = directory / "userConfigurations.json"
    installed = json.loads(target.read_text())
    installed[0]["parserInputs"]["manualManifests"] = "/wrong/folder"
    target.write_text(json.dumps(installed))
    with (
        patch.object(srm, "ensure_srm_closed"),
        patch.object(srm, "process_running", return_value=False),
        patch.object(srm, "detect_srm_directory", return_value=directory),
        patch.object(srm, "_run_srm_add") as command,
        pytest.raises(RuntimeError, match="préréglages SRM ont changé"),
    ):
        srm.synchronize(config, plan)
    command.assert_not_called()


def test_sync_fills_empty_srm_cli_settings_with_backup(setup):
    """Régression : userAccounts vide => splash SRM => le CLI ne termine jamais."""
    config, directory, steam = setup
    plan = srm.prepare(config, directory, steam, ["switch"])
    with patch.object(srm, "ensure_srm_closed"):
        srm.install(plan)
    (directory / "userSettings.json").write_text(
        json.dumps(
            {
                "version": 11,
                "environmentVariables": {"steamDirectory": "", "userAccounts": []},
            }
        )
    )
    shortcut_file = steam / "userdata" / "123" / "config" / "shortcuts.vdf"
    game = next(iter(plan.manifests.values()))[0]

    def add(*_args, **_kwargs):
        _write_shortcuts(shortcut_file, [game])

    with (
        patch.object(srm, "ensure_srm_closed"),
        patch.object(srm, "process_running", return_value=False),
        patch.object(srm, "detect_srm_directory", return_value=directory),
        patch.object(srm.shutil, "which", return_value="/usr/bin/steam-rom-manager"),
        patch.object(srm, "_run_srm_add", side_effect=add),
    ):
        srm.synchronize(config, plan)
    env = json.loads((directory / "userSettings.json").read_text())["environmentVariables"]
    assert env["userAccounts"] == ["player1"]
    assert env["steamDirectory"] == str(steam)
    backups = list(directory.glob("userSettings.cochwa-backup-*.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text())["environmentVariables"]["userAccounts"] == []


def test_sync_preserves_existing_srm_accounts(setup):
    config, directory, steam = setup
    plan = srm.prepare(config, directory, steam, ["switch"])
    with patch.object(srm, "ensure_srm_closed"):
        srm.install(plan)
    original = {
        "version": 11,
        "environmentVariables": {
            "steamDirectory": "/custom/steam",
            "userAccounts": ["someone"],
        },
    }
    (directory / "userSettings.json").write_text(json.dumps(original))
    with (
        patch.object(srm, "ensure_srm_closed"),
        patch.object(srm, "process_running", return_value=False),
        patch.object(srm, "detect_srm_directory", return_value=directory),
        patch.object(srm.shutil, "which", return_value="/usr/bin/steam-rom-manager"),
        patch.object(srm, "_run_srm_add"),
        pytest.raises(RuntimeError, match="absents de Steam"),
    ):
        srm.synchronize(config, plan)
    assert json.loads((directory / "userSettings.json").read_text()) == original
    assert not list(directory.glob("userSettings.cochwa-backup-*.json"))


def test_sync_without_any_steam_account_fails_fast(setup):
    config, directory, steam = setup
    empty_steam = steam.parent / "steam-sans-compte"
    (empty_steam / "userdata").mkdir(parents=True)
    plan = srm.prepare(config, directory, empty_steam, ["switch"])
    with patch.object(srm, "ensure_srm_closed"):
        srm.install(plan)
    with (
        patch.object(srm, "ensure_srm_closed"),
        patch.object(srm, "process_running", return_value=False),
        patch.object(srm, "detect_srm_directory", return_value=directory),
        patch.object(srm, "_run_srm_add") as command,
        pytest.raises(RuntimeError, match="Aucun compte Steam"),
    ):
        srm.synchronize(config, plan)
    command.assert_not_called()


def test_run_srm_add_strips_electron_run_as_node(monkeypatch):
    monkeypatch.setenv("ELECTRON_RUN_AS_NODE", "1")
    captured = {}

    class FakeProcess:
        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    def popen(command, **kwargs):
        captured.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(srm.subprocess, "Popen", popen)
    srm._run_srm_add(["steam-rom-manager", "add"])
    assert "ELECTRON_RUN_AS_NODE" not in captured["env"]
    assert captured["env"]["PATH"]
