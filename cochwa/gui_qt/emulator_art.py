"""Vignettes carrées hors ligne pour le catalogue des émulateurs."""

import hashlib

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap

from cochwa.gui_qt import theme


def emulator_artwork(name, brand, size=116):
    """Illustration typographique locale, sans dépendance à un logo distant."""
    digest = hashlib.sha256(name.encode()).digest()
    palette = {
        "Sony": ("#534B96", "#312C59"),
        "Nintendo": ("#A44768", "#4B2947"),
        "Sega": ("#336999", "#283B61"),
        "Microsoft": ("#39795D", "#263D47"),
        "NEC": ("#876147", "#45394C"),
        "SNK": ("#4D7790", "#303B58"),
        "Bandai": ("#8A527F", "#493552"),
        "Sammy": ("#745C9B", "#393354"),
    }
    first, last = palette.get(brand, ("#625C9B", "#38374E"))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(size / 116, size / 116)
    gradient = QLinearGradient(0, 0, 116, 116)
    gradient.setColorAt(0, QColor(first))
    gradient.setColorAt(1, QColor(last))
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(QRectF(0, 0, 116, 116), 11, 11)
    painter.setPen(QPen(QColor(255, 255, 255, 28), 1.5))
    painter.setBrush(Qt.NoBrush)
    for offset in (0, 17, 34):
        painter.drawEllipse(QRectF(58 + offset, -29 + offset, 78, 78))
    painter.setPen(QColor(theme.TEXT))
    font = QFont()
    font.setPixelSize(35 if len(name) < 13 else 29)
    font.setWeight(QFont.Bold)
    painter.setFont(font)
    letters = "".join(word[0] for word in name.replace("/", " ").split()[:2]).upper()
    painter.drawText(QRectF(8, 24, 100, 62), Qt.AlignCenter, letters[:2])
    painter.setPen(QPen(QColor(theme.SECONDARY if digest[0] % 2 else theme.SUCCESS), 3))
    painter.drawLine(39, 94, 77, 94)
    painter.end()
    return pixmap
