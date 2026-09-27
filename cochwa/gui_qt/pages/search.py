"""Recherche à la demande (Internet Archive + MiNERVA) avec pagination."""

from __future__ import annotations

import threading

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cochwa.gui_qt.cards import GameCard
from cochwa.gui_qt.grid import CardGrid

SOURCES = {"Toutes": "all", "Internet Archive": "ia_redump", "MiNERVA": "minerva"}


class SearchPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.generation = 0
        self.cancel = threading.Event()
        self.page = 1
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 8)

        bar = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Chercher un titre PS2…")
        self.query.returnPressed.connect(lambda: self.do_search())
        bar.addWidget(self.query, stretch=1)
        self.search_btn = QPushButton("Rechercher")
        self.search_btn.setObjectName("primary")
        self.search_btn.clicked.connect(lambda: self.do_search())
        bar.addWidget(self.search_btn)
        layout.addLayout(bar)

        filters = QHBoxLayout()
        self.verified = QCheckBox("Hash source Redump reconnu")
        filters.addWidget(self.verified)
        filters.addWidget(QLabel("Région"))
        self.region = QComboBox()
        self.region.setEditable(True)
        self.region.addItems(["", "Europe", "USA", "Japan"])
        filters.addWidget(self.region)
        filters.addWidget(QLabel("Langue"))
        self.language = QComboBox()
        self.language.setEditable(True)
        self.language.addItems(["", "Fr", "En", "De", "Es", "It", "Ja"])
        filters.addWidget(self.language)
        filters.addWidget(QLabel("Source"))
        self.source = QComboBox()
        self.source.addItems(list(SOURCES))
        filters.addWidget(self.source)
        filters.addStretch(1)
        layout.addLayout(filters)

        self.status = QLabel(
            "Chercher un titre ; les fichiers et éditions seront proposés avant téléchargement."
        )
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.grid = CardGrid()
        layout.addWidget(self.grid, stretch=1)

        pager = QHBoxLayout()
        self.prev = QPushButton("← Page précédente")
        self.prev.clicked.connect(lambda: self.do_search(self.page - 1))
        self.next = QPushButton("Page suivante →")
        self.next.clicked.connect(lambda: self.do_search(self.page + 1))
        self.prev.setEnabled(False)
        self.next.setEnabled(False)
        pager.addWidget(self.prev)
        pager.addStretch(1)
        pager.addWidget(self.next)
        layout.addLayout(pager)
        self.app.covers.loaded.connect(self._on_cover)

    def activate(self):
        """La recherche n'est branchée que sur des sources PS2 pour l'instant."""
        ps2 = self.app.console.id == "ps2"
        self.query.setEnabled(ps2)
        self.search_btn.setEnabled(ps2)
        if not ps2:
            self._blocked_note = True
            self.status.setText(
                f"Recherche {self.app.console.name} indisponible : les sources "
                "(Internet Archive, MiNERVA) ne sont branchées que sur la PS2. "
                "La bibliothèque locale Switch est gérée dans l'onglet Bibliothèque."
            )
        elif getattr(self, "_blocked_note", False):
            self._blocked_note = False
            self.status.setText(
                "Chercher un titre ; les fichiers et éditions seront proposés avant téléchargement."
            )

    def do_search(self, page=1):
        if self.app.console.id != "ps2":
            self.activate()
            return
        query = self.query.text().strip()
        if not query:
            return
        self.cancel.set()
        self.cancel = threading.Event()
        cancel = self.cancel
        self.generation += 1
        generation = self.generation
        page = max(1, page)
        self.page = page
        self.grid.clear()
        self.status.setText(f"Recherche « {query} » — page {page}…")
        self.prev.setEnabled(False)
        self.next.setEnabled(False)
        self.app.worker.submit(
            lambda: self.app.search.search(
                query,
                source=SOURCES[self.source.currentText()],
                page=page,
                verified_only=self.verified.isChecked(),
                region=self.region.currentText(),
                language=self.language.currentText(),
                cancel=cancel,
            ),
            lambda result: self.show(result, generation),
            lambda error: self.fail(error, generation),
        )

    def fail(self, error, generation):
        if generation == self.generation:
            self.status.setText("Erreur : " + error)

    def show(self, result, generation):
        if generation != self.generation:
            return
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
                action_text="Voir la source torrent" if game.external else "Choisir les fichiers",
            )
            self.grid.add(card, index=i)
            self.app.cover(
                card, game.clean_title, ia_identifier=None if game.external else game.identifier
            )
        self.grid.set_empty("" if result.games else "Aucun résultat pour cette recherche.")

    def _on_cover(self, base, path):
        if not path:
            return
        for card in self.grid.cards:
            if card.base_title == base:
                card.set_cover(str(path))
