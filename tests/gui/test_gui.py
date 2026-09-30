"""Tests GUI Qt (offscreen), sans réseau, émulateur ni écritures dans la bibliothèque utilisateur."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QPoint, QRect, Qt, QThread  # noqa: E402
from PySide6.QtWidgets import QDialog, QPushButton  # noqa: E402

from cochwa.config import Config, ProviderConfig  # noqa: E402
from cochwa.gui_qt.app import MainWindow  # noqa: E402
from cochwa.models import IAGame, SearchResult  # noqa: E402


@pytest.fixture
def window(qtbot, tmp_path):
    (tmp_path / "Game.iso").write_bytes(b"image")
    config = Config(
        ps2_dir=tmp_path,
        state_dir=Path(tmp_path) / "state",
        source=Path(tmp_path) / "config.toml",
        providers={
            "ia_redump": ProviderConfig("ia_redump", options={"cache_dir": str(tmp_path / "cache")})
        },
    )
    win = MainWindow(config, start_workers=False)
    qtbot.addWidget(win)
    win.show()
    return win


def test_console_selector_and_brand(window):
    from cochwa.consoles import CONSOLES, DEFAULT_CONSOLE

    assert window.logo.text() == "Cochwa"
    assert not window.windowIcon().isNull()
    assert window.pages.currentWidget() is window.tab_library
    assert window.console is DEFAULT_CONSOLE
    assert window.console_box.count() == len(CONSOLES)
    states = [
        (window.console_box.itemText(i), window.console_box.model().item(i).isEnabled())
        for i in range(window.console_box.count())
    ]
    assert states == [("PlayStation 2", True), ("Switch", True)]
    # Bascule vers la Switch : titre de fenêtre et console active suivent.
    window.select_console(1)
    assert window.console.id == "switch"
    assert "Switch" in window.windowTitle()
    window.select_console(0)
    assert window.console is DEFAULT_CONSOLE
    assert "PlayStation 2" in window.windowTitle()


def test_dialogs_are_frameless(window, qtbot):
    """Toutes les fenêtres contextuelles de l'app sont sans bordure système."""
    from cochwa.gui_qt.dialogs import RemoteDetailsDialog
    from cochwa.gui_qt.srm_dialog import SRMDialog
    from cochwa.gui_qt.window_chrome import FramelessDialog

    game = IAGame("fixture", "Title", "Title", [], None, 0)
    for dialog in (SRMDialog(window), RemoteDetailsDialog(window, game, window)):
        qtbot.addWidget(dialog)
        assert isinstance(dialog, FramelessDialog)
        assert dialog.windowFlags() & Qt.FramelessWindowHint
        assert dialog.windowFlags() & Qt.Dialog
        assert dialog.objectName() == "framelessDialog"


def test_confirm_dialog_defaults_to_cancel(window, qtbot, monkeypatch):
    from cochwa.gui_qt import window_chrome

    created = {}

    def fake_exec(self):
        created["dialog"] = self
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(window_chrome.FramelessDialog, "exec", fake_exec)
    accepted = window_chrome.confirm(
        window,
        "Supprimer la collection",
        "Supprimer « Test » ?",
        accept_text="Supprimer",
        danger=True,
    )
    assert not accepted
    dialog = created["dialog"]
    assert dialog.windowFlags() & Qt.FramelessWindowHint
    buttons = dialog.findChildren(QPushButton)
    assert [button.text() for button in buttons] == ["Annuler", "Supprimer"]
    assert buttons[0].isDefault()
    assert buttons[1].objectName() == "danger"

    monkeypatch.setattr(
        window_chrome.FramelessDialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )
    assert window_chrome.confirm(
        window, "Conversion en masse", "Convertir ?", accept_text="Convertir"
    )


def test_frameless_titlebar_controls_and_resize_edges(window, qtbot):
    assert window.windowFlags() & Qt.FramelessWindowHint
    titlebar = window.title_bar
    assert titlebar.caption.text() == window.windowTitle()
    assert titlebar.maximize_button.accessibleName() == "Agrandir la fenêtre"
    assert titlebar.close_button.accessibleName() == "Fermer la fenêtre"
    assert all(
        button.focusPolicy() == Qt.StrongFocus
        for button in (titlebar.minimize_button, titlebar.maximize_button, titlebar.close_button)
    )

    for size in ((800, 600), (1280, 860)):
        window.resize(*size)
        assert window.size().width() == size[0]
        assert window.size().height() == size[1]
        for handle, _ in window._resize_handles:
            assert window.rect().contains(handle.geometry())

    qtbot.mouseClick(titlebar.maximize_button, Qt.LeftButton)
    assert window.isMaximized()
    assert titlebar.maximize_button.accessibleName() == "Restaurer la fenêtre"
    assert all(not handle.isVisible() for handle, _ in window._resize_handles)
    qtbot.mouseDClick(titlebar, Qt.LeftButton)
    assert not window.isMaximized()
    assert all(handle.isVisible() for handle, _ in window._resize_handles)


def test_cover_memory_isolated_by_platform(window):
    window.covers.request("Shared Game", "ps2")
    window.covers.request("Shared Game", "switch")
    assert ("ps2", "Shared Game") in window.covers.results
    assert ("switch", "Shared Game") in window.covers.results


def test_manual_cover_is_loaded_without_provider_key(window):
    from PIL import Image

    from cochwa.api.steamgriddb import cover_cache_path

    path = cover_cache_path(window.config.cache_dir / "covers", "ps2", "Shared Game")
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (3, 5), "red").save(path)
    path.with_suffix(".source.json").write_text('{"source":"manual"}')
    window.covers.request("Shared Game", "ps2")
    assert window.covers.results[("ps2", "Shared Game")] == path
    assert window.covers.sources[("ps2", "Shared Game")] == "manual"


def test_igdb_cover_replaces_text_match_but_preserves_manual_choice(window, tmp_path):
    from cochwa.api.steamgriddb import cover_cache_path

    key = ("switch", "Shared Game")
    cover = cover_cache_path(tmp_path, *key)
    window.covers.results[key] = cover
    window.covers.sources[key] = "sgdb_or_ia"
    url = "https://images.igdb.com/igdb/image/upload/t_cover_big/example.jpg"

    def run_now(work, done, _error=None):
        done(work())

    with (
        patch.object(window.covers.worker, "submit", side_effect=run_now),
        patch("cochwa.api.steamgriddb.cover_cache_path", return_value=cover),
        patch("cochwa.api.steamgriddb._fetch_image", return_value=b"igdb-image") as fetch,
    ):
        window.covers.request_igdb_cover("Shared Game", url, "switch")
        assert window.covers.sources[key] == "igdb"
        assert cover.read_bytes() == b"igdb-image"
        window.covers.sources[key] = "manual"
        window.covers.request_igdb_cover("Shared Game", url, "switch")
        fetch.assert_called_once()


def test_platform_menu_keyboard_animation_and_screen_bounds(window, qtbot):
    selector = window.console_box
    window.resize(800, 600)
    qtbot.mouseClick(selector, Qt.LeftButton)
    menu = selector.menu
    assert menu.isVisible()
    assert menu.parentWidget() is window
    assert menu.animation.duration() == 180
    assert menu._travel == 6
    menu_global = QRect(menu.mapToGlobal(QPoint(0, 0)), menu.size())
    selector_bottom = selector.mapToGlobal(QPoint(0, selector.height()))
    assert abs(menu_global.left() - selector_bottom.x()) <= 12
    assert 0 <= menu_global.top() - selector_bottom.y() <= 12
    assert selector.screen().availableGeometry().contains(menu_global)
    assert menu.items.currentRow() == 0
    qtbot.keyClick(menu.items, Qt.Key_Down)
    assert menu.items.currentRow() == 1
    qtbot.keyClick(menu.items, Qt.Key_Return)
    assert window.console.id == "switch"
    qtbot.waitUntil(lambda: not menu.isVisible(), timeout=1000)

    qtbot.keyClick(selector, Qt.Key_Space)
    assert menu.isVisible()
    qtbot.keyClick(menu.items, Qt.Key_Up)
    assert menu.items.currentRow() == 0
    qtbot.keyClick(menu.items, Qt.Key_Escape)
    assert window.console.id == "switch"
    qtbot.waitUntil(lambda: not menu.isVisible(), timeout=1000)

    window.config.reduce_motion = True
    qtbot.keyClick(selector, Qt.Key_Return)
    assert menu.isVisible()
    assert menu._travel == 0
    first_item = menu.items.visualItemRect(menu.items.item(0)).center()
    qtbot.mouseClick(menu.items.viewport(), Qt.LeftButton, pos=first_item)
    assert window.console.id == "ps2"
    qtbot.waitUntil(lambda: not menu.isVisible(), timeout=1000)


def test_platform_menu_disabled_items_and_long_list(window, qtbot):
    selector = window.console_box
    for index in range(24):
        selector.addItem(f"Console future {index + 1}")
        selector.model().item(selector.count() - 1).setEnabled(False)
    window.resize(800, 600)
    selector.showPopup()
    menu = selector.menu
    menu_global = QRect(menu.mapToGlobal(QPoint(0, 0)), menu.size())
    assert selector.screen().availableGeometry().contains(menu_global)
    assert menu.items.verticalScrollBar().maximum() > 0
    menu.choose(2)
    assert window.console.id == "ps2"
    assert menu.isVisible()
    qtbot.keyClick(menu.items, Qt.Key_Escape)
    qtbot.waitUntil(lambda: not menu.isVisible(), timeout=1000)


def test_switch_library_uses_console_settings(window, tmp_path):
    switch_dir = tmp_path / "switch"
    switch_dir.mkdir()
    (switch_dir / "Game [0100ABCD][v0][US].nsp").write_bytes(b"rom")
    (switch_dir / "notes.txt").write_text("ignore")
    window.config.switch_dir = switch_dir
    window.select_console(1)
    # Scan direct : seules les extensions Switch sont retenues.
    from cochwa.services.library import scan

    games = scan(switch_dir, extensions=window.console.rom_extensions)
    assert [g.title for g in games] == ["Game [0100ABCD][v0][US]"]
    # Dossier Switch non configuré : message explicite, pas de crash.
    window.config.switch_dir = None
    window.tab_library.refresh()
    assert "non configuré" in window.tab_library.status.text()


def test_voir_les_editions_declenche_la_recherche(window, qtbot):
    """Régression : clicked(bool) ne doit pas écraser le titre du lambda."""
    window.navigate("recommended")  # Recommandés → cartes rendues
    assert window.tab_recommended.grid.cards
    card = window.tab_recommended.grid.cards[0]
    with patch.object(window.search, "search", return_value=SearchResult()) as mock:
        card.button.click()
        assert window.sidebar.currentRow() == window.routes["search"]
        expected = card.base_title
        assert window.tab_search.query.text() == expected
        qtbot.waitUntil(lambda: mock.called, timeout=2000)  # recherche en worker
        assert mock.call_args.args[0] == expected


def test_support_page_links(window):
    from PySide6.QtWidgets import QPushButton

    assert window.sidebar.count() == 10
    window.navigate("support")
    buttons = [b.text() for b in window.tab_support.findChildren(QPushButton)]
    assert any("PCSX2" in b for b in buttons)
    assert any("Ryubing" in b for b in buttons)
    assert any("Steam ROM Manager" in b for b in buttons)
    assert any("GitHub" in b for b in buttons)


def test_settings_and_support_use_responsive_cards(window, qtbot):
    window.navigate("settings")
    window.resize(1280, 860)
    qtbot.wait(30)
    assert window.tab_settings.settings_grid.columns == 2
    window.resize(800, 600)
    qtbot.wait(30)
    assert window.tab_settings.settings_grid.columns == 1


def test_central_page_cross_dissolve_is_interruptible_and_respects_setting(window, qtbot):
    sidebar_position = window.sidebar.pos()
    window.navigate("tools")
    first = window._page_transition
    assert first is not None
    assert first.parentWidget() is window.pages
    assert first.duration_ms == 200
    assert first.travel_px == 8
    assert window.sidebar.pos() == sidebar_position

    window.navigate("settings")
    assert first._done
    assert window.pages.currentWidget() is window.tab_settings
    assert window._page_transition is not first
    qtbot.waitUntil(lambda: window._page_transition is None, timeout=1000)

    window.tab_settings.reduce_motion_check.setChecked(True)
    window.tab_settings.save()
    assert window.config.reduce_motion
    assert Config.load(window.config.source).reduce_motion
    window.navigate("support")
    reduced = window._page_transition
    assert reduced is not None and reduced.travel_px == 0
    qtbot.waitUntil(lambda: window._page_transition is None, timeout=1000)


def test_first_launch_tutorial_can_be_skipped_and_replayed(window, qtbot):
    assert not window.tutorial_seen()
    window.start_tutorial_if_needed()
    overlay = window._tutorial
    assert overlay is not None and overlay.isVisible()
    overlay.show_step(2)
    qtbot.wait(30)
    assert window.pages.currentWidget() is window.tab_tools
    assert overlay.page_label.text() == "PAGE OUTILS"
    assert overlay.navigation_highlight.width() > 0
    overlay.show_step(5)
    qtbot.wait(30)
    assert window.pages.currentWidget() is window.tab_settings
    assert overlay.page_label.text() == "PAGE PARAMÈTRES"
    assert overlay.highlight.width() > 0
    overlay.skip.click()
    assert window.tutorial_seen()
    assert window._tutorial is None
    window.start_tutorial_if_needed()
    assert window._tutorial is None
    window.navigate("support")
    window.start_tutorial()
    assert window._tutorial is not None
    window._tutorial.finish(skipped=True)


def test_igdb_refresh_is_automatic_and_throttled(window, tmp_path):
    from cochwa.config import ProviderConfig

    window.config.providers["ia_redump"] = ProviderConfig(
        "ia_redump", options={"cache_dir": str(tmp_path / "igdb-cache")}
    )
    window.catalogs.configure("client-id", "client-secret")
    with patch.object(window.catalogs, "refresh_all", return_value=True) as refresh:
        assert window.catalogs.refresh_if_stale()
        refresh.assert_called_once_with(["ps2", "switch"])
        assert not window.catalogs.refresh_if_stale()
        refresh.assert_called_once()


def test_switch_top_pages_all_igdb_scored_games(window, tmp_path):
    import time

    from cochwa.catalog import clear_catalog_cache
    from cochwa.config import ProviderConfig
    from cochwa.infrastructure.storage import write_json

    cache = tmp_path / "igdb-cache"
    window.config.providers["ia_redump"] = ProviderConfig(
        "ia_redump", options={"cache_dir": str(cache)}
    )
    write_json(
        cache / "catalogs" / "igdb-switch.json",
        {
            "time": time.time(),
            "games": [
                {
                    "title": f"Rated Switch Game {index}",
                    "genre": "Action",
                    "source": "IGDB",
                    "score": 90 - index // 10,
                    "critic_score": 90 - index / 10,
                }
                for index in range(75)
            ],
        },
    )
    clear_catalog_cache()
    window.select_console(1)
    window.navigate("top")
    assert len(window.tab_top._entries) == 75
    assert len(window.tab_top.grid.cards) == 60
    assert window.tab_top.next.isEnabled()
    window.tab_top.next.click()
    assert len(window.tab_top.grid.cards) == 15


def test_tabs_and_responsive_grid(window, qtbot):
    assert window.sidebar.count() == 10
    window.navigate("recommended")
    assert len(window.tab_recommended.grid.cards) == 30
    window.resize(800, 600)
    qtbot.wait(100)
    small = window.tab_recommended.grid.columns
    window.resize(1400, 900)
    qtbot.wait(100)
    assert window.tab_recommended.grid.columns > small


def test_stale_search_is_ignored(window):
    tab = window.tab_search
    tab.generation = 2
    game = IAGame("fixture", "Title", "Title", [], None, 0)
    tab.show(SearchResult(games=[game]), 1)
    assert len(tab.grid.cards) == 0
    tab.show(SearchResult(games=[game]), 2)
    assert len(tab.grid.cards) == 1


def test_worker_error_delivered_on_gui_thread(window, qtbot):
    delivered = []

    def fail():
        raise ValueError("fixture failure")

    window.worker.submit(
        fail,
        lambda value: None,
        lambda error: delivered.append((error, QThread.currentThread())),
    )
    qtbot.waitUntil(lambda: bool(delivered), timeout=2000)
    assert delivered[0][0] == "fixture failure"
    assert delivered[0][1] == window.thread()


def test_external_source_dialog_opens_only_on_click(window):
    game = IAGame(
        "minerva-123",
        "Game",
        "Game",
        [],
        None,
        0,
        source="minerva",
        source_url="https://minerva-archive.org/rom?id=123",
        external=True,
    )
    with patch("cochwa.gui_qt.dialogs.webbrowser.open") as browser:
        dialog = window.details(game)
        assert isinstance(dialog, QDialog)
        browser.assert_not_called()
        buttons = [b for b in dialog.findChildren(QPushButton)]
        assert not any("file" in button.text() for button in buttons)
        next(button for button in buttons if button.text() == "Ouvrir la fiche MiNERVA").click()
        browser.assert_called_once_with(game.source_url)
        dialog.close()
    assert window.store.list() == []


def test_source_selection_dialog(window):
    game = IAGame("fixture", "Title", "Title", [{"name": "disc.iso", "size": 6}], "disc.iso", 6)
    dialog = window.details(game)
    assert isinstance(dialog, QDialog)
    assert dialog.table.rowCount() == 1
    dialog.close()


def test_download_selection_survives_refresh(window):
    page = window.tab_downloads
    rows = [
        dict(id="a", title="Premier", status="running", progress=25, total=100, error=""),
        dict(id="b", title="Second", status="paused", progress=10, total=100, error=""),
    ]
    with patch.object(window.store, "list", return_value=rows):
        page.refresh()
        page.table.selectRow(1)
        page.refresh()
        assert page.selected_key() == "b"
        assert page.actions["Reprendre"].isEnabled()
        assert not page.actions["Pause"].isEnabled()
        with patch.object(window.manager, "pause") as pause:
            page.actions["Annuler"].click()
            pause.assert_called_once_with("b", True)


def test_empty_library_and_filter_have_distinct_actions(window, tmp_path):
    from cochwa.services.library import InstalledGame

    page = window.tab_library
    page.games = [InstalledGame("Game", [tmp_path / "Game.iso"], 5, "Non vérifié", tmp_path)]
    page.query.setText("absent")
    assert page.grid.empty.title.text() == "Aucun jeu correspondant"
    page.grid.empty.button.click()
    assert page.query.text() == ""
    assert len(page.grid.cards) == 1
    with patch.object(page, "launch") as launch:
        page.grid.cards[0].button.click()
        launch.assert_called_once_with(page.games[0])


def test_remote_selection_disables_enqueue_when_empty(window):
    game = IAGame("fixture", "Title", "Title", [{"name": "disc.iso", "size": 6}], "disc.iso", 6)
    dialog = window.details(game)
    assert dialog.enqueue_button.isEnabled()
    dialog.table.clearSelection()
    assert not dialog.enqueue_button.isEnabled()
    dialog.table.selectAll()
    assert dialog.enqueue_button.isEnabled()
    dialog.close()


def test_console_change_discards_inflight_search(window):
    page = window.tab_search
    page.generation = 8
    window.select_console(1)
    page.show(SearchResult(games=[IAGame("old", "PS2", "PS2", [], None, 0)]), 8)
    assert not page.grid.cards
    assert page.query.isEnabled()
    assert page.platform == "switch"
    assert not page.verified.isVisible()
    assert not page.next.isEnabled()
    window.select_console(0)
    assert page.query.isEnabled()


def test_search_filters_are_captured_before_worker_runs(window):
    page = window.tab_search
    page.query.setText("Game")
    page.region.setCurrentText("Europe")
    with patch.object(window.worker, "submit") as submit:
        page.do_search()
        work = submit.call_args.args[0]
        page.region.setCurrentText("USA")
        with patch.object(window.search, "search", return_value=SearchResult()) as search:
            work()
            assert search.call_args.kwargs["region"] == "Europe"
            assert search.call_args.kwargs["language"] == ""


def test_ctrl_k_opens_search(window, qtbot):
    from PySide6.QtCore import Qt

    window.activateWindow()
    qtbot.wait(20)
    qtbot.keyClick(window, Qt.Key_K, Qt.ControlModifier)
    assert window.pages.currentWidget() is window.tab_search
    assert window.tab_search.query.hasFocus()


def test_local_details_prefers_chd_and_enables_conversion_for_source_only(window, tmp_path):
    from cochwa.services.library import InstalledGame

    game = InstalledGame(
        "Game", [tmp_path / "Game.iso", tmp_path / "Game.chd"], 5, "Importé", tmp_path
    )
    dialog = window.local_details(game)
    assert dialog.chosen().suffix == ".chd"
    assert not dialog.convert_button.isEnabled()
    dialog.paths.setCurrentRow(0)
    assert dialog.convert_button.isEnabled()
    assert dialog.media.currentData() == "dvd"
    dialog.close()


def test_platform_navigation_and_search_state_are_isolated(window):
    window.tab_search.query.setText("Gran Turismo")
    window.select_console(1)
    assert window.sidebar.item(window.routes["top"]).text() == "Top Switch"
    assert "SWITCH" in window.tab_search.header.eyebrow.text()
    window.navigate("top")
    assert window.tab_top.grid.cards
    assert not any("Gran Turismo" in c.base_title for c in window.tab_top.grid.cards)
    window.tab_search.query.setText("Mario")
    window.select_console(0)
    assert window.sidebar.item(window.routes["top"]).text() == "Top PS2"
    assert window.tab_search.query.text() == "Gran Turismo"
    window.select_console(1)
    assert window.tab_search.query.text() == "Mario"


def test_download_delete_button_uses_selected_task(window):
    row = dict(id="remove-me", title="Game", status="completed", progress=10, total=10, error="")
    with (
        patch.object(window.store, "list", return_value=[row]),
        patch("cochwa.gui_qt.pages.downloads.confirm", return_value=True),
        patch.object(window.manager, "remove") as remove,
    ):
        page = window.tab_downloads
        page.refresh()
        page.table.selectRow(0)
        assert page.actions["Supprimer"].isEnabled()
        page.actions["Supprimer"].click()
        remove.assert_called_once_with("remove-me")


def test_settings_sections_generated_from_consoles(window):
    """P2 : une section par console du registre, clés génériques, activate()."""
    from cochwa.consoles import CONSOLES, DEFAULT_CONSOLE

    page = window.tab_settings
    assert set(page.console_panels) == {c.id for c in CONSOLES}
    for console in CONSOLES:
        assert f"{console.id}_directory" in page.values
        assert f"{console.id}_launcher" in page.values
    # La console par défaut est dépliée (pas de toggle), les autres repliées.
    assert DEFAULT_CONSOLE.id not in page.console_toggles
    assert set(page.console_toggles) == {c.id for c in CONSOLES if c is not DEFAULT_CONSOLE}
    # Seule la section de la console active est visible
    # (isHidden : la page elle-même n'est pas affichée pendant le test).
    window.select_console(1)
    page.activate()
    assert page.console_panels["ps2"].isHidden()
    assert not page.console_panels["switch"].isHidden()
    window.select_console(0)
    page.activate()
    assert not page.console_panels["ps2"].isHidden()
    assert page.console_panels["switch"].isHidden()


def test_settings_save_generic_roundtrip(window, tmp_path):
    """P2 : save() générique écrit <id>_dir / <id>_launcher et restaure sur erreur."""
    page = window.tab_settings
    switch_roms = tmp_path / "switch roms"
    switch_roms.mkdir()
    page.values["switch_directory"].setText(str(switch_roms))
    page.values["switch_launcher"].setText(str(tmp_path / "ryubing.sh"))
    page.save()
    assert window.config.switch_dir == switch_roms
    assert window.config.switch_launcher == tmp_path / "ryubing.sh"
    loaded = Config.load(window.config.source)
    assert loaded.console_dirs["switch"] == switch_roms
    assert loaded.console_launchers["switch"] == tmp_path / "ryubing.sh"
    # Dossier Switch inexistant : refusé, config intacte.
    page.values["switch_directory"].setText(str(tmp_path / "absent"))
    page.save()
    assert window.config.switch_dir == switch_roms


def test_named_routes_preserve_actions_after_menu_reorder(window):
    for key in ("collections", "emulators", "tools", "settings", "downloads", "support"):
        window.navigate(key)
        assert window.pages.currentWidget() is getattr(window, "tab_" + key)
    window.focus_search()
    assert window.pages.currentWidget() is window.tab_search
    window.show_downloads()
    assert window.pages.currentWidget() is window.tab_downloads
    window.select_console(1)
    window.navigate("tools")
    assert not window.tab_tools.convert.isEnabled()
    window.select_console(0)
    assert window.tab_tools.convert.isEnabled()


def test_collections_never_mix_console_games(window):
    from cochwa.services.library import scan

    window.tab_library.games = scan(window.config.ps2_dir)
    page = window.tab_collections
    page.store.save("PS2 favoris", "ps2", ["Game"])
    page.store.save("Switch favoris", "switch", ["Mario"])
    window.navigate("collections")
    assert page.choice.currentText() == "PS2 favoris"
    assert len(page.grid.cards) == 1
    window.select_console(1)
    assert page.choice.currentText() == "Switch favoris"
    assert not page.grid.cards


def test_emulators_filter_across_consoles_without_switching_library(window):
    window.navigate("emulators")
    page = window.tab_emulators
    page.platform.setCurrentText("GameCube")
    assert "1 projet" in page.status.text()
    assert window.console.id == "ps2"
    page.query.setText("no matching emulator")
    assert "0 projets" in page.status.text()


def test_emulators_brand_grid_and_combined_filters(window, qtbot):
    from PySide6.QtWidgets import QLabel

    window.navigate("emulators")
    page = window.tab_emulators
    qtbot.waitUntil(lambda: page.grid.viewport().width() >= 750)
    assert len(page.grid.cards) == 22
    assert page.grid.flow.itemAtPosition(0, 2).widget() is page.grid.cards[2]
    artwork = page.grid.cards[0].findChildren(QLabel)[0]
    assert not artwork.pixmap().isNull()

    page.manufacturer.setCurrentText("Sony")
    page.decade.setCurrentText("Années 2000")
    page.processor.setCurrentText("128 bits")
    assert [card.accessibleName().split(" · ")[0] for card in page.grid.cards] == ["PCSX2"]
    with patch.object(page, "configure") as configure:
        menu = page.grid.cards[0].findChildren(QPushButton)[-1].menu()
        next(
            action for action in menu.actions() if action.text().startswith("Configurer")
        ).trigger()
        configure.assert_called_once_with("ps2")
    page.processor.setCurrentText("x86")
    assert not page.grid.cards
