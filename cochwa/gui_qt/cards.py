"""Cartes jeu Qt : coins arrondis natifs, fondu GPU, hover animé, double-clic.

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
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cochwa.gui_qt import theme

COVER_W, COVER_H = 190, 214


def pad_cover(path, size=(COVER_W, COVER_H)):
    """Charge une jaquette : cadre comme ImageOps.pad, coins arrondis."""
    source = QPixmap(str(path))
    if source.isNull():
        return None
    scaled = source.scaled(size[0], size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)
    canvas = QPixmap(size[0], size[1])
    canvas.fill(QColor(theme.PANEL))
    painter = QPainter(canvas)
    painter.drawPixmap((size[0] - scaled.width()) // 2, (size[1] - scaled.height()) // 2, scaled)
    painter.end()
    return _round(canvas, 8)


def placeholder_pixmap(size=(COVER_W, COVER_H), title="Cochwa"):
    """Pochette typographique, explicitement distincte d'une vraie jaquette."""
    import hashlib

    canvas = QPixmap(*size)
    canvas.fill(QColor(theme.CARD))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    colors = ["#51458A", "#38476B", "#644152", "#315C59"]
    color = colors[hashlib.sha256(title.encode()).digest()[0] % len(colors)]
    gradient = QLinearGradient(0, 0, size[0], size[1])
    gradient.setColorAt(0, QColor(color))
    gradient.setColorAt(1, QColor(theme.PANEL))
    painter.fillRect(canvas.rect(), gradient)
    painter.setPen(QColor(255, 255, 255, 24))
    painter.setBrush(Qt.NoBrush)
    for offset in (0, 24, 48):
        painter.drawEllipse(QRectF(70 + offset, -50 + offset, 170, 170))
    painter.setPen(QColor(theme.TEXT))
    font = QFont()
    font.setPixelSize(36)
    font.setWeight(QFont.DemiBold)
    painter.setFont(font)
    initials = "".join(w[0] for w in title.split()[:2]).upper()
    painter.drawText(QRectF(18, 60, size[0] - 36, 70), Qt.AlignCenter, initials)
    font.setPixelSize(10)
    font.setWeight(QFont.Normal)
    painter.setFont(font)
    painter.setPen(QColor("#C9C5DB"))
    painter.drawText(QRectF(0, size[1] - 30, size[0], 20), Qt.AlignCenter, "JAQUETTE À AJOUTER")
    painter.end()
    return _round(canvas, 8)


def _round(pixmap, radius):
    rounded = QPixmap(pixmap.size())
    rounded.fill(Qt.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(pixmap.rect()), radius, radius)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return rounded


def elide_two_lines(text, metrics, width):
    """Titre sur 2 lignes max avec « … »."""
    if metrics.horizontalAdvance(text) <= width:
        return text
    words = text.split()
    first = ""
    rest = list(words)
    while rest and metrics.horizontalAdvance(f"{first} {rest[0]}".strip()) <= width:
        first = f"{first} {rest.pop(0)}".strip()
    return first + "\n" + metrics.elidedText(" ".join(rest), Qt.ElideRight, width)


class GameCard(QWidget):
    """Carte jeu : jaquette, titre, méta, badges, taille et bouton d'action."""

    def __init__(
        self,
        title,
        subtitle="",
        size_bytes=0,
        badges=(),
        action=None,
        action_text="Détails",
        on_double_click=None,
        parent=None,
        secondary_action=None,
        secondary_text="Détails",
    ):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)  # QSS sur QWidget
        self.setProperty("hover", False)
        self.setFixedSize(216, 440 if secondary_action else 400)
        self._cover = None  # QPixmap final, base du zoom au survol
        self._on_double_click = on_double_click
        self.base_title = title.split("(")[0].strip()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(COVER_W, COVER_H)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setPixmap(placeholder_pixmap(title=self.base_title))
        layout.addWidget(self.cover_label, alignment=Qt.AlignHCenter)

        self._raw_title = title
        self._base_subtitle = subtitle
        self.title_label = QLabel(elide_two_lines(title, self.fontMetrics(), 186))
        self.title_label.setObjectName("cardTitle")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.title_label.setToolTip(title)
        self.setAccessibleName(title)
        self.title_label.setFixedHeight(38)
        layout.addWidget(self.title_label)

        self.meta_label = QLabel(
            self.fontMetrics().elidedText(subtitle, Qt.ElideRight, 186) if subtitle else ""
        )
        self.meta_label.setObjectName("cardMeta")
        self.meta_label.setToolTip(subtitle)
        self.meta_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.meta_label)

        if badges:
            chips = QHBoxLayout()
            chips.setSpacing(6)
            for text, color in badges:
                chip = QLabel(text)
                chip.setObjectName("chip")
                chip.setStyleSheet(f"color: {color}; background: {theme.CARD};")
                chips.addWidget(chip)
            chips.addStretch(1)
            layout.addLayout(chips)

        if size_bytes:
            from cochwa.util import human_size

            size_label = QLabel(human_size(size_bytes))
            size_label.setObjectName("cardSize")
            size_label.setAlignment(Qt.AlignHCenter)
            layout.addWidget(size_label)

        layout.addStretch(1)
        self.button = QPushButton(action_text)
        self.button.setObjectName("primary" if secondary_action else "cardBtn")
        self.button.setCursor(Qt.PointingHandCursor)
        if action:
            # clicked émet un booléen « checked » : sans ce relais il serait
            # passé en premier argument de l'action (écrasant le paramètre
            # par défaut du lambda — « Voir les éditions » recevait False).
            self.button.clicked.connect(lambda _checked=False, act=action: act())
        self.button.setAccessibleName(f"{action_text} : {title}")
        layout.addWidget(self.button)
        if secondary_action:
            details = QPushButton(secondary_text)
            details.setObjectName("secondaryAction")
            details.clicked.connect(lambda: secondary_action())
            layout.addWidget(details)

        # Les labels laissent passer la souris : le survol de la carte reste
        # détecté même au-dessus du texte ou de la jaquette.
        for label in self.findChildren(QLabel):
            label.setAttribute(Qt.WA_TransparentForMouseEvents)

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
        # Sans ce retrait, l'effet force le rendu via un cache hors écran :
        # la jaquette se « décolle » de la carte pendant le défilement.
        self._fade.finished.connect(lambda: self.cover_label.setGraphicsEffect(None))
        self._fade.start(QPropertyAnimation.DeleteWhenStopped)

    def set_igdb_metadata(self, metadata):
        """Ajoute année, genres et studio sous le titre quand IGDB a un match."""
        if not metadata:
            return
        self.igdb_metadata = metadata
        year = metadata.get("release_date", "")[:4]
        details = [value for value in (year, ", ".join(metadata.get("genres", []))) if value]
        if metadata.get("developers"):
            details.append(", ".join(metadata["developers"][:2]))
        suffix = " · ".join(details)
        text = " · ".join(value for value in (self._base_subtitle, suffix) if value)
        self.meta_label.setText(self.fontMetrics().elidedText(text, Qt.ElideRight, 186))
        self.meta_label.setToolTip(text)

    # -- Survol : zoom jaquette + bordure accentuée --------------------

    def enterEvent(self, event):
        self._set_hover(True)
        self._zoom(1.0, 1.07)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._set_hover(False)
        self._zoom(1.07, 1.0)
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._on_double_click:
            self._on_double_click()
        super().mouseDoubleClickEvent(event)

    def _set_hover(self, hovering):
        self.setProperty("hover", hovering)
        self.style().unpolish(self)
        self.style().polish(self)

    def _zoom(self, start, end):
        if self._cover is None:
            return
        # Stoppe l'animation précédente : parentées à la carte, elles
        # s'accumuleraient en se battant pour la jaquette à chaque survol.
        # (DeleteWhenStopped laisserait une référence pendante → RuntimeError.)
        previous = getattr(self, "_zoom_anim", None)
        if previous is not None:
            previous.stop()
            previous.deleteLater()

        def apply(factor):
            size = QSize(int(COVER_W * factor), int(COVER_H * factor))
            self.cover_label.setPixmap(
                self._cover.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

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
