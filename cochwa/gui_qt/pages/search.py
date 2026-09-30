"""Recherche à la demande (Internet Archive + MiNERVA) avec pagination."""

from __future__ import annotations

import threading
import webbrowser
from difflib import SequenceMatcher

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from cochwa.catalog import catalog_entries
from cochwa.gui_qt.cards import GameCard
from cochwa.gui_qt.grid import CardGrid
from cochwa.gui_qt.widgets import PageHeader
from cochwa.services.relevance import normalized

SOURCES = {"Toutes": "all", "Internet Archive": "ia_redump", "MiNERVA": "minerva"}


class SearchPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.generation = 0
        self.cancel = threading.Event()
        self.page = 1
        self.platform = app.console.id
        self.contexts = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(14)
        self.header = PageHeader(
            "Explorer le catalogue",
            "Retrouvez un jeu, puis choisissez l’édition qui vous correspond.",
            "DÉCOUVRIR · PLAYSTATION 2",
        )
        layout.addWidget(self.header)

        bar = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Rechercher un jeu PS2…")
        self.query.setAccessibleName("Titre du jeu à rechercher")
        self.query.setClearButtonEnabled(True)
        self.query.returnPressed.connect(lambda: self.do_search())
        bar.addWidget(self.query, stretch=1)
        self.search_btn = QPushButton("Rechercher")
        self.search_btn.setObjectName("primary")
        self.search_btn.clicked.connect(lambda: self.do_search())
        bar.addWidget(self.search_btn)
        layout.addLayout(bar)

        filters = QHBoxLayout()
        self.verified = QCheckBox("Empreinte reconnue par Redump")
        self.verified.setToolTip(
            "Filtrer les fichiers dont le hash source est identifié dans Redump."
        )
        filters.addWidget(QLabel("Région"))
        self.region = QComboBox()
        self.region.setEditable(True)
        self.region.addItems(["Toutes", "Europe", "USA", "Japan"])
        filters.addWidget(self.region)
        filters.addWidget(QLabel("Langue"))
        self.language = QComboBox()
        self.language.setEditable(True)
        self.language.addItems(["Toutes", "Fr", "En", "De", "Es", "It", "Ja"])
        filters.addWidget(self.language)
        filters.addWidget(QLabel("Source"))
        self.source = QComboBox()
        self.source.addItems(list(SOURCES))
        filters.addWidget(self.source)
        filters.addStretch(1)
        layout.addLayout(filters)
        options = QHBoxLayout()
        options.addWidget(self.verified)
        options.addStretch()
        reset = QPushButton("Effacer les filtres")
        reset.setObjectName("secondaryAction")
        reset.clicked.connect(self.reset_filters)
        options.addWidget(reset)
        layout.addLayout(options)
        self.busy = QProgressBar()
        self.busy.setRange(0, 0)
        self.busy.setTextVisible(False)
        self.busy.setFixedHeight(4)
        self.busy.hide()
        layout.addWidget(self.busy)

        self.status = QLabel(
            "Chercher un titre ; les fichiers et éditions seront proposés avant téléchargement."
        )
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.grid = CardGrid()
        layout.addWidget(self.grid, stretch=1)
        self.grid.set_empty(
            "Recherchez un titre ou parcourez la sélection du jour.",
            "Votre prochain jeu commence ici",
            "Découvrir les recommandations",
            lambda: self.app.navigate("recommended"),
        )

        pager = QHBoxLayout()
        self.prev = QPushButton("← Page précédente")
        self.prev.clicked.connect(lambda: self.do_search(self.page - 1))
        self.next = QPushButton("Page suivante →")
        self.next.clicked.connect(lambda: self.do_search(self.page + 1))
        self.prev.setEnabled(False)
        self.next.setEnabled(False)
        pager.addWidget(self.prev)
        pager.addStretch(1)
        self.page_label = QLabel("Page 1")
        self.page_label.setObjectName("muted")
        pager.addWidget(self.page_label)
        pager.addStretch(1)
        pager.addWidget(self.next)
        layout.addLayout(pager)
        self.app.covers.loaded.connect(self._on_cover)

    def reset_filters(self):
        self.verified.setChecked(False)
        self.region.setCurrentIndex(0)
        self.language.setCurrentIndex(0)
        self.source.setCurrentIndex(0)

    def activate(self):
        console = self.app.console
        changed = console.id != self.platform
        if changed:
            self.contexts[self.platform] = (
                self.query.text(),
                self.region.currentText(),
                self.language.currentText(),
            )
            self.platform = console.id
            self.cancel.set()
            self.generation += 1
            self.grid.clear()
            self.busy.hide()
            self.search_btn.setText("Rechercher")
            self.page = 1
            self.page_label.setText("Page 1")
            self.prev.setEnabled(False)
            self.next.setEnabled(False)
            query, region, language = self.contexts.get(self.platform, ("", "Toutes", "Toutes"))
            self.query.setText(query)
            self.region.setCurrentText(region)
            self.language.setCurrentText(language)
            self.source.clear()
            self.source.addItems(
                ["Internet Archive"] if self.platform == "switch" else list(SOURCES)
            )
            self.grid.set_empty(
                f"Recherchez un titre {console.name} pour découvrir ses éditions.",
                f"Explorer les jeux {console.name}",
            )
        self.header.eyebrow.setText(f"DÉCOUVRIR · {console.name.upper()}")
        self.query.setPlaceholderText(f"Rechercher un jeu {console.name}…")
        self.verified.setVisible(console.disc_based)
        if not console.disc_based:
            self.verified.setChecked(False)
        if changed:
            self.status.setText(
                "NSP/XCI : fichiers directs et fiches d’archives externes. Empreintes source, sans certification Redump."
                if self.platform == "switch"
                else "Choisissez une édition PS2 avant le téléchargement."
            )

    def do_search(self, page=1):
        query = self.query.text().strip()
        if not query:
            self.query.setFocus()
            self.status.setText("Saisissez un titre pour lancer la recherche.")
            return
        self.cancel.set()
        self.cancel = threading.Event()
        cancel = self.cancel
        self.generation += 1
        generation = self.generation
        page = max(1, page)
        self.page = page
        self.grid.clear()
        self.grid.set_empty("Les éditions et fichiers vont apparaître ici.", "Recherche en cours…")
        self.busy.show()
        self.search_btn.setText("Relancer")
        self.page_label.setText(f"Page {page}")
        self.status.setText(f"Recherche « {query} » — page {page}…")
        self.prev.setEnabled(False)
        self.next.setEnabled(False)
        filters = dict(
            source="ia_switch" if self.platform == "switch" else SOURCES[self.source.currentText()],
            platform=self.platform,
            verified_only=self.verified.isChecked(),
            region="" if self.region.currentText() == "Toutes" else self.region.currentText(),
            language="" if self.language.currentText() == "Toutes" else self.language.currentText(),
        )
        self.app.worker.submit(
            lambda: self.app.search.search(
                query,
                page=page,
                **filters,
                cancel=cancel,
            ),
            lambda result: self.show(result, generation),
            lambda error: self.fail(error, generation),
        )

    def fail(self, error, generation):
        if generation == self.generation:
            self.busy.hide()
            self.search_btn.setText("Rechercher")
            self.status.setText("La recherche n’a pas abouti : " + error)
            self.grid.set_empty(
                "Vérifiez votre connexion puis réessayez.",
                "Recherche interrompue",
                "Réessayer",
                lambda: self.do_search(self.page),
            )

    def show(self, result, generation):
        if generation != self.generation:
            return
        self.busy.hide()
        self.search_btn.setText("Rechercher")
        self.status.setText(
            f"{len(result.games)} résultats sur cette page · {result.total_items} items source · "
            + " / ".join(result.warnings)
        )
        self.prev.setEnabled(self.page > 1)
        self.next.setEnabled(result.has_more)
        if result.suggestions:
            self.status.setText(
                self.status.text() + " · Suggestions : " + " / ".join(result.suggestions)
            )
        for i, game in enumerate(result.games):
            card = GameCard(
                game.clean_title,
                subtitle=("Internet Archive · " if not game.external else "")
                + game.label
                + (f" · {len(game.alternatives)} copie(s)" if game.alternatives else ""),
                size_bytes=game.total_size,
                action=lambda g=game: self.app.details(g),
                action_text="Ouvrir la fiche source" if game.external else "Choisir les fichiers",
            )
            self.grid.add(card, index=i)
            self.app.cover(
                card,
                game.clean_title,
                ia_identifier=None if game.external else game.identifier,
            )

            def apply_metadata(
                metadata, target=card, game_title=game.clean_title, platform=game.platform
            ):
                if metadata and isValid(target):
                    target.set_igdb_metadata(metadata)
                    self.app.covers.request_igdb_cover(
                        game_title, metadata.get("cover_url", ""), platform
                    )

            self.app.metadata.request(
                game.clean_title,
                game.platform,
                apply_metadata,
            )
        if not result.games and not result.warnings:
            fallback = self._igdb_match(self.query.text().strip())
            if fallback:
                card = GameCard(
                    fallback["title"],
                    subtitle="Fiche IGDB · aucune édition Internet Archive trouvée",
                    action=lambda url=fallback["igdb_url"]: webbrowser.open(url),
                    action_text="Ouvrir la fiche IGDB",
                )
                self.grid.add(card)
                if self.app.start_workers and fallback.get("cover_url"):
                    self.app.covers.request_igdb_cover(
                        fallback["title"], fallback["cover_url"], self.app.console.id
                    )
        self.grid.set_empty(
            "" if result.games else "Essayez un titre plus court ou retirez certains filtres.",
            "Aucun jeu trouvé",
        )

    def _igdb_match(self, query):
        target = normalized(query)
        candidates = []
        for entry in catalog_entries(self.platform, self.app.config.cache_dir):
            url = entry.get("igdb_url", "")
            if not url:
                continue
            title = normalized(entry.get("title", ""))
            ratio = SequenceMatcher(None, target, title).ratio()
            if ratio >= 0.9:
                candidates.append((ratio, entry))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.04:
            return None
        return candidates[0][1]

    def _on_cover(self, platform, base, path):
        if platform != self.app.console.id or not path:
            return
        for card in self.grid.cards:
            if card.base_title == base:
                card.set_cover(str(path))
