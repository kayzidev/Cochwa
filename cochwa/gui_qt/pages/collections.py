"""Organisation personnelle de la bibliothèque de la console active."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cochwa.gui_qt.cards import GameCard
from cochwa.gui_qt.grid import CardGrid
from cochwa.gui_qt.widgets import PageHeader
from cochwa.gui_qt.window_chrome import FramelessDialog, confirm
from cochwa.services.collections import CollectionStore


class CollectionsPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.store = CollectionStore(app.config.state_dir)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        self.header = PageHeader(
            "Vos collections", "Regroupez vos jeux par envie, série ou occasion."
        )
        layout.addWidget(self.header)
        bar = QHBoxLayout()
        self.choice = QComboBox()
        self.choice.currentIndexChanged.connect(self.render)
        bar.addWidget(self.choice, 1)
        create = QPushButton("Nouvelle collection")
        create.setObjectName("primary")
        create.clicked.connect(lambda: self.edit())
        bar.addWidget(create)
        self.modify = QPushButton("Modifier")
        self.modify.clicked.connect(lambda: self.edit(self.choice.currentData()))
        bar.addWidget(self.modify)
        self.delete = QPushButton("Supprimer")
        self.delete.clicked.connect(self.remove)
        bar.addWidget(self.delete)
        layout.addLayout(bar)
        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.grid = CardGrid()
        layout.addWidget(self.grid, 1)
        self.app.covers.loaded.connect(self._cover)

    def activate(self):
        self.header.eyebrow.setText(f"COLLECTIONS · {self.app.console.name.upper()}")
        previous = self.choice.currentData()
        try:
            rows = [r for r in self.store.read() if r["platform"] == self.app.console.id]
        except (OSError, ValueError) as exc:
            self.app.error(str(exc))
            return
        self.choice.blockSignals(True)
        self.choice.clear()
        for row in rows:
            self.choice.addItem(row["name"], row)
        if previous:
            for i, row in enumerate(rows):
                if row["id"] == previous["id"]:
                    self.choice.setCurrentIndex(i)
        self.choice.blockSignals(False)
        self.render()

    def render(self, *_):
        row = self.choice.currentData()
        self.modify.setEnabled(bool(row))
        self.delete.setEnabled(bool(row))
        self.grid.clear()
        titles = set(row["titles"]) if row else set()
        games = [g for g in self.app.tab_library.games if g.title in titles]
        self.status.setText(
            f"{len(games)} jeux disponibles · {len(titles)} références enregistrées"
        )
        for i, game in enumerate(games):
            card = GameCard(
                game.title,
                subtitle=self.app.console.name,
                action=lambda g=game: self.app.tab_library.launch(g),
                action_text="▶  Jouer",
                secondary_action=lambda g=game: self.app.local_details(g),
                secondary_text="Détails et outils",
            )
            self.grid.add(card, index=i)
            self.app.cover(card, game.title)
        if not games:
            self.grid.set_empty(
                "Créez une collection et choisissez les jeux de votre bibliothèque."
                if not row
                else "Ajoutez des jeux à cette collection ou actualisez votre bibliothèque.",
                "Vos jeux, à votre manière" if not row else "Aucun jeu disponible",
                "Nouvelle collection" if not row else "Modifier la collection",
                lambda: self.edit(row),
            )

    def edit(self, row=None):
        console = self.app.console
        dialog = FramelessDialog(self)
        dialog.setWindowTitle("Modifier la collection" if row else "Nouvelle collection")
        dialog.resize(540, 520)
        box = QVBoxLayout(dialog)
        name = QLineEdit(row["name"] if row else "")
        name.setPlaceholderText("Nom de la collection")
        name.setMaxLength(80)
        box.addWidget(name)
        box.addWidget(QLabel(f"Jeux {console.name} · les fichiers restent à leur place"))
        selection = QListWidget()
        titles = set(row["titles"]) if row else set()
        available = {g.title for g in self.app.tab_library.games}
        for title in sorted(available | titles):
            item = QListWidgetItem(
                title + (" · indisponible" if title not in available else ""), selection
            )
            item.setData(Qt.UserRole, title)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if title in titles else Qt.Unchecked)
        box.addWidget(selection)
        error = QLabel()
        error.setWordWrap(True)
        box.addWidget(error)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Enregistrer")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")

        def save():
            try:
                saved = self.store.save(
                    name.text(),
                    console.id,
                    [
                        selection.item(i).data(Qt.UserRole)
                        for i in range(selection.count())
                        if selection.item(i).checkState() == Qt.Checked
                    ],
                    row["id"] if row else None,
                )
                dialog.accept()
                self.activate()
                for i in range(self.choice.count()):
                    if self.choice.itemData(i)["id"] == saved["id"]:
                        self.choice.setCurrentIndex(i)
            except (OSError, ValueError) as exc:
                error.setText(str(exc))

        buttons.accepted.connect(save)
        buttons.rejected.connect(dialog.reject)
        box.addWidget(buttons)
        dialog.exec()

    def remove(self):
        row = self.choice.currentData()
        if row and confirm(
            self,
            "Supprimer la collection",
            f"Supprimer « {row['name']} » ? Les jeux et leurs fichiers sont conservés.",
            accept_text="Supprimer",
            danger=True,
        ):
            try:
                self.store.remove(row["id"])
                self.activate()
            except (OSError, ValueError) as exc:
                self.app.error(str(exc))

    def _cover(self, platform, base, path):
        if platform == self.app.console.id and path:
            for card in self.grid.cards:
                if card.base_title == base:
                    card.set_cover(str(path))
