"""Recherche à la demande (Internet Archive + MiNERVA) avec pagination."""

from __future__ import annotations

import threading

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

from cochwa.gui_qt.cards import GameCard
from cochwa.gui_qt.grid import CardGrid
from cochwa.gui_qt.widgets import PageHeader

SOURCES = {"Toutes": "all", "Internet Archive": "ia_redump", "MiNERVA": "minerva"}


class SearchPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.generation = 0
        self.cancel = threading.Event()
        self.page = 1
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(14)
        layout.addWidget(
            PageHeader(
                "Explorer le catalogue",
                "Retrouvez un jeu, puis choisissez l’édition qui vous correspond.",
                "DÉCOUVRIR · PLAYSTATION 2",
            )
        )

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
            lambda: self.app.sidebar.setCurrentRow(2),
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
        """La recherche n'est branchée que sur des sources PS2 pour l'instant."""
        ps2 = self.app.console.id == "ps2"
        self.query.setEnabled(ps2)
        self.search_btn.setEnabled(ps2)
        for widget in (self.region, self.language, self.source, self.verified):
            widget.setEnabled(ps2)
        if not ps2:
            self.cancel.set()
            self.generation += 1
            self.busy.hide()
            self.search_btn.setText("Rechercher")
            self.prev.setEnabled(False)
            self.next.setEnabled(False)
            self.grid.clear()
            self.grid.set_empty(
                "Le catalogue disponible est celui de la PlayStation 2. Vous pouvez toujours ouvrir vos jeux Switch dans la bibliothèque.",
                "Catalogue PlayStation 2",
                "Ouvrir la bibliothèque",
                lambda: self.app.sidebar.setCurrentRow(0),
            )
            self._blocked_note = True
            self.status.setText(
                f"Recherche {self.app.console.name} indisponible : les sources "
                "(Internet Archive, MiNERVA) ne sont branchées que sur la PS2. "
                "La bibliothèque locale Switch est gérée dans l'onglet Bibliothèque."
            )
        elif getattr(self, "_blocked_note", False):
            self._blocked_note = False
            self.grid.set_empty(
                "Saisissez un titre PS2 pour découvrir ses éditions.", "Explorer les jeux PS2"
            )
            self.status.setText(
                "Chercher un titre ; les fichiers et éditions seront proposés avant téléchargement."
            )

    def do_search(self, page=1):
        if self.app.console.id != "ps2":
            self.activate()
            return
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
            source=SOURCES[self.source.currentText()],
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
                action_text="Voir la source torrent" if game.external else "Choisir les fichiers",
            )
            self.grid.add(card, index=i)
            self.app.cover(
                card, game.clean_title, ia_identifier=None if game.external else game.identifier
            )
        self.grid.set_empty(
            "" if result.games else "Essayez un titre plus court ou retirez certains filtres.",
            "Aucun jeu trouvé",
        )

    def _on_cover(self, base, path):
        if not path:
            return
        for card in self.grid.cards:
            if card.base_title == base:
                card.set_cover(str(path))
