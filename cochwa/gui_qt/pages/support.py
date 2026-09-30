"""Support : liens vers les émulateurs, Steam ROM Manager et le projet GitHub."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from cochwa.consoles import CONSOLES
from cochwa.gui_qt.widgets import PageHeader, ResponsiveGrid, section

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
        content = QVBoxLayout(body)
        content.setContentsMargins(0, 0, 8, 0)
        content.setSpacing(16)
        cards = ResponsiveGrid(min_card_width=320)
        content.addWidget(cards)
        tutorial, box = section(
            "Découvrir Cochwa", "Retrouvez les zones essentielles de l’application pas à pas."
        )
        row = QHBoxLayout()
        replay = QPushButton("Revoir le tutoriel")
        replay.clicked.connect(app.start_tutorial)
        row.addWidget(replay)
        row.addStretch()
        box.addLayout(row)
        cards.add_card(tutorial)
        for console in CONSOLES:
            cards.add_card(
                self._link_card(
                    f"{console.emulator} · {console.name}",
                    console.emulator_url,
                    "Site officiel et téléchargements de l’émulateur.",
                )
            )
        cards.add_card(
            self._link_card(
                "Steam ROM Manager",
                SRM_URL,
                "Préparez vos jeux pour Steam et synchronisez-les depuis SRM.",
            )
        )
        cards.add_card(
            self._link_card(
                "Cochwa sur GitHub", PROJECT_URL, "Code source, versions et suivi du projet."
            )
        )
        cards.add_card(
            self._link_card(
                "Signaler un bug",
                PROJECT_URL + "/issues",
                "Décrivez le problème et joignez le diagnostic local.",
            )
        )
        content.addStretch(1)

        about = QLabel(
            "Cochwa n'héberge aucun contenu : il interroge des catalogues "
            "publics (Internet Archive, MiNERVA) et renvoie vers leurs pages."
        )
        about.setObjectName("muted")
        about.setWordWrap(True)
        content.addWidget(about)

    def _link_card(self, title, url, description):
        panel, box = section(title, description)
        link = QLabel(url)
        link.setObjectName("muted")
        link.setWordWrap(True)
        link.setTextInteractionFlags(Qt.TextSelectableByMouse)
        box.addWidget(link)
        row = QHBoxLayout()
        button = QPushButton(f"Ouvrir {title.split(' · ')[0]} ↗")
        button.setToolTip(url)
        button.clicked.connect(lambda _checked=False, u=url: QDesktopServices.openUrl(QUrl(u)))
        row.addWidget(button)
        row.addStretch()
        box.addLayout(row)
        return panel
