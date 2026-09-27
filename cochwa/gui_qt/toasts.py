"""Notifications toast empilées en bas à droite : fondu, glissement, repli au clic."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel

from cochwa.gui_qt import theme


class ToastManager:
    def __init__(self, window):
        self.window = window
        self.toasts = []

    def show(self, message, kind="info"):
        toast = _Toast(self.window, message, theme.TOAST_KINDS.get(kind, theme.ACCENT))
        toast.destroyed.connect(lambda *_: self._drop(toast))
        self.toasts.append(toast)
        self._restack()
        toast.show_animated()

    def _drop(self, toast):
        if toast in self.toasts:
            self.toasts.remove(toast)
        self._restack()

    def _restack(self):
        try:
            y = self.window.height() - 70
            for toast in reversed(self.toasts):
                y -= toast.height() + 10
                toast.move(self.window.width() - toast.width() - 18, y)
        except RuntimeError:
            # Fenêtre détruite (fermeture de l'app) : plus rien à replacer.
            self.toasts.clear()


class _Toast(QFrame):
    WIDTH = 330

    def __init__(self, window, message, color):
        super().__init__(window)
        self.setObjectName("toast")
        self.setFixedWidth(self.WIDTH)
        bar = QFrame(self)
        bar.setObjectName("toastBar")
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"background: {color};")
        label = QLabel(message, self)
        label.setWordWrap(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(bar)
        layout.addWidget(label, stretch=1)
        label.setContentsMargins(10, 9, 10, 9)
        self.adjustSize()
        self.setCursor(Qt.PointingHandCursor)

    def show_animated(self):
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self._fade = QPropertyAnimation(effect, b"opacity", self)
        self._fade.setDuration(180)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(0.97)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.start()
        self.show()
        QTimer.singleShot(3800, self.fade_out)

    def fade_out(self):
        effect = self.graphicsEffect()
        if effect is None:
            effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)
        self._fade = QPropertyAnimation(effect, b"opacity", self)
        self._fade.setDuration(300)
        self._fade.setStartValue(0.97)
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self.close)
        self._fade.start()

    def mousePressEvent(self, event):
        self.close()  # repli immédiat au clic
