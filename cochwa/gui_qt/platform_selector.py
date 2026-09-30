"""Sélecteur de plateforme avec menu flottant accessible."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QRect, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from cochwa.gui_qt.theme import SECONDARY, TEXT


class _PlatformItemDelegate(QStyledItemDelegate):
    """Ligne lisible avec focus, survol et coche de sélection distincts."""

    def __init__(self, selector, parent=None):
        super().__init__(parent)
        self.selector = selector

    def sizeHint(self, option, index):
        return QSize(240, 46)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect.adjusted(3, 2, -3, -2)
        enabled = bool(option.state & QStyle.State_Enabled)
        focused = enabled and bool(option.state & QStyle.State_Selected)
        hovered = enabled and bool(option.state & QStyle.State_MouseOver)
        chosen = index.row() == self.selector.currentIndex()

        if focused:
            painter.setPen(QColor("#655A7A"))
            painter.setBrush(QColor("#383344"))
            painter.drawRoundedRect(rect, 8, 8)
        elif hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#2B2E3C"))
            painter.drawRoundedRect(rect, 8, 8)
        elif chosen:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#302B35"))
            painter.drawRoundedRect(rect, 8, 8)

        painter.setPen(QColor(TEXT if enabled else "#777C8D"))
        font = option.font
        font.setPointSize(11)
        font.setWeight(QFont.Weight.DemiBold if chosen else QFont.Weight.Normal)
        painter.setFont(font)
        text_rect = QRect(rect.left() + 13, rect.top(), rect.width() - 47, rect.height())
        label = painter.fontMetrics().elidedText(index.data(), Qt.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, label)
        if chosen:
            painter.setPen(QColor(SECONDARY))
            check_rect = QRect(rect.right() - 32, rect.top(), 24, rect.height())
            painter.drawText(check_rect, Qt.AlignCenter, "✓")
        painter.restore()


class _PlatformList(QListWidget):
    def __init__(self, menu):
        super().__init__(menu)
        self.menu = menu

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.menu.close_menu()
            event.accept()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.menu.choose(self.currentRow())
            event.accept()
        else:
            super().keyPressEvent(event)


class _PlatformMenu(QWidget):
    DURATION_MS = 180
    TRAVEL_PX = 6

    def __init__(self, selector, parent):
        super().__init__(parent)
        self.selector = selector
        self.setObjectName("platformMenu")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus)
        self._anchor = QPoint()
        self._direction = 1
        self._travel = 6
        self._progress = 0.0
        self._closing = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        self.panel = QFrame()
        self.panel.setObjectName("platformMenuPanel")
        self.panel.setAttribute(Qt.WA_StyledBackground)
        self.opacity_effect = QGraphicsOpacityEffect(self.panel)
        self.panel.setGraphicsEffect(self.opacity_effect)
        outer.addWidget(self.panel)
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(6, 6, 6, 6)
        self.items = _PlatformList(self)
        self.items.setObjectName("platformMenuItems")
        self.items.setAccessibleName("Plateformes disponibles")
        self.items.setItemDelegate(_PlatformItemDelegate(selector, self.items))
        self.items.setMouseTracking(True)
        self.items.viewport().setMouseTracking(True)
        self.items.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.items.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.items.itemEntered.connect(self.items.setCurrentItem)
        self.items.itemClicked.connect(lambda item: self.choose(self.items.row(item)))
        self.items.itemActivated.connect(lambda item: self.choose(self.items.row(item)))
        panel_layout.addWidget(self.items)

        self.animation = QVariantAnimation(self)
        self.animation.setDuration(self.DURATION_MS)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self._set_progress)
        self.animation.finished.connect(self._animation_finished)

    def open_menu(self):
        self.animation.stop()
        self._closing = False
        self._travel = 0 if self.selector.reduce_motion() else self.TRAVEL_PX
        self.items.clear()
        for index in range(self.selector.count()):
            item = QListWidgetItem(self.selector.itemText(index))
            if not self.selector.model().item(index).isEnabled():
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable)
            self.items.addItem(item)
        self.items.setCurrentRow(self.selector.currentIndex())
        self._place()
        self._set_progress(0.0)
        self.show()
        self.raise_()
        QApplication.instance().installEventFilter(self)
        self.items.setFocus(Qt.PopupFocusReason)
        self._animate(1.0)

    def _place(self):
        parent = self.parentWidget()
        screen = self.selector.screen().availableGeometry()
        screen_in_parent = QRect(parent.mapFromGlobal(screen.topLeft()), screen.size())
        available = parent.rect().intersected(screen_in_parent)
        if available.isEmpty():
            available = parent.rect()
        width = min(max(self.selector.width() + 28, 270), available.width() - 16)
        max_height = max(80, available.height() - 16)
        item_height = min(self.items.count() * 46, max_height - 36)
        self.items.setFixedHeight(max(44, item_height))
        self.resize(width, self.items.height() + 36)
        below = self.selector.mapTo(parent, QPoint(-8, self.selector.height() + 2))
        above_y = self.selector.mapTo(parent, QPoint(0, 0)).y() - self.height() - 2
        if below.y() + self.height() <= available.bottom() + 1 or above_y < available.top():
            self._direction = 1
            y = min(below.y(), available.bottom() + 1 - self.height() - self._travel)
        else:
            self._direction = -1
            y = max(above_y, available.top() + self._travel)
        x = max(available.left(), min(below.x(), available.right() + 1 - width))
        y = max(available.top(), y)
        self._anchor = QPoint(x, y)

    def _animate(self, end):
        self.animation.stop()
        self.animation.setStartValue(self._progress)
        self.animation.setEndValue(end)
        self.animation.start()

    def _set_progress(self, value):
        self._progress = float(value)
        self.opacity_effect.setOpacity(self._progress)
        self.update()
        offset = round((1.0 - self._progress) * self._travel * self._direction)
        self.move(self._anchor + QPoint(0, offset))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        panel = self.panel.geometry()
        for spread, alpha in ((9, 6), (7, 8), (5, 10), (3, 13)):
            painter.setBrush(QColor(0, 0, 0, round(alpha * self._progress)))
            shadow = panel.adjusted(-spread, -spread + 5, spread, spread + 5)
            painter.drawRoundedRect(shadow, 14 + spread, 14 + spread)

    def _animation_finished(self):
        if self._closing:
            self.hide()
            self._closing = False

    def close_menu(self):
        if not self.isVisible() or self._closing:
            return
        self._closing = True
        QApplication.instance().removeEventFilter(self)
        self.selector.setFocus(Qt.OtherFocusReason)
        self._animate(0.0)

    def choose(self, index):
        if index < 0 or index >= self.selector.count():
            return
        if not self.selector.model().item(index).isEnabled():
            return
        self.selector.setCurrentIndex(index)
        self.selector.activated.emit(index)
        self.close_menu()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.MouseButtonPress and isinstance(watched, QWidget):
            if not (watched is self or self.isAncestorOf(watched)):
                if watched is not self.selector and not self.selector.isAncestorOf(watched):
                    self.close_menu()
        elif event.type() == QEvent.ApplicationDeactivate:
            self.close_menu()
        return False


class PlatformSelector(QComboBox):
    """Conserve le modèle Qt du combo, avec un menu flottant indépendant."""

    def __init__(self, reduce_motion, parent=None):
        super().__init__(parent)
        self.reduce_motion = reduce_motion
        self.menu = None
        self.setAccessibleName("Choisir la plateforme active")
        self.setAccessibleDescription("Ouvrir avec Entrée ou Espace ; parcourir avec les flèches")

    def showPopup(self):
        if self.menu is None:
            self.menu = _PlatformMenu(self, self.window())
        if not self.menu.isVisible() or self.menu._closing:
            self.menu.open_menu()

    def hidePopup(self):
        if self.menu is not None:
            self.menu.close_menu()

    def mousePressEvent(self, event):
        if self.menu is not None and self.menu.isVisible() and not self.menu._closing:
            self.hidePopup()
            event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Down, Qt.Key_Up):
            self.showPopup()
            event.accept()
        else:
            super().keyPressEvent(event)
