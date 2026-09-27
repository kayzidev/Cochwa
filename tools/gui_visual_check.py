"""Validation visuelle : capture chaque onglet du GUI dans un dossier PNG.

Nécessite une session graphique et spectacle (KDE) — capture la fenêtre active.
Usage : .venv/bin/python tools/gui_visual_check.py [dossier_sortie]
"""

import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path

from romget.gui.app import RomgetApp

TABS = [
    "rechercher",
    "recommandes",
    "top-ps2",
    "bibliotheque",
    "telechargements",
    "parametres",
]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = Path(args[0]) if args else Path("docs/validation")
    workers = "--workers" in sys.argv  # workers réels : bibliothèque + jaquettes
    out.mkdir(parents=True, exist_ok=True)
    app = RomgetApp(start_workers=workers)
    app.root.deiconify()
    app.root.lift()
    app.root.focus_force()
    app.root.update_idletasks()
    app.root.update()
    time.sleep(1.0)  # laisse le gestionnaire de fenêtres mapper la fenêtre
    if workers:
        # Laisse bibliothèque et jaquettes se charger avant les captures.
        deadline = time.time() + 20
        while time.time() < deadline and not app.cover_results:
            app.root.update()
            time.sleep(0.5)
        time.sleep(2.0)
    for index, name in enumerate(TABS):
        app.notebook.select(index)
        app.root.lift()
        app.root.focus_force()
        # Pompe la boucle d'événements ~3,5 s : jaquettes téléchargées et
        # animations (cascade, fondu) terminées avant la capture.
        deadline = time.time() + 3.5
        while time.time() < deadline:
            app.root.update()
            time.sleep(0.05)
        target = out / f"tab-{index + 1}-{name}.png"
        # -b : arrière-plan (sans UI) ; -n : pas de notification ; -a : fenêtre active
        subprocess.run(["spectacle", "-b", "-n", "-a", "-o", str(target)], check=True)
        print("capturé :", target)
    if workers:
        app.close()
        try:
            while app.root.winfo_exists():
                app.root.update()
                time.sleep(0.1)
        except tk.TclError:
            pass  # close() a déjà détruit la fenêtre
    else:
        app.root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
