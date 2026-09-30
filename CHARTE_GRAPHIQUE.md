Crée à la racine du projet un fichier `CHARTE_GRAPHIQUE.md` qui servira de **source de vérité visuelle** pour toute l’interface de Cochwa.

# Contexte du projet

**Cochwa** est un gestionnaire de ROM moderne qui centralise les bibliothèques de jeux, facilite l’utilisation des émulateurs et peut intégrer des logiciels tiers pour simplifier au maximum l’accès à l’émulation.

L’identité doit être :

- moderne ;
- élégante ;
- accessible ;
- chaleureuse ;
- légèrement gaming, sans tomber dans les clichés rétro ;
- software-first ;
- multi-plateformes ;
- cohérente entre toutes les vues.

Éviter absolument :

- pixel art utilisé comme identité principale ;
- manettes génériques dans tous les visuels ;
- esthétique arcade 8-bit ;
- imitation de Nintendo, PlayStation, Xbox, Steam ou d’une autre marque existante ;
- interfaces surchargées ;
- effets néon excessifs.

---

# Identité Cochwa

**Choix utilisateur actuel : logo n°3 « Interface féline » de `PlancheGraphique.png`.**
Le symbole de référence est le C violet avec un œil félin corail en espace central.
Il est décliné en SVG pour la fenêtre, la barre latérale et les états vides.
Ce choix remplace le logo n°1 précédemment sélectionné.

Le logo repose sur un **C stylisé**, associé à l’idée de :

- portail ;
- bibliothèque unifiée ;
- collection ;
- accès rapide aux jeux ;
- lancement.

Il intègre également un **clin d’œil subtil au léopard normand**, en référence aux origines du nom Cochwa et à la Normandie.

Cette référence doit rester :

- géométrique ;
- minimaliste ;
- moderne ;
- identifiable sans devenir une mascotte cartoon.

Elle peut apparaître par :

- une silhouette féline intégrée au C ;
- un œil ;
- une oreille ;
- une courbe rappelant une tête ou une posture de félin ;
- du negative space.

Le symbole doit rester lisible à petite taille et pouvoir fonctionner comme :

- icône d’application ;
- favicon ;
- icône de barre des tâches ;
- logo GitHub ;
- écran de chargement.

---

# Palette officielle

Utiliser ces couleurs comme **tokens de référence**.

## Couleurs principales

| Token | Couleur |
|---|---|
| `primary` | `#7567FF` |
| `secondary` | `#FF7867` |
| `success` | `#5EE6B1` |
| `warning` | `#FFBE55` |
| `error` | `#FF5D70` |

## Couleurs neutres

| Token | Couleur |
|---|---|
| `background` | `#11131A` |
| `surface` | `#191C26` |
| `surfaceElevated` | `#222633` |
| `text` | `#F4F5FA` |
| `textMuted` | `#969BAD` |

Le thème principal est **dark**.

`#11131A` doit être utilisé comme fond principal.

`#191C26` pour :

- cartes ;
- panneaux ;
- sidebars ;
- zones de contenu.

`#222633` pour :

- menus ouverts ;
- composants élevés ;
- zones actives ;
- hover importants.

Le violet `#7567FF` constitue la couleur principale de l’application.

Le corail `#FF7867` doit servir d’accent secondaire et non de couleur dominante.

---

# Typographie

Police principale :

**Geist**

Utiliser Geist pour :

- interface ;
- navigation ;
- boutons ;
- titres ;
- textes ;
- labels ;
- logo typographique si nécessaire.

Hiérarchie recommandée :

- titres majeurs : `600` ou `700`;
- titres de sections : `600`;
- texte courant : `400`;
- labels : `500`;
- boutons : `500` ou `600`;
- informations secondaires : `400` avec `textMuted`.

Favoriser une interface très lisible avec suffisamment d’espace.

---

# Formes et composants

L’identité Cochwa utilise des composants aux formes légèrement arrondies.

Rayons recommandés :

- petits éléments : `8px`;
- boutons : `10px`;
- champs : `10px`;
- cartes : `12px`;
- panneaux importants : `16px`;
- modales : `16px`.

Éviter les arrondis excessifs qui donneraient une apparence mobile ou enfantine.

Les bordures doivent rester discrètes.

Exemple :

`1px solid rgba(255,255,255,0.06)`

---

# Ombres

Les ombres doivent être légères.

Éviter les grosses ombres diffuses.

Exemple :

`0 8px 30px rgba(0,0,0,0.20)`

Les élévations doivent surtout être produites par la différence entre :

- background ;
- surface ;
- surfaceElevated.

---

# Dégradés

Les dégradés sont autorisés uniquement pour renforcer l’identité de marque.

Dégradé principal possible :

`#7567FF → #9A62FF → #FF7867`

Utilisations possibles :

- logo ;
- onboarding ;
- écran d’accueil ;
- éléments décoratifs ;
- glow très discret.

Ne pas utiliser ce dégradé partout dans l’interface.

---

# Bibliothèque de jeux

La bibliothèque représente le cœur visuel de Cochwa.

L’interface doit mettre en avant :

- jaquettes ;
- artworks ;
- captures ;
- collections.

Les jeux fournissent naturellement la majorité des couleurs de l’interface.

L’UI Cochwa doit donc rester volontairement sobre.

Exemple de navigation :

- Bibliothèque
- Collections
- Émulateurs
- Outils
- Paramètres

Ne jamais donner l’impression que Cochwa est uniquement un outil technique destiné aux utilisateurs avancés.

L’utilisateur doit avant tout voir :

**sa bibliothèque de jeux.**

---

# Cartes de jeux

Les cartes peuvent contenir :

- jaquette ;
- titre ;
- plateforme ;
- favori ;
- statut ;
- émulateur utilisé.

Exemple :

`Metroid Prime`

Tags :

`GameCube`

`Dolphin`

Les tags utilisent des petites capsules arrondies.

Ils doivent rester secondaires face au visuel du jeu.

---

# Capsules et tags

Les capsules sont un élément important du langage graphique Cochwa.

Elles servent notamment pour :

- plateformes ;
- émulateurs ;
- régions ;
- collections ;
- états ;
- filtres.

Exemples :

`GameCube`

`PAL`

`Dolphin`

`Prêt`

Utiliser :

- surfaceElevated pour les tags neutres ;
- primary pour les tags actifs ;
- success pour les états positifs ;
- warning pour les avertissements ;
- error uniquement pour les erreurs réelles.

---

# Boutons

## Primaire

Fond :

`#7567FF`

Texte :

`#F4F5FA`

Exemple :

`Lancer le jeu`

## Secondaire

Fond :

`#222633`

Texte :

`#F4F5FA`

## Destructif

Fond ou accent :

`#FF5D70`

Les actions destructives doivent être clairement distinguées.

---

# États

## Success

`#5EE6B1`

Exemples :

- ROM vérifiée ;
- émulateur configuré ;
- BIOS présent ;
- jeu prêt.

## Warning

`#FFBE55`

Exemples :

- BIOS manquant ;
- configuration incomplète ;
- métadonnées douteuses.

## Error

`#FF5D70`

Exemples :

- ROM introuvable ;
- émulateur inaccessible ;
- fichier corrompu.

---

# Navigation

La navigation principale doit rester simple.

Préférer une sidebar desktop.

Exemple :

Cochwa

- Bibliothèque
- Collections
- Émulateurs
- Outils
- Paramètres

L’entrée active peut utiliser :

- fond `primary`;
- texte blanc ;
- éventuellement un glow très discret.

---

# Philosophie UX

Cochwa doit masquer la complexité de l’émulation.

L’utilisateur ne devrait pas avoir l’impression d’utiliser :

« un gestionnaire de ROM avec plusieurs émulateurs ».

Il devrait avoir l’impression d’utiliser :

**une bibliothèque de jeux universelle.**

Les éléments techniques doivent être accessibles mais rester secondaires.

Exemple :

Informations avancées dans :

`Jeu > Paramètres > Émulation`

plutôt que directement dans la fiche principale.

---

# Style général

Chercher une esthétique proche des logiciels modernes de médiathèque.

Mots-clés visuels :

- modern desktop app ;
- gaming library ;
- media manager ;
- clean dark UI ;
- premium software ;
- subtle gradients ;
- information hierarchy ;
- accessible UX.

L’interface doit fonctionner correctement sur :

- Windows ;
- Linux ;
- Steam Deck ou interfaces proches ;
- écrans desktop classiques.

---

# Accessibilité

Toujours vérifier :

- contrastes ;
- lisibilité ;
- taille minimale des textes ;
- états hover ;
- focus clavier ;
- états disabled ;
- sélection ;
- erreurs.

Ne jamais communiquer une information uniquement par la couleur.

Associer couleur + texte + icône lorsque nécessaire.

---

# Règle pour tout développement futur

Avant de créer ou modifier un composant graphique :

1. consulter `CHARTE_GRAPHIQUE.md`;
2. réutiliser les tokens existants ;
3. ne pas inventer une nouvelle couleur sans justification ;
4. ne pas créer de nouveau style de bouton s’il existe déjà un équivalent ;
5. préserver une cohérence globale entre toutes les pages ;
6. favoriser la simplicité plutôt que l’ajout d’effets graphiques ;
7. considérer cette charte comme la référence principale de l’interface Cochwa.

Si le projet utilise Tailwind, CSS variables, un système de thèmes ou des design tokens, créer les variables correspondantes à partir de cette charte et les utiliser dans tout le projet.

Le résultat final doit donner à Cochwa une identité immédiatement reconnaissable : **moderne, accessible, élégante, ludique et subtilement normande.**