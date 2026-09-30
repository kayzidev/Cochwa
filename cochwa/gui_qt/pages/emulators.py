"""Catalogue filtrable et raccourcis des émulateurs présents."""

import webbrowser

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from cochwa.gui_qt.widgets import PageHeader, navigation_icon, section
from cochwa.services.emulators import EmulatorRegistry, catalog


class ReadyPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setObjectName("section")
        from PySide6.QtCore import Qt

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
        self.platform.addItem("Toutes les consoles")
        self.platform.addItems(sorted({p for e in catalog() for p in e["platforms"]}))
        self.platform.currentTextChanged.connect(self.render)
        bar.addWidget(self.platform)
        refresh = QPushButton("Détecter à nouveau")
        refresh.clicked.connect(self.activate)
        bar.addWidget(refresh)
        layout.addLayout(bar)
        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        self.rows = QVBoxLayout(body)
        self.rows.setContentsMargins(0, 8, 8, 8)
        self.rows.setSpacing(14)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

    def activate(self):
        try:
            self.items = self.registry.detect()
            self.render()
            self.app.tab_library.ready.refresh()
        except (OSError, ValueError) as exc:
            self.app.error(str(exc))

    def render(self, *_):
        while self.rows.count():
            widget = self.rows.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        text = self.query.text().casefold()
        platform = self.platform.currentText()
        items = [
            e
            for e in self.items
            if text in (e["name"] + " " + " ".join(e["platforms"])).casefold()
            and (self.platform.currentIndex() == 0 or platform in e["platforms"])
        ]
        self.status.setText(
            f"{len(items)} projets · {sum(e['ready'] for e in self.items)} installations / lanceurs reconnus. "
            "Bibliothèque et lancement des ROMs intégrés : PS2 et Switch."
        )
        for item in items:
            state = (
                "Disponible"
                if item["command"]
                else (
                    "Lanceur configuré"
                    if item["configured"]
                    else ("Chemin indisponible" if item["custom"] else "À ajouter")
                )
            )
            panel, box = section(item["name"] + "  ·  " + state, " / ".join(item["platforms"]))
            detail = QLabel(item["note"])
            detail.setWordWrap(True)
            box.addWidget(detail)
            if item["origin"]:
                location = QLabel(item["origin"])
                location.setObjectName("cardMeta")
                location.setWordWrap(True)
                box.addWidget(location)
            actions = QHBoxLayout()
            for label, callback in (
                ("Ouvrir", lambda checked=False, eid=item["id"]: self.open_emulator(eid)),
                ("Choisir un exécutable…", lambda checked=False, eid=item["id"]: self.add(eid)),
                ("Site officiel ↗", lambda checked=False, url=item["url"]: webbrowser.open(url)),
            ):
                button = QPushButton(label)
                if label == "Ouvrir":
                    button.setEnabled(bool(item["command"]))
                    button.setObjectName("primary")
                button.clicked.connect(callback)
                actions.addWidget(button)
            box.addLayout(actions)
            if item["custom"]:
                forget = QPushButton("Oublier ce chemin personnalisé")
                forget.clicked.connect(lambda checked=False, eid=item["id"]: self.forget(eid))
                box.addWidget(forget)
            if item["integration"]:
                configure = QPushButton("Configurer les jeux et le lanceur dans Cochwa")
                configure.clicked.connect(
                    lambda checked=False, cid=item["integration"]: self.configure(cid)
                )
                box.addWidget(configure)
            self.rows.addWidget(panel)
        if not items:
            self.rows.addWidget(QLabel("Aucun émulateur ne correspond aux filtres."))
        self.rows.addStretch()

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
