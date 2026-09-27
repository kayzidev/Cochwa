"""Composition de l'application Tkinter ; logique métier dans services/."""

from __future__ import annotations

import subprocess
import tkinter as tk
from tkinter import filedialog, ttk

from romget.api.redump import get_datfile
from romget.gui import theme
from romget.gui.theme import HoverButton
from romget.infrastructure.storage import atomic_write
from romget.services.conversion import convert_chd
from romget.services.library import launch, verify_manifest
from romget.util import human_size


def show_remote_details(app, game):
    window = tk.Toplevel(app.root)
    window.title(game.clean_title)
    window.geometry("950x560")
    window.configure(bg=theme.BG)
    window.transient(app.root)
    ttk.Label(window, text=game.clean_title, font=theme.F_H2, wraplength=900).pack(
        fill="x", padx=12, pady=10
    )
    ttk.Label(window, text=game.label + " · Source IA : " + game.identifier, wraplength=900).pack(
        fill="x", padx=12
    )
    ttk.Label(
        window,
        text="Sélectionner explicitement les disques et pistes souhaités. Les variantes ne sont pas fusionnées.",
    ).pack(fill="x", padx=12, pady=6)
    frame = ttk.Frame(window)
    frame.pack(fill="both", expand=True, padx=12)
    tree = ttk.Treeview(
        frame, columns=("name", "size", "identity"), show="headings", selectmode="extended"
    )
    for key, label, width in [
        ("name", "Fichier / édition", 540),
        ("size", "Taille", 100),
        ("identity", "Identification source", 200),
    ]:
        tree.heading(key, text=label)
        tree.column(key, width=width)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)
    for i, file in enumerate(game.files):
        tree.insert(
            "",
            "end",
            iid=str(i),
            values=(file["name"], human_size(file["size"]), file.get("title") or "Non reconnu"),
        )
    if len(game.files) == 1:
        tree.selection_set("0")
    status = tk.StringVar(value="Aucun fichier sélectionné")
    ttk.Label(window, textvariable=status).pack(fill="x", padx=12, pady=8)

    def selection(event=None):
        files = [game.files[int(i)] for i in tree.selection()]
        status.set(
            f"{len(files)} fichier(s) · {human_size(sum(f['size'] for f in files))} · CUE : sélectionner aussi ses pistes BIN"
        )

    tree.bind("<<TreeviewSelect>>", selection)
    selection()

    def enqueue():
        try:
            app.store.add(
                game,
                [game.files[int(i)]["name"] for i in tree.selection()],
                app.config.download_path,
            )
            app.manager.start()
            app.notebook.select(app.tab_downloads)
            app.tab_downloads.refresh()
            window.destroy()
        except Exception as exc:
            status.set(str(exc))

    controls = ttk.Frame(window)
    controls.pack(fill="x", padx=12, pady=12)
    HoverButton(
        controls, text="⬇ Ajouter la sélection à la file", command=enqueue, kind="primary"
    ).pack(side="left")
    ttk.Button(
        controls,
        text="Tout sélectionner",
        command=lambda: tree.selection_set(tree.get_children()),
    ).pack(side="left", padx=8)
    ttk.Button(
        controls,
        text="Jaquette…",
        command=lambda: app.choose_cover(game.clean_title),
    ).pack(side="left", padx=8)
    ttk.Button(controls, text="Fermer", command=window.destroy).pack(side="right")


def show_local_details(app, game):
    window = tk.Toplevel(app.root)
    window.title(game.title)
    window.geometry("820x420")
    window.configure(bg=theme.BG)
    window.transient(app.root)
    ttk.Label(window, text=game.title, font=theme.F_H2, wraplength=780).pack(padx=12, pady=12)
    ttk.Label(window, text=game.status).pack()
    paths = tk.Listbox(
        window,
        exportselection=False,
        bg=theme.PANEL,
        fg=theme.TEXT,
        selectbackground=theme.ACCENT_DARK,
        highlightthickness=0,
        height=6,
    )
    paths.pack(fill="both", expand=True, padx=12, pady=8)
    for path in game.paths:
        paths.insert("end", str(path))
    if game.paths:
        paths.selection_set(0)
    status = tk.StringVar()
    ttk.Label(window, textvariable=status, wraplength=780).pack(fill="x", padx=12)

    def chosen():
        selection = paths.curselection()
        if not selection:
            raise ValueError("Sélectionner un disque")
        return game.paths[selection[0]]

    def play():
        try:
            process, log = launch(chosen(), app.config)
            status.set(f"Lancement demandé ; journal : {log}")

            def check():
                if not window.winfo_exists():
                    return
                code = process.poll()
                if code is not None and code != 0:
                    status.set(f"Le lanceur a échoué (code {code}) ; consulter {log}")
                elif code is None:
                    window.after(1000, check)

            window.after(1000, check)
        except Exception as exc:
            status.set(str(exc))

    def verify():
        try:
            path = chosen()
        except ValueError as exc:
            status.set(str(exc))
            return
        status.set("Vérification du fichier, cela peut prendre plusieurs minutes…")

        def work():
            if (game.directory / ".romget.json").exists():
                return verify_manifest(game.directory, cancel=app.work_cancel)
            return app.index.verify(
                path,
                get_datfile(app.config.cache_dir, app.config.datfile_url),
                cancel=app.work_cancel,
            )

        app.dispatch.submit(
            work,
            lambda value: status.set(str(value)) if window.winfo_exists() else None,
            lambda error: status.set(error) if window.winfo_exists() else None,
        )

    media = tk.StringVar(value="dvd")

    def convert():
        try:
            path = chosen()
        except ValueError as exc:
            status.set(str(exc))
            return
        kind = media.get()
        status.set("Conversion et vérification CHD ; les originaux sont conservés…")
        app.dispatch.submit(
            lambda: convert_chd(path, kind, cancel=app.work_cancel),
            lambda result: (
                app.tab_library.refresh(),
                status.set("CHD vérifié : " + str(result)) if window.winfo_exists() else None,
            ),
            lambda error: status.set(error) if window.winfo_exists() else None,
        )

    buttons = ttk.Frame(window)
    buttons.pack(fill="x", padx=12, pady=12)
    HoverButton(buttons, text="▶ Jouer", command=play, kind="primary").pack(side="left")
    ttk.Button(buttons, text="Vérifier", command=verify).pack(side="left", padx=5)
    ttk.Combobox(buttons, textvariable=media, values=["cd", "dvd"], state="readonly", width=5).pack(
        side="left"
    )
    ttk.Button(buttons, text="Convertir en CHD", command=convert).pack(side="left", padx=5)
    ttk.Button(
        buttons,
        text="Ouvrir dossier",
        command=lambda: subprocess.Popen(
            ["xdg-open", str(game.directory)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
    ).pack(side="left")
    ttk.Button(buttons, text="Jaquette…", command=lambda: app.choose_cover(game.title)).pack(
        side="left", padx=5
    )


def choose_cover(app, title):
    filename = filedialog.askopenfilename(
        title="Choisir une jaquette locale", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")]
    )
    if not filename:
        return
    import hashlib
    import io

    from PIL import Image

    title = title.split("(")[0].strip()
    try:
        with Image.open(filename) as source:
            source.thumbnail((600, 900))
            buffer = io.BytesIO()
            source.convert("RGB").save(buffer, "PNG")
        path = (
            app.config.cache_dir
            / "covers"
            / (hashlib.sha256(title.casefold().encode()).hexdigest() + ".png")
        )
        atomic_write(path, buffer.getvalue())
        app.cover_results[title] = path
        app.tab_library.render()
    except Exception as exc:
        app.error(str(exc))
