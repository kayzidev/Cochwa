# Cochwa

Bibliothèque de ROMs pour Linux : PS2 et Nintendo Switch, recherche Internet Archive (et MiNERVA pour la PS2), téléchargements vérifiés et reprenables, jaquettes, lanceurs par console et préréglages Steam ROM Manager générés depuis Cochwa.

## Contenu hébergé : aucun

Cochwa **n'héberge aucun lien ni aucun contenu**. Le logiciel interroge des catalogues publics (Internet Archive, MiNERVA) et renvoie vers leurs pages ; les téléchargements s'effectuent directement entre l'utilisateur et ces services tiers. Cochwa ne contient aucune ROM, aucun lien vers des ROMs et aucune clé de contournement.

## Démarrer sur cette machine

Les wrappers existants `romget` et `romget-gui` restent compatibles (alias des entry points `cochwa` / `cochwa-gui`). Depuis le projet :

```bash
./install.sh            # crée .venv et installe le paquet (GUI PySide6 inclus)
./run.sh                # GUI
./run.sh --cli doctor    # diagnostic local, sans réseau ni affichage de clé
```

Sur une nouvelle installation : Python ≥ 3.11 avec venv/pip, puis `./install.sh`. Le script crée `.venv` et installe le paquet (requests, Pillow, PySide6) sans modifier Python système. La conversion optionnelle requiert `chdman` ; le lancement requiert un émulateur/configuration PCSX2 déjà fonctionnels.

## Configuration

Le fichier existant `~/.config/romget/config.toml` est lu sans migration destructive (repli automatique sur l'ancien dossier XDG `romget` s'il existe ; les nouvelles installations utilisent `~/.config/cochwa/`). Pour une installation neuve, les dossiers par défaut sont `~/Games/roms/ps2`, `$XDG_CACHE_HOME/cochwa` et `$XDG_STATE_HOME/cochwa` (ou leurs valeurs usuelles). Le dossier ROMs doit exister avant un téléchargement. La GUI permet de choisir le dossier, le lanceur PCSX2 et une clé SteamGridDB puis de les enregistrer. La clé reste locale ; aucun secret par défaut.

Un fichier alternatif s'utilise avec `cochwa --config /chemin/config.toml …` ou `cochwa-gui --config /chemin/config.toml`.

## CLI

```bash
cochwa search 'gran turismo 4' --region Europe --language Fr
cochwa search 'final fantasy x' --source minerva
cochwa search 'god of war 2' --source ia_redump
cochwa search 'gran turismo 4' --page 2 --limit 20
cochwa inspect IDENTIFIANT_IA
cochwa download IDENTIFIANT_IA --file 'Nom exact.iso' --dry-run
cochwa download IDENTIFIANT_IA --file 'Nom exact.iso'
cochwa download IDENTIFIANT_IA --file 'Disque.cue' --file 'Piste.bin' --enqueue
cochwa jobs list
cochwa jobs run
cochwa jobs resume ID_TACHE
cochwa list --query 'Gran Turismo'
cochwa verify '/chemin/jeu.iso'
cochwa verify '/chemin/dossier-avec-manifeste'
cochwa convert '/chemin/jeu.iso' --media dvd
cochwa play '/chemin/jeu.chd'
cochwa add-steam
cochwa --json doctor
```

`--all` sélectionne explicitement tous les fichiers d'un item, y compris ses différentes éditions. `--chd --media cd|dvd` permet la conversion après un téléchargement CLI. `--enqueue` enregistre seulement la tâche ; la GUI ou `jobs run` l'exécute. `--json`, `--config` et `--verbose` précèdent la commande. Codes : 0 succès, 1 échec d'opération, 2 arguments/configuration invalides, 130 interruption.

La recherche interroge les sources activées en parallèle. MiNERVA ouvre une fiche torrent à utiliser dans un client externe ; la file de téléchargement Cochwa reste réservée à Internet Archive. `--limit` s’applique par source.

## Interface par plateforme

Le sélecteur de console adapte la bibliothèque, la recherche, les recommandations,
le Top, les téléchargements et les paramètres. Le Top Switch est une sélection
éditoriale distincte des scores indicatifs du Top PS2.

La recherche Switch est disponible dans l’interface graphique : NSP/XCI directs
sur Internet Archive et fiches externes pour les archives explicitement identifiées.
Les mises à jour et DLC identifiables ne sont pas proposés comme jeux de base.
Les empreintes IA servent au contrôle du transfert, sans identification Redump.
Les commandes CLI de recherche/téléchargement restent PS2 dans cette version.

Téléchargements : bouton **Supprimer** ou clic droit → **Supprimer**. Un transfert
actif est arrêté ; l’entrée est retirée de la liste et les fichiers sur disque sont conservés.

## Comportements importants

- Aucun fichier existant non reconnu n'est écrasé. Les fragments `.part` ne sont pas des jeux installés.
- Une reprise contrôle HTTP 200/206/416 et vérifie taille et SHA-1/MD5 disponible avant publication. Sans empreinte source, l'état reste « taille contrôlée ».
- « Hash source reconnu Redump » décrit les métadonnées distantes ; ce n'est pas encore la vérification d'un fichier local.
- Chaque sélection possède une destination stable et distincte. Les jeux déjà présents ne sont pas déplacés ; Europe, versions et mods restent séparés.
- Un CUE exige ses pistes sélectionnées. Les archives ZIP/7z ne sont pas extraites automatiquement.
- La conversion vérifie le CHD et conserve **tous** les originaux. Pour un ISO, choisir explicitement CD ou DVD. Un CUE utilise CD.
- La fermeture suspend le téléchargement actif ; sa reprise reste explicite. Une seule instance possède le moteur de transfert ; les autres peuvent consulter la file.
- Paramètres → Configurer mes consoles dans Steam : aperçu, installation sauvegardée des parseurs PS2/Switch, puis synchronisation via SRM. Les parseurs personnels sont préservés ; ceux qui couvrent les mêmes dossiers peuvent être désactivés explicitement dans l’assistant. Steam et SRM doivent être fermés manuellement avant la synchronisation.
- Le datfile Redump reste configurable ; sa source historique utilise HTTP. Le mode hors ligne accepte un cache périmé avec un état explicite.

## Développement

```bash
python3 -m pip install -e '.[dev]'   # dans un environnement virtuel
ruff check cochwa tests tools
ruff format --check cochwa tests tools
python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/gui -v  # sans affichage
python3 -m build
```

La CI exécute les tests sur Python 3.11/3.14, les tests GUI Qt en mode offscreen, le lint et la construction.

## Organisation

```text
cochwa/
  models.py             # modèles sérialisables
  config.py             # TOML, validation, chemins XDG (repli romget)
  consoles.py           # registre des consoles (base multiconsole)
  infrastructure/       # HTTP, écritures atomiques, verrous, chemins
  services/             # recherche, transfert, conversion, file, bibliothèque/index
  api/                  # Redump, SteamGridDB, façade historique IA
  providers/            # contrat de source et adaptateur de compatibilité
  gui_qt/               # PySide6 : sidebar, pages, dialogues, workers, thème
  cli.py                # commandes du même cœur applicatif
tests/                  # régressions métier, CLI et GUI
.github/workflows/      # validation automatique
docs/                  # architecture et notes internes (non publiées)
tools/                 # contrôles manuels ciblés
```

### Collections et émulateurs

La barre latérale propose **Collections**, **Émulateurs** et **Outils**. Créez des
collections par console et sélectionnez leurs jeux sans déplacer les ROMs.
Dans Émulateurs, filtrez les 22 projets par console, consultez leur site officiel
ou choisissez un exécutable installé (y compris AppImage). Cochwa mémorise ce
chemin et propose l’ouverture depuis **Prêt à jouer** dans la bibliothèque.
Les binaires accessibles dans le PATH et les déploiements Flatpak usuels sont détectés.
Les lanceurs PS2/Switch existants restent en place ; leur réglage reste accessible
depuis la fiche de l’émulateur. Le catalogue couvre d’autres consoles, tandis que
la gestion intégrée des ROMs reste PS2/Switch.
