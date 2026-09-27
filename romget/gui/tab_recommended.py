from romget.gui.games_data import recommended_entries, recommended_pool
from romget.gui.tab_gamelist import GameListTab


class RecommendedTab(GameListTab):
    def __init__(self, parent, app):
        super().__init__(
            parent,
            app,
            recommended_entries(),
            f"Recommandés du jour — {len(recommended_pool())} jeux en rotation",
        )

    def activate(self):
        # Rotation quotidienne : la sélection change si le jour a changé.
        self.entries = recommended_entries()
        super().activate()
