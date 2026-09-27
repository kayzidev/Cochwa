"""Support : liens vers les émulateurs, Steam ROM Manager et le projet GitHub."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from cochwa.consoles import CONSOLES
from cochwa.gui_qt import theme
from cochwa.gui_qt.widgets import PageHeader

PROJECT_URL = "https://github.com/kayzidev/Cochwa"
SRM_URL = "https://steamgriddb.github.io/steam-rom-manager/"


class SupportPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(14)
        layout.addWidget(
            PageHeader(
                "Un coup de main ?", "Les ressources utiles pour profiter de vos jeux.", "SUPPORT"
            )
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout.addWidget(scroll, stretch=1)
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(16)
        layout.addWidget(self._section("Émulateurs"))
        for console in CONSOLES:
            layout.addLayout(
                self._link(
                    f"{console.emulator} — {console.name}",
                    console.emulator_url,
                    f"Site et téléchargements de l'émulateur {console.name} utilisé par Cochwa.",
                )
            )

        layout.addWidget(self._section("Intégration Steam"))
        layout.addLayout(
            self._link(
                "Steam ROM Manager",
                SRM_URL,
                "Ajoute les ROMs à Steam : ouvrir SRM, Parse, Preview, "
                "« Save apps to Steam » (redémarrage de Steam manuel).",
            )
        )

        layout.addWidget(self._section("Projet"))
        layout.addLayout(
            self._link(
                "Cochwa sur GitHub",
                PROJECT_URL,
                "Code source, releases et suivi du projet.",
            )
        )
        layout.addLayout(
            self._link(
                "Signaler un bug",
                PROJECT_URL + "/issues",
                "Ouvrir un ticket : décrire le contexte, joindre le diagnostic "
                "local (onglet Paramètres).",
            )
        )
        layout.addStretch(1)

        about = QLabel(
            "Cochwa n'héberge aucun contenu : il interroge des catalogues "
            "publics (Internet Archive, MiNERVA) et renvoie vers leurs pages."
        )
        about.setObjectName("muted")
        about.setWordWrap(True)
        layout.addWidget(about)

    def _section(self, text):
        label = QLabel(f"<b>{text}</b>")
        label.setContentsMargins(0, 10, 0, 2)
        return label

    def _link(self, text, url, description):
        """Bouton d'ouverture dans le navigateur + description + URL visible."""
        row = QVBoxLayout()
        row.setSpacing(8)
        button = QPushButton(text)
        button.setToolTip(url)
        button.setStyleSheet("text-align: left; padding: 12px 16px;")
        # clicked émet un booléen « checked » : ne pas le passer à openUrl.
        button.clicked.connect(lambda _checked=False, u=url: QDesktopServices.openUrl(QUrl(u)))
        row.addWidget(button)
        desc = QLabel(f"{description}<br><span style='color:{theme.ACCENT}'>{url}</span>")
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        desc.setTextInteractionFlags(Qt.TextSelectableByMouse)  # URL copiable
        row.addWidget(desc, stretch=1)
        return row
