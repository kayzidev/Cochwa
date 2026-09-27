"""Grille de cartes adaptative : reflow au redimensionnement, cascade, état vide."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QGridLayout, QLabel, QScrollArea, QWidget


class CardGrid(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.inner = QWidget()
        self.flow = QGridLayout(self.inner)
        self.flow.setContentsMargins(16, 16, 16, 16)
        self.flow.setSpacing(10)
        self.setWidget(self.inner)
        self.cards = []
        self.columns = 0
        self.empty_label = QLabel("")
        self.empty_label.setObjectName("empty")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setVisible(False)
        self.flow.addWidget(self.empty_label, 0, 0, 1, -1)

    def clear(self):
        for card in self.cards:
            card.deleteLater()
        self.cards = []
        self._relayout()

    def add(self, card, animate=True, index=None):
        self.cards.append(card)
        self._relayout()
        if animate:
            i = index if index is not None else len(self.cards) - 1
            card.setVisible(False)
            QTimer.singleShot(min(i * 25, 400), card.appear)
        self._update_empty()

    def set_empty(self, text):
        self.empty_label.setText(text)
        self._update_empty()

    def _update_empty(self):
        self.empty_label.setVisible(not self.cards and bool(self.empty_label.text()))

    def resizeEvent(self, event):
        self._relayout()
        super().resizeEvent(event)

    def _relayout(self):
        columns = max(1, self.viewport().width() // 230)
        if columns == self.columns and self._grid_populated():
            return
        self.columns = columns
        while self.flow.count():
            self.flow.takeAt(0)
        for i, card in enumerate(self.cards):
            self.flow.addWidget(card, i // columns, i % columns, Qt.AlignTop)
        self.flow.addWidget(self.empty_label, 0, 0, max(1, columns), 1, Qt.AlignCenter)
        self._update_empty()

    def _grid_populated(self):
        return self.flow.count() == len(self.cards) + 1
