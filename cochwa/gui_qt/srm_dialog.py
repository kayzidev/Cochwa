"""Assistant Steam : aperçu → installation des parseurs → synchronisation SRM."""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from cochwa.consoles import CONSOLES
from cochwa.gui_qt.widgets import PageHeader
from cochwa.services import srm


class SRMDialog(QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent or app)
        self.app = app
        self.plan = None
        self.setWindowTitle("Cochwa → Steam")
        self.resize(820, 650)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(
            PageHeader(
                "Vos consoles dans Steam",
                "Cochwa prépare les jeux, lanceurs et catégories. Aucun parseur à écrire.",
                "STEAM ROM MANAGER",
            )
        )
        self.platforms = {}
        row = QHBoxLayout()
        for console in CONSOLES:
            box = QCheckBox(console.name)
            box.setChecked(app.config.roms_dir(console) is not None)
            self.platforms[console.id] = box
            row.addWidget(box)
        row.addStretch()
        layout.addLayout(row)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.directory = self.path_row(form, "Dossier userData de SRM", srm.detect_srm_directory())
        self.steam_dir = self.path_row(form, "Dossier Steam", srm.detect_steam_directory())
        layout.addLayout(form)
        note = QLabel(
            "Les dossiers et lanceurs enregistrés dans Cochwa sont utilisés. Fermez SRM avant l’installation ; fermez Steam avant la synchronisation. Cochwa n’arrête aucun programme."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText(
            "1. Choisissez vos consoles.\n2. Préparez l’aperçu.\n3. Installez les préréglages puis synchronisez."
        )
        layout.addWidget(self.preview, stretch=1)
        self.replace_overlaps = QCheckBox(
            "Désactiver les anciens parseurs de ces dossiers pour éviter les doublons"
        )
        self.replace_overlaps.hide()
        layout.addWidget(self.replace_overlaps)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.prepare_button = QPushButton("Préparer l’aperçu")
        self.prepare_button.clicked.connect(self.prepare)
        buttons.addWidget(self.prepare_button)
        self.install_button = QPushButton("Installer les préréglages")
        self.install_button.setObjectName("primary")
        self.install_button.clicked.connect(self.install)
        self.install_button.setEnabled(False)
        buttons.addWidget(self.install_button)
        self.sync_button = QPushButton("Synchroniser avec Steam")
        self.sync_button.clicked.connect(self.sync)
        self.sync_button.setEnabled(False)
        buttons.addWidget(self.sync_button)
        layout.addLayout(buttons)
        close = QPushButton("Fermer")
        close.clicked.connect(self.reject)
        layout.addWidget(close)
        for field in (self.directory, self.steam_dir):
            field.textChanged.connect(self.invalidate)
        for box in self.platforms.values():
            box.toggled.connect(self.invalidate)
        self.generation = 0

    def path_row(self, form, title, path):
        field = QLineEdit(str(path or ""))
        field.setAccessibleName(title)
        row = QHBoxLayout()
        row.addWidget(field, stretch=1)
        browse = QPushButton("Choisir…")

        def pick():
            selected = QFileDialog.getExistingDirectory(self, title, field.text())
            if selected:
                field.setText(selected)

        browse.clicked.connect(pick)
        row.addWidget(browse)
        form.addRow(title, row)
        return field

    def invalidate(self):
        self.generation += 1
        self.plan = None
        self.install_button.setEnabled(False)
        self.sync_button.setEnabled(False)
        self.status.setText("Préparez un nouvel aperçu pour ces paramètres.")

    def prepare(self):
        if not self.directory.text().strip() or not self.steam_dir.text().strip():
            self.status.setText("Choisissez les dossiers SRM et Steam.")
            return
        self.invalidate()
        generation = self.generation
        directory, steam_dir = self.directory.text(), self.steam_dir.text()
        selected = [key for key, box in self.platforms.items() if box.isChecked()]
        self.prepare_button.setEnabled(False)
        self.status.setText("Lecture de vos bibliothèques…")

        def done(plan):
            self.prepare_button.setEnabled(True)
            if generation != self.generation:
                return
            self.plan = plan
            self.replace_overlaps.setVisible(bool(plan.overlap_ids))
            self.replace_overlaps.setChecked(False)
            lines = plan.summaries + [
                "",
                "Les parseurs personnels sont conservés.",
                "Les jeux PS2 préfèrent le CHD ; les variantes gardent leur titre.",
            ]
            if plan.overlaps:
                lines += [
                    "",
                    "Attention : des parseurs actifs couvrent déjà ces dossiers : "
                    + ", ".join(plan.overlaps),
                    "Ils peuvent créer des doublons. La case ci-dessous permet de les désactiver depuis Cochwa.",
                ]
            self.preview.setPlainText("\n".join(lines))
            self.install_button.setEnabled(True)
            self.status.setText("Prêt à installer. Une sauvegarde des réglages SRM sera créée.")

        def failed(error):
            self.prepare_button.setEnabled(True)
            self.status.setText(error)

        self.app.worker.submit(
            lambda: srm.prepare(self.app.config, directory, steam_dir, selected), done, failed
        )

    def install(self):
        if not self.plan:
            return
        try:
            backup = srm.install(self.plan, disable_overlaps=self.replace_overlaps.isChecked())
            self.install_button.setEnabled(False)
            default = srm.detect_srm_directory()
            self.sync_button.setEnabled(
                default is not None and default.resolve() == self.plan.directory.resolve()
            )
            self.status.setText(f"Préréglages installés. Sauvegarde : {backup.name}")
        except Exception as error:
            self.status.setText(str(error))

    def sync(self):
        answer = QMessageBox.question(
            self,
            "Synchroniser les jeux avec Steam",
            "SRM ajoutera les jeux de tous ses parseurs activés, y compris vos parseurs personnels. Steam et SRM doivent être fermés. Continuer ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.sync_button.setEnabled(False)
        self.status.setText("Synchronisation et recherche des jaquettes…")

        def done(message):
            self.sync_button.setEnabled(True)
            self.status.setText(message)

        self.app.worker.submit(lambda: srm.synchronize(self.app.config), done, done)
