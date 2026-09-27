"""Bibliothèque locale : scan, filtre, tri, lancement PCSX2, CHD, doublons, CSV."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cochwa.gui_qt import theme
from cochwa.gui_qt.cards import GameCard
from cochwa.gui_qt.grid import CardGrid
from cochwa.services.conversion import convert_all_chd
from cochwa.services.library import export_csv, scan
from cochwa.services.library import launch as launch_game


class LibraryPage(QWidget):
    convert_progress = Signal(int, int, str)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.games = []
        self.generation = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 8)

        bar = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Filtrer la bibliothèque…")
        self.query.textChanged.connect(lambda _: self.render())
        bar.addWidget(self.query, stretch=1)
        self.sort = QComboBox()
        self.sort.addItems(["Titre", "Taille"])
        self.sort.currentTextChanged.connect(lambda _: self.render())
        bar.addWidget(self.sort)
        for label, callback in [
            ("Actualiser", self.refresh),
            ("Tout convertir en CHD", self.convert_all),
            ("Doublons", self.show_duplicates),
            ("Exporter CSV", self.export_csv),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            bar.addWidget(button)
        layout.addLayout(bar)

        self.status = QLabel("Chargement…")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.grid = CardGrid()
        layout.addWidget(self.grid, stretch=1)
        self.app.covers.loaded.connect(self._on_cover)
        self.convert_progress.connect(
            lambda i, total, name: self.status.setText(f"Conversion {i}/{total} : {name}")
        )

    # -- Chargement -----------------------------------------------------

    def refresh(self):
        self.generation += 1
        generation = self.generation
        root = self.app.config.ps2_dir
        extra = self.app.config.download_dir
        self.status.setText(f"Lecture de {root}…")

        def work():
            games = scan(root, self.app.index)
            # Le dossier de téléchargement distinct est scanné aussi.
            if extra and extra != root and extra.is_dir():
                games = games + scan(extra, self.app.index)
            return games

        self.app.worker.submit(
            work,
            lambda games: self.loaded(games, generation),
            lambda error: self.failed(error, generation),
        )

    def loaded(self, games, generation):
        if generation != self.generation:
            return
        self.games = games
        self.render()

    def failed(self, error, generation):
        if generation == self.generation:
            self.games = []
            self.grid.clear()
            self.status.setText(error)

    def render(self):
        self.grid.clear()
        games = [g for g in self.games if self.query.text().casefold() in g.title.casefold()]
        games.sort(
            key=(lambda g: -g.size)
            if self.sort.currentText() == "Taille"
            else (lambda g: g.title.casefold())
        )
        roots = str(self.app.config.ps2_dir)
        extra = self.app.config.download_dir
        if extra and extra != self.app.config.ps2_dir:
            roots += f" + {extra}"
        self.status.setText(f"{len(games)} jeu(x) · {roots}")
        for i, game in enumerate(games):
            badges = []
            if game.status:
                color = theme.SUCCESS if game.status.startswith("Vérifié") else theme.MUTED
                badges.append((game.status, color))
            card = GameCard(
                game.title,
                size_bytes=game.size,
                badges=badges,
                action=lambda g=game: self.app.local_details(g),
                action_text="▶ Jouer / gérer",
                on_double_click=lambda g=game: self.launch(g),
            )
            self.grid.add(card, index=i)
            self.app.cover(card, game.title)
        self.grid.set_empty(
            ""
            if games
            else "Bibliothèque vide — vérifier le dossier PS2 dans Paramètres, puis Actualiser."
        )

    # -- Actions ----------------------------------------------------------

    def launch(self, game):
        # Préfère le CHD converti quand il existe.
        path = next((p for p in game.paths if p.suffix.lower() == ".chd"), game.paths[0])
        self.status.setText(f"Lancement de {game.title}…")
        self.app.worker.submit(
            lambda: launch_game(path, self.app.config),
            lambda result: self.status.setText(f"{game.title} lancé ; journal : {result[1]}"),
            lambda error: self.status.setText(error),
        )

    def convert_all(self):
        candidates = [
            p
            for g in self.games
            for p in g.paths
            if p.suffix.lower() in {".iso", ".cue"} and not p.with_suffix(".chd").exists()
        ]
        if not candidates:
            self.status.setText("Aucun ISO/CUE sans CHD à convertir.")
            return
        answer = QMessageBox.question(
            self,
            "Conversion en masse",
            f"Convertir {len(candidates)} disque(s) en CHD ?\n"
            "Les ISO sont traités comme DVD, les CUE comme CD. Les originaux sont conservés.",
        )
        if answer != QMessageBox.Yes:
            return

        def progress(index, total, name):
            self.convert_progress.emit(index, total, name)

        def done(report):
            self.refresh()
            message = f"CHD convertis : {len(report['converted'])}"
            if report["failed"]:
                message += f" · échecs : {len(report['failed'])} — " + " | ".join(
                    report["failed"][:3]
                )
            self.status.setText(message)
            self.app.notify(message, "error" if report["failed"] else "success")

        self.app.worker.submit(
            lambda: convert_all_chd(self.games, cancel=self.app.work_cancel, progress=progress),
            done,
            lambda error: self.status.setText(error),
        )

    def export_csv(self):
        if not self.games:
            self.status.setText("Bibliothèque vide ; rien à exporter.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exporter la bibliothèque", "bibliotheque-ps2.csv", "CSV (*.csv)"
        )
        if not filename:
            return
        try:
            export_csv(self.games, filename)
            self.status.setText(f"Bibliothèque exportée : {filename}")
            self.app.notify("Bibliothèque exportée : " + filename, "success")
        except OSError as exc:
            self.status.setText(str(exc))

    def show_duplicates(self):
        self.app.worker.submit(
            self.app.index.duplicates,
            self._duplicates_dialog,
            lambda error: self.status.setText(error),
        )

    def _duplicates_dialog(self, groups):
        if not groups:
            self.status.setText(
                "Aucun doublon parmi les fichiers vérifiés (hash calculé via « Vérifier »)."
            )
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Doublons par hash")
        dialog.resize(820, 420)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            QLabel(
                f"{len(groups)} hash présents en plusieurs exemplaires "
                "(fichiers vérifiés seulement) :"
            )
        )
        text = QPlainTextEdit()
        text.setReadOnly(True)
        for md5, paths in groups.items():
            text.appendPlainText(f"MD5 {md5}")
            for path in paths:
                text.appendPlainText(f"    {path}")
            text.appendPlainText("")
        layout.addWidget(text)
        dialog.exec()

    def _on_cover(self, base, path):
        if not path:
            return
        for card in self.grid.cards:
            if card.base_title == base:
                card.set_cover(str(path))
