import time
from tkinter import ttk

from romget.gui import theme
from romget.gui.theme import animate
from romget.util import human_duration, human_size

# Fenêtre glissante pour la vitesse moyenne (secondes).
_RATE_WINDOW = 30.0


class DownloadsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.samples = {}
        self.rows = {}
        self.tree = ttk.Treeview(
            self,
            columns=("title", "state", "progress", "rate", "error"),
            show="headings",
            selectmode="browse",
        )
        for key, text, width in [
            ("title", "Jeu", 260),
            ("state", "État", 100),
            ("progress", "Progression", 180),
            ("rate", "Débit / restant", 150),
            ("error", "Détail", 250),
        ]:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width)
        # Teinte de ligne par état : le statut se lit d'un coup d'œil.
        self.tree.tag_configure("running", background="#1f2d3a")
        self.tree.tag_configure("completed", background="#1f3128")
        self.tree.tag_configure("failed", background="#372225")
        self.tree.tag_configure("cancelled", background="#2a2530")
        self.tree.tag_configure("paused", background="#2e2a20")
        self.tree.pack(fill="both", expand=True)
        self.empty = ttk.Label(
            self,
            text="Aucun téléchargement en file — les jeux choisis apparaîtront ici.",
            foreground=theme.MUTED,
            font=("TkDefaultFont", 11),
        )
        self._progress_anim = None
        self.progress = ttk.Progressbar(self, maximum=100)
        self.progress.pack(fill="x", pady=8)
        self.tree.bind("<<TreeviewSelect>>", lambda event: self.selected())
        buttons = ttk.Frame(self)
        buttons.pack(fill="x")
        for label, callback in [
            ("Pause", lambda key: app.manager.pause(key)),
            ("Reprendre", self.resume),
            ("Annuler", lambda key: app.manager.pause(key, True)),
        ]:
            ttk.Button(buttons, text=label, command=lambda cb=callback: self.act(cb)).pack(
                side="left", padx=4
            )
        ttk.Label(
            self,
            text="Les fichiers partiels sont conservés. Une tâche interrompue reprend sur demande.",
        ).pack(anchor="w", pady=6)

    def act(self, callback):
        selection = self.tree.selection()
        if selection:
            callback(selection[0])
            self.refresh()

    def resume(self, key):
        self.app.store.resume(key)
        self.app.manager.start()

    def selected(self):
        selection = self.tree.selection()
        row = self.rows.get(selection[0]) if selection else None
        self._set_progress(100 * row["progress"] / max(1, row["total"]) if row else 0)

    def _set_progress(self, target):
        """Barre lissée : interpolation vers la valeur cible (~300 ms)."""
        start = self.progress["value"]
        if self._progress_anim:
            self._progress_anim["cancelled"] = True
            self._progress_anim = None
        if abs(start - target) < 0.5:
            self.progress["value"] = target
            return
        self._progress_anim = animate(
            self,
            300,
            lambda t: self.progress.configure(value=start + (target - start) * t),
        )

    def refresh(self):
        now = time.monotonic()
        rows = self.app.store.list()
        if rows:
            self.empty.place_forget()
        else:
            self.empty.place(relx=0.5, rely=0.4, anchor="center")
        for row in rows:
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
            speed = "—"
            if rate > 0 and row["status"] == "running":
                remaining = human_duration((row["total"] - row["progress"]) / rate)
                speed = f"{human_size(rate)}/s · reste {remaining}"
            if row["status"] != "running":
                self.samples.pop(key, None)
            self.rows[key] = row
            labels = {
                "queued": "En attente",
                "running": "En cours",
                "paused": "En pause",
                "cancelled": "Annulé",
                "failed": "Échec",
                "completed": "Terminé",
            }
            values = (
                row["title"],
                labels.get(row["status"], row["status"]),
                f"{human_size(row['progress'])} / {human_size(row['total'])}",
                speed,
                row["error"],
            )
            if self.tree.exists(key):
                self.tree.item(key, values=values, tags=(row["status"],))
            else:
                self.tree.insert("", "end", iid=key, values=values, tags=(row["status"],))
        self.selected()
