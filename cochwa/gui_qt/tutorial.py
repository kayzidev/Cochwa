"""Visite guidée locale du premier lancement."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from cochwa.gui_qt import theme


class TutorialOverlay(QWidget):
    """Éclaire une zone réelle de la fenêtre sans modifier les pages visitées."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.initial_row = window.sidebar.currentRow()
        self.index = 0
        self.highlight = QRectF()
        self.navigation_highlight = QRectF()
        self.steps = [
            (
                "library",
                lambda: window.console_box.parentWidget(),
                "Choisissez une plateforme",
                "Ce sélecteur change la bibliothèque, la recherche et les classements de la console active.",
            ),
            (
                "library",
                lambda: window.sidebar,
                "Parcourez Cochwa",
                "La barre latérale donne accès à vos jeux, aux recommandations, aux émulateurs et aux téléchargements.",
            ),
            (
                "tools",
                lambda: window.tab_tools.panels["Steam"],
                "Préparez Steam",
                "Dans Outils, configurez Steam ROM Manager et lancez la synchronisation depuis ses raccourcis.",
            ),
            (
                "tools",
                lambda: window.tab_tools.panels["Bibliothèque"],
                "Entretenez vos jeux",
                "Export CSV, recherche de doublons et conversion CHD sont regroupés ici selon la plateforme.",
            ),
            (
                "settings",
                lambda: window.tab_settings.console_stack,
                "Réglez vos dossiers",
                "Choisissez le dossier de jeux et le lanceur de la console active dans Paramètres.",
            ),
            (
                "settings",
                lambda: window.tab_settings.igdb_panel,
                "Complétez le catalogue",
                "Ajoutez vos identifiants Twitch/IGDB pour enrichir automatiquement les jeux et les classements.",
            ),
            (
                "settings",
                lambda: window.tab_settings.save_button,
                "Enregistrez vos réglages",
                "Enregistrez vos changements. Le catalogue IGDB se mettra à jour en arrière-plan. Le tutoriel peut être relancé depuis Support.",
            ),
        ]
        self.setObjectName("tutorialOverlay")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus)

        self.card = QWidget(self)
        self.card.setObjectName("tutorialCard")
        self.card.setAttribute(Qt.WA_StyledBackground)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(10)
        self.progress = QLabel()
        self.progress.setObjectName("eyebrow")
        card_layout.addWidget(self.progress)
        self.page_label = QLabel()
        self.page_label.setObjectName("tutorialPage")
        card_layout.addWidget(self.page_label)
        self.title = QLabel()
        self.title.setObjectName("sectionTitle")
        self.title.setWordWrap(True)
        card_layout.addWidget(self.title)
        self.description = QLabel()
        self.description.setObjectName("muted")
        self.description.setWordWrap(True)
        card_layout.addWidget(self.description)
        actions = QHBoxLayout()
        self.skip = QPushButton("Ignorer")
        self.skip.clicked.connect(lambda: self.finish(skipped=True))
        actions.addWidget(self.skip)
        actions.addStretch()
        self.previous = QPushButton("Précédent")
        self.previous.clicked.connect(lambda: self.show_step(self.index - 1))
        actions.addWidget(self.previous)
        self.next = QPushButton("Suivant")
        self.next.setObjectName("primary")
        self.next.clicked.connect(self.advance)
        actions.addWidget(self.next)
        card_layout.addLayout(actions)
        self.card.setFixedWidth(370)
        self.resize(window.size())
        self.show_step(0)
        self.show()
        self.raise_()
        self.setFocus()

    def show_step(self, index):
        self.index = max(0, min(index, len(self.steps) - 1))
        route, target, title, description = self.steps[self.index]
        if route:
            self.window.navigate(route)
        widget = target()
        scroll = (
            self.window.tab_settings.scroll
            if route == "settings"
            else self.window.tab_tools.scroll
            if route == "tools"
            else None
        )
        if scroll and widget is not self.window.tab_settings.save_button:
            scroll.ensureWidgetVisible(widget, 12, 12)
        self.progress.setText(f"DÉCOUVERTE · {self.index + 1}/{len(self.steps)}")
        page_name = self.window.sidebar.item(self.window.routes[route]).text()
        self.page_label.setText(f"PAGE {page_name.upper()}")
        self.page_label.setAccessibleName(f"Page actuelle : {page_name}")
        self.title.setText(title)
        self.description.setText(description)
        self.previous.setEnabled(self.index > 0)
        self.next.setText("Terminer" if self.index == len(self.steps) - 1 else "Suivant")
        QTimer.singleShot(0, self._reposition)

    def advance(self):
        if self.index + 1 == len(self.steps):
            self.finish(skipped=False)
        else:
            self.show_step(self.index + 1)

    def _reposition(self):
        if not self.isVisible():
            return
        target = self.steps[self.index][1]()
        corner = target.mapTo(self.window, QPoint(0, 0))
        highlight = QRectF(
            corner.x() - 7, corner.y() - 7, target.width() + 14, target.height() + 14
        )
        route = self.steps[self.index][0]
        if route in {"tools", "settings"} and target is not self.window.tab_settings.save_button:
            scroll = (
                self.window.tab_tools.scroll
                if route == "tools"
                else self.window.tab_settings.scroll
            )
            viewport = scroll.viewport()
            top_left = viewport.mapTo(self.window, QPoint(0, 0))
            highlight = highlight.intersected(
                QRectF(top_left.x(), top_left.y(), viewport.width(), viewport.height())
            )
        self.highlight = highlight.intersected(QRectF(self.rect()))
        sidebar = self.window.sidebar
        current_item = sidebar.item(sidebar.currentRow())
        if current_item is not None:
            item_rect = sidebar.visualItemRect(current_item)
            item_corner = sidebar.viewport().mapTo(self.window, item_rect.topLeft())
            self.navigation_highlight = QRectF(
                item_corner.x() - 3,
                item_corner.y() - 3,
                item_rect.width() + 6,
                item_rect.height() + 6,
            ).intersected(QRectF(self.rect()))
        else:
            self.navigation_highlight = QRectF()
        self.card.adjustSize()
        width, height = self.card.width(), self.card.height()
        right = int(self.highlight.right()) + 20
        below = int(self.highlight.bottom()) + 20
        if right + width <= self.width() - 12:
            x, y = right, int(self.highlight.top())
        elif below + height <= self.height() - 12:
            x, y = int(self.highlight.left()), below
        else:
            x, y = int(self.highlight.left()), int(self.highlight.top()) - height - 20
        self.card.move(
            max(12, min(x, self.width() - width - 12)),
            max(12, min(y, self.height() - height - 12)),
        )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        shade = QPainterPath()
        shade.addRect(QRectF(self.rect()))
        opening = QPainterPath()
        opening.addRoundedRect(self.highlight, 12, 12)
        navigation = QPainterPath()
        navigation.addRoundedRect(self.navigation_highlight, 9, 9)
        painter.fillPath(shade.subtracted(opening).subtracted(navigation), QColor(5, 7, 13, 205))
        painter.setPen(QPen(QColor(theme.SECONDARY), 3))
        painter.drawRoundedRect(self.highlight, 12, 12)
        painter.setPen(QPen(QColor(theme.ACCENT), 2))
        painter.drawRoundedRect(self.navigation_highlight, 9, 9)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.finish(skipped=True)
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Right):
            self.advance()
        elif event.key() == Qt.Key_Left:
            self.show_step(self.index - 1)
        else:
            super().keyPressEvent(event)

    def finish(self, *, skipped):
        self.window.mark_tutorial_seen()
        self.hide()
        self.deleteLater()
        self.window._tutorial = None
        if skipped and self.initial_row >= 0:
            self.window.sidebar.setCurrentRow(self.initial_row)
