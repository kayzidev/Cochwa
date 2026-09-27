# Sources de ROM PS2 — état des lieux (2026-09-27)

Sondes réelles effectuées le 2026-09-27 (requêtes archive.org/metadata et
advancedsearch). Conclusion : **Internet Archive reste la seule source
programmatique viable** pour la PS2 à cette date.

## Sources actives dans romget

| Source | Rôle | Statut |
|--------|------|--------|
| Internet Archive (`advancedsearch` + `metadata`) | Recherche et téléchargement de ROMs | ✅ Active — seule source de téléchargement |
| Redump (`redump.org/datfile/ps2`) | Identification par hash MD5 (datfile) | ✅ Active — métadonnées seulement, aucun téléchargement |
| SteamGridDB | Jaquettes | ✅ Active — nécessite une clé API |
| Fichiers IA des items (cover/front/boxart) | Jaquettes de secours | ✅ Active (session 3+) |

## Sources évaluées et écartées

| Source | Raison |
|--------|--------|
| **Myrient** | Fermé le 31/03/2026 |
| **Collection IA `redump`** (« The Unofficial Redump Hoard », 3 083 items) | Sonde 2026-09-27 : **aucun contenu PS2** (GT4 = 0, GoW = 0) — consoles anciennes/PC |
| Collections IA `sony_playstation2`, `redump-sony-playstation-2`, `ps2`, `ps2redump`, `playstation2` | Inexistantes ou vides (sonde : 0 item) |
| **Vimm's Lair**, **CDRomance**, **Emuparadise** | Pas d'API publique ; scraping contraire aux conditions d'utilisation → import manuel dans la bibliothèque |
| **GameTDB** | Ne couvre pas la PS2 (Nintendo + PS3/PSP) |
| **LaunchBox Games Database** | Pas d'API publique gratuite (images liées à leur CDN/application) |
| Usenet / torrents / DDL forums | Hors scope (pas d'API stable, légalité, fiabilité) |

## Ajouter des sources : mécanisme en place

### Collections IA de confiance (session 5)

La recherche IA est globale, mais les items appartenant à des collections
jugées fiables peuvent être **boostés au classement** (+0,05 au score
composite). Configuration dans `~/.config/romget/config.toml` :

```toml
[providers.ia_redump]
ia_collections = ["redump", "fav-playstation_chavy"]
```

Utile si une collection PS2 curée émerge (les collections de favoris
utilisateurs `fav-*` fonctionnent aussi). Les collections inexistantes sont
ignorées silencieusement (aucun item ne les référence).

### Ajouter un vrai provider

L'architecture est extensible (`romget/providers/base.py`) : un provider
doit exposer recherche + fichiers + hashes. Toute source future disposant
d'une API HTTP stable peut être branchée sans toucher au GUI ni aux services.

## Recommandations pratiques

- **Privilégier les items identifiés par hash Redump** (badge « Hash source
  Redump reconnu » dans la recherche) : dump conforme au datfile.
- Les items très téléchargés (`downloads` IA) sont généralement les bons dumps ;
  le tri composite en tient déjà compte.
- Pour les titres absents d'IA : téléchargement manuel puis import dans
  `~/Games/roms/ps2` — le scan bibliothèque les prend en charge, et le bouton
  « Vérifier » les identifie par hash Redump.
