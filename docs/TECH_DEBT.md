# Dette technique et TODO prioritaire — romget

Établi le 2026-09-27 après installation de pip (26.0.1) et création du `.venv`.
Base : 3 532 lignes Python, 50/50 tests unittest verts, CI GitHub Actions rédigée
(ruff + unittest + xvfb + build) mais jamais exécutée.

**Mise à jour 2026-09-27 (session 3)** : correction de la dette technique
(D2, D4, D5, D6, D7, D8, D9, D10 corrigés — détails en §5). D1 (commit git)
reporté sur décision utilisateur ; D3 réduit au renouvellement de la clé SGDB
(action utilisateur). Suite : 55 tests unitaires + 4 tests GUI verts, ruff
lint+format propres, 4 tests d'intégration réseau réels validés.

**Mise à jour 2026-09-27 (session 8)** : réécriture totale du GUI en PySide6
(Tkinter supprimé, D2 et D4 soldés). Tests GUI portés sur pytest-qt en
offscreen — ils tournent dans le sandbox, sans display. Suite : 86 tests +
10 sous-tests verts, ruff propre, captures Qt dans `docs/validation/qt/`.
CI mise à jour (libs Qt offscreen) et **première exécution réussie** sur
GitHub (dépôt privé kayzidev/Cochwa).

**Mise à jour 2026-09-27 (session 9)** : projet renommé **Cochwa** (paquet,
entry points avec alias `romget*` conservés, dépôt GitHub). Reste :
renommer le dossier du projet `~/Games/scripts/cochwa` (touche les wrappers
et le remote local — décision utilisateur), et implémenter la console Switch
(registre `consoles.py` prêt, UI en place).

**Mise à jour 2026-09-27 (session 13)** : chantiers de scalabilité de l'audit
soldés — **S2** (stratégie plateforme dans `SearchProfile` + vrai provider
`providers/ia_redump.py`, `SearchService` = orchestration pure), **S1** (config
générique par `console.id`, settings générés depuis le registre), **M1**
(extensions en source unique dans le registre), **M4** (CLI `--console`),
**M2** (purge des caches au démarrage), **M5** (`tomli-w`), **S3** (scan
incrémental sqlite). Suite : 133 tests + 10 sous-tests verts, ruff propre.

## 1. Point sur la dette technique

### Critique (historique — soldé)

| # | Dette | Impact | État |
|---|-------|--------|------|
| D1 | **Git : 0 commit**, tout était untracked | Perte possible de tout le travail ; CI jamais exécutée | **Reporté puis soldé** : dépôt GitHub créé (session 8), commits réguliers depuis session 8 |
| D2 | **Triple chemin de lancement divergent** : wrappers `~/.local/bin` (python3 système + PYTHONPATH) vs `run.sh` (venv si présent) vs entry points `.venv/bin/romget*` | Le GUI actif tournait sur le Python système : Pillow système sans ImageTk, dépendances non verrouillées | **Soldé** (session 3) : wrappers et `run.sh` délèguent aux entry points du venv, PYTHONPATH supprimé, mode `--system` retiré d'`install.sh` |
| D3 | **Clé SteamGridDB en clair** dans `~/.config/cochwa/config.toml` (perms 600) ; renouvellement recommandé car elle a circulé dans des docs historiques | Compromission possible du quota SGDB | **Partiel** (session 3) : aucune clé dans sources/docs (vérifié par grep), perms 600 confirmées ; **renouvellement = action utilisateur** |

### Moyenne (historique — soldé)

| # | Dette | Impact | État |
|---|-------|--------|------|
| D4 | **Contournement `PhotoImage(data=...)`** dans `gui/widgets.py` (ImageTk absent du Pillow système, présent dans le venv) | Double chemin de rendu à maintenir ; PNG re-encodé en mémoire à chaque image | **Soldé** (session 8) : GUI réécrit en PySide6, Tkinter supprimé, plus de dépendance ImageTk |
| D5 | **ruff non installé** dans le venv local alors que la CI l'exige | Dérive de style non détectée localement | **Soldé** (session 3) : `.[dev]` installé, lint+format appliqués et propres |
| D6 | **Filtre plateforme imparfait** : items PSP/PS1 sans marqueur explicite (« Tekken 3 (PlayStation) ») passent | Résultats non-PS2 occasionnels | **Soldé** (session 3) : « PlayStation » seul (lookahead anti-« 2 »), termes PS1 ajoutés, signal des collections IA (`fl[]=collection`) |
| D7 | **Fallback cover IA rarement utile** : la plupart des items ROMs n'ont que des images paysage (captures/logos), rejetées par le filtre portrait | Requêtes IA souvent gaspillées | **Soldé** (session 3) : métadonnées IA inspectées d'abord (cache 24 h) ; sans fichier image « cover/front/boxart », aucune requête image tentée |
| D8 | **Aucun test d'intégration réseau** : les 50 tests mockent IA/SGDB ; les changements d'API réels ne sont détectés qu'à l'usage | Régressions silencieuses possibles | **Soldé** (session 3) : `tests/test_integration_network.py` (4 tests réels, `ROMGET_NETWORK_TESTS=1`, hors CI par défaut) — validés en réel |
| D9 | **Validation visuelle GUI jamais faite** (audit : « capture X11 indisponible ») | Défauts d'affichage inconnus | **Soldé** (session 3, puis session 11) : `tools/gui_visual_check.py` (7 écrans capturés) ; validation complète avec PySide6 dans `docs/validation/cochwa/` |
| D10 | `tools/check_public_search.py` et `docs/audits/baseline-probes/` hors CI | Sondes de non-régression manuelles | **Soldé** (session 3) : workflow `.github/workflows/probe.yml` (cron hebdo + dispatch manuel) |

### Faible / accepté (ou soldé)

- `cli.py` unifié sur les services ; `--console ps2|switch` sur `list`/`play`/`doctor` (session 13 — M4 soldé).
- Cache metadata IA en JSON par item (TTL 3600) — suffisant à cette échelle ; fichiers expirés purgés au démarrage (session 13 — M2 soldé).
- Sérialisation TOML confiée à `tomli-w` (session 13 — M5 soldé, sérialiseur maison supprimé).
- P0 de l'audit initial (suppression disques non convertis, reprise HTTP, confinement chemins) : soldés dans la refonte 0.2 selon `docs/ARCHITECTURE.md`.

## 2. Points d'amélioration

**Recherche** : détection plateforme via les fichiers réels (extensions .iso/.chd vs .apk/.pbp) plutôt que le titre ;
pagination infinie dans l'onglet Recherche. Ajouter une console = entrée
registre + `SearchProfile` + provider branché dans `SearchService` (P1/P2
soldés, session 13).

**Covers** : cache disque permanent (`covers/<hash>.png`) — les jaquettes ne sont
jamais re-téléchargées entre les lancements ; cache négatif 24 h (session 4),
marqueurs périmés purgés au démarrage (session 13).

**Téléchargements** : extraction d'archives en cours de téléchargement (streaming 7z impossible — rester en post-download).

## 3. TODO prioritaire (historique — soldé)

### P0 — Stabilité (soldé session 3-8)

- [x] **Commit initial git** + push (déclenche la CI pour la première fois) — D1 — **soldé (session 8)** : dépôt GitHub créé, CI réussie
- [x] **Unifier le lancement** : wrappers `~/.local/bin/cochwa*` → `exec ~/Games/scripts/cochwa/.venv/bin/cochwa* "$@"` — D2 — **soldé (session 3)**
- [x] Installer les dev deps : `.venv/bin/pip install -e '.[dev]'` + lancer ruff — D5 — **soldé (session 3)**
- [ ] Renouveler la clé SGDB (elle a circulé en clair) et la saisir via l'onglet Paramètres — D3 — **action utilisateur** (nécessite le compte SteamGridDB)
- [x] Validation visuelle GUI complète — D9 — **soldé (sessions 3, 11)** : 7 écrans capturés avec PySide6

### P1 — Fiabilité (soldé session 3-4)

- [x] Test d'intégration réseau marqué `slow` — D8 — **soldé (session 3)**
- [x] Brancher `tools/check_public_search.py` en job CI planifié — D10 — **soldé (session 3)**
- [x] Dédupplication des résultats de recherche — **soldé (session 4)**
- [x] Vérification hash Redump post-extraction — **soldé (session 4)**
- [x] Supprimer le contournement PhotoImage — D4 — **soldé (session 8)** : GUI PySide6, plus de Tkinter/ImageTk

### P2 — Ergonomie (soldé session 4)

- [x] Temps restant estimé + vitesse moyenne dans l'onglet Téléchargements — **soldé (session 4)**
- [x] Choix manuel de jaquette — **soldé (session 4)**
- [x] Filtres région/langue exposés dans l'onglet Recherche — **déjà en place**
- [x] Raccourci : double-clic sur un jeu installé → lancement — **soldé (session 4)**

### P3 — Intégration & features (soldé session 4)

- [x] Conversion CHD en masse depuis l'onglet Bibliothèque — **soldé (session 4)**
- [x] Détection doublons par hash dans l'index — **soldé (session 4)**
- [x] Réessai SGDB avec variantes de titre — **soldé (session 4)**
- [x] Cache négatif covers 1 h → 24 h — **soldé (session 4)**
- [x] Export bibliothèque CSV — **soldé (session 4)**
- [x] Évaluer GameTDB/LaunchBox comme source de covers complémentaire — **soldé (session 4), écarté** : SGDB reste primaire

### Catalogue dynamique (session 4, demande utilisateur)

- Catalogue déplacé vers `cochwa/data/catalog_ps2.json` (titre Redump exact + genre + flag `recommended`) — évolutif sans toucher au code.
- Extension utilisateur : `~/.config/cochwa/catalog_ps2.json` (fusion par titre, rechargée à chaud).
- Onglet **Recommandés du jour** : rotation quotidienne déterministe (graine = date) parmi les entrées `recommended`.
- Onglet **Top PS2** : filtre par genre.
- Badge « ✓ Installé » sur les cartes des deux onglets (croisement avec la bibliothèque).

### Catalogue v2 (session 5, demande utilisateur)

- **Top** = 64 entrées avec score (Metacritic indicatif), triées par score décroissant — le vrai top des mieux notés.
- **Recommandés** = 100 entrées **distinctes du Top**, rotation quotidienne de 18/jour.
- **Sources ROM** : état des lieux sondé dans `docs/SOURCES.md` ; option `ia_collections` (boost des collections IA de confiance).

## 4. Hors scope assumé (ou évolutif)

- Support d'autres consoles au-delà de PS2/Switch : architecture extensible (registre `consoles.py`, `SearchProfile`, providers modulaires). PS2 + Switch actifs depuis session 12.
- Rafraîchissement global du catalogue IA (abandonné : 2 579 items × metadata trop lent ; recherche à la demande retenue).
- Arrêt/relance automatique de Steam (manuel — décision utilisateur).

## 5. Détail des corrections de la session 3 (2026-09-27) — historique

- **Lancement (D2)** : `~/.local/bin/cochwa` et `cochwa-gui` réécrits en `exec` des
  entry points du venv ; `run.sh` simplifié (plus de PYTHONPATH, erreur claire si
  le venv est absent) ; `install.sh` : mode `--system` supprimé, vérification
  PySide6 ajoutée (ImageTk temporairement vérifiée avant migration PySide6). Chemin unique : le venv du projet.
- **Rendu images (D4)** : `gui/widgets.py` utilisait temporairement `ImageTk.PhotoImage`
  directement (session 3) — devenu sans objet après réécriture PySide6 (session 8).
- **Outillage (D5)** : `pip install -e '.[dev]'` ; `ruff format` appliqué
  (4 fichiers) ; lint+format propres sur `cochwa tests tools`.
- **Filtre plateforme (D6)** : regex « PlayStation » non suivi de « 2 » (PS1),
  termes `playstation 1`, `ps one`, `psone`, `playstation classic` ; collections
  IA récupérées (`fl[]=collection`) et exploitées : collections renseignées sans
  signal PS2 et avec signal autre console → exclusion. Tests ajoutés.
- **Fallback covers (D7)** : `_ia_cover_url()` inspecte les métadonnées IA
  (cache disque 24 h) et ne télécharge que si un fichier image nommé
  cover/front/boxart/jaquette/sleeve existe ; sinon aucune requête image
  (services/img ne sert que le logo générique). Tests ajoutés.
- **Tests réseau (D8)** : `tests/test_integration_network.py`, 4 tests réels
  (recherche IA, metadata item, sonde cover IA, recherche SGDB si clé),
  activés par `COCHWA_NETWORK_TESTS=1` — validés en réel le 2026-09-27.
- **Validation visuelle (D9)** : `tools/gui_visual_check.py` capture les écrans
  via spectacle (fenêtre active) ; exécuté avec workers réels :
  rendu PySide6, jaquettes, badges bibliothèque, onglets — aucun défaut.
  Captures dans `docs/validation/cochwa/`.
- **CI (D10)** : `.github/workflows/probe.yml` — cron hebdo (lundi 06:00 UTC)
  + dispatch manuel : sonde `tools/check_public_search.py` + tests réseau.
- **Secrets (D3)** : grep complet sources/docs/tests — aucune clé réelle ;
  `~/.config/cochwa/config.toml` en 600. Renouvellement SGDB à faire par
  l'utilisateur (compte SteamGridDB requis).
