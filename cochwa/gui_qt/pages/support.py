"""Support : liens vers les émulateurs, Steam ROM Manager et le projet GitHub."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from cochwa.consoles import CONSOLES

PROJECT_URL = "https://github.com/kayzidev/Cochwa"
SRM_URL = "https://steamgriddb.github.io/steam-rom-manager/"


class SupportPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)
        heading = QLabel("Support & liens utiles")
        heading.setObjectName("heading")
        layout.addWidget(heading)

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
        row = QHBoxLayout()
        button = QPushButton(text)
        button.setToolTip(url)
        # clicked émet un booléen « checked » : ne pas le passer à openUrl.
        button.clicked.connect(lambda _checked=False, u=url: QDesktopServices.openUrl(QUrl(u)))
        row.addWidget(button)
        desc = QLabel(f"{description}<br><span style='color:#66c0f4'>{url}</span>")
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        desc.setTextInteractionFlags(Qt.TextSelectableByMouse)  # URL copiable
        row.addWidget(desc, stretch=1)
        return row
