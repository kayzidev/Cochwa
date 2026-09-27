"""Grille adaptative de jaquettes, alignée en haut, avec état vide contextualisé."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QScrollArea, QVBoxLayout, QWidget

from cochwa.gui_qt.widgets import EmptyState


class CardGrid(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.inner = QWidget()
        outer = QVBoxLayout(self.inner)
        outer.setContentsMargins(0, 8, 0, 8)
        self.flow = QGridLayout()
        self.flow.setContentsMargins(0, 0, 0, 0)
        self.flow.setSpacing(16)
        self.flow.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        outer.addLayout(self.flow)
        self.empty = EmptyState("", "")
        self.empty_label = self.empty.description
        self.empty.hide()
        outer.addWidget(self.empty, stretch=1)
        outer.addStretch()
        self.setWidget(self.inner)
        self.cards = []
        self.columns = 0

    def clear(self):
        while self.flow.count():
            self.flow.takeAt(0)
        for card in self.cards:
            card.hide()
            card.deleteLater()
        self.cards = []
        self._update_empty()

    def add(self, card, animate=True, index=None):
        self.cards.append(card)
        # Pas d'animation d'opacité imbriquée : garde les jaquettes nettes au scroll.
        self._relayout()
        card.show()
        self._update_empty()

    def set_empty(self, text, title="", action_text=None, action=None):
        self.empty.title.setText(title)
        self.empty.title.setVisible(bool(title))
        self.empty_label.setText(text)
        button = self.empty.button
        button.setText(action_text or "")
        button.setVisible(bool(action_text))
        if getattr(self, "_empty_action", None):
            button.clicked.disconnect(self._empty_action)
        self._empty_action = (lambda: action()) if action else None
        if self._empty_action:
            button.clicked.connect(self._empty_action)
        self._update_empty()

    def _update_empty(self):
        self.empty.setVisible(not self.cards and bool(self.empty_label.text()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self):
        self.columns = max(1, (self.viewport().width() + 16) // (216 + 16))
        while self.flow.count():
            self.flow.takeAt(0)
        for i, card in enumerate(self.cards):
            self.flow.addWidget(card, i // self.columns, i % self.columns, Qt.AlignTop)
