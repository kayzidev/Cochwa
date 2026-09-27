"""Catalogue local instantané ; résolution de source seulement au clic."""

import tkinter as tk
from tkinter import ttk

from romget.gui import theme
from romget.gui.widgets import GameGrid


class GameListTab(ttk.Frame):
    def __init__(self, parent, app, entries, label="Jeux", genre_filter=False):
        super().__init__(parent, padding=10)
        self.app = app
        self.entries = entries  # [{"title": ..., "genre": ...}]
        ttk.Label(self, text=label, font=theme.F_TITLE).pack(anchor="w")
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=8)
        ttk.Label(
            bar,
            text="Liste de découverte ; choisir une édition dans les résultats avant téléchargement.",
        ).pack(side="left")
        self.genre = tk.StringVar(value="")
        if genre_filter:
            values = [""] + sorted({e.get("genre", "") for e in entries if e.get("genre")})
            combo = ttk.Combobox(
                bar, textvariable=self.genre, values=values, width=18, state="readonly"
            )
            combo.pack(side="right")
            combo.bind("<<ComboboxSelected>>", lambda event: self.render())
            ttk.Label(bar, text="Genre").pack(side="right", padx=5)
        self.grid = GameGrid(self)
        self.grid.pack(fill="both", expand=True)

    def activate(self):
        # Reconstruit à chaque affichage : badges « Installé » et filtre genre
        # à jour ; les jaquettes sont servies par le cache mémoire/disque.
        self.render()

    def render(self):
        self.grid.begin()
        installed = set()
        for title in self.app.installed_titles():
            installed.add(title.casefold())
            installed.add(title.split("(")[0].strip().casefold())
        selected = self.genre.get()
        for entry in self.entries:
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
            card = self.grid.add(
                key=title,
                title=title,
                subtitle=entry.get("genre") or "Éditions à rechercher",
                badges=badges,
                action=lambda t=title: self.app.search_title(t),
                action_text="Voir les éditions",
            )
            self.app.cover(card, title)
        self.grid.set_empty("Aucun jeu pour ce genre." if selected else "")
        self.grid.commit()
