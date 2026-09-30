"""Transitions courtes entre les pages du panneau central."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRect, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from cochwa.gui_qt.theme import BG


class PageTransition(QWidget):
    """Fondu entre deux instantanés ; la navigation réelle reste interactive."""

    def __init__(self, parent, outgoing, incoming, *, reduce_motion=False, finished=None):
        super().__init__(parent)
        self.outgoing = outgoing
        self.incoming = incoming
        self.travel_px = 0 if reduce_motion else 8
        self.duration_ms = 200
        self.progress = 0.0
        self._done = False
        self._finished_callback = finished
        self.setObjectName("pageTransition")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(parent.rect())

        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setDuration(self.duration_ms)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self._set_progress)
        self.animation.finished.connect(self._finish)

    def start(self):
        self.show()
        self.raise_()
        self.animation.start()

    def cancel(self):
        if self._done:
            return
        self._done = True
        self.animation.stop()
        self.hide()
        self.deleteLater()

    def _set_progress(self, value):
        self.progress = float(value)
        self.update()

    def _finish(self):
        if self._done:
            return
        self._done = True
        self.hide()
        if self._finished_callback:
            self._finished_callback(self)
        self.deleteLater()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        area = self.rect()
        painter.fillRect(area, QColor(BG))
        painter.setOpacity(1.0 - self.progress)
        painter.drawPixmap(area, self.outgoing, self.outgoing.rect())
        painter.setOpacity(self.progress)
        travel = round((1.0 - self.progress) * self.travel_px)
        incoming_area = QRect(area.x(), area.y() + travel, area.width(), area.height())
        painter.drawPixmap(incoming_area, self.incoming, self.incoming.rect())
