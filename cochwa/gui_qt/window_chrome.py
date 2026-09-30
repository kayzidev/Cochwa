"""Barre de titre et poignées de redimensionnement de la fenêtre principale."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from cochwa.gui_qt import theme
from cochwa.gui_qt.widgets import brand_pixmap


def _wayland() -> bool:
    return "wayland" in QGuiApplication.platformName().lower()


class FramelessDialog(QDialog):
    """Dialogue sans bordure système : déplaçable par son fond, Échap ferme.

    Le fond arrondi est peint à la main : avec WA_TranslucentBackground, Qt ne
    peint pas le `background` QSS d'une fenêtre dont la règle a un
    border-radius (le cadre resterait invisible).
    """

    RADIUS = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("framelessDialog")
        self._drag_origin = None
        self._dialog_origin = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(theme.BORDER))
        painter.setBrush(QColor(theme.BG))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), self.RADIUS, self.RADIUS)
        painter.end()
        super().paintEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_origin = event.globalPosition().toPoint()
            self._dialog_origin = self.pos()
            handle = self.windowHandle()
            if handle and handle.startSystemMove():
                self._drag_origin = None
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_origin is not None and event.buttons() & Qt.LeftButton and not _wayland():
            self.move(self._dialog_origin + event.globalPosition().toPoint() - self._drag_origin)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_origin = None
        self._dialog_origin = None
        super().mouseReleaseEvent(event)


def confirm(parent, title, message, *, accept_text="Confirmer", danger=False):
    """Confirmation modale sans bordure système ; Annuler reste le choix par défaut."""
    dialog = FramelessDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 24, 24, 20)
    layout.setSpacing(16)
    heading = QLabel(title)
    heading.setObjectName("sectionTitle")
    heading.setWordWrap(True)
    layout.addWidget(heading)
    body = QLabel(message)
    body.setWordWrap(True)
    body.setAccessibleName(message.replace("\n", " "))
    layout.addWidget(body, stretch=1)
    buttons = QHBoxLayout()
    buttons.addStretch(1)
    cancel = QPushButton("Annuler")
    cancel.setDefault(True)
    cancel.clicked.connect(dialog.reject)
    buttons.addWidget(cancel)
    accept = QPushButton(accept_text)
    accept.setObjectName("danger" if danger else "primary")
    accept.clicked.connect(dialog.accept)
    buttons.addWidget(accept)
    layout.addLayout(buttons)
    dialog.setMinimumWidth(420)
    return dialog.exec() == QDialog.DialogCode.Accepted


class TitleBar(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.owner = window
        self.setObjectName("windowTitleBar")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setFixedHeight(42)
        self.setMouseTracking(True)
        self._drag_origin = None
        self._window_origin = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 4, 6, 4)
        layout.setSpacing(7)
        icon = QLabel()
        icon.setPixmap(brand_pixmap(20))
        icon.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(icon)
        self.caption = QLabel(window.windowTitle())
        self.caption.setObjectName("windowCaption")
        self.caption.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.caption)
        layout.addStretch(1)

        self.minimize_button = self._button("−", "Réduire la fenêtre", "titleMinimize")
        self.maximize_button = self._button("□", "Agrandir la fenêtre", "titleMaximize")
        self.close_button = self._button("×", "Fermer la fenêtre", "titleClose")
        for button in (self.minimize_button, self.maximize_button, self.close_button):
            layout.addWidget(button)
        self.minimize_button.clicked.connect(window.showMinimized)
        self.maximize_button.clicked.connect(self.toggle_maximized)
        self.close_button.clicked.connect(window.close)
        window.windowTitleChanged.connect(self.caption.setText)

    def _button(self, text, accessible_name, object_name):
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setAccessibleName(accessible_name)
        button.setToolTip(accessible_name)
        button.setFixedSize(36, 30)
        button.setFocusPolicy(Qt.StrongFocus)
        return button

    def toggle_maximized(self):
        if self.owner.isMaximized():
            self.owner.showNormal()
        else:
            self.owner.showMaximized()
        self.update_maximize_button()

    def update_maximize_button(self):
        maximized = self.owner.isMaximized()
        self.maximize_button.setText("❐" if maximized else "□")
        label = "Restaurer la fenêtre" if maximized else "Agrandir la fenêtre"
        self.maximize_button.setAccessibleName(label)
        self.maximize_button.setToolTip(label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_origin = event.globalPosition().toPoint()
            self._window_origin = self.owner.pos()
            handle = self.owner.windowHandle()
            if handle and handle.startSystemMove():
                self._drag_origin = None
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_origin is not None and event.buttons() & Qt.LeftButton and not _wayland():
            if not self.owner.isMaximized():
                self.owner.move(
                    self._window_origin + event.globalPosition().toPoint() - self._drag_origin
                )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_origin = None
        self._window_origin = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class ResizeHandle(QWidget):
    """Poignée discrète ; Qt demande au système de gérer le geste natif."""

    def __init__(self, window, edges):
        super().__init__(window)
        self.owner = window
        self.edges = edges
        self._press = None
        self._rect = None
        self.setMouseTracking(True)
        horizontal = bool(edges & (Qt.LeftEdge | Qt.RightEdge))
        vertical = bool(edges & (Qt.TopEdge | Qt.BottomEdge))
        if horizontal and vertical:
            same = bool(edges & Qt.LeftEdge) == bool(edges & Qt.TopEdge)
            self.setCursor(Qt.SizeFDiagCursor if same else Qt.SizeBDiagCursor)
        elif horizontal:
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.SizeVerCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.owner.isMaximized():
            self._press = event.globalPosition().toPoint()
            self._rect = self.owner.geometry()
            handle = self.owner.windowHandle()
            if handle and handle.startSystemResize(self.edges):
                self._press = None
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press is not None and event.buttons() & Qt.LeftButton and not _wayland():
            delta = event.globalPosition().toPoint() - self._press
            rect = self._rect
            left, top, right, bottom = rect.left(), rect.top(), rect.right(), rect.bottom()
            minimum = self.owner.minimumSize()
            if self.edges & Qt.LeftEdge:
                left = min(left + delta.x(), right - minimum.width() + 1)
            if self.edges & Qt.RightEdge:
                right = max(right + delta.x(), left + minimum.width() - 1)
            if self.edges & Qt.TopEdge:
                top = min(top + delta.y(), bottom - minimum.height() + 1)
            if self.edges & Qt.BottomEdge:
                bottom = max(bottom + delta.y(), top + minimum.height() - 1)
            self.owner.setGeometry(left, top, right - left + 1, bottom - top + 1)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._press = None
        self._rect = None
        super().mouseReleaseEvent(event)


def install_resize_handles(window):
    margin, corner = 6, 12
    definitions = (
        (Qt.LeftEdge, lambda w, h: (0, corner, margin, h - 2 * corner)),
        (Qt.RightEdge, lambda w, h: (w - margin, corner, margin, h - 2 * corner)),
        (Qt.TopEdge, lambda w, h: (corner, 0, w - 2 * corner, margin)),
        (Qt.BottomEdge, lambda w, h: (corner, h - margin, w - 2 * corner, margin)),
        (Qt.LeftEdge | Qt.TopEdge, lambda w, h: (0, 0, corner, corner)),
        (Qt.RightEdge | Qt.TopEdge, lambda w, h: (w - corner, 0, corner, corner)),
        (Qt.LeftEdge | Qt.BottomEdge, lambda w, h: (0, h - corner, corner, corner)),
        (Qt.RightEdge | Qt.BottomEdge, lambda w, h: (w - corner, h - corner, corner, corner)),
    )
    handles = [(ResizeHandle(window, edges), geometry) for edges, geometry in definitions]
    return handles


def layout_resize_handles(window, handles):
    for handle, geometry in handles:
        handle.setGeometry(*geometry(window.width(), window.height()))
        handle.setVisible(not window.isMaximized())
        handle.raise_()
