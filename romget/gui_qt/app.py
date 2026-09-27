"""POC PySide6 : fenêtre principale, sidebar animée, onglet Recommandés réel.

Les autres onglets sont des placeholders — le POC valide le ressenti, les
performances à 100 cartes et le branchement des services existants.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QScrollArea,
    QStackedWidget,
    QWidget,
)

from romget.api.steamgriddb import download_cover
from romget.config import Config
from romget.gui.games_data import recommended_entries, recommended_pool
from romget.gui_qt.cards import GameCard

QSS = """
QMainWindow, QWidget { background: #171a21; color: #e8eaed; font-size: 13px; }
QListWidget#sidebar { background: #1e2530; border: none; outline: 0;
                      font-size: 14px; }
QListWidget#sidebar::item { padding: 13px 16px; color: #9aa5b1;
                            border-left: 3px solid transparent; }
QListWidget#sidebar::item:selected { background: #242c38; color: #66c0f4;
                                     border-left: 3px solid #66c0f4; }
QListWidget#sidebar::item:hover:!selected { color: #e8eaed; background: #212833; }
QFrame#card, QWidget#card { background: #242c38; border: 1px solid #39424f;
                            border-radius: 12px; }
QWidget#card[hover="true"] { border: 1px solid #66c0f4; background: #2b3543; }
QLabel { background: transparent; border: none; }
QLabel#cardTitle { font-weight: bold; font-size: 13px; }
QLabel#cardMeta { color: #9aa5b1; font-size: 11px; }
QLabel#chip { border-radius: 8px; padding: 1px 7px; font-size: 10px;
              font-weight: bold; }
QLabel#heading { font-size: 20px; font-weight: bold; }
QLabel#muted { color: #9aa5b1; }
QPushButton#cardBtn { background: #31435a; border: none; border-radius: 7px;
                      padding: 7px; font-weight: bold; color: #e8eaed; }
QPushButton#cardBtn:hover { background: #66c0f4; color: #10212e; }
QPushButton#cardBtn:pressed { background: #3d6e96; }
QScrollArea { border: none; }
QStatusBar { background: #1e2530; color: #9aa5b1; }
QScrollBar:vertical { background: #171a21; width: 10px; }
QScrollBar::handle:vertical { background: #39424f; border-radius: 5px;
                              min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #66c0f4; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

TABS = [
    ("◎ Rechercher", False),
    ("◆ Recommandés", True),  # seul onglet migré dans le POC
    ("★ Top PS2", False),
    ("▤ Bibliothèque", False),
    ("⬇ Téléchargements", False),
    ("⚙ Paramètres", False),
]


class CoverHub(QObject):
    """Relais thread-safe : les workers émettent, la GUI reçoit (queued)."""

    loaded = Signal(str, object)  # titre de base, chemin ou None


class CoverWorker(QObject):
    """Téléchargement de jaquette via le service existant, hors thread GUI."""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.hub = CoverHub()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(4)

    def request(self, title):
        base = title.split("(")[0].strip()

        def work():
            try:
                path = download_cover(
                    self.config.steamgrid_api_key,
                    base,
                    cache_dir=self.config.cache_dir / "covers",
                )
            except Exception:
                path = None
            self.hub.loaded.emit(base, path)

        self.pool.start(work)  # QThreadPool accepte un callable en PySide6


class RecommendedPage(QWidget):
    """Grille des 20 recommandés du jour : cascade, covers en fondu."""

    def __init__(self, covers, parent=None):
        super().__init__(parent)
        self.covers = covers
        self.cards = []
        layout = QGridLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        self._grid = layout
        entries = recommended_entries()
        for i, entry in enumerate(entries):
            badges = []
            if type(entry.get("score")) is int:
                badges.append((f"★ {entry['score']}", "#6cbd91"))
            card = GameCard(entry["title"], entry.get("genre", ""), badges=badges)
            self.cards.append(card)
            # Cascade : chaque carte apparaît 25 ms après la précédente.
            card.setVisible(False)
            QTimer.singleShot(min(i * 25, 400), card.appear)
        self.columns = 0
        self._relayout()

    def load_covers(self):
        """À appeler APRÈS connexion du hub : les workers du cache disque
        répondent en quelques ms, avant toute connexion tardive sinon."""
        for card in self.cards:
            self.covers.request(card._raw_title)

    def set_cover(self, base_title, path):
        if not path:
            return
        for card in self.cards:
            if card._raw_title.split("(")[0].strip() == base_title:
                card.set_cover(str(path))

    def resizeEvent(self, event):
        self._relayout()
        super().resizeEvent(event)

    def _relayout(self):
        columns = max(1, self.width() // 230)
        if columns == self.columns:
            return
        self.columns = columns
        while self._grid.count():
            self._grid.takeAt(0)
        for i, card in enumerate(self.cards):
            self._grid.addWidget(card, i // columns, i % columns)


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.setWindowTitle("romget — POC PySide6")
        self.resize(1150, 800)
        self.config = config
        self.covers = CoverWorker(config)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(210)
        for label, _ in TABS:
            QListWidgetItem(label, self.sidebar)
        root.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        for label, implemented in TABS:
            if implemented:
                page = self._recommended_page()
            else:
                page = QLabel(f"{label}\n\nPOC — vue non migrée.")
                page.setObjectName("muted")
                page.setAlignment(Qt.AlignCenter)
            self.pages.addWidget(page)
        root.addWidget(self.pages, stretch=1)
        self.setCentralWidget(central)

        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sidebar.setCurrentRow(1)  # Recommandés
        self.statusBar().showMessage(
            f"POC PySide6 — {len(recommended_pool())} jeux en rotation, 20 du jour"
        )

    def _recommended_page(self):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.recommended = RecommendedPage(self.covers)
        scroll.setWidget(self.recommended)
        layout.addWidget(scroll)
        self.covers.hub.loaded.connect(self.recommended.set_cover)
        self.recommended.load_covers()
        return container


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    window = MainWindow(Config.load())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
