"""Composants communs : en-têtes, panneaux et symbole vectoriel Cochwa."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from cochwa.gui_qt import theme


def brand_pixmap(size=48):
    """Premier logo de la planche : portail C arrondi et carré corail."""
    from pathlib import Path

    from PySide6.QtSvg import QSvgRenderer

    pixmap = QPixmap(size * 2, size * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer = QSvgRenderer(str(Path(__file__).parent / "assets" / "logo.svg"))
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def brand_icon():
    return QIcon(brand_pixmap(64))


class PageHeader(QWidget):
    def __init__(self, title, description, eyebrow="VOS JEUX, SIMPLEMENT"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(6)
        overline = QLabel(eyebrow)
        self.eyebrow = overline
        overline.setObjectName("eyebrow")
        layout.addWidget(overline)
        self.title = QLabel(title)
        self.title.setObjectName("heading")
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.description = QLabel(description)
        self.description.setObjectName("muted")
        self.description.setWordWrap(True)
        layout.addWidget(self.description)


def section(title, description=""):
    panel = QWidget()
    panel.setObjectName("section")
    panel.setAttribute(Qt.WA_StyledBackground)
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    label = QLabel(title)
    label.setObjectName("sectionTitle")
    layout.addWidget(label)
    if description:
        hint = QLabel(description)
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
    return panel, layout


class EmptyState(QWidget):
    def __init__(self, title, description, action_text=None, action=None):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 30, 24, 30)
        layout.setSpacing(12)
        layout.addStretch()
        mark = QLabel()
        mark.setPixmap(brand_pixmap(56))
        layout.addWidget(mark, alignment=Qt.AlignCenter)
        self.title = QLabel(title)
        self.title.setObjectName("sectionTitle")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.description = QLabel(description)
        self.description.setObjectName("muted")
        self.description.setAlignment(Qt.AlignCenter)
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self.button = QPushButton(action_text or "")
        self.button.setObjectName("primary")
        self.button.setVisible(bool(action_text))
        if action:
            self.button.clicked.connect(lambda: action())
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.button)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()


def navigation_icon(name):
    """Pictogrammes de navigation au trait, indépendants des polices emoji."""
    from PySide6.QtGui import QPen

    icon = QIcon()
    for mode, color in ((QIcon.Normal, theme.MUTED), (QIcon.Selected, theme.TEXT)):
        pixmap = QPixmap(36, 36)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(color), 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if name == "Bibliothèque":
            for x, y in ((2, 2), (10, 2), (2, 10), (10, 10)):
                p.drawRoundedRect(QRectF(x, y, 5, 5), 1, 1)
        elif name == "Rechercher":
            p.drawEllipse(QRectF(2, 2, 10, 10))
            p.drawLine(11, 11, 16, 16)
        elif name == "Téléchargements":
            p.drawLine(9, 2, 9, 12)
            p.drawLine(5, 8, 9, 12)
            p.drawLine(9, 12, 13, 8)
            p.drawLine(2, 12, 2, 16)
            p.drawLine(2, 16, 16, 16)
            p.drawLine(16, 16, 16, 12)
        elif name == "Paramètres":
            for y, x in ((4, 6), (9, 12), (14, 7)):
                p.drawLine(2, y, 16, y)
                p.setBrush(QColor(theme.PANEL))
                p.drawEllipse(QRectF(x - 2, y - 2, 4, 4))
        elif name == "Support":
            p.drawEllipse(QRectF(2, 2, 14, 14))
            p.drawText(QRectF(2, 0, 14, 18), Qt.AlignCenter, "?")
        else:
            path = QPainterPath()
            path.moveTo(9, 1)
            for x, y in (
                (11, 6),
                (16, 7),
                (12, 11),
                (13, 16),
                (9, 13),
                (4, 16),
                (5, 11),
                (1, 7),
                (7, 6),
            ):
                path.lineTo(x, y)
            path.closeSubpath()
            p.drawPath(path)
        p.end()
        icon.addPixmap(pixmap, mode)
    return icon
