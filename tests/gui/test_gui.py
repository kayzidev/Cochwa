"""Tests réels Tkinter, sans réseau, émulateur ni écritures dans la bibliothèque utilisateur."""

import tempfile
import threading
import time
import tkinter as tk
import unittest
from pathlib import Path

from romget.config import Config
from romget.gui.app import RomgetApp
from romget.models import IAGame, SearchResult


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "Game.iso").write_bytes(b"image")
        config = Config(
            ps2_dir=self.root, state_dir=self.root / "state", source=self.root / "config.toml"
        )
        self.app = RomgetApp(config, start_workers=False)
        self.app.root.update()
        self.addCleanup(self.close)

    def close(self):
        self.app.close()

    def test_tabs_and_responsive_grid(self):
        self.assertEqual(len(self.app.notebook.tabs()), 6)
        self.app.notebook.select(self.app.tab_recommended)
        self.app.root.update()
        self.assertEqual(len(self.app.tab_recommended.grid.cards), 20)
        self.app.root.geometry("800x600")
        self.app.root.update()
        small = self.app.tab_recommended.grid.columns
        self.app.root.geometry("1400x900")
        self.app.root.update()
        self.assertGreater(self.app.tab_recommended.grid.columns, small)

    def test_stale_search_is_ignored(self):
        tab = self.app.tab_search
        tab.generation = 2
        game = IAGame("fixture", "Title", "Title", [], None, 0)
        tab.show(SearchResult(games=[game]), 1)
        self.assertEqual(len(tab.grid.cards), 0)
        tab.show(SearchResult(games=[game]), 2)
        self.assertEqual(len(tab.grid.cards), 1)

    def test_worker_error_delivered_on_gui_thread(self):
        delivered = []
        gui_thread = threading.get_ident()

        def fail():
            raise ValueError("fixture failure")

        self.app.dispatch.submit(
            fail, lambda value: None, lambda error: delivered.append((error, threading.get_ident()))
        )
        deadline = time.monotonic() + 2
        while not delivered and time.monotonic() < deadline:
            self.app.root.update()
            time.sleep(0.01)
        self.assertEqual(delivered, [("fixture failure", gui_thread)])

    def test_source_selection_dialog(self):
        game = IAGame("fixture", "Title", "Title", [{"name": "disc.iso", "size": 6}], "disc.iso", 6)
        self.app.details(game)
        self.app.root.update()
        windows = [
            child for child in self.app.root.winfo_children() if isinstance(child, tk.Toplevel)
        ]
        self.assertEqual(len(windows), 1)
        windows[0].destroy()


if __name__ == "__main__":
    unittest.main()
