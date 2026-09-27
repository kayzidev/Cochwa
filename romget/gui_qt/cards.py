"""Cartes jeu Qt : coins arrondis natifs, fondu GPU, hover animé.

Ce que Tkinter faisait à la main (masques PIL, moteur after, interpolation
de couleurs) est ici déclaratif : QPainter + QPropertyAnimation.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QVariantAnimation,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

COVER_W, COVER_H = 150, 225
PANEL = "#1e2530"
SKELETON = "#2b3340"


def pad_cover(path, size=(COVER_W, COVER_H)):
    """Charge une jaquette : cadre comme ImageOps.pad, coins arrondis."""
    source = QPixmap(path)
    if source.isNull():
        return None
    scaled = source.scaled(size[0], size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)
    canvas = QPixmap(size[0], size[1])
    canvas.fill(QColor(PANEL))
    painter = QPainter(canvas)
    painter.drawPixmap((size[0] - scaled.width()) // 2, (size[1] - scaled.height()) // 2, scaled)
    painter.end()
    rounded = QPixmap(size[0], size[1])
    rounded.fill(Qt.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, size[0], size[1]), 8, 8)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, canvas)
    painter.end()
    return rounded


def placeholder_pixmap(size=(COVER_W, COVER_H)):
    canvas = QPixmap(size[0], size[1])
    canvas.fill(QColor(SKELETON))
    rounded = QPixmap(size[0], size[1])
    rounded.fill(Qt.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, size[0], size[1]), 8, 8)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, canvas)
    painter.end()
    return rounded


def elide_two_lines(text, metrics, width):
    """Titre sur 2 lignes max avec « … » (équivalent du _fit Tkinter)."""
    if metrics.horizontalAdvance(text) <= width:
        return text
    words = text.split()
    first = ""
    rest = list(words)
    while rest and metrics.horizontalAdvance(f"{first} {rest[0]}".strip()) <= width:
        first = f"{first} {rest.pop(0)}".strip()
    return first + "\n" + metrics.elidedText(" ".join(rest), Qt.ElideRight, width)


class GameCard(QWidget):
    """Carte jeu : jaquette, titre, méta, badges, bouton d'action."""

    def __init__(self, title, subtitle="", badges=(), action_text="Voir les éditions", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)  # QSS sur QWidget
        self.setProperty("hover", False)
        self.setFixedSize(210, 366)
        self._cover = None  # QPixmap final, base du zoom au survol

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(COVER_W, COVER_H)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setPixmap(placeholder_pixmap())
        layout.addWidget(self.cover_label, alignment=Qt.AlignHCenter)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        self.title_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.title_label.setFixedHeight(34)
        layout.addWidget(self.title_label)

        self.meta_label = QLabel(subtitle)
        self.meta_label.setObjectName("cardMeta")
        self.meta_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(self.meta_label)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        for text, color in badges:
            chip = QLabel(text)
            chip.setObjectName("chip")
            chip.setStyleSheet(f"color: {color}; border: 1px solid {color};")
            chips.addWidget(chip)
        chips.addStretch(1)
        layout.addLayout(chips)

        layout.addStretch(1)
        self.button = QPushButton(action_text)
        self.button.setObjectName("cardBtn")
        self.button.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.button)

        # Les labels laissent passer la souris : le survol de la carte reste
        # détecté même au-dessus du texte ou de la jaquette.
        for label in self.findChildren(QLabel):
            label.setAttribute(Qt.WA_TransparentForMouseEvents)

        layout.addStretch(1)
        self.button = QPushButton(action_text)
        self.button.setObjectName("cardBtn")
        self.button.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.button)

        # Les textes sont mesurés une fois la police effective disponible.
        self._raw_title = title
        self._relayout_text()

    def _relayout_text(self):
        metrics = self.title_label.fontMetrics()
        self.title_label.setText(
            elide_two_lines(self._raw_title, metrics, self.title_label.width() or 186)
        )
        self.meta_label.setText(
            self.meta_label.fontMetrics().elidedText(self.meta_label.text(), Qt.ElideRight, 186)
        )

    # -- Jaquette -----------------------------------------------------

    def set_cover(self, path):
        """Fondu d'apparition de la jaquette (QGraphicsOpacityEffect, GPU)."""
        pixmap = pad_cover(path)
        if pixmap is None:
            return
        self._cover = pixmap
        self.cover_label.setPixmap(pixmap)
        effect = QGraphicsOpacityEffect(self.cover_label)
        self.cover_label.setGraphicsEffect(effect)
        self._fade = QPropertyAnimation(effect, b"opacity", self)
        self._fade.setDuration(250)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.start(QPropertyAnimation.DeleteWhenStopped)

    # -- Survol : zoom jaquette + bordure accentuée --------------------

    def enterEvent(self, event):
        self._set_hover(True)
        self._zoom(1.0, 1.07)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._set_hover(False)
        self._zoom(1.07, 1.0)
        super().leaveEvent(event)

    def _set_hover(self, hovering):
        self.setProperty("hover", hovering)
        self.style().unpolish(self)
        self.style().polish(self)

    def _zoom(self, start, end):
        if self._cover is None:
            return

        def apply(factor):
            size = QSize(int(COVER_W * factor), int(COVER_H * factor))
            scaled = self._cover.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.cover_label.setPixmap(scaled)

        self._zoom_anim = QVariantAnimation(self)
        self._zoom_anim.setDuration(140)
        self._zoom_anim.setStartValue(start)
        self._zoom_anim.setEndValue(end)
        self._zoom_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._zoom_anim.valueChanged.connect(apply)
        self._zoom_anim.start()

    # -- Apparition (cascade) -------------------------------------------

    def appear(self):
        """Fondu d'entrée de la carte entière (appelé avec un délai progressif)."""
        self.setVisible(True)
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self._appear = QPropertyAnimation(effect, b"opacity", self)
        self._appear.setDuration(220)
        self._appear.setStartValue(0.0)
        self._appear.setEndValue(1.0)
        self._appear.setEasingCurve(QEasingCurve.OutCubic)

        def cleanup():
            self.setGraphicsEffect(None)  # libère l'effet pour le fondu cover

        self._appear.finished.connect(cleanup)
        self._appear.start(QPropertyAnimation.DeleteWhenStopped)
