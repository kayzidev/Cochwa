"""Composition de l'application Tkinter ; logique métier dans services/."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from romget.api.redump import get_datfile
from romget.api.steamgriddb import download_cover
from romget.config import Config
from romget.gui import theme
from romget.gui.dialogs import choose_cover, show_local_details, show_remote_details
from romget.gui.events import Dispatcher
from romget.gui.settings import build_settings
from romget.gui.tab_downloads import DownloadsTab
from romget.gui.tab_library import LibraryTab
from romget.gui.tab_recommended import RecommendedTab
from romget.gui.tab_search import SearchTab
from romget.gui.tab_top import TopByConsoleTab
from romget.gui.theme import ToastManager
from romget.gui.widgets import make_placeholder
from romget.services.index import LibraryIndex
from romget.services.jobs import DownloadManager, JobStore
from romget.services.search import SearchService


class RomgetApp:
    def __init__(self, config=None, *, start_workers=True):
        self.config = config or Config.load()
        self.root = tk.Tk()
        self.root.title("romget — Bibliothèque PS2")
        self.root.geometry("1150x800")
        self.root.minsize(800, 600)
        self.closing = False
        self.work_cancel = threading.Event()
        self.cover_pending = {}
        self.cover_results = {}
        self.start_workers = start_workers
        self._setup_style()
        self.status_var = tk.StringVar(value="Prêt")
        self.dispatch = Dispatcher(self.root, self.error)
        self.search = SearchService(self.config)
        self.index = LibraryIndex(self.config.state_dir / "library.sqlite3")
        self.store = JobStore(self.config.state_dir)
        self.manager = DownloadManager(
            self.store,
            lambda kind, msg: self.dispatch.post(lambda value: self.job_event(kind, value), msg),
            datfile=lambda: get_datfile(self.config.cache_dir, self.config.datfile_url),
        )
        self.placeholder = make_placeholder()
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)
        self.tab_search = SearchTab(self.notebook, self)
        self.tab_recommended = RecommendedTab(self.notebook, self)
        self.tab_top = TopByConsoleTab(self.notebook, self)
        self.tab_library = LibraryTab(self.notebook, self)
        self.tab_downloads = DownloadsTab(self.notebook, self)
        self.tab_settings = self.settings(self.notebook)
        for tab, label in [
            (self.tab_search, "◎ Rechercher"),
            (self.tab_recommended, "◆ Recommandés"),
            (self.tab_top, "★ Top PS2"),
            (self.tab_library, "▤ Bibliothèque"),
            (self.tab_downloads, "⬇ Téléchargements"),
            (self.tab_settings, "⚙ Paramètres"),
        ]:
            self.notebook.add(tab, text=label)
        self.notebook.bind("<<NotebookTabChanged>>", self.activate)
        self.toasts = ToastManager(self.root)
        ttk.Label(
            self.root, textvariable=self.status_var, anchor="w", padding=8, style="Status.TLabel"
        ).pack(fill="x")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Control-f>", lambda event: self.notebook.select(self.tab_search))
        if start_workers:
            self.manager.start()
            self.tab_library.refresh()
        self.timer = self.root.after(1000, self.tick)

    def _setup_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        self.root.configure(bg=theme.BG)
        style.configure(".", background=theme.BG, foreground=theme.TEXT, font=theme.F_BODY)
        style.configure("TFrame", background=theme.BG)
        style.configure("TLabel", background=theme.BG)
        style.configure("Status.TLabel", background=theme.PANEL, foreground=theme.MUTED)
        style.configure("TButton", background="#2c3542", padding=(10, 6), borderwidth=0)
        style.map(
            "TButton",
            background=[("active", theme.ACCENT_DARK), ("disabled", theme.PANEL)],
            foreground=[("disabled", theme.MUTED)],
        )
        style.configure(
            "TEntry",
            fieldbackground=theme.PANEL,
            foreground=theme.TEXT,
            insertcolor=theme.TEXT,
            bordercolor=theme.BORDER,
        )
        style.configure("TCombobox", fieldbackground=theme.PANEL, foreground=theme.TEXT)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", theme.PANEL)],
            foreground=[("readonly", theme.TEXT)],
        )
        style.configure("TNotebook", background=theme.BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab", padding=(14, 8), background=theme.PANEL, foreground=theme.MUTED
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", theme.CARD)],
            foreground=[("selected", theme.ACCENT)],
        )
        style.configure(
            "Treeview", fieldbackground=theme.PANEL, background=theme.PANEL, rowheight=30
        )
        style.configure("Treeview.Heading", background=theme.BG, foreground=theme.MUTED, padding=6)
        style.map("Treeview", background=[("selected", theme.ACCENT_DARK)])
        style.configure(
            "TProgressbar", background=theme.SUCCESS, troughcolor=theme.PANEL, borderwidth=0
        )
        style.configure("TCheckbutton", background=theme.BG)
        style.configure(
            "Vertical.TScrollbar",
            background=theme.PANEL,
            troughcolor=theme.BG,
            borderwidth=0,
            arrowcolor=theme.MUTED,
        )

    def notify(self, message, kind="info"):
        """Barre de statut + toast (info / success / error)."""
        self.status_var.set(message)
        if not self.closing:
            self.toasts.show(message, kind)

    def error(self, message):
        if not self.closing:
            self.status_var.set("Erreur : " + str(message))
            self.toasts.show(str(message), "error")

    def activate(self, event=None):
        selected = self.root.nametowidget(self.notebook.select())
        if hasattr(selected, "activate"):
            selected.activate()

    def tick(self):
        if self.closing:
            return
        self.tab_downloads.refresh()
        self.timer = self.root.after(1000, self.tick)

    def job_event(self, kind, message):
        if kind == "error":
            self.error(message)
        elif kind == "jobs":
            self.tab_downloads.refresh()
            self.tab_library.refresh()
            self.status_var.set("Tâche mise à jour ; consulter Téléchargements pour son résultat.")

    def search_title(self, title):
        self.notebook.select(self.tab_search)
        self.tab_search.query.set(title.split("(")[0].strip())
        self.tab_search.do_search()

    def installed_titles(self):
        """Titres de la bibliothèque locale (vide avant le premier scan)."""
        return [g.title for g in self.tab_library.games]

    def cover(self, card, title, ia_identifier=None):
        if not self.start_workers:
            card.set_cover(None)
            return
        # Base artwork may be shared by editions; labels keep the full edition title.
        title = title.split("(")[0].strip()

        def set_image(path):
            if not self.closing and card.winfo_exists():
                card.set_cover(path)

        if title in self.cover_results:
            set_image(self.cover_results[title])
            return
        if title in self.cover_pending:
            self.cover_pending[title].append(set_image)
            return
        if not self.config.steamgrid_api_key and not ia_identifier:
            card.set_cover(None)
            return
        self.cover_pending[title] = [set_image]

        def ready(path):
            self.cover_results[title] = path
            for callback in self.cover_pending.pop(title, []):
                callback(path)

        self.dispatch.submit(
            lambda: download_cover(
                self.config.steamgrid_api_key,
                title,
                cache_dir=self.config.cache_dir / "covers",
                ia_identifier=ia_identifier,
            ),
            ready,
            lambda error: (ready(None), self.status_var.set("Jaquette indisponible : " + error)),
        )

    def details(self, game):
        return show_remote_details(self, game)

    def local_details(self, game):
        return show_local_details(self, game)

    def choose_cover(self, title):
        return choose_cover(self, title)

    def settings(self, parent):
        return build_settings(self, parent)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.work_cancel.set()
        self.tab_search.cancel.set()
        self.manager.close()
        self.root.after_cancel(self.timer)
        self.status_var.set("Fermeture ; les tâches et fragments sont conservés pour reprise.")
        self.dispatch.close()

        def finish():
            if self.manager._thread and self.manager._thread.is_alive():
                self.root.after(100, finish)
            else:
                self.root.destroy()

        finish()

    def run(self):
        self.root.mainloop()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="romget — GUI PS2")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    try:
        RomgetApp(Config.load(args.config)).run()
    except (OSError, ValueError, tk.TclError) as exc:
        import sys

        print(f"Impossible de démarrer romget : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
