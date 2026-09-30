"""Collections utilisateur : références de jeux, jamais de déplacement de ROM."""

import json
import uuid

from cochwa.infrastructure.storage import file_lock, write_json


class CollectionStore:
    def __init__(self, state_dir):
        self.path = state_dir / "collections.json"

    def read(self):
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text())
        if not isinstance(data, list) or not all(
            isinstance(row, dict)
            and all(isinstance(row.get(k), str) for k in ("id", "name", "platform"))
            and isinstance(row.get("titles"), list)
            and all(isinstance(t, str) for t in row["titles"])
            for row in data
        ):
            raise ValueError("Collections illisibles ; fichier conservé.")
        return data

    def save(self, name, platform, titles, collection_id=None):
        name = name.strip()
        if not name or len(name) > 80:
            raise ValueError("Le nom doit contenir entre 1 et 80 caractères.")
        with file_lock(self.path.with_suffix(".lock")):
            data = self.read()
            if any(
                r["platform"] == platform
                and r["name"].casefold() == name.casefold()
                and r["id"] != collection_id
                for r in data
            ):
                raise ValueError("Une collection porte déjà ce nom sur cette console.")
            row = dict(
                id=collection_id or uuid.uuid4().hex,
                name=name,
                platform=platform,
                titles=sorted(set(titles)),
            )
            data = [r for r in data if r["id"] != row["id"]] + [row]
            write_json(self.path, data)
            return row

    def remove(self, collection_id):
        with file_lock(self.path.with_suffix(".lock")):
            write_json(self.path, [r for r in self.read() if r["id"] != collection_id])
