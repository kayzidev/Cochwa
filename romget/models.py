"""Modèles sérialisables, sans dépendance à Tkinter ou au réseau."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import NotRequired, TypedDict


class RemoteFile(TypedDict):
    name: str
    size: int
    md5: NotRequired[str]
    sha1: NotRequired[str]
    title: NotRequired[str]
    identification: NotRequired[str]
    mtime_ns: NotRequired[int]


@dataclass
class IAGame:
    identifier: str
    ia_title: str
    clean_title: str
    files: list[RemoteFile]
    main_rom: str | None
    total_size: int
    is_ps2: bool = False
    identification: str = "unknown"
    platform: str = "ps2"

    def to_dict(self):
        return asdict(self)

    @property
    def label(self):
        return {
            "hash": "Hash source reconnu Redump",
            "title": "Identifié par titre",
            "unknown": "Plateforme non vérifiée / mod possible",
        }.get(self.identification, "Non vérifié")


@dataclass
class SearchResult:
    games: list[IAGame] = field(default_factory=list)
    total_items: int = 0
    page: int = 1
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
