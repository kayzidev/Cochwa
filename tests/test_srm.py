import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cochwa.config import Config
from cochwa.services import srm


@pytest.fixture
def setup(tmp_path):
    ps2 = tmp_path / "ps2"
    switch = tmp_path / "switch"
    steam = tmp_path / "Steam"
    for p in (ps2, switch, steam / "userdata"):
        p.mkdir(parents=True)
    for name in ("Grand Tour (Europe).iso", "Grand Tour (Europe).chd", "Grand Tour (Spec II).iso"):
        (ps2 / name).write_bytes(b"rom")
    (switch / "Game [BASE].nsp").write_bytes(b"rom")
    (switch / "Game [UPD].nsp").write_bytes(b"update")
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
    assert any("Spec II" in p["title"] for p in ps2)
    assert len(switch) == 1
    assert all(p["target"] == str(config.launcher) for p in ps2 + switch)
    assert plan.configurations[1]["steamCategories"] == ["Cochwa", "Switch"]


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
    config, _, _ = setup
    with (
        patch.object(srm, "ensure_srm_closed"),
        patch.object(srm, "process_running", return_value=True),
        patch.object(srm.subprocess, "run") as run,
        pytest.raises(RuntimeError, match="Fermez Steam"),
    ):
        srm.synchronize(config)
    run.assert_not_called()
