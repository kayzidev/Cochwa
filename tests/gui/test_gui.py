"""Tests GUI Qt (offscreen), sans réseau, émulateur ni écritures dans la bibliothèque utilisateur."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import QDialog, QPushButton  # noqa: E402

from cochwa.config import Config  # noqa: E402
from cochwa.gui_qt.app import MainWindow  # noqa: E402
from cochwa.models import IAGame, SearchResult  # noqa: E402


@pytest.fixture
def window(qtbot, tmp_path):
    (tmp_path / "Game.iso").write_bytes(b"image")
    config = Config(
        ps2_dir=tmp_path, state_dir=Path(tmp_path) / "state", source=Path(tmp_path) / "config.toml"
    )
    win = MainWindow(config, start_workers=False)
    qtbot.addWidget(win)
    win.show()
    return win


def test_console_selector_and_logo_placeholder(window):
    from cochwa.consoles import CONSOLES, DEFAULT_CONSOLE

    assert window.logo.text() == "COCHWA"  # emplacement du futur logo
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
    window.sidebar.setCurrentRow(1)  # Recommandés → cartes rendues
    assert window.tab_recommended.grid.cards
    card = window.tab_recommended.grid.cards[0]
    with patch.object(window.search, "search", return_value=SearchResult()) as mock:
        card.button.click()
        assert window.sidebar.currentRow() == 0
        expected = card.base_title
        assert window.tab_search.query.text() == expected
        qtbot.waitUntil(lambda: mock.called, timeout=2000)  # recherche en worker
        assert mock.call_args.args[0] == expected


def test_support_page_links(window):
    from PySide6.QtWidgets import QPushButton

    assert window.sidebar.count() == 7
    window.sidebar.setCurrentRow(6)
    buttons = [b.text() for b in window.tab_support.findChildren(QPushButton)]
    assert any("PCSX2" in b for b in buttons)
    assert any("Ryubing" in b for b in buttons)
    assert any("Steam ROM Manager" in b for b in buttons)
    assert any("GitHub" in b for b in buttons)


def test_tabs_and_responsive_grid(window, qtbot):
    assert window.sidebar.count() == 7
    window.sidebar.setCurrentRow(1)
    assert len(window.tab_recommended.grid.cards) == 20
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
