"""Catalogue filtrable et raccourcis des émulateurs présents."""

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from cochwa.gui_qt.emulator_art import emulator_artwork
from cochwa.gui_qt.widgets import PageHeader, navigation_icon
from cochwa.services.emulator_filters import PLATFORMS, brand_label, filter_emulators
from cochwa.services.emulators import EmulatorRegistry, catalog


class ReadyPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setObjectName("section")
        self.setAttribute(Qt.WA_StyledBackground)
        self.compact = False
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(18, 16, 18, 16)
        self.refresh()

    def refresh(self):
        while self.box.count():
            widget = self.box.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        title = QLabel("Prêt à jouer")
        title.setObjectName("sectionTitle")
        self.box.addWidget(title)
        hint = QLabel("Émulateurs reconnus sur cet ordinateur.")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        self.box.addWidget(hint)
        hint.setVisible(not self.compact)
        try:
            ready = [e for e in EmulatorRegistry(self.app.config).detect() if e["ready"]]
        except (OSError, ValueError):
            ready = []
        ready.sort(key=lambda e: e["integration"] != self.app.console.id)
        title.setText(f"Prêt à jouer · {len(ready)} reconnu{'s' if len(ready) > 1 else ''}")
        for item in ready[:4] if not self.compact else []:
            name = "Ryubing" if item["id"] == "ryubing" else item["name"]
            state = "Disponible" if item["command"] else "Configuré"
            button = QPushButton(f"{name}  ·  {state}  ›")
            button.setIcon(navigation_icon("Émulateurs"))
            button.setToolTip(
                item["origin"]
                + (
                    " — ouvrir l’émulateur"
                    if item["command"]
                    else " — voir les jeux de cette console"
                )
            )
            button.clicked.connect(lambda checked=False, e=item: self.open_item(e))
            self.box.addWidget(button)
        if not ready and not self.compact:
            label = QLabel("Ajoutez un émulateur pour retrouver ici vos raccourcis.")
            label.setWordWrap(True)
            label.setObjectName("muted")
            self.box.addWidget(label)
        add = QPushButton("Gérer les émulateurs  +")
        add.setObjectName("primary")
        add.clicked.connect(lambda: self.app.navigate("emulators"))
        self.box.addWidget(add)
        note = QLabel("BIOS, firmware et compatibilité à vérifier dans chaque émulateur.")
        note.setObjectName("cardMeta")
        note.setWordWrap(True)
        self.box.addWidget(note)
        note.setVisible(not self.compact)
        self.box.addStretch()

    def set_compact(self, compact):
        if compact != self.compact:
            self.compact = compact
            self.refresh()

    def open_item(self, item):
        if item["command"]:
            self.app.tab_emulators.open_emulator(item["id"])
        else:
            from cochwa.consoles import CONSOLES

            index = next(i for i, c in enumerate(CONSOLES) if c.id == item["integration"])
            self.app.select_console(index)
            self.app.navigate("library")


class EmulatorCard(QWidget):
    """Carte compacte avec illustration carrée et actions regroupées."""

    def __init__(self, item, page):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setFixedHeight(342)
        self.setAccessibleName(f"{item['name']} · {brand_label(item)}")
        box = QVBoxLayout(self)
        box.setContentsMargins(14, 14, 14, 14)
        box.setSpacing(5)

        artwork = QLabel()
        artwork.setFixedSize(116, 116)
        artwork.setPixmap(emulator_artwork(item["name"], brand_label(item)))
        artwork.setAccessibleName(f"Illustration de {item['name']}")
        box.addWidget(artwork, alignment=Qt.AlignHCenter)

        title = QLabel(item["name"])
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        title.setFixedHeight(35)
        box.addWidget(title)

        platforms = QLabel(" · ".join(item["platforms"]))
        platforms.setObjectName("cardMeta")
        platforms.setAlignment(Qt.AlignCenter)
        platforms.setWordWrap(True)
        platforms.setFixedHeight(34)
        platforms.setToolTip(" / ".join(item["platforms"]))
        box.addWidget(platforms)

        state = (
            "Disponible"
            if item["command"]
            else "Lanceur configuré"
            if item["configured"]
            else "Chemin indisponible"
            if item["custom"]
            else "À ajouter"
        )
        badge = QLabel(f"{brand_label(item)}  ·  {state}")
        badge.setObjectName("cardMeta")
        badge.setAlignment(Qt.AlignCenter)
        badge.setToolTip(item["origin"] or item["note"])
        box.addWidget(badge)

        note = QLabel(item["note"])
        note.setObjectName("muted")
        note.setAlignment(Qt.AlignCenter)
        note.setWordWrap(True)
        note.setFixedHeight(35)
        note.setToolTip(item["note"])
        box.addWidget(note)
        box.addStretch()

        actions = QHBoxLayout()
        primary = QPushButton("Ouvrir" if item["command"] else "Choisir un exécutable…")
        primary.setObjectName("primary")
        primary.setAccessibleName(f"{primary.text()} : {item['name']}")
        if item["command"]:
            primary.clicked.connect(lambda _=False, eid=item["id"]: page.open_emulator(eid))
        else:
            primary.clicked.connect(lambda _=False, eid=item["id"]: page.add(eid))
        actions.addWidget(primary, 1)

        more = QPushButton("⋯")
        more.setFixedWidth(38)
        more.setAccessibleName(f"Autres actions : {item['name']}")
        menu = QMenu(more)
        menu.addAction("Choisir un exécutable…", lambda _=False, eid=item["id"]: page.add(eid))
        menu.addAction("Site officiel ↗", lambda _=False, url=item["url"]: webbrowser.open(url))
        if item["custom"]:
            menu.addAction(
                "Oublier ce chemin personnalisé",
                lambda _=False, eid=item["id"]: page.forget(eid),
            )
        if item["integration"]:
            menu.addAction(
                "Configurer les jeux et le lanceur dans Cochwa",
                lambda _=False, cid=item["integration"]: page.configure(cid),
            )
        more.setMenu(menu)
        actions.addWidget(more)
        box.addLayout(actions)


class EmulatorGrid(QScrollArea):
    """Trois cartes par rangée, deux ou une quand la fenêtre rétrécit."""

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.flow = QGridLayout(self.body)
        self.flow.setContentsMargins(0, 8, 8, 8)
        self.flow.setHorizontalSpacing(14)
        self.flow.setVerticalSpacing(14)
        self.flow.setAlignment(Qt.AlignTop)
        self.setWidget(self.body)
        self.cards = []
        self.empty = QLabel("Aucun émulateur ne correspond aux filtres.")
        self.empty.setObjectName("empty")

    def set_cards(self, cards):
        while self.flow.count():
            widget = self.flow.takeAt(0).widget()
            if widget:
                widget.hide()
                if widget is not self.empty:
                    widget.deleteLater()
        self.cards = cards
        self._relayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self):
        while self.flow.count():
            self.flow.takeAt(0)
        if not self.cards:
            self.body.setMinimumHeight(0)
            self.flow.addWidget(self.empty, 0, 0)
            return
        available = max(0, self.viewport().width() - 8)
        columns = min(3, max(1, (available + 14) // (236 + 14)))
        width = max(236, (available - 14 * (columns - 1)) // columns)
        rows = (len(self.cards) + columns - 1) // columns
        self.body.setMinimumHeight(rows * 342 + (rows - 1) * 14 + 16)
        for index, card in enumerate(self.cards):
            card.setFixedWidth(width)
            self.flow.addWidget(card, index // columns, index % columns, Qt.AlignTop)


class EmulatorsPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.registry = EmulatorRegistry(app.config)
        self.items = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.addWidget(
            PageHeader(
                "Vos émulateurs",
                "Retrouvez les projets de référence, ajoutez vos installations et ouvrez-les depuis Cochwa.",
                "ÉMULATEURS · TOUTES LES PLATEFORMES",
            )
        )
        bar = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Rechercher un émulateur ou une console…")
        self.query.setClearButtonEnabled(True)
        self.query.setAccessibleName("Rechercher un émulateur")
        self.query.textChanged.connect(self.render)
        bar.addWidget(self.query, 1)
        self.platform = QComboBox()
        self.platform.setAccessibleName("Filtrer les émulateurs par console")
        self.platform.addItem("Toutes", "")
        self.platform.addItems(sorted({p for e in catalog() for p in e["platforms"]}))
        self.platform.currentIndexChanged.connect(self.render)
        refresh = QPushButton("Détecter à nouveau")
        refresh.clicked.connect(self.activate)
        bar.addWidget(refresh)
        layout.addLayout(bar)

        filters = QHBoxLayout()
        self.manufacturer = QComboBox()
        self.manufacturer.setAccessibleName("Filtrer par constructeur")
        self.manufacturer.addItem("Tous", "")
        self.manufacturer.addItems(sorted({f.manufacturer for f in PLATFORMS.values()}))
        self.manufacturer.currentIndexChanged.connect(self.render)
        self.decade = QComboBox()
        self.decade.setAccessibleName("Filtrer par décennie")
        self.decade.addItem("Toutes", None)
        for decade in sorted({f.year // 10 * 10 for f in PLATFORMS.values() if f.year}):
            self.decade.addItem(f"Années {decade}", decade)
        self.decade.currentIndexChanged.connect(self.render)
        self.processor = QComboBox()
        self.processor.setAccessibleName("Filtrer par bits ou architecture du processeur")
        self.processor.addItem("Tous", "")
        for value in ("8 bits", "16 bits", "32 bits", "64 bits", "128 bits", "x86"):
            self.processor.addItem(value, value)
        self.processor.setToolTip("Largeur du processeur ; x86 désigne une architecture.")
        self.processor.currentIndexChanged.connect(self.render)
        for label, combo in (
            ("CONSOLE", self.platform),
            ("CONSTRUCTEUR", self.manufacturer),
            ("DÉCENNIE", self.decade),
            ("BITS / ARCHITECTURE", self.processor),
        ):
            column = QVBoxLayout()
            column.setSpacing(4)
            heading = QLabel(label)
            heading.setObjectName("eyebrow")
            column.addWidget(heading)
            column.addWidget(combo)
            filters.addLayout(column, 1)
        layout.addLayout(filters)

        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.grid = EmulatorGrid()
        layout.addWidget(self.grid, 1)

    def activate(self):
        try:
            self.items = self.registry.detect()
            self.render()
            self.app.tab_library.ready.refresh()
        except (OSError, ValueError) as exc:
            self.app.error(str(exc))

    def render(self, *_):
        items = filter_emulators(
            self.items,
            query=self.query.text(),
            platform=self.platform.currentText() if self.platform.currentIndex() else "",
            manufacturer=self.manufacturer.currentText()
            if self.manufacturer.currentIndex()
            else "",
            decade=self.decade.currentData(),
            processor=self.processor.currentData() or "",
        )
        self.status.setText(
            f"{len(items)} projet{'s' if len(items) != 1 else ''} · "
            f"{sum(e['ready'] for e in self.items)} installations / lanceurs reconnus. "
            "Tri par constructeur. Bibliothèque et lancement des ROMs intégrés : PS2 et Switch."
        )
        self.grid.set_cards([EmulatorCard(item, self) for item in items])

    def configure(self, console_id):
        from cochwa.consoles import CONSOLES

        self.app.select_console(next(i for i, c in enumerate(CONSOLES) if c.id == console_id))
        self.app.navigate("settings")

    def add(self, emulator_id):
        path, _ = QFileDialog.getOpenFileName(
            self, "Ajouter un émulateur installé · binaire, AppImage ou script"
        )
        if path:
            try:
                self.registry.set_path(emulator_id, path)
                self.activate()
                self.app.notify("Émulateur ajouté aux raccourcis", "success")
            except (OSError, ValueError) as exc:
                self.app.error(str(exc))

    def forget(self, emulator_id):
        try:
            self.registry.clear_path(emulator_id)
            self.activate()
        except (OSError, ValueError) as exc:
            self.app.error(str(exc))

    def open_emulator(self, emulator_id):
        try:
            self.registry.open(emulator_id)
            self.app.notify("Ouverture de l’émulateur…")
        except (OSError, ValueError) as exc:
            self.app.error(str(exc))
