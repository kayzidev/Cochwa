"""Dialogues Qt : sélection de fichiers distants, détails locaux, jaquette manuelle."""

from __future__ import annotations

import subprocess
import webbrowser

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from cochwa.api.redump import get_datfile
from cochwa.infrastructure.storage import atomic_write
from cochwa.services.conversion import convert_chd
from cochwa.services.library import launch, verify_manifest
from cochwa.util import human_size


class RemoteDetailsDialog(QDialog):
    """Sélection explicite des disques/pistes avant mise en file."""

    def __init__(self, app, game, parent=None):
        super().__init__(parent or app)
        self.app = app
        self.game = game
        self.setWindowTitle(game.clean_title)
        self.resize(950, 560)
        layout = QVBoxLayout(self)

        title = QLabel(game.clean_title)
        title.setObjectName("heading")
        title.setWordWrap(True)
        layout.addWidget(title)
        info = QLabel(f"{game.label} · Source : {game.source} / {game.identifier}")
        info.setObjectName("muted")
        info.setWordWrap(True)
        layout.addWidget(info)

        if game.external:
            note = QLabel(
                "Ouvrir la fiche MiNERVA, choisir le torrent dans votre client, "
                "puis placer les fichiers extraits dans le dossier PS2."
            )
            note.setWordWrap(True)
            layout.addWidget(note)
            open_btn = QPushButton("Ouvrir la fiche MiNERVA")
            open_btn.setObjectName("primary")
            open_btn.clicked.connect(lambda: webbrowser.open(game.source_reference()["url"]))
            layout.addWidget(open_btn)
            close = QPushButton("Fermer")
            close.clicked.connect(self.reject)
            layout.addWidget(close)
            return

        if game.alternatives:
            copies = QHBoxLayout()
            copies.addWidget(QLabel("Autres copies :"))
            for ref in game.alternatives:
                button = QPushButton(ref["source"] + " / " + ref["identifier"])
                button.clicked.connect(lambda checked=False, url=ref["url"]: webbrowser.open(url))
                copies.addWidget(button)
            copies.addStretch(1)
            layout.addLayout(copies)

        hint = QLabel(
            "Sélectionner explicitement les disques et pistes souhaités. "
            "Les variantes ne sont pas fusionnées."
        )
        hint.setObjectName("muted")
        layout.addWidget(hint)

        self.table = QTableWidget(len(game.files), 3)
        self.table.setHorizontalHeaderLabels(
            ["Fichier / édition", "Taille", "Identification source"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        for row, file in enumerate(game.files):
            for column, text in enumerate(
                (file["name"], human_size(file["size"]), file.get("title") or "Non reconnu")
            ):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, column, item)
        if len(game.files) == 1:
            self.table.selectRow(0)
        self.table.selectionModel().selectionChanged.connect(lambda *_: self._update_status())
        layout.addWidget(self.table, stretch=1)

        self.status = QLabel("")
        self.status.setObjectName("muted")
        layout.addWidget(self.status)
        self._update_status()

        controls = QHBoxLayout()
        enqueue = QPushButton("⬇ Ajouter la sélection à la file")
        enqueue.setObjectName("primary")
        enqueue.clicked.connect(self.enqueue)
        controls.addWidget(enqueue)
        select_all = QPushButton("Tout sélectionner")
        select_all.clicked.connect(self.table.selectAll)
        controls.addWidget(select_all)
        cover = QPushButton("Jaquette…")
        cover.clicked.connect(lambda: choose_cover(self.app, game.clean_title))
        controls.addWidget(cover)
        controls.addStretch(1)
        close = QPushButton("Fermer")
        close.clicked.connect(self.reject)
        controls.addWidget(close)
        layout.addLayout(controls)

    def _selected_files(self):
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        return [self.game.files[row] for row in rows]

    def _update_status(self):
        files = self._selected_files()
        self.status.setText(
            f"{len(files)} fichier(s) · {human_size(sum(f['size'] for f in files))} · "
            "CUE : sélectionner aussi ses pistes BIN"
        )

    def enqueue(self):
        try:
            self.app.store.add(
                self.game,
                [f["name"] for f in self._selected_files()],
                self.app.config.download_path,
            )
            self.app.manager.start()
            self.app.show_downloads()
            self.accept()
        except Exception as exc:
            self.status.setText(str(exc))


class LocalDetailsDialog(QDialog):
    """Jeu installé : lancement, vérification, conversion CHD, jaquette."""

    def __init__(self, app, game, parent=None):
        super().__init__(parent or app)
        self.app = app
        self.game = game
        self.setWindowTitle(game.title)
        self.resize(820, 420)
        layout = QVBoxLayout(self)

        title = QLabel(game.title)
        title.setObjectName("heading")
        title.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(QLabel(game.status))

        self.paths = QListWidget()
        self.paths.setObjectName("paths")
        for path in game.paths:
            self.paths.addItem(str(path))
        if game.paths:
            self.paths.setCurrentRow(0)
        layout.addWidget(self.paths, stretch=1)

        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        play = QPushButton("▶ Jouer")
        play.setObjectName("primary")
        play.clicked.connect(self.play)
        buttons.addWidget(play)
        verify = QPushButton("Vérifier")
        verify.clicked.connect(self.verify)
        buttons.addWidget(verify)
        self.media = QComboBox()
        self.media.addItems(["cd", "dvd"])
        buttons.addWidget(self.media)
        convert = QPushButton("Convertir en CHD")
        convert.clicked.connect(self.convert)
        buttons.addWidget(convert)
        folder = QPushButton("Ouvrir dossier")
        folder.clicked.connect(self.open_folder)
        buttons.addWidget(folder)
        cover = QPushButton("Jaquette…")
        cover.clicked.connect(lambda: choose_cover(self.app, game.title))
        buttons.addWidget(cover)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def chosen(self):
        row = self.paths.currentRow()
        if row < 0:
            raise ValueError("Sélectionner un disque")
        return self.game.paths[row]

    def play(self):
        try:
            process, log = launch(self.chosen(), self.app.config)
            self.status.setText(f"Lancement demandé ; journal : {log}")

            def check():
                code = process.poll()
                if code is not None and code != 0:
                    self.status.setText(f"Le lanceur a échoué (code {code}) ; consulter {log}")
                elif code is None:
                    QTimer.singleShot(1000, check)

            QTimer.singleShot(1000, check)
        except Exception as exc:
            self.status.setText(str(exc))

    def verify(self):
        try:
            path = self.chosen()
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self.status.setText("Vérification du fichier, cela peut prendre plusieurs minutes…")

        def work():
            if (self.game.directory / ".romget.json").exists():
                return verify_manifest(self.game.directory, cancel=self.app.work_cancel)
            return self.app.index.verify(
                path,
                get_datfile(self.app.config.cache_dir, self.app.config.datfile_url),
                cancel=self.app.work_cancel,
            )

        self.app.worker.submit(
            work,
            lambda value: self.status.setText(str(value)),
            lambda error: self.status.setText(error),
        )

    def convert(self):
        try:
            path = self.chosen()
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self.status.setText("Conversion et vérification CHD ; les originaux sont conservés…")
        self.app.worker.submit(
            lambda: convert_chd(path, self.media.currentText(), cancel=self.app.work_cancel),
            lambda result: (
                self.app.tab_library.refresh(),
                self.status.setText("CHD vérifié : " + str(result)),
            ),
            lambda error: self.status.setText(error),
        )

    def open_folder(self):
        subprocess.Popen(
            ["xdg-open", str(self.game.directory)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def choose_cover(app, title):
    """Jaquette locale : redimensionnée, nommée par hash du titre, cache mis à jour."""
    filename, _ = QFileDialog.getOpenFileName(
        app, "Choisir une jaquette locale", "", "Images (*.png *.jpg *.jpeg *.webp)"
    )
    if not filename:
        return
    import hashlib
    import io

    from PIL import Image

    base = title.split("(")[0].strip()
    try:
        with Image.open(filename) as source:
            source.thumbnail((600, 900))
            buffer = io.BytesIO()
            source.convert("RGB").save(buffer, "PNG")
        path = (
            app.config.cache_dir
            / "covers"
            / (hashlib.sha256(base.casefold().encode()).hexdigest() + ".png")
        )
        atomic_write(path, buffer.getvalue())
        app.covers.results[base] = path
        app.covers.loaded.emit(base, path)
        app.tab_library.render()
    except Exception as exc:
        app.error(str(exc))
