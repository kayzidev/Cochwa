import threading
import tkinter as tk
from tkinter import ttk

from romget.gui.widgets import GameGrid


class SearchTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.generation = 0
        self.cancel = threading.Event()
        self.page = 1
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        self.query = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.query)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda event: self.do_search())
        ttk.Button(bar, text="Rechercher", command=self.do_search).pack(side="left", padx=5)
        filters = ttk.Frame(self)
        filters.pack(fill="x", pady=8)
        self.verified = tk.BooleanVar(value=False)
        ttk.Checkbutton(filters, text="Hash source Redump reconnu", variable=self.verified).pack(
            side="left"
        )
        self.region = tk.StringVar()
        self.language = tk.StringVar()
        ttk.Label(filters, text="Région").pack(side="left", padx=5)
        ttk.Combobox(
            filters, textvariable=self.region, values=["", "Europe", "USA", "Japan"], width=12
        ).pack(side="left")
        ttk.Label(filters, text="Langue").pack(side="left", padx=5)
        ttk.Combobox(
            filters,
            textvariable=self.language,
            values=["", "Fr", "En", "De", "Es", "It", "Ja"],
            width=5,
        ).pack(side="left")
        self.source = tk.StringVar(value="Toutes")
        ttk.Label(filters, text="Source").pack(side="left", padx=5)
        ttk.Combobox(
            filters,
            textvariable=self.source,
            values=["Toutes", "Internet Archive", "MiNERVA"],
            state="readonly",
            width=16,
        ).pack(side="left")
        self.status = tk.StringVar(
            value="Chercher un titre ; les fichiers et éditions seront proposés avant téléchargement."
        )
        ttk.Label(self, textvariable=self.status, wraplength=1000).pack(fill="x", pady=5)
        self.grid = GameGrid(self)
        self.grid.pack(fill="both", expand=True)
        pager = ttk.Frame(self)
        pager.pack(fill="x")
        self.prev = ttk.Button(
            pager, text="← Page précédente", command=lambda: self.do_search(self.page - 1)
        )
        self.prev.pack(side="left")
        self.next = ttk.Button(
            pager, text="Page suivante →", command=lambda: self.do_search(self.page + 1)
        )
        self.next.pack(side="right")
        self.prev.state(["disabled"])
        self.next.state(["disabled"])

    def do_search(self, page=1):
        query = self.query.get().strip()
        if not query:
            return
        self.cancel.set()
        self.cancel = threading.Event()
        cancel = self.cancel
        self.generation += 1
        generation = self.generation
        page = max(1, page)
        self.page = page
        verified, region, language = self.verified.get(), self.region.get(), self.language.get()
        source = {"Toutes": "all", "Internet Archive": "ia_redump", "MiNERVA": "minerva"}[
            self.source.get()
        ]
        self.grid.clear()
        self.status.set(f"Recherche « {query} » — page {page}…")
        self.prev.state(["disabled"])
        self.next.state(["disabled"])
        self.app.dispatch.submit(
            lambda: self.app.search.search(
                query,
                source=source,
                page=page,
                verified_only=verified,
                region=region,
                language=language,
                cancel=cancel,
            ),
            lambda result: self.show(result, generation),
            lambda error: self.fail(error, generation),
        )

    def fail(self, error, generation):
        if generation == self.generation:
            self.status.set("Erreur : " + error)

    def show(self, result, generation):
        if generation != self.generation:
            return
        self.status.set(
            f"{len(result.games)} résultats sur cette page · {result.total_items} items source · "
            + " / ".join(result.warnings)
        )
        self.prev.state(["!disabled"] if self.page > 1 else ["disabled"])
        self.next.state(["!disabled"] if result.has_more else ["disabled"])
        if result.suggestions:
            self.status.set(
                self.status.get() + " · Suggestions : " + " / ".join(result.suggestions)
            )
        self.grid.begin()
        for game in result.games:
            card = self.grid.add(
                key=game.identifier or game.clean_title,
                title=game.clean_title,
                subtitle=game.label
                + (f" · {len(game.alternatives)} copie(s)" if game.alternatives else ""),
                size_bytes=game.total_size,
                action=lambda g=game: self.app.details(g),
                action_text="Voir la source torrent" if game.external else "Choisir les fichiers",
            )
            self.app.cover(
                card, game.clean_title, ia_identifier=None if game.external else game.identifier
            )
        self.grid.set_empty("" if result.games else "Aucun résultat pour cette recherche.")
        self.grid.commit()
