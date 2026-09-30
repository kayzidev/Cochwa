"""Accès central aux outils existants, sans dupliquer leur logique métier."""

from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from cochwa.gui_qt.widgets import PageHeader, section


class ToolsPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        self.header = PageHeader(
            "Vos outils", "Entretenez votre bibliothèque et préparez vos jeux pour Steam."
        )
        layout.addWidget(self.header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        content = QVBoxLayout(body)
        content.setContentsMargins(0, 0, 8, 0)
        for title, description, actions in (
            (
                "Steam",
                "Préréglages par console, aperçu des modifications et synchronisation.",
                [
                    ("Configurer Steam ROM Manager", app.tab_settings.setup_srm),
                    ("Ouvrir Steam ROM Manager", app.tab_settings.open_srm),
                ],
            ),
            (
                "Bibliothèque",
                "Export, doublons vérifiés et conversion des disques.",
                [
                    ("Exporter en CSV", app.tab_library.export_csv),
                    ("Rechercher les doublons", app.tab_library.show_duplicates),
                    ("Convertir en CHD", app.tab_library.convert_all),
                ],
            ),
            (
                "Diagnostic",
                "Vérifiez les dossiers, lanceurs et outils de votre installation.",
                [("Diagnostic local", app.tab_settings.diagnose)],
            ),
        ):
            panel, box = section(title, description)
            for label, callback in actions:
                button = QPushButton(label)
                button.clicked.connect(lambda checked=False, action=callback: self.run(action))
                box.addWidget(button)
                if label == "Convertir en CHD":
                    self.convert = button
            content.addWidget(panel)
        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        content.addWidget(self.status)
        content.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

    def activate(self):
        self.header.eyebrow.setText(f"OUTILS · {self.app.console.name.upper()}")
        self.convert.setEnabled(self.app.console.disc_based)
        self.convert.setToolTip("Conversion réservée aux consoles à disques.")

    def run(self, action):
        if getattr(action, "__self__", None) is self.app.tab_library:
            self.app.navigate("library")
        action()
        self.status.setText(self.app.tab_library.status.text())
