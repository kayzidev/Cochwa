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
(Tkinter supprimé, D4 devenue sans objet). Tests GUI portés sur pytest-qt en
offscreen — ils tournent dans le sandbox, sans display. Suite : 86 tests +
10 sous-tests verts, ruff propre, captures Qt dans `docs/validation/qt/`.
CI mise à jour (libs Qt offscreen) et **première exécution réussie** sur
GitHub (dépôt privé kayzidev/Cochwa).

**Mise à jour 2026-09-27 (session 9)** : projet renommé **Cochwa** (paquet,
entry points avec alias `romget*` conservés, dépôt GitHub). Reste :
renommer le dossier du projet `~/Games/scripts/cochwa` (touche les wrappers
et le remote local — décision utilisateur), et implémenter la console Switch
(registre `consoles.py` prêt, UI en place).

## 1. Point sur la dette technique

### Critique

| # | Dette | Impact | État |
|---|-------|--------|------|
| D1 | **Git : 0 commit**, tout est untracked | Perte possible de tout le travail ; CI jamais exécutée | **Reporté** (décision utilisateur : pas de commit) |
| D2 | **Triple chemin de lancement divergent** : wrappers `~/.local/bin` (python3 système + PYTHONPATH) vs `run.sh` (venv si présent) vs entry points `.venv/bin/romget*` | Le GUI actif tourne sur le Python système : Pillow système sans ImageTk, dépendances non verrouillées | **Corrigé** : wrappers et `run.sh` délèguent aux entry points du venv, PYTHONPATH supprimé, mode `--system` retiré d'`install.sh` |
| D3 | **Clé SteamGridDB en clair** dans `~/.config/romget/config.toml` (perms 600) ; renouvellement recommandé car elle a circulé dans des docs historiques | Compromission possible du quota SGDB | **Partiel** : aucune clé dans sources/docs (vérifié par grep), perms 600 confirmées ; **renouvellement = action utilisateur** |

### Moyenne

| # | Dette | Impact | État |
|---|-------|--------|------|
| D4 | **Contournement `PhotoImage(data=...)`** dans `gui/widgets.py` (ImageTk absent du Pillow système, présent dans le venv) | Double chemin de rendu à maintenir ; PNG re-encodé en mémoire à chaque image | **Corrigé** : `ImageTk.PhotoImage` direct, plus de ré-encodage PNG |
| D5 | **ruff non installé** dans le venv local alors que la CI l'exige | Dérive de style non détectée localement | **Corrigé** : `.[dev]` installé, lint+format appliqués et propres |
| D6 | **Filtre plateforme imparfait** : items PSP/PS1 sans marqueur explicite (« Tekken 3 (PlayStation) ») passent | Résultats non-PS2 occasionnels | **Corrigé** : « PlayStation » seul (lookahead anti-« 2 »), termes PS1 ajoutés, signal des collections IA (`fl[]=collection`) |
| D7 | **Fallback cover IA rarement utile** : la plupart des items ROMs n'ont que des images paysage (captures/logos), rejetées par le filtre portrait | Requêtes IA souvent gaspillées | **Corrigé** : métadonnées IA inspectées d'abord (cache 24 h) ; sans fichier image « cover/front/boxart », aucune requête image tentée |
| D8 | **Aucun test d'intégration réseau** : les 50 tests mockent IA/SGDB ; les changements d'API réels ne sont détectés qu'à l'usage | Régressions silencieuses possibles | **Corrigé** : `tests/test_integration_network.py` (4 tests réels, `ROMGET_NETWORK_TESTS=1`, hors CI par défaut) — validés en réel |
| D9 | **Validation visuelle GUI jamais faite** (audit : « capture X11 indisponible ») | Défauts d'affichage inconnus | **Corrigé** : `tools/gui_visual_check.py` (spectacle) ; 6 onglets capturés avec workers réels dans `docs/validation/` — aucun défaut |
| D10 | `tools/check_public_search.py` et `docs/audits/baseline-probes/` hors CI | Sondes de non-régression manuelles | **Corrigé** : workflow `.github/workflows/probe.yml` (cron hebdo + dispatch manuel) |

### Faible / accepté

- `cli.py` (351 lignes) encore partiellement lié au provider historique — unification CLI/GUI déjà recommandée par l'audit.
- Cache metadata IA en JSON par item (TTL 3600) — suffisant à cette échelle.
- P0 de l'audit initial (suppression disques non convertis, reprise HTTP, confinement chemins) : corrigés dans la refonte 0.2 selon `docs/ARCHITECTURE.md`, à re-vérifier par tests ciblés.

## 2. Points d'amélioration

**Recherche** : détection plateforme via les fichiers réels (extensions .iso/.chd vs .apk/.pbp) plutôt que le titre ;
pagination infinie dans l'onglet Recherche.

**Covers** : cache disque permanent (`covers/<hash>.png`) — les jaquettes ne sont
jamais re-téléchargées entre les lancements ; cache négatif 24 h (session 4).

**Téléchargements** : extraction d'archives en cours de téléchargement (streaming 7z impossible — rester en post-download).

## 3. TODO prioritaire

### P0 — Stabilité (cette semaine)

- [ ] **Commit initial git** + push (déclenche la CI pour la première fois) — D1 — **reporté (décision utilisateur, session 3)**
- [x] **Unifier le lancement** : wrappers `~/.local/bin/romget*` → `exec ~/Games/scripts/cochwa/.venv/bin/romget* "$@"` ; supprimer le PYTHONPATH — D2 — **fait (session 3)**
- [x] Installer les dev deps : `.venv/bin/pip install -e '.[dev]'` + lancer ruff — D5 — **fait (session 3)**
- [ ] Renouveler la clé SGDB (elle a circulé en clair) et la saisir via l'onglet Paramètres — D3 — **action utilisateur** (nécessite le compte SteamGridDB)
- [x] Validation visuelle GUI complète (6 onglets, recherche, covers, téléchargement réel d'une archive) — D9 — **fait (session 3)** : 6 onglets capturés avec workers réels (`docs/validation/`) ; le téléchargement réel d'une archive reste à faire manuellement

### P1 — Fiabilité (ce mois)

- [x] Test d'intégration réseau marqué `slow` (hors CI par défaut, lancé manuellement) : recherche IA réelle + 1 cover SGDB réelle — D8 — **fait (session 3)** : `ROMGET_NETWORK_TESTS=1 .venv/bin/python -m unittest tests.test_integration_network -v`
- [x] Brancher `tools/check_public_search.py` en job CI planifié (cron hebdo) — D10 — **fait (session 3)** : `.github/workflows/probe.yml`
- [x] Dédupplication des résultats de recherche (titre nettoyé + taille ±5 %) — **fait (session 4)** : `_dedupe()` après tri ; variantes région/version préservées
- [x] Vérification hash Redump post-extraction quand le MD5 est connu du datfile — **fait (session 4)** : MD5 calculé sur chaque fichier extrait, lookup Redump, `md5`/`title` écrits dans le manifeste → statut « Vérifié » en bibliothèque
- [x] Supprimer le contournement PhotoImage une fois le mode système abandonné — D4 — **fait (session 3)**

### P2 — Ergonomie

- [x] Temps restant estimé + vitesse moyenne dans l'onglet Téléchargements — **fait (session 4)** : moyenne sur fenêtre glissante 30 s + ETA lisible (`human_duration`)
- [x] Choix manuel de jaquette (dialogue `choose_cover` déjà présent, à câbler sur un bouton) — **fait (session 4)** : bouton « Jaquette… » ajouté au dialogue des résultats distants (déjà présent en détails locaux)
- [x] Filtres région/langue exposés dans l'onglet Recherche (le service les supporte déjà) — **déjà en place** (comboboxes Région/Langue dans `tab_search.py`)
- [x] Raccourci : double-clic sur un jeu installé → lancement PCSX2 — **fait (session 4)** : `bind_recursive` sur les cartes Bibliothèque, CHD préféré

### P3 — Intégration & features

- [x] Conversion CHD en masse depuis l'onglet Bibliothèque — **fait (session 4)** : `convert_all_chd()` (ISO→DVD, CUE→CD, originaux conservés), bouton + confirmation + rapport
- [x] Détection doublons par hash dans l'index — **fait (session 4)** : `LibraryIndex.duplicates()` + dialogue « Doublons » (fichiers vérifiés)
- [x] Réessai SGDB avec variantes de titre (sans « The », sans région) — **fait (session 4)** : `_title_variants()`
- [x] Cache négatif covers 1 h → 24 h — **fait (session 4)** : `NEGATIVE_TTL = 86400` (cache positif déjà permanent sur disque)
- [x] Export bibliothèque CSV — **fait (session 4)** : `export_csv()` (séparateur « ; », UTF-8 BOM) + bouton
- [x] Évaluer GameTDB/LaunchBox comme source de covers complémentaire — **fait (session 4), écarté** : GameTDB ne couvre pas la PS2 (Nintendo + PS3/PSP seulement) ; LaunchBox Games Database n'a pas d'API publique gratuite (images liées à leur CDN/application). SGDB reste primaire, fallback fichiers IA conservé.

### Catalogue dynamique (session 4, demande utilisateur)

- Catalogue déplacé vers `romget/data/catalog_ps2.json` (titre Redump exact + genre + flag `recommended`) — évolutif sans toucher au code.
- Extension utilisateur : `~/.config/romget/catalog_ps2.json` (fusion par titre, rechargée à chaud).
- Onglet **Recommandés du jour** : rotation quotidienne déterministe (graine = date) parmi les entrées `recommended`.
- Onglet **Top PS2** : filtre par genre.
- Badge « ✓ Installé » sur les cartes des deux onglets (croisement avec la bibliothèque).

### Catalogue v2 (session 5, demande utilisateur)

- **Top** = 64 entrées avec score (Metacritic indicatif), triées par score décroissant — le vrai top des mieux notés.
- **Recommandés** = 100 entrées **distinctes du Top**, rotation quotidienne de 18/jour.
- **Sources ROM** : état des lieux sondé dans `docs/SOURCES.md` ; option `ia_collections` (boost des collections IA de confiance).

## 4. Hors scope assumé

- Support d'autres consoles (architecture extensible prévue, PS2 d'abord — décision utilisateur).
- Rafraîchissement global du catalogue IA (abandonné : 2 579 items × metadata trop lent ; recherche à la demande retenue).
- Arrêt/relance automatique de Steam (manuel — décision utilisateur).

## 5. Détail des corrections de la session 3 (2026-09-27)

- **Lancement (D2)** : `~/.local/bin/romget` et `romget-gui` réécrits en `exec` des
  entry points du venv ; `run.sh` simplifié (plus de PYTHONPATH, erreur claire si
  le venv est absent) ; `install.sh` : mode `--system` supprimé, vérification
  `ImageTk` ajoutée. Chemin unique : le venv du projet.
- **Rendu images (D4)** : `gui/widgets.py` utilise `ImageTk.PhotoImage`
  directement — fin du double chemin et du ré-encodage PNG en mémoire.
- **Outillage (D5)** : `pip install -e '.[dev]'` ; `ruff format` appliqué
  (4 fichiers) ; lint+format propres sur `romget tests tools`.
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
  activés par `ROMGET_NETWORK_TESTS=1` — validés en réel le 2026-09-27.
- **Validation visuelle (D9)** : `tools/gui_visual_check.py` capture les 6
  onglets via spectacle (fenêtre active) ; exécuté avec workers réels :
  rendu, jaquettes ImageTk, badges bibliothèque, onglets — aucun défaut.
  Captures dans `docs/validation/`.
- **CI (D10)** : `.github/workflows/probe.yml` — cron hebdo (lundi 06:00 UTC)
  + dispatch manuel : sonde `tools/check_public_search.py` + tests réseau.
- **Secrets (D3)** : grep complet sources/docs/tests — aucune clé réelle ;
  `~/.config/romget/config.toml` en 600. Renouvellement SGDB à faire par
  l'utilisateur (compte SteamGridDB requis).
