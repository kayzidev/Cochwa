"""Dialogues Qt : sélection de fichiers distants, détails locaux, jaquette manuelle."""

from __future__ import annotations

import subprocess
import webbrowser
from html import escape

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
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from cochwa.api.redump import get_datfile
from cochwa.gui_qt.widgets import PageHeader
from cochwa.infrastructure.storage import atomic_write
from cochwa.services.conversion import convert_chd
from cochwa.services.library import launch, verify_manifest
from cochwa.util import human_size


def _igdb_html(metadata):
    """Présente l'ensemble des champs IGDB récupérés, avec liens échappés."""
    if not metadata:
        return "Aucune correspondance IGDB fiable pour ce titre."
    rows = []

    def row(label, value):
        if value:
            rows.append(f"<b>{escape(label)} :</b> {escape(str(value))}")

    row("Type", metadata.get("game_type"))
    row("Plateformes", ", ".join(metadata.get("platforms", [])))
    row("Première sortie", metadata.get("release_date"))
    releases = metadata.get("release_dates", [])
    if releases:
        row(
            "Sorties par plateforme",
            "; ".join(
                " · ".join(
                    part for part in (r.get("platform"), r.get("date"), r.get("region")) if part
                )
                for r in releases
            ),
        )
    for label, key in (
        ("Genres", "genres"),
        ("Développeurs", "developers"),
        ("Éditeurs", "publishers"),
        ("Modes de jeu", "modes"),
        ("Perspectives", "perspectives"),
        ("Thèmes", "themes"),
        ("Moteurs", "engines"),
        ("Franchises", "franchises"),
        ("Collections", "collections"),
    ):
        row(label, ", ".join(metadata.get(key, [])))
    ratings = metadata.get("age_ratings", [])
    row(
        "Classifications",
        ", ".join(f"{r.get('organization')}: {r.get('rating')}" for r in ratings),
    )
    row("Note utilisateurs IGDB", metadata.get("rating"))
    row("Note critiques IGDB", metadata.get("critic_rating"))
    row("Résumé", metadata.get("summary"))
    row("Scénario", metadata.get("storyline"))
    if metadata.get("cover_url"):
        url = escape(metadata["cover_url"], quote=True)
        rows.append(f'<b>Jaquette :</b> <a href="{url}">ouvrir l’image IGDB</a>')
    websites = metadata.get("websites", [])
    if websites:
        links = " · ".join(
            f'<a href="{escape(url, quote=True)}">{escape(url)}</a>' for url in websites
        )
        rows.append(f"<b>Sites :</b> {links}")
    game_url = escape(metadata.get("url", "https://www.igdb.com/"), quote=True)
    rows.append(f'<a href="{game_url}">Données fournies par IGDB.com</a>')
    return "<br>".join(rows)


def _igdb_view(layout, app, title, platform):
    view = QTextBrowser()
    view.setOpenExternalLinks(True)
    view.setReadOnly(True)
    view.setMaximumHeight(150)
    view.setAccessibleName("Métadonnées du jeu fournies par IGDB")
    view.setHtml("Chargement des métadonnées IGDB…")
    layout.addWidget(view)

    def update(metadata):
        if isValid(view):
            view.setHtml(
                _igdb_html(metadata)
                if metadata
                else (
                    "Configurez votre Twitch Client ID et Client Secret dans Paramètres pour "
                    "activer l’enrichissement IGDB."
                    if not app.metadata.client.configured
                    else _igdb_html(None)
                )
            )

    app.metadata.request(title, platform, update)
    return view


class RemoteDetailsDialog(QDialog):
    """Sélection explicite des disques/pistes avant mise en file."""

    def __init__(self, app, game, parent=None):
        super().__init__(parent or app)
        self.app = app
        self.game = game
        self.console = app.console
        self.setWindowTitle(game.clean_title)
        self.resize(950, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        title = QLabel(game.clean_title)
        title.setObjectName("heading")
        title.setWordWrap(True)
        layout.addWidget(title)
        info = QLabel(f"{game.label} · Source : {game.source} / {game.identifier}")
        info.setObjectName("muted")
        info.setWordWrap(True)
        layout.addWidget(info)
        _igdb_view(layout, app, game.clean_title, game.platform)

        if game.external:
            minerva = game.source == "minerva"
            note = QLabel(
                "Ouvrir la fiche MiNERVA, choisir le torrent dans votre client, puis placer les fichiers extraits dans le dossier PS2."
                if minerva
                else "Cette fiche propose une archive Switch. Ouvrez la source, extrayez le NSP/XCI dans votre dossier Switch, puis actualisez la bibliothèque. Le contenu de l’archive n’a pas été vérifié par Cochwa."
            )
            note.setWordWrap(True)
            layout.addWidget(note)
            open_btn = QPushButton(
                "Ouvrir la fiche MiNERVA" if minerva else "Ouvrir la fiche Internet Archive"
            )
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
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget(len(game.files), 3)
        self.table.setHorizontalHeaderLabels(
            [
                "Fichier / édition",
                "Taille",
                "Contenu" if game.platform == "switch" else "Identification source",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        for row, file in enumerate(game.files):
            for column, text in enumerate(
                (
                    file["name"],
                    human_size(file["size"]),
                    (
                        {"game": "Jeu de base", "update": "Mise à jour", "dlc": "DLC"}.get(
                            file.get("content_type"), "NSP/XCI"
                        )
                        if game.platform == "switch"
                        else file.get("title") or "Non reconnu"
                    ),
                )
            ):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, column, item)
        if len(game.files) == 1:
            self.table.selectRow(0)
        self.table.selectionModel().selectionChanged.connect(lambda *_: self._update_status())
        layout.addWidget(self.table, stretch=1)

        self.status = QLabel("")
        self.status.setObjectName("muted")
        layout.addWidget(self.status)

        controls = QHBoxLayout()
        enqueue = QPushButton("Ajouter à mes téléchargements")
        self.enqueue_button = enqueue
        enqueue.setObjectName("primary")
        enqueue.clicked.connect(self.enqueue)
        controls.addWidget(enqueue)
        if game.platform == "switch" and app.config.switch_dir is None:
            setup = QPushButton("Configurer Switch")
            setup.clicked.connect(lambda: (app.navigate("settings"), self.reject()))
            controls.addWidget(setup)
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
        self._update_status()

    def _selected_files(self):
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        return [self.game.files[row] for row in rows]

    def _update_status(self):
        files = self._selected_files()
        configured = self.game.platform != "switch" or self.app.config.switch_dir is not None
        self.enqueue_button.setEnabled(bool(files) and configured)
        self.enqueue_button.setToolTip(
            "Configurez le dossier Switch dans Paramètres." if not configured else ""
        )
        self.status.setText(
            f"{len(files)} fichier(s) · {human_size(sum(f['size'] for f in files))} · "
            "CUE : sélectionner aussi ses pistes BIN"
        )

    def enqueue(self):
        try:
            self.app.store.add(
                self.game,
                [f["name"] for f in self._selected_files()],
                (
                    self.app.config.switch_dir
                    if self.game.platform == "switch"
                    else self.app.config.download_path
                ),
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
        self.console = app.console
        self.setWindowTitle(game.title)
        self.resize(820, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        layout.addWidget(
            PageHeader(
                game.title,
                f"{app.console.name} · {human_size(game.size)} · {game.status}",
                "DANS VOTRE BIBLIOTHÈQUE",
            )
        )
        _igdb_view(layout, app, game.title, self.console.id)
        main_actions = QHBoxLayout()
        play = QPushButton("▶  Jouer")
        play.setObjectName("primary")
        play.clicked.connect(self.play)
        main_actions.addWidget(play)
        folder = QPushButton("Ouvrir le dossier")
        folder.clicked.connect(self.open_folder)
        main_actions.addWidget(folder)
        cover = QPushButton("Changer la jaquette")
        cover.clicked.connect(lambda: choose_cover(self.app, game.title))
        main_actions.addWidget(cover)
        main_actions.addStretch()
        close = QPushButton("Fermer")
        close.clicked.connect(self.reject)
        main_actions.addWidget(close)
        layout.addLayout(main_actions)
        advanced = QPushButton("Fichiers et outils avancés")
        advanced.setCheckable(True)
        layout.addWidget(advanced)
        details = QWidget()
        detail_layout = QVBoxLayout(details)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        self.paths = QListWidget()
        self.paths.setObjectName("paths")
        for path in game.paths:
            self.paths.addItem(str(path))
        if game.paths:
            self.paths.setCurrentRow(0)
        detail_layout.addWidget(self.paths, stretch=1)
        self.paths.setCurrentRow(
            next((i for i, p in enumerate(game.paths) if p.suffix.lower() == ".chd"), 0)
        )

        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        verify = QPushButton("Vérifier")
        verify.clicked.connect(self.verify)
        buttons.addWidget(verify)
        self.media = QComboBox()
        self.media.addItem("CD", "cd")
        self.media.addItem("DVD", "dvd")
        self.media.setAccessibleName("Type de disque pour la conversion CHD")
        buttons.addWidget(self.media)
        convert = QPushButton("Convertir en CHD")
        self.convert_button = convert
        convert.clicked.connect(self.convert)
        buttons.addWidget(convert)
        # CHD = format disque : sans objet pour les ROMs cartouche (Switch).
        if not app.console.disc_based:
            self.media.setVisible(False)
            convert.setVisible(False)
        self.paths.currentRowChanged.connect(self.update_file_actions)
        self.update_file_actions()
        buttons.addStretch(1)
        detail_layout.addLayout(buttons)
        layout.addWidget(details, stretch=1)
        details.hide()
        advanced.toggled.connect(details.setVisible)
        advanced.toggled.connect(
            lambda checked: advanced.setText(
                "Masquer les outils avancés" if checked else "Fichiers et outils avancés"
            )
        )
        layout.addStretch()

    def update_file_actions(self):
        row = self.paths.currentRow()
        suffix = self.game.paths[row].suffix.lower() if row >= 0 else ""
        convertible = self.console.disc_based and suffix in {".iso", ".cue"}
        self.convert_button.setEnabled(convertible)
        self.media.setEnabled(convertible)
        self.media.setCurrentIndex(0 if suffix == ".cue" else 1)

    def chosen(self):
        row = self.paths.currentRow()
        if row < 0:
            raise ValueError("Sélectionner un disque")
        return self.game.paths[row]

    def play(self):
        try:
            process, log = launch(self.chosen(), self.app.config, console=self.console)
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
        if not self.console.disc_based and not (self.game.directory / ".romget.json").exists():
            self.status.setText(
                "Aucune empreinte source enregistrée pour ce jeu Switch. Redump ne s’applique pas à cette plateforme."
            )
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
        media = self.media.currentData()
        self.app.worker.submit(
            lambda: convert_chd(path, media, cancel=self.app.work_cancel),
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
