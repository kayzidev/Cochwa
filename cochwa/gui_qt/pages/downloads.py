"""Téléchargements : modèle/vue Qt, progression lissée, teintes par état."""

from __future__ import annotations

import json
import time

from PySide6.QtCore import QAbstractTableModel, QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from cochwa.gui_qt import theme
from cochwa.gui_qt.widgets import EmptyState, PageHeader
from cochwa.util import human_duration, human_size

# Fenêtre glissante pour la vitesse moyenne (secondes).
_RATE_WINDOW = 30.0

COLUMNS = ("Jeu", "État", "Progression", "Débit / restant", "Détail")


class DownloadsModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self.rows)

    def columnCount(self, parent=None):
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        if role == Qt.BackgroundRole:
            tint = theme.ROW_TINTS.get(row["status"])
            return QColor(tint) if tint else None
        if role != Qt.DisplayRole:
            return None
        column = index.column()
        if column == 0:
            return row["title"]
        if column == 1:
            return theme.STATE_LABELS.get(row["status"], row["status"])
        if column == 2:
            return f"{human_size(row['progress'])} / {human_size(row['total'])}"
        if column == 3:
            return row.get("speed", "—")
        return row["error"]


class DownloadsPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.samples = {}
        self.rows = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(14)
        self.header = PageHeader(
            "Vos téléchargements",
            "Suivez vos transferts et reprenez-les quand vous le souhaitez.",
            "VOTRE ACTIVITÉ",
        )
        layout.addWidget(self.header)
        self.summary = QLabel("Aucun transfert en cours")
        self.summary.setObjectName("muted")
        layout.addWidget(self.summary)

        self.model = DownloadsModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.context_menu)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(52)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.selectionModel().selectionChanged.connect(lambda *_: self.selected())
        layout.addWidget(self.table, stretch=1)

        self.empty = EmptyState(
            "Tout est calme ici",
            "Choisissez un jeu dans le catalogue, puis ajoutez les fichiers souhaités à la file.",
            "Explorer le catalogue",
            self.app.focus_search,
        )
        layout.addWidget(self.empty, stretch=1)

        self.progress = QProgressBar()
        self.progress.setMaximum(100)
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()
        self.actions = {}
        for label, callback in [
            ("Pause", lambda key: app.manager.pause(key)),
            ("Reprendre", self.resume),
            ("Annuler", lambda key: app.manager.pause(key, True)),
            ("Supprimer", self.remove),
        ]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, cb=callback: self.act(cb))
            self.actions[label] = button
            button.setEnabled(False)
            if label in {"Annuler", "Supprimer"}:
                button.setObjectName("danger")
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        hint = QLabel(
            "Les fichiers partiels sont conservés. Une tâche interrompue reprend sur demande."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.refresh()

    def activate(self):
        self.refresh()

    def act(self, callback):
        key = self.selected_key()
        if key:
            callback(key)
            self.refresh()

    def context_menu(self, position):
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        self.table.selectRow(index.row())
        menu = QMenu("Options", self)
        menu.addSection("Options du téléchargement")
        for label, button in self.actions.items():
            action = menu.addAction(label, button.click)
            action.setEnabled(button.isEnabled())
        menu.exec(self.table.viewport().mapToGlobal(position))

    def remove(self, key):
        answer = QMessageBox.question(
            self,
            "Supprimer le téléchargement",
            "Retirer ce téléchargement de la liste ?\nUn transfert actif sera arrêté. Les fichiers déjà présents sur disque seront conservés.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.app.manager.remove(key)

    def resume(self, key):
        self.app.store.resume(key)
        self.app.manager.start()

    def selected_key(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self.model.rows[indexes[0].row()]["id"]

    def selected(self):
        key = self.selected_key()
        row = self.rows.get(key) if key else None
        status = row["status"] if row else None
        self.actions["Pause"].setEnabled(status in {"queued", "running"})
        self.actions["Reprendre"].setEnabled(status in {"paused", "failed", "cancelled"})
        self.actions["Annuler"].setEnabled(status in {"queued", "running", "paused"})
        self.actions["Supprimer"].setEnabled(row is not None and status != "removing")
        self.progress.setVisible(row is not None)
        self._set_progress(round(100 * row["progress"] / max(1, row["total"])) if row else 0)

    def _set_progress(self, target):
        """Barre lissée : QPropertyAnimation native vers la valeur cible."""
        if abs(self.progress.value() - target) < 1:
            self.progress.setValue(target)
            return
        previous = getattr(self, "_anim", None)
        if previous is not None:
            previous.stop()
            previous.deleteLater()
        self._anim = QPropertyAnimation(self.progress, b"value", self)
        self._anim.setDuration(300)
        self._anim.setStartValue(self.progress.value())
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def refresh(self):
        self.header.eyebrow.setText(f"VOTRE ACTIVITÉ · {self.app.console.name.upper()}")
        selected_key = self.selected_key()
        now = time.monotonic()
        rows = []
        for row in self.app.store.list():
            payload = json.loads(row.get("payload", "{}"))
            if payload.get("platform", "ps2") != self.app.console.id:
                continue
            key = row["id"]
            # Vitesse moyenne sur une fenêtre glissante : moins de jitter
            # qu'un débit instantané, ETA plus stable.
            samples = self.samples.setdefault(key, [])
            samples.append((now, row["progress"]))
            cutoff = now - _RATE_WINDOW
            while len(samples) > 1 and samples[0][0] < cutoff:
                samples.pop(0)
            rate = 0
            if len(samples) > 1 and samples[-1][0] > samples[0][0]:
                rate = (samples[-1][1] - samples[0][1]) / (samples[-1][0] - samples[0][0])
            row["speed"] = "—"
            if rate > 0 and row["status"] == "running":
                remaining = human_duration((row["total"] - row["progress"]) / rate)
                row["speed"] = f"{human_size(rate)}/s · reste {remaining}"
            if row["status"] != "running":
                self.samples.pop(key, None)
            self.rows[key] = row
            rows.append(row)
        self.model.set_rows(rows)
        self.rows = {row["id"]: row for row in rows}
        for index, row in enumerate(rows):
            if row["id"] == selected_key:
                self.table.selectRow(index)
                break
        active = sum(row["status"] in {"running", "queued"} for row in rows)
        complete = sum(row["status"] == "completed" for row in rows)
        self.summary.setText(
            f"{active} en cours ou en attente  ·  {complete} terminé(s)  ·  {len(rows)} au total"
        )
        has_rows = bool(rows)
        self.table.setVisible(has_rows)
        self.empty.setVisible(not has_rows)
        for button in self.actions.values():
            button.setVisible(has_rows)
        self.selected()
