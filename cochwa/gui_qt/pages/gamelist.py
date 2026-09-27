"""Pages catalogue : Recommandés du jour et Top PS2 (découverte locale instantanée)."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from cochwa.catalog import genres, recommended_entries, recommended_pool, top_entries
from cochwa.gui_qt import theme
from cochwa.gui_qt.cards import GameCard
from cochwa.gui_qt.grid import CardGrid


class GameListPage(QWidget):
    def __init__(self, app, label, genre_filter=False):
        super().__init__()
        self.app = app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 8)
        self.heading = QLabel(label)
        self.heading.setObjectName("heading")
        layout.addWidget(self.heading)
        bar = QHBoxLayout()
        hint = QLabel(
            "Liste de découverte ; choisir une édition dans les résultats avant téléchargement."
        )
        hint.setObjectName("muted")
        bar.addWidget(hint, stretch=1)
        self.genre = None
        if genre_filter:
            bar.addWidget(QLabel("Genre"))
            self.genre = QComboBox()
            self.genre.addItems([""] + genres())
            self.genre.currentTextChanged.connect(lambda _: self.render())
            bar.addWidget(self.genre)
        layout.addLayout(bar)
        self.grid = CardGrid()
        layout.addWidget(self.grid, stretch=1)
        self.app.covers.loaded.connect(self._on_cover)

    def entries(self):
        raise NotImplementedError

    def activate(self):
        # Reconstruit à chaque affichage : badges « Installé » et filtre genre
        # à jour ; les jaquettes sont servies par le cache mémoire/disque.
        self.render()

    def render(self):
        self.grid.clear()
        if self.app.console.id != "ps2":
            self.grid.set_empty(
                "Listes de découverte PS2 — le catalogue Switch arrivera avec sa "
                "source de recherche. La bibliothèque Switch est dans l'onglet Bibliothèque."
            )
            return
        installed = set()
        for title in self.app.installed_titles():
            installed.add(title.casefold())
            installed.add(title.split("(")[0].strip().casefold())
        selected = self.genre.currentText() if self.genre else ""
        for i, entry in enumerate(self.entries()):
            title = entry["title"]
            if selected and entry.get("genre") != selected:
                continue
            base = title.split("(")[0].strip().casefold()
            is_installed = title.casefold() in installed or base in installed
            badges = []
            if type(entry.get("score")) is int:
                badges.append((f"★ {entry['score']}", theme.score_color(entry["score"])))
            if is_installed:
                badges.append(("✓ Installé", theme.SUCCESS))
            card = GameCard(
                title,
                subtitle=entry.get("genre") or "Éditions à rechercher",
                badges=badges,
                action=lambda t=title: self.app.search_title(t),
                action_text="Voir les éditions",
            )
            self.grid.add(card, index=i)
            self.app.cover(card, title)
        self.grid.set_empty("Aucun jeu pour ce genre." if selected else "")

    def _on_cover(self, base, path):
        if not path:
            return
        for card in self.grid.cards:
            if card.base_title == base:
                card.set_cover(str(path))


class RecommendedPage(GameListPage):
    def __init__(self, app):
        super().__init__(app, f"Recommandés du jour — {len(recommended_pool())} jeux en rotation")

    def entries(self):
        # Rotation quotidienne : la sélection change si le jour a changé.
        return recommended_entries()


class TopPage(GameListPage):
    def __init__(self, app):
        entries = top_entries()
        super().__init__(
            app,
            f"Top PS2 — les {len(entries)} mieux notés (scores Metacritic indicatifs)",
            genre_filter=True,
        )
        self._entries = entries

    def entries(self):
        return self._entries
