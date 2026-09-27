"""Captures Qt reproductibles, sans téléchargement ni lancement de jeu.

QT_QPA_PLATFORM=offscreen .venv/bin/python tools/gui_visual_check.py [sortie]
--local-library : lecture seule des jeux et jaquettes locales configurés.
--workers : autorise également la récupération réseau des jaquettes.
--compact : fenêtre 800 × 600 (sinon 1280 × 860).
L'état SQLite est toujours isolé dans un dossier temporaire.
"""

import argparse
import hashlib
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QApplication

from cochwa.config import Config, ProviderConfig
from cochwa.gui_qt import theme
from cochwa.gui_qt.app import MainWindow
from cochwa.services.library import scan

TABS = [
    "bibliotheque",
    "rechercher",
    "recommandes",
    "top-ps2",
    "telechargements",
    "parametres",
    "support",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=Path("docs/validation/cochwa"))
    parser.add_argument("--workers", action="store_true")
    parser.add_argument("--local-library", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    theme.apply(app)
    with tempfile.TemporaryDirectory(prefix="cochwa-visual-") as temporary:
        root = Path(temporary)
        config = Config(
            ps2_dir=root,
            state_dir=root / "state",
            source=root / "config.toml",
            providers={
                "ia_redump": ProviderConfig("ia_redump", options={"cache_dir": str(root / "cache")})
            },
        )
        if args.local_library or args.workers:
            config = replace(Config.load(), state_dir=root / "state")
        window = MainWindow(config, start_workers=False)
        if args.compact:
            window.resize(800, 600)
        if args.local_library or args.workers:
            games = scan(config.ps2_dir)
            if (
                config.download_dir
                and config.download_dir != config.ps2_dir
                and config.download_dir.is_dir()
            ):
                games += scan(config.download_dir)
            window.tab_library.loaded(games, window.tab_library.generation)
        window.start_workers = args.workers
        window.show()
        for index, name in enumerate(TABS):
            window.sidebar.setCurrentRow(index)
            page = window.pages.currentWidget()
            if hasattr(page, "grid"):
                for card in page.grid.cards:
                    cache_key = hashlib.sha256(card.base_title.casefold().encode()).hexdigest()
                    cover = config.cache_dir / "covers" / (cache_key + ".png")
                    if cover.is_file():
                        card.set_cover(str(cover))
            deadline = time.monotonic() + (3.5 if args.workers else 0.3)
            while time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.02)
            target = args.output / f"tab-{index + 1}-{name}.png"
            window.grab().save(str(target))
            print("capturé :", target)
        window.close()
        window.covers.worker.pool.waitForDone()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
