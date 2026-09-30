"""Lecture seule des raccourcis Steam (format binaire KeyValues)."""

from __future__ import annotations

import struct
from pathlib import Path

MAX_VDF_BYTES = 64 * 1024 * 1024


class _Reader:
    def __init__(self, data):
        self.data = data
        self.position = 0

    def _bytes(self, length):
        end = self.position + length
        if end > len(self.data):
            raise ValueError("Fichier shortcuts.vdf tronqué")
        value = self.data[self.position : end]
        self.position = end
        return value

    def _string(self):
        end = self.data.find(b"\0", self.position)
        if end < 0 or end - self.position > 1024 * 1024:
            raise ValueError("Chaîne invalide dans shortcuts.vdf")
        value = self.data[self.position : end].decode("utf-8", errors="replace")
        self.position = end + 1
        return value

    def object(self, depth=0):
        if depth > 32:
            raise ValueError("Imbrication invalide dans shortcuts.vdf")
        result = {}
        while self.position < len(self.data):
            kind = self._bytes(1)[0]
            if kind == 8:
                return result
            key = self._string()
            if kind == 0:
                value = self.object(depth + 1)
            elif kind == 1:
                value = self._string()
            elif kind in (2, 4):
                value = struct.unpack("<I", self._bytes(4))[0]
            elif kind == 3:
                value = struct.unpack("<f", self._bytes(4))[0]
            elif kind == 6:
                value = self._bytes(4)
            elif kind in (7, 9):
                value = struct.unpack("<Q", self._bytes(8))[0]
            else:
                raise ValueError(f"Type {kind} inconnu dans shortcuts.vdf")
            result[key] = value
        raise ValueError("Fichier shortcuts.vdf incomplet")


def read_shortcuts(path: Path) -> list[dict]:
    """Lit les entrées sans modifier le fichier Steam."""
    path = Path(path)
    try:
        if not path.is_file():
            return []
        if path.stat().st_size > MAX_VDF_BYTES:
            raise ValueError("Fichier shortcuts.vdf trop volumineux")
        reader = _Reader(path.read_bytes())
        root = reader.object()
        shortcuts = root.get("shortcuts")
        if not isinstance(shortcuts, dict) or reader.position != len(reader.data):
            raise ValueError("Structure shortcuts.vdf invalide")
        return [entry for entry in shortcuts.values() if isinstance(entry, dict)]
    except OSError as error:
        raise ValueError(f"Impossible de lire {path}: {error}") from error
