"""Facettes historiques des plateformes prises en charge par le catalogue."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformFacts:
    manufacturer: str
    year: int | None
    processors: tuple[str, ...] = ()


# Les bits décrivent le processeur, sauf la PS2 dont l'Emotion Engine est
# officiellement décrit par Sony comme un processeur RISC 128 bits.
# « x86 » est une architecture, proposée à côté de la largeur en bits.
PLATFORMS = {
    "PlayStation": PlatformFacts("Sony", 1994, ("32 bits",)),
    "PlayStation 2": PlatformFacts("Sony", 2000, ("128 bits",)),
    "PlayStation 3": PlatformFacts("Sony", 2006, ("64 bits",)),
    "PSP": PlatformFacts("Sony", 2004, ("32 bits",)),
    "PS Vita": PlatformFacts("Sony", 2011, ("32 bits",)),
    "Switch": PlatformFacts("Nintendo", 2017, ("64 bits",)),
    "GameCube": PlatformFacts("Nintendo", 2001, ("32 bits",)),
    "Wii": PlatformFacts("Nintendo", 2006, ("32 bits",)),
    "Wii U": PlatformFacts("Nintendo", 2012, ("32 bits",)),
    "Nintendo 3DS": PlatformFacts("Nintendo", 2011, ("32 bits",)),
    "Nintendo DS": PlatformFacts("Nintendo", 2004, ("32 bits",)),
    "Nintendo DSi": PlatformFacts("Nintendo", 2008, ("32 bits",)),
    "Game Boy": PlatformFacts("Nintendo", 1989, ("8 bits",)),
    "Game Boy Color": PlatformFacts("Nintendo", 1998, ("8 bits",)),
    "Game Boy Advance": PlatformFacts("Nintendo", 2001, ("32 bits",)),
    "Nintendo 64": PlatformFacts("Nintendo", 1996, ("64 bits",)),
    "NES": PlatformFacts("Nintendo", 1983, ("8 bits",)),
    "Super Nintendo": PlatformFacts("Nintendo", 1990, ("16 bits",)),
    "Dreamcast": PlatformFacts("Sega", 1998, ("32 bits",)),
    "Naomi": PlatformFacts("Sega", 1998, ("32 bits",)),
    "Atomiswave": PlatformFacts("Sammy", 2003, ("32 bits",)),
    "Saturn": PlatformFacts("Sega", 1994, ("32 bits",)),
    "Mega Drive": PlatformFacts("Sega", 1988, ("16 bits",)),
    "Master System": PlatformFacts("Sega", 1985, ("8 bits",)),
    "Game Gear": PlatformFacts("Sega", 1990, ("8 bits",)),
    "PC Engine": PlatformFacts("NEC", 1987, ("8 bits",)),
    "Neo Geo Pocket": PlatformFacts("SNK", 1998, ("16 bits",)),
    "WonderSwan": PlatformFacts("Bandai", 1999, ("16 bits",)),
    "Xbox": PlatformFacts("Microsoft", 2001, ("32 bits", "x86")),
    "Xbox 360": PlatformFacts("Microsoft", 2005, ("64 bits",)),
    "Arcade": PlatformFacts("Arcade / divers", None),
    "Multiconsole": PlatformFacts("Multi constructeurs", None),
}


def facets(item):
    """Une entrée multiconsole hérite des facettes de toutes ses plateformes."""
    facts = [PLATFORMS[name] for name in item["platforms"]]
    brands = {fact.manufacturer for fact in facts}
    decades = {fact.year // 10 * 10 for fact in facts if fact.year is not None}
    processors = {processor for fact in facts for processor in fact.processors}
    return brands, decades, processors


def brand_label(item):
    brands, _, _ = facets(item)
    return next(iter(brands)) if len(brands) == 1 else "Multi constructeurs"


def filter_emulators(items, query="", platform="", manufacturer="", decade=None, processor=""):
    query = query.strip().casefold()
    matched = []
    for item in items:
        brands, _, _ = facets(item)
        haystack = " ".join(
            (item["name"], *item["platforms"], *brands, brand_label(item))
        ).casefold()
        matching_platform = any(
            (not platform or name == platform)
            and (
                not manufacturer
                or fact.manufacturer == manufacturer
                or (manufacturer == "Multi constructeurs" and brand_label(item) == manufacturer)
            )
            and (decade is None or (fact.year is not None and fact.year // 10 * 10 == decade))
            and (not processor or processor in fact.processors)
            for name in item["platforms"]
            for fact in (PLATFORMS[name],)
        )
        if query in haystack and matching_platform:
            matched.append(item)
    return sorted(
        matched,
        key=lambda item: (
            brand_label(item) == "Multi constructeurs",
            brand_label(item).casefold(),
            item["name"].casefold(),
        ),
    )
