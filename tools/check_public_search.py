"""Sonde IA publique uniquement : aucune configuration ni clé utilisateur lue."""

import json
import shutil
import tempfile
from pathlib import Path

from romget.config import DEFAULT_CACHE_DIR, Config, ProviderConfig
from romget.services.search import SearchService

with tempfile.TemporaryDirectory(prefix="romget-public-") as directory:
    cache = Path(directory)
    old = DEFAULT_CACHE_DIR / "ps2_datfile.json"
    if old.exists():
        shutil.copyfile(old, cache / "ps2_datfile.json")
    config = Config(
        providers={"ia_redump": ProviderConfig("ia_redump", options={"cache_dir": str(cache)})}
    )
    result = SearchService(config).search("gran turismo 4", limit=3)
    print(
        json.dumps(
            {
                "source_items": result.total_items,
                "games": [
                    {"id": g.identifier, "files": len(g.files), "identification": g.identification}
                    for g in result.games
                ],
                "warnings": result.warnings,
            },
            ensure_ascii=False,
        )
    )
