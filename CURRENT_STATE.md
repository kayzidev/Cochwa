# État de reprise — romget

Date : 2026-09-27 (Europe/Paris), mise à jour soir.

## Session 6 ter (2026-09-27) — git initialisé + POC PySide6

- **D1 levé** (décision utilisateur) : commit initial sur `master`, branche
  `poc-pyside6` pour le POC Qt.
- **Étude PySide6** : GUI Tkinter ~2 050 lignes à réécrire, ~2 070 lignes
  (services/api/models/config/games_data) réutilisées telles quelles — le GUI
  est totalement isolé (seul « tkinter » hors gui/ = sonde doctor du CLI).
- **POC livré** (`romget/gui_qt/`, lancer : `.venv/bin/python -m romget.gui_qt`) :
  sidebar QSS + `QStackedWidget`, onglet Recommandés réel (20 cartes),
  jaquettes via le service existant en `QThreadPool` (signaux thread-safe),
  fondu GPU (`QGraphicsOpacityEffect`), hover (bordure accent + zoom 1.07),
  cascade d'apparition, élision 2 lignes des titres. Mesure : 19/20 covers en
  1,3 s (cache disque). Capture : `docs/validation/poc-pyside6.png`.
- Piège corrigé : connecter le hub de signaux AVANT de lancer les workers
  (cache disque → réponses en ms, signaux perdus sinon).
- Décision en attente : go/no-go réécriture complète (étapes 1-3 de l'étude).

## Session 6 bis (2026-09-27) — correctifs UI + dossier de téléchargement

- **Bug covers visibles seulement au survol** : l'animation squelette pulsant
  n'était pas annulée à l'arrivée de la jaquette et repeignait le placeholder
  par-dessus → annulation explicite (`_pulse_anim["cancelled"]`). Correction
  annexe : cache de polices canvas **par interpréteur Tk** (les fonts meurent
  avec leur root — cassait les tests GUI en suite) et `animate()` blindé
  contre la destruction de l'interpréteur.
- **Chevauchements carte** : textes mesurés et empilés dynamiquement
  (titre 2 lignes max, méta 1 ligne, badges, taille) avec troncature « … » ;
  le bouton reste ancré en bas.
- **Dossier de téléchargement** : `Config.download_dir` (optionnel, vide =
  dossier PS2, propriété `download_path`), champ + « Choisir… » dans
  Paramètres, utilisé par GUI (`dialogs.enqueue`) et CLI ; la bibliothèque
  scanne aussi ce dossier quand il est distinct. Test de roundtrip ajouté.
- `tools/gui_visual_check.py` : pompage d'événements 3,5 s par onglet (les
  captures attendent jaquettes + animations).
- Suite : 67 tests + 4 tests GUI verts, ruff propre, captures régénérées.

## Session 6 (2026-09-27) — 20 recommandés + modernisation UI (lots A+B)

- **Recommandés du jour : 18 → 20** (`recommended_entries(count=20)`, tests alignés).
- **Lot A (animations, Tkinter pur)** : fondu des jaquettes (crossfade PIL),
  survol des cartes (contour accentué + zoom 1.07), apparition en cascade
  (stagger 25 ms), toasts empilés avec fondu (`ToastManager`, Toplevel alpha),
  squelettes pulsants en attente de cover, barre de progression lissée +
  teintes par état dans Téléchargements, transitions de couleur sur boutons
  (`HoverButton`) et cartes.
- **Lot B (visuel)** : palette type launcher dans `gui/theme.py` (BG #171a21,
  accent #66c0f4), cartes Canvas à coins arrondis + ombre, badges chips
  (score coloré, « ✓ Installé », statut bibliothèque), hiérarchie typo
  (F_TITLE/F_H2/F_BODY/F_SMALL), états vides sur grilles et téléchargements,
  glyphes sur onglets (◎ ◆ ★ ▤ ⬇ ⚙) et boutons (▶ ⬇ ✓).
- **Perf** : `GameGrid.begin()/commit()` — réutilisation des cartes par clé au
  lieu de tout reconstruire (plus de flash au changement d'onglet).
- Nouveau module `romget/gui/theme.py` (palette, `animate()`, `lerp_color()`,
  `HoverButton`, `ToastManager`) ; `widgets.py` réécrit (GameCard Canvas).
- Suite : 66 tests + 4 tests GUI verts, ruff propre, captures régénérées
  dans `docs/validation/`.

## Session 5 (2026-09-27) — vrai Top / 100 recommandés / sources ROM

- **Top PS2** : 64 jeux les mieux notés (scores Metacritic indicatifs), triés par
  score décroissant, affichés avec genre + score + filtre genre.
- **Recommandés** : pool de **100 jeux distincts du Top** (découverte), rotation
  quotidienne de 20/jour (18 → 20 sur demande utilisateur) — les deux onglets
  ne se ressemblent plus.
- **Sources ROM** : état des lieux sondé et documenté dans `docs/SOURCES.md`
  (IA = seule source programmatique viable ; Myrient fermé ; collection IA
  `redump` sans contenu PS2 ; Vimm/CDRomance sans API → import manuel ;
  GameTDB/LaunchBox écartés). Ajout de l'option `ia_collections` (boost des
  collections de confiance au classement, configurable dans config.toml).
- Suite : 70 tests + 4 tests GUI verts, ruff propre ; captures régénérées.

## Session 4 (2026-09-27) — P1/P2/P3 + catalogue dynamique

- **Cache covers** : déjà permanent sur disque (positif) ; cache négatif passé à 24 h.
- **P1** : dédupplication recherche (`_dedupe`, variantes préservées) ; hash Redump
  post-extraction écrit dans le manifeste (statut « Vérifié »).
- **P2** : vitesse moyenne (fenêtre 30 s) + ETA lisible ; double-clic bibliothèque →
  PCSX2 ; bouton « Jaquette… » dans les détails distants ; filtres région/langue
  déjà exposés (constat).
- **P3** : conversion CHD en masse, détection doublons par hash, export CSV,
  variantes de titre SGDB ; GameTDB/LaunchBox évalués et écartés (pas de PS2 /
  pas d'API publique).
- **Catalogue dynamique** : `romget/data/catalog_ps2.json` + extension utilisateur
  `~/.config/romget/catalog_ps2.json` ; Recommandés du jour (rotation quotidienne),
  filtre genre sur Top PS2, badge « ✓ Installé ».
- Suite : 66 tests + 4 tests GUI verts, ruff propre ; captures à jour dans
  `docs/validation/`.

## Session 3 (2026-09-27) — dette technique corrigée

Correction de toute la dette technique de `docs/TECH_DEBT.md` (détail en §5 du
fichier) : lancement unifié sur le venv (D2), ImageTk direct (D4), ruff
installé et appliqué (D5), filtre plateforme renforcé (D6), fallback cover IA
conditionné aux métadonnées (D7), tests d'intégration réseau réels (D8),
validation visuelle des 6 onglets (D9, captures dans `docs/validation/`),
sonde publique branchée en CI hebdo (D10). D1 (commit git) reporté sur décision
utilisateur ; D3 : aucune clé dans le dépôt, renouvellement SGDB à faire par
l'utilisateur. Suites : 55 tests + 4 tests GUI verts, ruff propre, tests réseau
réels validés (`ROMGET_NETWORK_TESTS=1`).

## Demande en cours
Améliorations demandées : vitesse de recherche, obtention des covers, pertinence des résultats, vérification des sources. **Implémentées cette session.**

## Améliorations du 2026-09-27 (session 2)

### Vitesse de recherche (`services/search.py`)
- Pool metadata 4 → 8 threads.
- Pré-filtrage Solr côté IA : `item_size:[100MB TO *]`, tri `downloads desc`, champs `item_size,downloads` — élimine cheats/assets sans appel metadata.
- Pré-filtre local par titre/identifier AVANT les appels metadata (exclusion autres plateformes).
- Mesures : « god of war » 15.8s → 1.3s à froid ; 0.12s avec cache.

### Pertinence des résultats (`services/search.py`)
- Query Solr étendue : `title:(…) OR subject:(…)`.
- Exclusion autres plateformes : `_OTHER_PLATFORM_TERMS` (ps vita, ps3, psp, xbox, pc…) comparés après normalisation (underscores/tirets → espaces, espaces autour) sur titre + identifier.
- Dépriorisation : `_LOW_PRIORITY_TERMS` (cheats, démos, trailers) en fin de liste ; prototypes/betas détectés dans titre ET identifier.
- Tri composite : similarité ×0.65 + popularité (downloads, plafond 50k) ×0.25 + bonus hash Redump ×0.10.
- Mesures : « gran turismo 4 » 8 → 13 résultats, version NTSC 4.36 GB la plus téléchargée en tête ; prototypes GoW relégués en fin ; FFX USA (hash Redump) en tête pour « final fantasy x ».

### Covers (`api/steamgriddb.py`)
- Match SGDB assoupli : meilleur résultat accepté si similarité SequenceMatcher ≥ 0.6 (plus de rejet des quasi-exacts).
- Fallback image IA `https://archive.org/services/img/<identifier>` si SGDB ne trouve rien, **filtré** : images paysage/carrées ou < 250px rejetées (le logo générique IA n'apparaît plus comme jaquette).
- `_fetch_image()` factorisé avec bornes mémoire ; GUI (`app.py`, `tab_search.py`) passe `ia_identifier`.

### Sources / archives (`services/extraction.py`, `services/jobs.py`, `util.py`)
- Myrient fermé le 31/03/2026 → IA confirmée source principale ; pas de grosse collection IA PS2 dédiée trouvée.
- Nombreux items IA en `.rar/.zip/.7z` → **extraction post-download** via 7z (unar en fallback) : `extract_if_archive()` supprime l'archive seulement après extraction réussie d'une image disque.
- Contenu de l'archive listé AVANT extraction (`7z l -ba`) car 7z préserve les mtime d'origine — détection fiable même en re-téléchargement.
- Manifeste `.romget.json` mis à jour : entrées archives remplacées par les fichiers extraits (chemins relatifs, `extracted_from` tracé) → scan bibliothèque affiche « Taille contrôlée ».
- `util.py` : `ARCHIVE_EXTENSIONS`, `is_archive()`, `is_rom_or_archive()` ; `extract_main_rom()` accepte les archives.

### Limites connues
- Items PSP/PS1 sans marqueur explicite : corrigé en session 3 (regex « PlayStation » sans « 2 », collections IA) — à surveiller sur recherches réelles variées.
- Fallback IA : ne tente plus de requête sans fichier jaquette dans les métadonnées (session 3) ; les items sans cover nommée restent sans jaquette hors SGDB.
- Validation visuelle GUI faite en session 3 (6 onglets, `docs/validation/`) ; le téléchargement réel d'une archive reste à valider manuellement.

## Contexte retenu
Application Python PS2 avec GUI Tkinter, recherche Internet Archive, identification Redump, jaquettes SteamGridDB, lancement PCSX2 et accompagnement manuel Steam ROM Manager. Préserver les variantes et mods, notamment GT4 Europe et Spec II. Ne pas arrêter Steam. Le handoff décrit l'environnement historique, qui doit être distingué de l'environnement réellement accessible.

## État observé au début de l'audit
- Sources et documents lus ; version déclarée 0.1.0.
- CLI encore liée au provider historique, GUI liée à l'API de recherche à la demande.
- tests/ vide ; git status ne reconnaît pas de dépôt exploitable dans cet environnement.
- Une clé API est présente en clair dans le handoff et la configuration par défaut du code : ne pas la recopier dans les rapports.
- L'audit détaillé, ses preuves et les limites de validation seront enregistrés dans AUDIT_2026-09-27.md.

Ce fichier constitue la mémoire persistante locale de cette reprise ; il ne suppose pas une mémoire globale entre conversations.

## Audit terminé
- Rapport : AUDIT_2026-09-27.md ; preuves reproductibles dans audit/.
- CLI réelle contrôlée : aide, providers list, recherche et inventaire des cinq ROMs.
- GUI réelle instanciée avec threads externes suspendus : quatre onglets, cinq jeux locaux, défauts de callbacks/badges/installation reproduits. Capture X11 indisponible ; validation visuelle complète encore à faire.
- HTTP réel : Internet Archive fonctionne pour la sonde ; endpoint SteamGridDB actuel 404, variante avec terme dans le chemin 200.
- P0 : suppression de disques non convertis par le convertisseur CHD, reprise HTTP corrompue annoncée réussie, absence de confinement des noms de fichiers distants.
- Suite recommandée : lot intégrité, puis unification CLI/GUI et identité des jeux, puis ergonomie et distribution.
- Aucun correctif produit appliqué. ROMs, Steam, configuration active et clé API inchangés. Secrets à retirer des sources/docs et à renouveler lors du lot de sécurisation.
