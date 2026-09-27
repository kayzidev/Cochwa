# romget

Bibliothèque PS2 pour Linux : recherche multi-sources Internet Archive et MiNERVA, sélection explicite des éditions et disques, téléchargements vérifiés et reprenables, lancement PCSX2, jaquettes et ouverture de Steam ROM Manager.

## Démarrer sur cette machine

Les wrappers existants `romget` et `romget-gui` restent compatibles. Depuis le projet :

```bash
./install.sh            # crée .venv et installe le paquet (GUI PySide6 inclus)
./run.sh                # GUI
./run.sh --cli doctor    # diagnostic local, sans réseau ni affichage de clé
```

Sur une nouvelle installation : Python ≥ 3.11 avec venv/pip, puis `./install.sh`. Le script crée `.venv` et installe le paquet (requests, Pillow, PySide6) sans modifier Python système. La conversion optionnelle requiert `chdman` ; le lancement requiert un émulateur/configuration PCSX2 déjà fonctionnels.

## Configuration

Le fichier existant `~/.config/romget/config.toml` est lu sans migration destructive. Pour une installation neuve, les dossiers par défaut sont `~/Games/roms/ps2`, `$XDG_CACHE_HOME/romget` et `$XDG_STATE_HOME/romget` (ou leurs valeurs usuelles). Le dossier ROMs doit exister avant un téléchargement. La GUI permet de choisir le dossier, le lanceur PCSX2 et une clé SteamGridDB puis de les enregistrer. La clé reste locale ; aucun secret par défaut.

Un fichier alternatif s'utilise avec `romget --config /chemin/config.toml …` ou `romget-gui --config /chemin/config.toml`.

## CLI

```bash
romget search 'gran turismo 4' --region Europe --language Fr
romget search 'final fantasy x' --source minerva
romget search 'god of war 2' --source ia_redump
romget search 'gran turismo 4' --page 2 --limit 20
romget inspect IDENTIFIANT_IA
romget download IDENTIFIANT_IA --file 'Nom exact.iso' --dry-run
romget download IDENTIFIANT_IA --file 'Nom exact.iso'
romget download IDENTIFIANT_IA --file 'Disque.cue' --file 'Piste.bin' --enqueue
romget jobs list
romget jobs run
romget jobs resume ID_TACHE
romget list --query 'Gran Turismo'
romget verify '/chemin/jeu.iso'
romget verify '/chemin/dossier-avec-manifeste'
romget convert '/chemin/jeu.iso' --media dvd
romget play '/chemin/jeu.chd'
romget add-steam
romget --json doctor
```

`--all` sélectionne explicitement tous les fichiers d'un item, y compris ses différentes éditions. `--chd --media cd|dvd` permet la conversion après un téléchargement CLI. `--enqueue` enregistre seulement la tâche ; la GUI ou `jobs run` l'exécute. `--json`, `--config` et `--verbose` précèdent la commande. Codes : 0 succès, 1 échec d'opération, 2 arguments/configuration invalides, 130 interruption.

La recherche interroge les sources activées en parallèle. MiNERVA ouvre une fiche torrent à utiliser dans un client externe ; la file de téléchargement romget reste réservée à Internet Archive. `--limit` s’applique par source. Voir [les sources et filtres](docs/SOURCES.md) pour la configuration, les vérifications et les limites de déduplication.

## Comportements importants

- Aucun fichier existant non reconnu n'est écrasé. Les fragments `.part` ne sont pas des jeux installés.
- Une reprise contrôle HTTP 200/206/416 et vérifie taille et SHA-1/MD5 disponible avant publication. Sans empreinte source, l'état reste « taille contrôlée ».
- « Hash source reconnu Redump » décrit les métadonnées distantes ; ce n'est pas encore la vérification d'un fichier local.
- Chaque sélection possède une destination stable et distincte. Les jeux déjà présents ne sont pas déplacés ; Europe, versions et mods restent séparés.
- Un CUE exige ses pistes sélectionnées. Les archives ZIP/7z ne sont pas extraites automatiquement.
- La conversion vérifie le CHD et conserve **tous** les originaux. Pour un ISO, choisir explicitement CD ou DVD. Un CUE utilise CD.
- La fermeture suspend le téléchargement actif ; sa reprise reste explicite. Une seule instance possède le moteur de transfert ; les autres peuvent consulter la file.
- SRM est ouvert avec des instructions : effectuer Parse puis Save dans SRM. romget ne prétend pas avoir ajouté un jeu à Steam et n'arrête jamais Steam.
- Le datfile Redump reste configurable ; sa source historique utilise HTTP. Le mode hors ligne accepte un cache périmé avec un état explicite.

## Développement

```bash
python3 -m pip install -e '.[dev]'   # dans un environnement virtuel
ruff check romget tests tools
ruff format --check romget tests tools
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s tests/gui -v  # nécessite un affichage Tk
python3 -m build
```

La CI exécute les tests sur Python 3.11/3.14, les tests GUI sous Xvfb, le lint et la construction. Elle est configurée mais ne tourne à distance qu'après publication dans un dépôt GitHub.

## Organisation

```text
romget/
  models.py             # modèles sérialisables
  config.py             # TOML, validation, chemins XDG
  infrastructure/       # HTTP, écritures atomiques, verrous, chemins
  services/             # recherche, transfert, conversion, file, bibliothèque/index
  api/                  # Redump, SteamGridDB, façade historique IA
  providers/            # contrat de source et adaptateur de compatibilité
  gui/                  # écrans, dialogues, paramètres, événements et widgets
  cli.py                # commandes du même cœur applicatif
tests/                  # régressions métier, CLI et GUI
.github/workflows/      # validation automatique
docs/                  # architecture, migration, audit et historique
tools/                 # contrôles manuels ciblés
```

Voir [l'architecture](docs/ARCHITECTURE.md), [la migration 0.1 → 0.2](docs/MIGRATION.md) et [le suivi de l'audit](docs/AUDIT_STATUS.md). Pour reprendre avec une IA, lire d'abord [CURRENT_STATE.md](CURRENT_STATE.md) : il évite de recharger l'historique entier.
