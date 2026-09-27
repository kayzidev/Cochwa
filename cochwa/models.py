"""Modèles sérialisables, sans dépendance à Tkinter ou au réseau."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import NotRequired, TypedDict
from urllib.parse import quote


class RemoteFile(TypedDict):
    name: str
    size: int
    md5: NotRequired[str]
    sha1: NotRequired[str]
    title: NotRequired[str]
    identification: NotRequired[str]
    content_type: NotRequired[str]
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
    source: str = "ia_redump"
    source_url: str = ""
    external: bool = False
    alternatives: list[dict[str, str]] = field(default_factory=list)

    def source_reference(self):
        return {
            "source": self.source,
            "identifier": self.identifier,
            "url": self.source_url
            or "https://archive.org/details/" + quote(self.identifier, safe=""),
        }

    def to_dict(self):
        return asdict(self)

    @property
    def label(self):
        if self.platform == "switch":
            if self.external:
                return "Switch · archive externe · contenu non vérifié"
            return (
                "Switch · empreinte source disponible"
                if self.identification == "source_checksum"
                else "Switch · empreinte non vérifiée"
            )
        if self.external:
            return "MiNERVA · Torrent externe · empreinte non vérifiée"
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
    has_more: bool = False
    source_totals: dict[str, int] = field(default_factory=dict)
