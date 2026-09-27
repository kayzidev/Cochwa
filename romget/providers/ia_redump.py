"""Adaptateur de compatibilité ; aucune implémentation parallèle de transfert."""

from pathlib import Path

from romget.api.redump import get_datfile
from romget.config import Config
from romget.services.download import download
from romget.services.search import SearchService


class IARedumpProvider:
    name = "ia_redump"
    display_name = "Internet Archive — recherche à la demande"
    platform = "ps2"

    def __init__(self, config):
        self.config = config
        self.service = SearchService(Config(providers={"ia_redump": config}))

    def refresh(self, force=False):
        index = get_datfile(self.config.cache_dir, self.config.datfile_url)
        if force:
            index.load(force=True)
        return len(index.md5_to_title)

    def search(self, query, limit=20):
        return self.service.search(query, limit=limit).games

    def find_by_id(self, game_id):
        return self.service.item(game_id)

    def list_games(self):
        raise ValueError(
            "Utiliser une recherche paginée ; le catalogue global historique est retiré"
        )

    def download(self, *args, **kwargs):
        raise ValueError("Sélection explicite requise : utiliser romget download --file")

    def _download_file(self, identifier, filename, dest_dir, expected_size):
        return download(identifier, filename, Path(dest_dir), size=expected_size)

    def _convert_to_chd(self, dest_dir):
        raise ValueError(
            "Conversion de dossier retirée : choisir chaque ISO/CUE et son type de support"
        )
