"""Comparaison de titres et regroupement conservateur des copies distantes."""

import re
import unicodedata
from collections import Counter
from dataclasses import replace
from pathlib import PurePosixPath

_ROMAN = dict(
    zip(
        ("ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"),
        map(str, range(2, 13)),
    )
)
_NOISE = re.compile(r"\b(?:sony\s+)?(?:playstation\s*2|ps2|redump)\b", re.I)
_ASSETS = re.compile(
    r"\b(?:cheats?|trainers?|walkthrough|soundtrack|trailers?|manuals?|"
    r"boxart|covers?|textures?|savegame|save\s+data|bios|patch(?:es)?|action replay|gameshark|codebreaker)\b",
    re.I,
)


def normalized(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(
        r"([a-z])([0-9])|([0-9])([a-z])", lambda m: " ".join(x for x in m.groups() if x), text
    )
    return " ".join(re.findall(r"[a-z0-9]+", text))


def tokens(text):
    return [_ROMAN.get(t, t) for t in normalized(_NOISE.sub(" ", text)).split()]


def relevant(query, text):
    """Mots entiers, accents/ponctuation neutralisés, chiffres romains équivalents.

    Un numéro de suite demandé ne doit pas matcher le numéro d'une autre suite
    ou celui d'une révision/année. Une recherche de franchise reste large.
    """
    wanted = tokens(query)
    found = tokens(text)
    if not wanted or not (Counter(wanted) <= Counter(found)):
        return False
    base = tokens(re.split(r"[([]", text)[0])
    for i, token in enumerate(wanted):
        if token.isdigit() and i and not wanted[i - 1].isdigit():
            if not any(base[j : j + 2] == wanted[i - 1 : i + 1] for j in range(len(base) - 1)):
                return False
    # X et X-2 ne sont pas la même édition ; une recherche de franchise
    # sans numéro continue à afficher les deux.
    if wanted[-1].isdigit():
        for j in range(len(base) - len(wanted) + 1):
            if base[j : j + len(wanted)] == wanted:
                end = j + len(wanted)
                if end < len(base) and base[end].isdigit():
                    return False
    return True


def is_unrequested_asset(query, text):
    return bool(_ASSETS.search(normalized(text))) and not _ASSETS.search(normalized(query))


def matches_filters(text, region="", language=""):
    haystack = set(normalized(text).split())
    regions = {
        "europe": {"europe", "eur", "pal"},
        "usa": {"usa", "us", "ntscu"},
        "japan": {"japan", "jpn", "ntscj"},
    }
    langs = {
        "fr": {"fr", "fre", "fra", "french", "francais"},
        "en": {"en", "eng", "english"},
        "ja": {"ja", "jp", "jpn", "japanese"},
        "de": {"de", "ger", "deu", "german"},
        "es": {"es", "spa", "spanish"},
        "it": {"it", "ita", "italian"},
    }
    for value, aliases in ((region, regions), (language, langs)):
        if value and not haystack.intersection(aliases.get(value.casefold(), {value.casefold()})):
            return False
    return True


def duplicate_key(game):
    """Les hashes couvrent tout le jeu de fichiers, jamais une seule piste.

    Sans empreinte complète : mêmes noms (dont région/révision/disque), mêmes
    tailles exactes et même titre. Aucune tolérance en pourcentage.
    """
    if not game.files:
        return ("source", game.source, game.identifier)
    for algorithm, length in (("sha1", 40), ("md5", 32)):
        if all(re.fullmatch("[0-9a-fA-F]{%d}" % length, f.get(algorithm, "")) for f in game.files):
            return (
                game.platform,
                algorithm,
                tuple(sorted((f[algorithm].lower(), f["size"]) for f in game.files)),
            )
    # Les empreintes différentes ne doivent jamais être remplacées par un
    # rapprochement sur les noms, même avec une empreinte manquante ailleurs.
    return (
        game.platform,
        normalized(game.clean_title),
        tuple(
            sorted(
                (
                    normalized(PurePosixPath(f["name"]).name),
                    f["size"],
                    f.get("md5", "").lower(),
                    f.get("sha1", "").lower(),
                )
                for f in game.files
            )
        ),
    )


def dedupe(games):
    kept = {}
    for game in games:
        key = duplicate_key(game)
        if key not in kept:
            kept[key] = replace(game, alternatives=list(game.alternatives))
        else:
            primary = kept[key]
            refs = [*primary.alternatives, game.source_reference(), *game.alternatives]
            seen = {primary.source_reference()["url"]}
            primary.alternatives = []
            for ref in refs:
                if ref["url"] not in seen:
                    primary.alternatives.append(ref)
                    seen.add(ref["url"])
    return list(kept.values())
