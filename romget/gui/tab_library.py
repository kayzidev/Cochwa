import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from romget.gui import theme
from romget.gui.widgets import GameGrid, bind_recursive
from romget.services.conversion import convert_all_chd
from romget.services.library import export_csv, scan
from romget.services.library import launch as launch_game


class LibraryTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.games = []
        self.generation = 0
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *args: self.render())
        ttk.Entry(bar, textvariable=self.query).pack(side="left", fill="x", expand=True)
        self.sort = tk.StringVar(value="Titre")
        order = ttk.Combobox(
            bar, textvariable=self.sort, values=["Titre", "Taille"], width=8, state="readonly"
        )
        order.pack(side="left", padx=5)
        order.bind("<<ComboboxSelected>>", lambda event: self.render())
        ttk.Button(bar, text="Actualiser", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Tout convertir en CHD", command=self.convert_all).pack(
            side="left", padx=5
        )
        ttk.Button(bar, text="Doublons", command=self.show_duplicates).pack(side="left")
        ttk.Button(bar, text="Exporter CSV", command=self.export_csv).pack(side="left", padx=5)
        self.status = tk.StringVar(value="Chargement…")
        ttk.Label(self, textvariable=self.status, wraplength=1000).pack(fill="x", pady=8)
        self.grid = GameGrid(self)
        self.grid.pack(fill="both", expand=True)

    def refresh(self):
        self.generation += 1
        generation = self.generation
        root = self.app.config.ps2_dir
        extra = self.app.config.download_dir
        self.status.set(f"Lecture de {root}…")

        def work():
            games = scan(root, self.app.index)
            # Le dossier de téléchargement distinct est scanné aussi : les
            # jeux téléchargés apparaissent sans attendre d'être déplacés.
            if extra and extra != root and extra.is_dir():
                games = games + scan(extra, self.app.index)
            return games

        self.app.dispatch.submit(
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
            self.status.set(error)

    def render(self):
        self.grid.begin()
        games = [g for g in self.games if self.query.get().casefold() in g.title.casefold()]
        games.sort(
            key=(lambda g: -g.size)
            if self.sort.get() == "Taille"
            else (lambda g: g.title.casefold())
        )
        roots = str(self.app.config.ps2_dir)
        extra = self.app.config.download_dir
        if extra and extra != self.app.config.ps2_dir:
            roots += f" + {extra}"
        self.status.set(f"{len(games)} jeu(x) · {roots}")
        for game in games:
            badges = []
            if game.status:
                color = theme.SUCCESS if game.status.startswith("Vérifié") else theme.MUTED
                badges.append((game.status, color))
            card = self.grid.add(
                key=game.title,
                title=game.title,
                size_bytes=game.size,
                badges=badges,
                action=lambda g=game: self.app.local_details(g),
                action_text="▶ Jouer / gérer",
            )
            # Double-clic sur la carte : lancement direct dans PCSX2.
            bind_recursive(card, "<Double-Button-1>", lambda event, g=game: self.launch(g))
            self.app.cover(card, game.title)
        self.grid.set_empty(
            ""
            if games
            else "Bibliothèque vide — vérifier le dossier PS2 dans Paramètres, puis Actualiser."
        )
        self.grid.commit()

    def launch(self, game):
        # Préfère le CHD converti quand il existe.
        path = next((p for p in game.paths if p.suffix.lower() == ".chd"), game.paths[0])
        self.status.set(f"Lancement de {game.title}…")
        self.app.dispatch.submit(
            lambda: launch_game(path, self.app.config),
            lambda result: self.status.set(f"{game.title} lancé ; journal : {result[1]}"),
            lambda error: self.status.set(error),
        )

    def convert_all(self):
        candidates = [
            p
            for g in self.games
            for p in g.paths
            if p.suffix.lower() in {".iso", ".cue"} and not p.with_suffix(".chd").exists()
        ]
        if not candidates:
            self.status.set("Aucun ISO/CUE sans CHD à convertir.")
            return
        if not messagebox.askyesno(
            "Conversion en masse",
            f"Convertir {len(candidates)} disque(s) en CHD ?\n"
            "Les ISO sont traités comme DVD, les CUE comme CD. "
            "Les originaux sont conservés.",
            parent=self,
        ):
            return

        def progress(index, total, name):
            self.app.dispatch.post(
                lambda value: self.status.set(f"Conversion {index}/{total} : {name}")
            )

        def done(report):
            self.refresh()
            message = f"CHD convertis : {len(report['converted'])}"
            if report["failed"]:
                message += f" · échecs : {len(report['failed'])} — " + " | ".join(
                    report["failed"][:3]
                )
            self.status.set(message)
            self.app.notify(message, "error" if report["failed"] else "success")

        self.app.dispatch.submit(
            lambda: convert_all_chd(self.games, cancel=self.app.work_cancel, progress=progress),
            done,
            lambda error: self.status.set(error),
        )

    def export_csv(self):
        if not self.games:
            self.status.set("Bibliothèque vide ; rien à exporter.")
            return
        filename = filedialog.asksaveasfilename(
            title="Exporter la bibliothèque",
            defaultextension=".csv",
            initialfile="bibliotheque-ps2.csv",
            filetypes=[("CSV", "*.csv")],
            parent=self,
        )
        if not filename:
            return
        try:
            export_csv(self.games, filename)
            self.status.set(f"Bibliothèque exportée : {filename}")
            self.app.notify("Bibliothèque exportée : " + filename, "success")
        except OSError as exc:
            self.status.set(str(exc))

    def show_duplicates(self):
        self.app.dispatch.submit(
            self.app.index.duplicates,
            self._duplicates_dialog,
            lambda error: self.status.set(error),
        )

    def _duplicates_dialog(self, groups):
        if not groups:
            self.status.set(
                "Aucun doublon parmi les fichiers vérifiés (hash calculé via « Vérifier »)."
            )
            return
        window = tk.Toplevel(self)
        window.title("Doublons par hash")
        window.geometry("820x420")
        window.configure(bg=theme.BG)
        window.transient(self.app.root)
        ttk.Label(
            window,
            text=f"{len(groups)} hash présents en plusieurs exemplaires "
            "(fichiers vérifiés seulement) :",
            wraplength=780,
        ).pack(fill="x", padx=12, pady=10)
        text = tk.Text(
            window,
            bg=theme.PANEL,
            fg=theme.TEXT,
            highlightthickness=0,
            wrap="none",
            state="normal",
            height=18,
        )
        text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        for md5, paths in groups.items():
            text.insert("end", f"MD5 {md5}\n")
            for path in paths:
                text.insert("end", f"    {path}\n")
            text.insert("end", "\n")
        text.configure(state="disabled")
