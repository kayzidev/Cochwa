# romget — Documentation projet (transfert ChatGPT)

> Outil Linux pour télécharger des ROMs PlayStation 2 depuis Internet Archive, les ranger proprement, et les ajouter à Steam via Steam ROM Manager.
>
> **Statut** : MVP fonctionnel (CLI + GUI Tkinter). Recherche IA à la demande, téléchargement avec resume, jaquettes SteamGridDB, intégration Steam via re-parse SRM.

---

## 1. Chemins et contexte

### Projet
- **Racine projet** : `/home/lucas/Games/scripts/romget/`
- **Wrappers installés** :
  - `~/.local/bin/romget` → CLI (`python3 -m romget`)
  - `~/.local/bin/romget-gui` → GUI Tkinter (`python3 -m romget.gui.app`)
- **Config utilisateur** : `~/.config/romget/config.toml` (auto-générée au 1er lancement)
- **Cache** : `~/.cache/romget/`
  - `ps2_datfile.json` — cache datfile Redump PS2 (14959 hashes MD5, TTL 7 jours)
  - `covers/` — jaquettes SteamGridDB téléchargées
  - `ia_redump.json` — cache provider (legacy, plus utilisé par le GUI)

### Environnement système
- **OS** : Fedora 44 (kernel 7.1.12, Wayland, Mesa 26.1.8, Vulkan 1.4.341)
- **Python** : 3.14.7 (pas de pip installé → wrappers utilisent `PYTHONPATH` au lieu de `pip install`)
- **Dépendances dispo** (toutes dans python3 système, pas besoin de pip) :
  - `requests` 2.33.1
  - `vdf` 3.4 (pour éditer `shortcuts.vdf` Steam)
  - `tomllib` (stdlib Python 3.11+)
  - `Pillow` 12.3.0 — **SANS `ImageTk`** (paquet `python3-pillow-tk` absent sur Fedora) → contournement via `tkinter.PhotoImage(data=png_bytes)`
  - `tkinter` 9.0 (stdlib)
- **Pas de** : `customtkinter`, `ttkbootstrap`, `internetarchive` (lib IA), `pipx`, `pip`

### Matériel
- AMD Ryzen 9 5900X, AMD Radeon RX 6950 XT (RADV Vulkan), 32 Go RAM
- Manette : Valve Steam Controller Puck (USB 28de:1304) — nécessite Steam Input

### Disques montés (fstab + ldmtool)
- `/mnt/Backup-ROMs` (NTFS, 233G) — **contient les ROMs PS2** : `/mnt/Backup-ROMs/Emulateurs/PS2/games/`
- `/mnt/SSD-Gaming` (ext4, 880G)
- `/mnt/Shared-Series` (NTFS, 466G)
- `/mnt/Shared-Movies` (NTFS LDM, 932G)

### Émulateur PCSX2 (déjà configuré)
- AppImage : `~/Emulateurs/pcsx2/pcsx2.AppImage` v2.9.90
- BIOS : `~/Emulateurs/pcsx2/bios/` (3 BIOS : SCPH-70012 USA, SCPH-77008 EUR, SCPH-90006 JAP)
- Script lancement : `~/Games/scripts/pcsx2/launch.sh` (appelé par le bouton "▶ Jouer" du GUI)
- Saves migrés (2,1 Go) : memcards, covers, textures HD GT4, gamesettings

### Steam
- **steamid** : `82197818` (ne pas éteindre Steam — l'utilisateur le fait manuellement)
- **shortcuts.vdf** : `~/.local/share/Steam/userdata/82197818/config/shortcuts.vdf`
- **SRM** (Steam ROM Manager) : flatpak `com.steamgriddb.steam-rom-manager` v2.5.44
  - Config parser PCSX2 : `~/.var/app/com.steamgriddb.steam-rom-manager/config/steam-rom-manager/userData/userConfigurations.json`
  - **fuzzyMatch.removeBrackets = false** (corrigé pour éviter la déduplication de GT4 Europe / GT4 Spec II)
  - romDirectory : `/mnt/Backup-ROMs/Emulateurs/PS2/games`
  - executable : `/home/lucas/Games/scripts/pcsx2/launch.sh`
- **Clé API SteamGridDB** : conservée uniquement dans la configuration locale (valeur retirée du document)

### ROMs PS2 déjà présentes (5)
1. `Gran Turismo 4 (Europe, Australia) (En,Fr,De,Es,It)/...iso` (5.3 GB)
2. `Gran Turismo 4 (Spec II v1.10)/...iso` (3.4 GB) — ROM patchée moddée
3. `Ratchet - Gladiator (Europe, Australia) (En,Fr,De,Es,It).iso` (4.1 GB)
4. `Spyro - A Hero's Tail (Europe, Australia) (En,Fr,De,Es,It,Nl)/...iso` (1.3 GB)
5. `[PS2] Rayman 2 - Revolution [E-F-G-I-S] [SLUS-20138]/...iso` (4.2 GB)

---

## 2. Architecture du code

```
/home/lucas/Games/scripts/romget/
├── pyproject.toml              # packaging (non utilisé — pas de pip)
├── install.sh                  # script install (legacy)
├── README.md
├── PROJECT_HANDOFF.md          # ce fichier
└── romget/
    ├── __init__.py             # version 0.1.0
    ├── __main__.py             # entry CLI: python -m romget
    ├── cli.py                  # argparse + dispatch commandes CLI
    ├── config.py               # chargement config TOML (dataclasses)
    ├── cache.py                # cache JSON provider (legacy)
    ├── util.py                 # sanitize_dirname, human_size, is_iso_like, extract_main_rom
    ├── steam.py                # trigger_srm_reparse() — ouvre SRM + guide utilisateur
    ├── api/
    │   ├── __init__.py
    │   ├── redump.py            # RedumpDatfile : cache datfile PS2 + lookup MD5 → titre propre
    │   ├── ia.py                # search_ps2(), find_by_title(), download_file() — API Internet Archive
    │   └── steamgriddb.py       # download_cover() — jaquettes
    ├── providers/
    │   ├── __init__.py          # registry providers
    │   ├── base.py              # Provider abstrait
    │   └── ia_redump.py         # Provider IA Redump (legacy refresh global — trop lent, abandonné)
    └── gui/
        ├── __init__.py
        ├── app.py               # RomgetApp : fenêtre principale + Notebook 4 onglets + gestion download
        ├── widgets.py           # GameCard, load_image, make_placeholder (contournement ImageTk)
        ├── games_data.py        # TOP_PS2 (39), RECOMMENDED_PS2 (12), TOP_BY_CONSOLE
        ├── tab_search.py        # 🔎 Rechercher
        ├── tab_recommended.py   # ⭐ Recommandés (wrapper GameListTab)
        ├── tab_top.py           # 🏆 Top par console (sélecteur + GameListTab)
        ├── tab_library.py       # 📚 Bibliothèque (scan local + bouton Jouer)
        └── tab_gamelist.py      # GameListTab : base pour listes (charge IA à la demande + jaquettes)
```

---

## 3. API Internet Archive — `romget/api/ia.py`

### `search_ps2(query, max_results=30, ps2_only=False, min_size_mb=500) -> list[IAGame]`

**Query Solr** :
```
q = title:(<query>) AND mediatype:software
```

**⚠️ IMPORTANT** : ne PAS filtrer par `identifier:redump-id-*` — cette collection IA ne contient que des **assets/press discs**, pas les jeux complets. Les vrais jeux PS2 sont des items IA libres avec des noms variés (ex: `gran-turismo-4-spec-ii-1.10`, `2004-gran-turismo-4-usa-v-2.00`).

**Pipeline** :
1. Recherche advancedsearch paginée (200 items/page, max 5 pages)
2. Pour chaque item, appel metadata API en parallèle (12 threads, timeout 15s, 1 retry)
3. Filtre par taille totale > 500 MB (élimine cheats/mods/assets)
4. Croisement MD5 avec datfile Redump PS2 :
   - Si MD5 d'un fichier matche → `clean_title` = titre propre du datfile, `is_ps2 = True`
   - Sinon → `clean_title` = titre IA, `is_ps2 = False` (mais quand même retourné)
5. Tri par taille décroissante

### `find_by_title(title) -> IAGame | None`
- Extrait mots-clés avant la 1ère parenthèse (ex: "Gran Turismo 4" depuis "Gran Turismo 4 (Europe, Australia) (En,Fr,De,Es,It)")
- Appelle `search_ps2(keywords, ps2_only=False)`
- Privilégie le résultat dont le titre IA contient les mots-clés
- Fallback : le plus gros résultat

### `download_file(identifier, filename, dest_path, expected_size, progress_callback) -> bool`
- HTTP stream avec `Range` header pour resume
- Skip si fichier déjà complet (taille == expected_size)
- `progress_callback(written_bytes, total_bytes)` pour barre de progression

### URLs IA
- Search : `https://archive.org/advancedsearch.php`
- Metadata : `https://archive.org/metadata/<identifier>`
- Download : `https://archive.org/download/<identifier>/<filename>`

---

## 4. API Redump — `romget/api/redump.py`

### `RedumpDatfile` (singleton `get_datfile()`)
- Télécharge `http://redump.org/datfile/ps2/` (zip 1.3 MB contenant un `.dat` XML Logiqx)
- Parse le XML : 11774 jeux, 14959 hashes MD5 indexés
- Cache local : `~/.cache/romget/ps2_datfile.json` (TTL 7 jours)
- `lookup_title_by_md5(md5) -> str | None` — retourne le titre propre si le MD5 est dans le datfile PS2
- `is_ps2_title(title) -> bool` — match exact de titre

### Structure datfile XML
```xml
<datafile>
  <header><version>2026-06-15 03-41-38</version></header>
  <game name="Gran Turismo 4 (Europe, Australia) (En,Fr,De,Es,It)">
    <rom name="...iso" size="..." crc="..." md5="..." sha1="..."/>
  </game>
  ...
</datafile>
```

---

## 5. API SteamGridDB — `romget/api/steamgriddb.py`

### `download_cover(api_key, game_title, cache_path=None) -> Path | None`
- Endpoint : `https://www.steamgriddb.com/api/v2`
- `GET /search/autocomplete?term=<title>` (header `Authorization: Bearer <key>`) → game_id
- `GET /grids/game/<game_id>?dimensions=600x900&types=static` → liste jaquettes
- Télécharge la 1ère jaquette, convertit en PNG, cache dans `~/.cache/romget/covers/<safe_name>.png`
- Pour les mods (GT4 Spec II), la recherche utilise le titre nettoyé (avant parenthèses) → jaquette du jeu original

---

## 6. GUI — `romget/gui/app.py`

### `RomgetApp` (classe principale)
- `tk.Tk()` root + `ttk.Notebook` 4 onglets
- Thème sombre : `ttk.Style` "clam" + couleurs dark (`#1e1e1e` bg, `#e0e0e0` fg)
- Taille : 1100x720, min 900x600
- Barre de statut en bas (`status_var`)
- Précharge le datfile en arrière-plan au démarrage (`_preload_datfile` thread)

### Onglets
| Onglet | Fichier | Rôle |
|---|---|---|
| 🔎 Rechercher | `tab_search.py` | Barre + Entrée → `search_ps2()` → grille de `GameCard` |
| ⭐ Recommandés | `tab_recommended.py` | Wrapper `GameListTab(RECOMMENDED_PS2)` (12 jeux) |
| 🏆 Top par console | `tab_top.py` | Sélecteur console (Combobox) + `GameListTab` |
| 📚 Bibliothèque | `tab_library.py` | Scan `ps2_dir` → `GameCard` avec bouton ▶ Jouer |

### `GameListTab` (base pour listes)
- Charge chaque titre via `find_by_title()` en arrière-plan (1 thread, ~1-2s par jeu)
- Affiche les cartes au fur et à mesure (`self.after(0, ...)`)
- Lance le chargement jaquette SteamGridDB par carte en arrière-plan

### `GameCard` (widget)
- Image jaquette (180x250) + titre + sous-titre + taille + bouton "↓ Télécharger" ou "▶ Jouer"
- `on_download(card)` / `on_play(card)` callbacks
- Placeholder `?` si pas de jaquette

### Gestion téléchargement (`app.start_download(game)`)
- Thread séparé (`_download_worker`)
- Pour chaque fichier du jeu : `download_file()` avec callback progression → `status_var`
- À la fin : `messagebox.showinfo` + `tab_library.refresh()`

### Lancement jeu (`app.play_path(path)`)
- Appelle `bash ~/Games/scripts/pcsx2/launch.sh <iso_path>` en `subprocess.Popen` (non bloquant)

---

## 7. CLI — `romget/cli.py`

Commandes (legacy, le GUI est prioritaire maintenant) :
```
romget providers list
romget providers refresh [--force]        # ⚠️ trop lent (2579 items × metadata), abandonné
romget search "<query>" [--limit N]
romget list-available [--limit N] [--offset N]
romget download <game_id> [--chd] [--add-steam]
romget list                                # liste ROMs déjà présentes
romget add-steam                           # re-parse SRM
```

---

## 8. Config — `~/.config/romget/config.toml`

```toml
[roms]
ps2_dir = "/mnt/Backup-ROMs/Emulateurs/PS2/games"

[steam]
method = "srm"                            # re-parse Steam ROM Manager
steamgrid_api_key = ""
srm_flatpak = "com.steamgriddb.steam-rom-manager"

[providers.ia_redump]
enabled = true
datfile_url = "http://redump.org/datfile/ps2/"
cache_dir = "~/.cache/romget"
ia_page_size = 200
```

---

## 9. Décisions techniques importantes

### 9.1 Pourquoi pas de `pip install` ?
- pip n'est pas installé sur le système (Python 3.14 system sans `python3-pip`)
- Solution : wrappers `~/.local/bin/romget` et `romget-gui` utilisent `PYTHONPATH=/home/lucas/Games/scripts/romget`
- Toutes les dépendances (requests, vdf, Pillow, tkinter) sont déjà dans le python3 système

### 9.2 Pourquoi pas `ImageTk` ?
- Pillow 12.3 sur Fedora n'inclut pas `ImageTk` (paquet `python3-pillow-tk` absent)
- Contournement dans `widgets.py` : `_pil_to_tk(img)` convertit PIL → PNG bytes → `tkinter.PhotoImage(data=...)`

### 9.3 Pourquoi pas de refresh global ?
- L'approche initiale (provider `ia_redump.refresh()`) listait tous les 2579 items `redump-id-*` et récupérait leurs metadata en parallèle
- **Problème 1** : 2579 appels metadata × 30s timeout = trop lent (> 10 min, timeouts fréquents)
- **Problème 2** : la collection `redump-id-*` ne contient que des assets, pas les jeux
- **Solution** : recherche à la demande dans le GUI (query IA au clic/recherche, 20-30 résultats max)

### 9.4 Pourquoi `removeBrackets = false` dans SRM ?
- SRM fuzzyMatch avec `removeBrackets=true` nettoyait les titres → "Gran Turismo 4 (Europe)" et "Gran Turismo 4 (Spec II)" devenaient tous deux "Gran Turismo 4" → SRM dédupliquait et ne gardait que le 1er (Europe)
- Corrigé dans `userConfigurations.json` : `removeBrackets = false` pour garder les titres distincts

---

## 10. Limitations connues

1. **Mods non validés** : les ROMs patchées (GT4 Spec II, traductions, undubs) ne sont pas dans le datfile Redump → marquées "non vérifié" mais téléchargeables
2. **Jaquettes mods** : pour les mods, la jaquette du jeu original est utilisée (recherche par titre nettoyé)
3. **Threading Tkinter** : utilisation de `self.after(0, ...)` pour les updates GUI depuis les threads (pas de `threading.Event` avancé)
4. **Pas de barre de progression visuelle** : la progression s'affiche dans la barre de statut texte (pas de ProgressBar widget)
5. **Pas de gestion d'erreurs avancée** : `messagebox.showerror` basique, pas de retry automatique au niveau GUI
6. **Single-user** : pas de gestion multi-utilisateurs, config dans `~/.config/romget/`

---

## 11. Commandes utiles (pour travailler sur le projet)

### Lancer le GUI
```bash
romget-gui                              # ou
python3 -m romget.gui.app
```

### Lancer le CLI
```bash
romget --help
romget search "gran turismo"
romget list
```

### Tuer le GUI en cours
```bash
pkill -f "romget.gui.app"
```

### Tester la recherche IA en CLI
```bash
cd /home/lucas/Games/scripts/romget
python3 -c "
import sys; sys.path.insert(0, '.')
from romget.api.ia import search_ps2
games = search_ps2('gran turismo 4', max_results=10)
for g in games:
    print(f'{g.identifier} | {g.clean_title[:60]} | {g.total_size/1e9:.2f} GB | PS2={g.is_ps2}')
"
```

### Forcer le re-téléchargement du datfile (cache périmé)
```bash
rm ~/.cache/romget/ps2_datfile.json
# Le datfile sera re-téléchargé au prochain lancement
```

### Vider le cache des jaquettes
```bash
rm -rf ~/.cache/romget/covers/
```

---

## 12. Améliorations possibles (TODO)

- [ ] ProgressBar visuelle dans GameCard pendant le téléchargement
- [ ] Onglet "Téléchargements en cours" avec queue
- [ ] Filtre par région (USA/Europe/Japan) dans la recherche
- [ ] Recherche par serial PS2 (SCUS/SCES/SLPS) en plus du titre
- [ ] Support multi-plateforme (PS1, PSP, GC, Wii) — l'architecture `providers/` est prête
- [ ] Conversion CHD automatique après download (wrapper `chdman`)
- [ ] Intégration directe `shortcuts.vdf` (mode Steam "direct" en plus du re-parse SRM)
- [ ] Cache des jaquettes partagé avec SRM (`~/.local/share/Steam/userdata/82197818/config/grid/`)
- [ ] Re-téléchargement auto quand une jaquette manque
- [ ] Drag-and-drop pour réorganiser les jeux
- [ ] Recherche fuzzy (fautes de frappe) dans la barre de recherche

---

## 13. Sources externes utilisées

| Source | URL | Usage |
|---|---|---|
| Internet Archive Search API | `https://archive.org/advancedsearch.php` | Recherche items par titre |
| Internet Archive Metadata API | `https://archive.org/metadata/<id>` | Fichiers + MD5 par item |
| Internet Archive Download | `https://archive.org/download/<id>/<file>` | Téléchargement ROMs |
| Redump PS2 datfile | `http://redump.org/datfile/ps2/` | Liste officielle 11774 jeux + hashes |
| SteamGridDB API v2 | `https://www.steamgriddb.com/api/v2` | Jaquettes (grille portrait 600x900) |
| Steam ROM Manager (SRM) | flatpak `com.steamgriddb.steam-rom-manager` | Ajout raccourcis Steam + jaquettes |

---

**Fin du document.** Transférable tel quel à ChatGPT pour reprise du projet.

---

## 14. Reprise et audit du 27 septembre 2026

Point de reprise durable : `CURRENT_STATE.md`. Audit indépendant du code, de la CLI et des widgets GUI : `AUDIT_2026-09-27.md`, avec preuves dans `audit/`.

Le statut historique « MVP fonctionnel » doit être nuancé : des défauts critiques d'intégrité ont été reproduits (reprise HTTP, suppression excessive après conversion CHD, chemins distants non confinés). La CLI suit encore le provider historique. L'endpoint SteamGridDB actuel retourne 404 lors de la sonde, contrairement à la variante avec le terme dans le chemin. Le fallback Redump sur cache périmé ne fonctionne pas comme décrit plus haut.

Les cinq ROMs locales et les quatre onglets ont été retrouvés. Les tests GUI ont neutralisé les threads externes ; la capture X11 a échoué, donc l'apparence du bureau et les parcours complets restent à valider. Aucun correctif fonctionnel n'a été appliqué à ce stade.

Ce document contient une clé API dans son contenu historique : ne pas le partager tel quel. L'audit ne recopie pas sa valeur et recommande de retirer le secret des sources/documents et de le renouveler.
