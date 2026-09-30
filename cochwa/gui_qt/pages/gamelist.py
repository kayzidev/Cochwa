"""Pages catalogue : Recommandés du jour et Top PS2 (découverte locale instantanée)."""

from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cochwa.catalog import (
    genres,
    has_igdb_catalog,
    recommended_entries,
    top_entries,
)
from cochwa.gui_qt import theme
from cochwa.gui_qt.cards import GameCard
from cochwa.gui_qt.grid import CardGrid
from cochwa.gui_qt.widgets import PageHeader
from cochwa.util import artwork_search_title


class GameListPage(QWidget):
    PAGE_SIZE = 60

    def __init__(self, app, label, genre_filter=False):
        super().__init__()
        self.app = app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(14)
        header = PageHeader(
            "Les incontournables" if genre_filter else "Une nouvelle envie de jouer ?",
            label,
            "DÉCOUVRIR",
        )
        self.header = header
        self.platform = app.console.id
        self.heading = header.title
        layout.addWidget(header)
        bar = QHBoxLayout()
        hint = QLabel("Une sélection à explorer, édition par édition.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        bar.addWidget(hint, stretch=1)
        self.genre = None
        if genre_filter:
            bar.addWidget(QLabel("Genre"))
            self.genre = QComboBox()
            self.genre.addItems([""] + genres(self.platform, self.app.config.cache_dir))
            self.genre.currentTextChanged.connect(lambda _: self.render())
            bar.addWidget(self.genre)
        layout.addLayout(bar)
        self.grid = CardGrid()
        layout.addWidget(self.grid, stretch=1)
        pager = QHBoxLayout()
        self.previous = QPushButton("← Précédent")
        self.previous.clicked.connect(lambda: self._show_page(self.page - 1))
        self.next = QPushButton("Suite →")
        self.next.clicked.connect(lambda: self._show_page(self.page + 1))
        pager.addWidget(self.previous)
        pager.addStretch(1)
        pager.addWidget(self.next)
        layout.addLayout(pager)
        self.page = 0
        self._entries = []
        self._visible_entry_by_title = {}
        self._requested_covers = set()
        self.grid.verticalScrollBar().valueChanged.connect(self._load_visible_covers)
        self.app.covers.loaded.connect(self._on_cover)
        self.app.catalogs.updated.connect(self._catalog_updated)

    def entries(self):
        raise NotImplementedError

    def activate(self):
        # Reconstruit à chaque affichage : badges « Installé » et filtre genre
        # à jour ; les jaquettes sont servies par le cache mémoire/disque.
        platform = self.app.console.id
        if platform != self.platform and self.genre:
            self.genre.blockSignals(True)
            self.genre.clear()
            self.genre.addItems([""] + genres(platform, self.app.config.cache_dir))
            self.genre.blockSignals(False)
        self.platform = platform
        self.header.eyebrow.setText(f"DÉCOUVRIR · {self.app.console.name.upper()}")
        if self.genre:
            self.heading.setText(f"Top {self.app.console.short_name}")
            self.header.description.setText(self._top_description())
        else:
            self.header.description.setText(
                f"Sélection de jeux pour {self.app.console.name}, renouvelée depuis le catalogue disponible."
            )
        self.render()

    def _top_description(self):
        if has_igdb_catalog(self.platform, self.app.config.cache_dir):
            return "Classés par note des critiques IGDB · scores distincts du Metascore Metacritic."
        if self.platform == "ps2":
            return "Classement local selon les scores Metacritic disponibles."
        return "Classement local de découverte ; connectez IGDB dans Paramètres pour les notes critiques."

    def render(self):
        self.grid.clear()
        self._requested_covers.clear()
        installed = set()
        for title in self.app.installed_titles():
            installed.add(title.casefold())
            installed.add(artwork_search_title(title).casefold())
        selected = self.genre.currentText() if self.genre else ""
        entries = self.entries()
        self._entries = [
            entry for entry in entries if not selected or entry.get("genre") == selected
        ]
        self.page = 0
        self._render_current_page(installed)

    def _render_current_page(self, installed=None):
        self.grid.clear()
        self._requested_covers.clear()
        if installed is None:
            installed = set()
            for title in self.app.installed_titles():
                installed.add(title.casefold())
                installed.add(artwork_search_title(title).casefold())
        if self.genre:
            start = self.page * self.PAGE_SIZE
            visible_entries = self._entries[start : start + self.PAGE_SIZE]
        else:
            visible_entries = self._entries
        cards = []
        self._visible_entry_by_title = {}
        start = self.page * self.PAGE_SIZE if self.genre else 0
        for offset, entry in enumerate(visible_entries):
            title = entry["title"]
            base = artwork_search_title(title).casefold()
            is_installed = title.casefold() in installed or base in installed
            badges = []
            if self.genre:
                badges.append((f"N° {start + offset + 1}", theme.MUTED))
            if type(entry.get("score")) is int:
                source = "IGDB" if entry.get("source") == "IGDB" else "Meta"
                badges.append((f"{source} {entry['score']}", theme.score_color(entry["score"])))
            if is_installed:
                badges.append(("✓ Installé", theme.SUCCESS))
            card = GameCard(
                title,
                subtitle=entry.get("genre") or "Éditions à rechercher",
                badges=badges,
                action=lambda t=title: self.app.search_title(t),
                action_text="Voir les éditions",
            )
            cards.append(card)
            self._visible_entry_by_title[card._raw_title] = entry
        self.grid.add_many(cards)
        pages = (len(self._entries) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        self.previous.setEnabled(bool(self.genre and self.page > 0))
        self.next.setEnabled(bool(self.genre and self.page + 1 < pages))
        self.previous.setVisible(bool(self.genre))
        self.next.setVisible(bool(self.genre))
        selected = self.genre.currentText() if self.genre else ""
        self.grid.set_empty("Aucun jeu pour ce genre." if selected else "")
        self._load_visible_covers()

    def _show_page(self, page):
        pages = (len(self._entries) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        self.page = max(0, min(page, max(0, pages - 1)))
        self._render_current_page()

    def _load_visible_covers(self, *_args):
        if not self.app.start_workers:
            return
        top = self.grid.verticalScrollBar().value()
        bottom = top + self.grid.viewport().height() + 360
        for card in self.grid.cards:
            title = card._raw_title
            key = title.casefold()
            position = card.mapTo(self.grid.inner, QPoint(0, 0)).y()
            if key in self._requested_covers or position + card.height() < top or position > bottom:
                continue
            self._requested_covers.add(key)
            entry = self._visible_entry_by_title.get(title, {})
            self.app.cover(card, title)
            if entry.get("cover_url"):
                self.app.covers.request_igdb_cover(title, entry["cover_url"], self.app.console.id)

    def _catalog_updated(self, _catalogs):
        if self.app.pages.currentWidget() is self:
            self.activate()

    def _on_cover(self, platform, base, path):
        if platform != self.app.console.id or not path:
            return
        for card in self.grid.cards:
            if card.base_title == base:
                card.set_cover(str(path))


class RecommendedPage(GameListPage):
    def __init__(self, app):
        super().__init__(app, "Une sélection variée à découvrir.")

    def entries(self):
        return recommended_entries(
            platform=self.app.console.id,
            cache_dir=self.app.config.cache_dir,
        )


class TopPage(GameListPage):
    def __init__(self, app):
        super().__init__(
            app,
            "Le classement complet des jeux disposant d’une note critique.",
            genre_filter=True,
        )

    def entries(self):
        return top_entries(self.app.console.id, self.app.config.cache_dir)
