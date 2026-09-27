"""Bibliothèque locale : scan, filtre, tri, lancement émulateur, CHD, doublons, CSV."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cochwa.gui_qt import theme
from cochwa.gui_qt.cards import GameCard
from cochwa.gui_qt.grid import CardGrid
from cochwa.gui_qt.widgets import PageHeader
from cochwa.services.conversion import convert_all_chd
from cochwa.services.library import export_csv, scan
from cochwa.services.library import launch as launch_game
from cochwa.util import clean_rom_title, human_size


class LibraryPage(QWidget):
    convert_progress = Signal(int, int, str)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.games = []
        self.generation = 0
        self.platform = app.console.id
        self.contexts = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(14)
        layout.addWidget(
            PageHeader(
                "Votre bibliothèque",
                "Tous vos jeux, un seul endroit. Choisissez votre prochaine aventure.",
            )
        )
        hero = QWidget()
        hero.setObjectName("hero")
        hero.setAttribute(Qt.WA_StyledBackground)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(22, 20, 22, 20)
        summary = QVBoxLayout()
        self.collection_title = QLabel("Votre collection PlayStation 2")
        self.collection_title.setObjectName("sectionTitle")
        summary.addWidget(self.collection_title)
        self.collection_stats = QLabel("Vos jeux locaux apparaîtront ici.")
        self.collection_stats.setObjectName("muted")
        self.collection_stats.setWordWrap(True)
        summary.addWidget(self.collection_stats)
        hero_layout.addLayout(summary, stretch=1)
        explore = QPushButton("Explorer le catalogue  →")
        explore.setObjectName("primary")
        explore.clicked.connect(self.app.focus_search)
        hero_layout.addWidget(explore)
        layout.addWidget(hero)

        bar = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Rechercher dans vos jeux…")
        self.query.setClearButtonEnabled(True)
        self.query.setAccessibleName("Filtrer la bibliothèque")
        self.query.textChanged.connect(lambda _: self.render())
        bar.addWidget(self.query, stretch=1)
        self.sort = QComboBox()
        self.sort.addItems(["Titre", "Taille"])
        self.sort.currentTextChanged.connect(lambda _: self.render())
        bar.addWidget(self.sort)
        refresh = QPushButton("Actualiser")
        refresh.clicked.connect(self.refresh)
        bar.addWidget(refresh)
        tools = QPushButton("Outils")
        menu = QMenu(tools)
        self.convert_button = menu.addAction("Tout convertir en CHD", self.convert_all)
        menu.addAction("Rechercher les doublons", self.show_duplicates)
        menu.addAction("Exporter la bibliothèque en CSV", self.export_csv)
        tools.setMenu(menu)
        bar.addWidget(tools)
        layout.addLayout(bar)

        self.status = QLabel("Votre collection locale")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.grid = CardGrid()
        layout.addWidget(self.grid, stretch=1)
        self.grid.set_empty(
            "Ajoutez votre dossier de jeux dans les paramètres, puis actualisez la bibliothèque.",
            "Faites place à vos jeux",
            "Configurer mes dossiers",
            lambda: self.app.sidebar.setCurrentRow(5),
        )
        self.app.covers.loaded.connect(self._on_cover)
        self.convert_progress.connect(
            lambda i, total, name: self.status.setText(f"Conversion {i}/{total} : {name}")
        )

    # -- Chargement -----------------------------------------------------

    def refresh(self):
        self.generation += 1
        generation = self.generation
        console = self.app.console
        if self.platform != console.id:
            self.contexts[self.platform] = (self.query.text(), self.sort.currentIndex())
            self.platform = console.id
            query, sort = self.contexts.get(console.id, ("", 0))
            self.query.blockSignals(True)
            self.sort.blockSignals(True)
            self.query.setText(query)
            self.sort.setCurrentIndex(sort)
            self.query.blockSignals(False)
            self.sort.blockSignals(False)
        self.collection_title.setText(f"Votre collection {console.name}")
        self.collection_stats.setText("Actualisation de cette plateforme…")
        # CHD = format disque (PS2) ; sans objet pour les ROMs cartouche.
        self.convert_button.setVisible(console.disc_based)
        root = self.app.roms_dir()
        if root is None:
            self.games = []
            self.grid.clear()
            self.status.setText(
                f"Dossier {console.name} non configuré — le renseigner dans Paramètres."
            )
            self.collection_stats.setText("Aucun dossier configuré")
            self.grid.set_empty(
                f"Choisissez le dossier de vos jeux {console.name}.",
                "Votre collection vous attend",
                "Configurer mes dossiers",
                lambda: self.app.sidebar.setCurrentRow(5),
            )
            return
        # Le dossier de téléchargement distinct ne concerne que la PS2
        # (les sources de téléchargement sont PS2 pour l'instant).
        extra = self.app.config.download_dir if console.id == "ps2" else None
        self.status.setText("Actualisation de votre bibliothèque…")
        self.status.setToolTip(str(root))

        def work():
            games = scan(root, self.app.index, extensions=console.rom_extensions)
            if extra and extra != root and extra.is_dir():
                games = games + scan(extra, self.app.index, extensions=console.rom_extensions)
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
            self.grid.set_empty(
                "Vérifiez le dossier et sa disponibilité.",
                "Bibliothèque inaccessible",
                "Réessayer",
                self.refresh,
            )

    def render(self):
        self.grid.clear()
        console = self.app.console
        games = [g for g in self.games if self.query.text().casefold() in g.title.casefold()]
        games.sort(
            key=(lambda g: -g.size)
            if self.sort.currentText() == "Taille"
            else (lambda g: g.title.casefold())
        )
        roots = str(self.app.roms_dir() or "—")
        extra = self.app.config.download_dir if console.id == "ps2" else None
        if extra and extra != self.app.roms_dir():
            roots += f" + {extra}"
        self.status.setText(f"{len(games)} jeu(x) affiché(s) · {console.name}")
        self.status.setToolTip(roots)
        self.collection_stats.setText(
            f"{len(self.games)} jeux  ·  {human_size(sum(g.size for g in self.games))}  ·  {console.emulator}"
        )
        for i, game in enumerate(games):
            badges = []
            if game.status:
                color = theme.SUCCESS if game.status.startswith("Vérifié") else theme.MUTED
                badges.append((game.status, color))
            # Les dumps Switch portent des tags [titleID][vX][région] : retirés
            # à l'affichage (et pour la recherche de jaquette).
            title = game.title if console.disc_based else clean_rom_title(game.title)
            card = GameCard(
                title,
                subtitle=console.name,
                size_bytes=game.size,
                badges=badges,
                action=lambda g=game: self.launch(g),
                action_text="▶  Jouer",
                secondary_action=lambda g=game: self.app.local_details(g),
                secondary_text="Détails et outils",
                on_double_click=lambda g=game: self.launch(g),
            )
            self.grid.add(card, index=i)
            self.app.cover(card, title)
        if games:
            self.grid.set_empty("")
        elif self.query.text():
            self.grid.set_empty(
                "Essayez un autre titre ou effacez votre recherche.",
                "Aucun jeu correspondant",
                "Effacer la recherche",
                self.query.clear,
            )
        else:
            self.grid.set_empty(
                f"Choisissez le dossier de vos jeux {console.name} dans les paramètres.",
                "Votre collection vous attend",
                "Configurer mes dossiers",
                lambda: self.app.sidebar.setCurrentRow(5),
            )

    # -- Actions ----------------------------------------------------------

    def launch(self, game):
        # Préfère le CHD converti quand il existe (consoles à disques).
        path = next((p for p in game.paths if p.suffix.lower() == ".chd"), game.paths[0])
        self.status.setText(f"Lancement de {game.title}…")
        console = self.app.console
        self.app.worker.submit(
            lambda: launch_game(path, self.app.config, console=console),
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
            self,
            "Exporter la bibliothèque",
            f"bibliotheque-{self.app.console.id}.csv",
            "CSV (*.csv)",
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
