from romget.gui.games_data import top_entries
from romget.gui.tab_gamelist import GameListTab


class TopByConsoleTab(GameListTab):
    def __init__(self, parent, app):
        entries = top_entries()
        super().__init__(
            parent,
            app,
            entries,
            f"Top PS2 — les {len(entries)} mieux notés (scores Metacritic indicatifs)",
            genre_filter=True,
        )
