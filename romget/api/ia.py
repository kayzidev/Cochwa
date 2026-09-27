"""Compatibilité 0.1 ; interfaces modernes dans romget.services."""

from romget.config import Config
from romget.models import IAGame as IAGame
from romget.services.download import download
from romget.services.search import SearchService


def search_ps2(query, max_results=30, ps2_only=False, min_size_mb=0):
    return (
        SearchService(Config.load()).search(query, limit=max_results, verified_only=ps2_only).games
    )


def find_by_title(title):
    # Never substitute an arbitrary larger item for a requested edition.
    games = search_ps2(title.split("(")[0].strip(), max_results=20)
    return next((g for g in games if g.clean_title.casefold() == title.casefold()), None)


def download_file(identifier, filename, dest_path, expected_size=0, progress_callback=None, md5=""):
    from pathlib import Path

    destination = Path(dest_path)
    download(
        identifier,
        filename,
        destination.parent,
        size=expected_size,
        md5=md5,
        progress=progress_callback,
    )
    return True
