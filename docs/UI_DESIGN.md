# Interface Cochwa — 27 septembre 2026

Références : [charte graphique](../CHARTE_GRAPHIQUE.md) et [planche](../PlancheGraphique.png).
La PS2 et la Switch disposent désormais de recherches et catalogues distincts.
Le sélecteur adapte les écrans, le Top, les téléchargements et les paramètres.

## Identité et composants

- Palette centralisée dans `cochwa/gui_qt/theme.py`, avec les dix couleurs de la charte.
- Geist Regular et SemiBold embarquées, licence SIL OFL dans `gui_qt/assets/OFL.txt`.
  Source des polices : https://github.com/vercel/geist-font (fichiers TTF, branche main).
- Logo n°3 « Interface féline » choisi par l’utilisateur : C violet et œil corail. Icône
  de fenêtre et pictogrammes natifs indépendants des polices emoji.
- En-têtes, panneaux et états vides communs dans `gui_qt/widgets.py`.
- Fonds sobres, focus clavier visible, statuts exprimés en texte, jaquettes
  conservées sans recadrage destructif. Pochette typographique si l'image manque.

## Parcours

- Bibliothèque en première position et à l'ouverture ; statistiques locales,
  recherche, tri, lancement direct et lien distinct vers les détails.
- Conversion, doublons et CSV réunis dans le menu Outils. La fiche locale
  privilégie Jouer, dossier et jaquette ; fichiers et conversion sont dépliables.
- Recherche : `Ctrl+K`, filtres réinitialisables, chargement, erreurs avec réessai,
  pagination explicite et résultats périmés ignorés au changement de console.
- Téléchargements : sélection conservée à l'actualisation ; actions adaptées à
  l'état de la tâche, progression, états vides avec accès au catalogue.
- Assistant Steam : aperçu, parseurs par console et manifestes générés, sauvegarde,
  désactivation facultative des anciens parseurs chevauchants et commande SRM add.
- Téléchargements supprimables par bouton ou menu contextuel (fichiers conservés).
- Paramètres regroupés en panneaux défilants avec enregistrement toujours
  accessible, clé masquée, indication des modifications non enregistrées.
- Support défilant, liens accompagnés de leur destination et d'une description.

## Validation

Captures des dix écrans à 1280 × 860 (bibliothèque PS2 réelle, lecture seule et
jaquettes en cache) et 800 × 600 (configuration temporaire) dans
[validation/feline](validation/feline). Dialogues et états peuplés de démonstration
également contrôlés dans `validation/cochwa/states`.

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/gui_visual_check.py docs/validation/cochwa --local-library
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/gui_visual_check.py docs/validation/cochwa/compact --compact
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/ruff check cochwa tests tools
.venv/bin/ruff format --check cochwa tests tools
.venv/bin/python -m build --outdir /tmp/cochwa-dist
```

La capture isole SQLite dans un dossier temporaire et ne démarre aucun transfert.
Les tests ne lancent pas d'émulateur et n'écrivent pas dans les ROMs utilisateur.
Les transferts réseau, émulateurs réels et le rendu natif Windows/Steam Deck ne
font pas partie de cette validation visuelle Linux Qt offscreen.

## Navigation et émulateurs

Ordre : Bibliothèque, Collections, Émulateurs, Rechercher, Recommandés, Top de
la console, Téléchargements, Outils, Paramètres, Support. Les actions utilisent
`navigate(key)` ; elles ne dépendent plus du numéro de ligne dans la sidebar.
Le pied de sidebar se replie en petite fenêtre pour garder les destinations visibles.

Collections : création, renommage, sélection des jeux, suppression des références
sans toucher aux ROMs. Les listes sont séparées par console et persistées atomiquement.
Prêt à jouer : panneau latéral en grand format, raccourci compact en 800 × 600.
Émulateurs : catalogue multiconsole, recherche, filtre, site officiel, ajout d’un
binaire/AppImage/script et ouverture. Un lanceur de ROM existant ne s’exécute
jamais sans jeu. Les chemins PS2/Switch déjà enregistrés ne sont pas remplacés.
Voir [les sources du catalogue](EMULATORS.md).
