"""Validation visuelle : capture chaque page du GUI Qt dans un dossier PNG.

Usage : .venv/bin/python tools/gui_visual_check.py [dossier_sortie] [--workers]
--workers : bibliothèque et jaquettes réelles (réseau), sinon pages vides.
"""

import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from cochwa.config import Config
from cochwa.gui_qt import theme
from cochwa.gui_qt.app import MainWindow

TABS = [
    "rechercher",
    "recommandes",
    "top-ps2",
    "bibliotheque",
    "telechargements",
    "parametres",
    "support",
]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = Path(args[0]) if args else Path("docs/validation")
    workers = "--workers" in sys.argv
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.QSS)
    window = MainWindow(Config.load(), start_workers=workers)
    window.show()
    if workers:
        # Laisse bibliothèque et jaquettes se charger avant les captures.
        deadline = time.time() + 20
        while time.time() < deadline and not window.covers.results:
            app.processEvents()
            time.sleep(0.2)
    for index, name in enumerate(TABS):
        window.sidebar.setCurrentRow(index)
        # Pompe la boucle ~3,5 s : jaquettes et animations terminées.
        deadline = time.time() + (3.5 if workers else 0.5)
        while time.time() < deadline:
            app.processEvents()
            time.sleep(0.05)
        target = out / f"tab-{index + 1}-{name}.png"
        window.centralWidget().grab().save(str(target))
        print("capturé :", target)
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
