"""Composition de l'application Tkinter ; logique métier dans services/."""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from romget.gui import theme
from romget.gui.theme import HoverButton


def build_settings(app, parent):
    frame = ttk.Frame(parent, padding=20)
    ttk.Label(frame, text="Paramètres", font=theme.F_TITLE).grid(
        row=0, column=0, sticky="w", pady=10
    )
    values = {}
    for row, (key, label, value) in enumerate(
        [
            ("directory", "Dossier PS2", str(app.config.ps2_dir)),
            (
                "download",
                "Téléchargements (vide = dossier PS2)",
                str(app.config.download_dir or ""),
            ),
            ("launcher", "Lanceur PCSX2", str(app.config.launcher)),
            ("key", "Clé SteamGridDB", app.config.steamgrid_api_key),
        ],
        start=1,
    ):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=8)
        values[key] = tk.StringVar(value=value)
        ttk.Entry(frame, textvariable=values[key], show="•" if key == "key" else "", width=70).grid(
            row=row, column=1, sticky="ew", padx=10
        )

    def directory():
        path = filedialog.askdirectory(initialdir=str(app.config.ps2_dir))
        if path:
            values["directory"].set(path)

    def download():
        path = filedialog.askdirectory(
            initialdir=str(app.config.download_dir or app.config.ps2_dir)
        )
        if path:
            values["download"].set(path)

    def launcher():
        path = filedialog.askopenfilename(title="Sélectionner le script ou exécutable PCSX2")
        if path:
            values["launcher"].set(path)

    ttk.Button(frame, text="Choisir…", command=directory).grid(row=1, column=2)
    ttk.Button(frame, text="Choisir…", command=download).grid(row=2, column=2)
    ttk.Button(frame, text="Choisir…", command=launcher).grid(row=3, column=2)

    def save():
        root = Path(values["directory"].get()).expanduser()
        if not root.is_dir():
            app.error("Choisir un dossier existant ; vérifier son disque avant de continuer")
            return
        download = values["download"].get().strip()
        download_dir = None
        if download:
            download_dir = Path(download).expanduser()
            if not download_dir.is_dir():
                app.error("Dossier de téléchargement inexistant : " + download)
                return
            download_dir = download_dir.absolute()
        previous = (
            app.config.ps2_dir,
            app.config.download_dir,
            app.config.launcher,
            app.config.steamgrid_api_key,
        )
        try:
            app.config.ps2_dir = root.absolute()
            app.config.download_dir = download_dir
            app.config.launcher = Path(values["launcher"].get()).expanduser().absolute()
            app.config.steamgrid_api_key = values["key"].get().strip()
            app.config.save()
            app.cover_results.clear()
            app.tab_library.refresh()
            app.notify("Paramètres enregistrés", "success")
        except Exception as exc:
            (
                app.config.ps2_dir,
                app.config.download_dir,
                app.config.launcher,
                app.config.steamgrid_api_key,
            ) = previous
            app.error(str(exc))

    HoverButton(frame, text="✓ Enregistrer", command=save, kind="primary").grid(
        row=5, column=1, sticky="w", pady=15
    )
    ttk.Label(
        frame,
        text="Steam ROM Manager : ouvrir SRM, Parse, Preview, Save apps to Steam.\nLe redémarrage de Steam reste manuel.",
        wraplength=750,
    ).grid(row=6, column=0, columnspan=3, sticky="w", pady=15)

    def steam():
        from romget.steam import trigger_srm_reparse

        app.dispatch.submit(
            lambda: trigger_srm_reparse(app.config.srm_flatpak),
            lambda ok: app.status_var.set(
                "SRM ouvert ; effectuer Parse puis Save dans SRM."
                if ok
                else "SRM indisponible ; vérifier Flatpak."
            ),
        )

    ttk.Button(frame, text="Ouvrir Steam ROM Manager", command=steam).grid(
        row=7, column=0, columnspan=2, sticky="w"
    )

    def diagnose():
        from romget.cli import doctor

        data = doctor(app.config)
        window = tk.Toplevel(app.root)
        window.title("Diagnostic local")
        window.configure(bg=theme.BG)
        text = tk.Text(window, width=90, height=25, bg=theme.PANEL, fg=theme.TEXT)
        text.pack(fill="both", expand=True)
        text.insert("1.0", json.dumps(data, ensure_ascii=False, indent=2))
        text.configure(state="disabled")

    ttk.Button(frame, text="Diagnostic local", command=diagnose).grid(
        row=8, column=0, sticky="w", pady=10
    )
    frame.columnconfigure(1, weight=1)
    return frame
