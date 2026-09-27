"""Fenêtre principale Qt : sidebar, pages empilées, services partagés.

La logique métier reste dans services/ ; cette couche ne fait que de la
présentation. Les workers ne touchent jamais les widgets (signaux Qt).
"""

from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QObject, QSize, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from cochwa.api.redump import get_datfile
from cochwa.config import Config
from cochwa.consoles import CONSOLES, DEFAULT_CONSOLE
from cochwa.gui_qt import theme
from cochwa.gui_qt.dialogs import LocalDetailsDialog, RemoteDetailsDialog, choose_cover
from cochwa.gui_qt.pages.downloads import DownloadsPage
from cochwa.gui_qt.pages.gamelist import RecommendedPage, TopPage
from cochwa.gui_qt.pages.library import LibraryPage
from cochwa.gui_qt.pages.search import SearchPage
from cochwa.gui_qt.pages.settings import SettingsPage
from cochwa.gui_qt.pages.support import SupportPage
from cochwa.gui_qt.toasts import ToastManager
from cochwa.gui_qt.widgets import brand_icon, brand_pixmap, navigation_icon
from cochwa.gui_qt.workers import CoverService, Worker
from cochwa.services.index import LibraryIndex
from cochwa.services.jobs import DownloadManager, JobStore
from cochwa.services.search import SearchService


class _JobHub(QObject):
    """Relais thread-safe des événements du DownloadManager vers la GUI."""

    event = Signal(str, object)


class MainWindow(QMainWindow):
    def __init__(self, config=None, *, start_workers=True):
        super().__init__()
        self.config = config or Config.load()
        self.setWindowTitle(f"Cochwa — Bibliothèque {DEFAULT_CONSOLE.name}")
        self.setWindowIcon(brand_icon())
        self.resize(1280, 860)
        self.setMinimumSize(800, 600)
        self.closing = False
        self.work_cancel = threading.Event()
        self.start_workers = start_workers
        self.console = DEFAULT_CONSOLE

        self.worker = Worker(self)
        self.covers = CoverService(self.config, self)
        self.search = SearchService(self.config)
        self.index = LibraryIndex(self.config.state_dir / "library.sqlite3")
        self.store = JobStore(self.config.state_dir)
        self.jobs_hub = _JobHub(self)
        self.manager = DownloadManager(
            self.store,
            lambda kind, msg: self.jobs_hub.event.emit(kind, msg),
            datfile=lambda: get_datfile(self.config.cache_dir, self.config.datfile_url),
        )
        self.jobs_hub.event.connect(self.job_event)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidepanel())
        self.pages = QStackedWidget()
        self.tab_search = SearchPage(self)
        self.tab_recommended = RecommendedPage(self)
        self.tab_top = TopPage(self)
        self.tab_library = LibraryPage(self)
        self.tab_downloads = DownloadsPage(self)
        self.tab_settings = SettingsPage(self)
        self.tab_support = SupportPage(self)
        for page, label in [
            (self.tab_library, "Bibliothèque"),
            (self.tab_search, "Rechercher"),
            (self.tab_recommended, "Recommandés"),
            (self.tab_top, "Top PS2"),
            (self.tab_downloads, "Téléchargements"),
            (self.tab_settings, "Paramètres"),
            (self.tab_support, "Support"),
        ]:
            QListWidgetItem(navigation_icon(label), label, self.sidebar)
            self.pages.addWidget(page)
        root.addWidget(self.pages, stretch=1)
        self.setCentralWidget(central)
        self.sidebar.currentRowChanged.connect(self.activate)
        self.sidebar.setCurrentRow(0)
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.search_shortcut.activated.connect(self.focus_search)

        self.toasts = ToastManager(self)
        self.statusBar().showMessage("Vos jeux, simplement.")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tab_downloads.refresh)
        self.timer.start(1000)
        if start_workers:
            self.manager.start()
            self.tab_library.refresh()

    def _build_sidepanel(self):
        """Identité de marque, plateforme active et navigation clavier native."""
        panel = QWidget()
        panel.setObjectName("sidepanel")
        panel.setFixedWidth(218)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(8)
        brand = QHBoxLayout()
        symbol = QLabel()
        symbol.setPixmap(brand_pixmap(40))
        brand.addWidget(symbol)
        self.logo = QLabel("Cochwa")
        self.logo.setObjectName("brand")
        brand.addWidget(self.logo)
        brand.addStretch()
        layout.addLayout(brand)
        slogan = QLabel("VOS JEUX, SIMPLEMENT")
        slogan.setObjectName("eyebrow")
        layout.addWidget(slogan)
        layout.addSpacing(12)
        platform = QLabel("PLATEFORME")
        platform.setObjectName("eyebrow")
        layout.addWidget(platform)
        # Sélecteur de console : PS2 et Switch actives ; les consoles futures
        # non implémentées restent grisées (« (bientôt) »).
        self.console_box = QComboBox()
        self.console_box.setObjectName("consoleSelect")
        for console in CONSOLES:
            label = console.name if console.enabled else console.name + " (bientôt)"
            self.console_box.addItem(label, console)
        for index in range(self.console_box.count()):
            if not self.console_box.itemData(index).enabled:
                self.console_box.model().item(index).setEnabled(False)
        self.console_box.setCurrentIndex(CONSOLES.index(DEFAULT_CONSOLE))
        self.console_box.activated.connect(self.select_console)
        layout.addWidget(self.console_box)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setIconSize(QSize(18, 18))
        self.sidebar.setAccessibleName("Navigation principale")
        layout.addWidget(self.sidebar, stretch=1)
        self.platform_note = QLabel("Catalogue & recherche\nPlayStation 2")
        self.platform_note.setObjectName("muted")
        self.platform_note.setWordWrap(True)
        layout.addWidget(self.platform_note)
        shortcut = QLabel("Recherche rapide  ·  Ctrl + K")
        shortcut.setObjectName("muted")
        shortcut.setStyleSheet("font-size: 11px;")
        layout.addWidget(shortcut)
        return panel

    def select_console(self, index):
        """Change de console : titre, bibliothèque et pages concernées suivent."""
        console = self.console_box.itemData(index)
        if not console or not console.enabled:
            self.console_box.setCurrentIndex(CONSOLES.index(self.console))
            return
        if console is self.console:
            return
        self.console = console
        self.console_box.setCurrentIndex(index)
        self.tab_search.activate()
        self.setWindowTitle(f"Cochwa — Bibliothèque {console.name}")
        self.tab_library.refresh()
        self.activate(self.sidebar.currentRow())
        self.notify(f"Console active : {console.name}")

    def roms_dir(self):
        """Dossier ROMs de la console active (None si non configuré)."""
        return self.config.roms_dir(self.console)

    # -- Navigation -----------------------------------------------------

    def activate(self, row):
        self.pages.setCurrentIndex(row)
        page = self.pages.currentWidget()
        if hasattr(page, "activate"):
            page.activate()

    def focus_search(self):
        self.sidebar.setCurrentRow(1)
        self.tab_search.query.setFocus()
        self.tab_search.query.selectAll()

    def show_downloads(self):
        self.sidebar.setCurrentRow(4)
        self.tab_downloads.refresh()

    def search_title(self, title):
        self.sidebar.setCurrentRow(1)
        self.tab_search.query.setText(title.split("(")[0].strip())
        self.tab_search.do_search()

    # -- Notifications ----------------------------------------------------

    def notify(self, message, kind="info"):
        """Barre de statut + toast (info / success / error)."""
        self.statusBar().showMessage(message)
        if not self.closing:
            self.toasts.show(message, kind)

    def error(self, message):
        if not self.closing:
            self.statusBar().showMessage("Erreur : " + str(message))
            self.toasts.show(str(message), "error")

    def job_event(self, kind, message):
        if kind == "error":
            self.error(message)
        elif kind == "jobs":
            self.tab_downloads.refresh()
            self.tab_library.refresh()
            self.statusBar().showMessage(
                "Tâche mise à jour ; consulter Téléchargements pour son résultat."
            )

    # -- Jaquettes et dialogues --------------------------------------------

    def cover(self, card, title, ia_identifier=None):
        if not self.start_workers:
            return
        base = title.split("(")[0].strip()
        if base in self.covers.results:
            path = self.covers.results[base]
            if path:
                card.set_cover(str(path))
            return
        self.covers.request(title, ia_identifier)

    def details(self, game):
        dialog = RemoteDetailsDialog(self, game, self)
        dialog.show()
        return dialog

    def local_details(self, game):
        dialog = LocalDetailsDialog(self, game, self)
        dialog.show()
        return dialog

    def choose_cover(self, title):
        return choose_cover(self, title)

    def installed_titles(self):
        """Titres de la bibliothèque locale (vide avant le premier scan)."""
        return [g.title for g in self.tab_library.games]

    # -- Fermeture ----------------------------------------------------------

    def closeEvent(self, event):
        self.closing = True
        self.work_cancel.set()
        self.tab_search.cancel.set()
        self.manager.close()
        self.timer.stop()
        super().closeEvent(event)


def main():
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Cochwa — GUI")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    app = QApplication(sys.argv)
    theme.apply(app)
    window = MainWindow(Config.load(args.config))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
