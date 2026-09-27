# Sources PS2 et qualité de recherche — 27 septembre 2026

## Sources intégrées

| Source | Recherche | Téléchargement / identification |
|---|---|---|
| [Internet Archive](https://archive.org/developers/) | API metadata + advancedsearch, pages à la demande | HTTP dans la file romget, contrôle des empreintes disponibles |
| [MiNERVA](https://minerva-archive.org/browse/Redump/) | Catalogue **Redump / Sony - PlayStation 2** ; index local en cache 24 h | Fiche ouverte sur demande dans le navigateur ; torrent dans un client externe |
| [Redump](http://redump.org/) | Index d'identification PS2 | Empreintes de référence, pas une source de ROM |
| [SteamGridDB](https://www.steamgriddb.com/) | Jaquettes | Clé API requise, secours via les fichiers de jaquette IA |

MiNERVA est une deuxième source de **recherche**, avec un mode de transfert
externe explicite. Sa [FAQ](https://minerva-archive.org/faq/) décrit la distribution
par torrents. Aucun torrent ni client n'est lancé automatiquement ; aucun hash
BitTorrent n'est utilisé comme hash Redump. Les tailles arrondies de la page ne
sont pas présentées comme des tailles vérifiables. Après transfert et extraction,
placer les images dans le dossier PS2 puis actualiser la bibliothèque.

### Vérifications effectuées

- Site Myrient : sa [page officielle](https://myrient.erista.me/) confirme la
  fermeture le **31 mars 2026**. Il ne constitue plus un backend de téléchargement.
- MiNERVA : récupération HTTP réelle du catalogue PS2 (8 700 404 octets,
  **12 157 entrées** lors de la sonde). Liens `/rom?id=<nombre>` et noms de ROM
  extraits par un parseur HTML ; liens JavaScript/magnets ignorés.
- Le [JavaScript public de recherche](https://minerva-archive.org/js/global_search.js)
  expose `/v1/api/rom/search` et `/v1/api/rom/filters`. L'endpoint de filtres
  répond ; deux essais de recherche ont expiré (20 et 25 secondes). L'intégration
  utilise donc le catalogue HTML effectivement validé, pas cette API non validée.
- Recherches multi-sources réelles : Gran Turismo 4, Final Fantasy X, God of War II.
  Aucune ROM téléchargée pendant la validation.
- CDRomance et Vimm : les consultations de pages via l'outil web n'ont pas abouti
  cette session. Aucun contrat API ni disponibilité n'a été validé ; pas d'adaptateur
  ajouté. L'ancienne affirmation générale « scraping contraire aux conditions »
  n'était pas étayée et est retirée.
- Retrobrews : ses [collections homebrew](https://github.com/retrobrews) couvrent
  notamment d'autres consoles ; aucun catalogue PS2 adapté à ce projet n'a été
  validé. Pas d'ajout qui mélangerait des plateformes.

## Utilisation

La GUI possède un filtre **Source** : Toutes, Internet Archive ou MiNERVA.
Les cartes indiquent leur source et, pour MiNERVA, **Voir la source torrent**.
La CLI fournit aussi le lien de la fiche externe :

```bash
romget search 'gran turismo 4' --source all
romget search 'final fantasy x' --source minerva --region Europe
romget search 'god of war 2' --source ia_redump
romget --json search 'gran turismo 4' --source all --limit 20
```

`--limit` s'applique **par source**, avant filtrage pour IA. Une page peut donc
contenir jusqu'à 40 résultats avec les deux sources et la limite par défaut.
`source_totals` distingue les volumes source ; `has_more` pilote la pagination.
Le total IA représente les candidats distants, pas le nombre de jeux pertinents.
Une source en panne laisse les autres résultats visibles avec un avertissement ;
une panne de toutes les sources produit une erreur, pas une recherche vide.

Les deux sources sont activées par défaut, y compris lors du chargement d'une
ancienne configuration. Pour conserver seulement IA :

```toml
[providers.minerva]
enabled = false
```

La première recherche MiNERVA récupère environ 9 Mo de catalogue ; les suivantes
utilisent l'index local pendant 24 heures. Téléchargement borné à 16 Mio ; un
changement de format ou un catalogue vide produit une erreur visible.

## Pertinence et copies

- Comparaison par mots entiers, accents/ponctuation normalisés, chiffres romains
  et arabes rapprochés. « Final Fantasy X » exclut « X-2 » ; « Final Fantasy »
  conserve les deux. Les requêtes IA recherchent aussi les variantes numériques.
- Autres plateformes écartées dans les titres, identifiants, collections et noms
  des fichiers. Le mot « Arcade » seul n'exclut plus un titre PS2.
- Manuels, textures, patches seuls, cheats, presse, démos, prototypes et betas
  exclus par défaut ; restent accessibles si leur type figure dans la requête.
  Les mods et traductions ne sont pas exclus globalement.
- Dans un pack IA, titre, région, langue et option Redump doivent correspondre
  au **même fichier**. La sélection proposée est limitée aux fichiers pertinents ;
  `romget inspect IDENTIFIANT_IA` permet toujours de consulter l'item complet.
- Copies regroupées à l'échelle de la page par empreintes et tailles de l'ensemble
  des fichiers. À défaut : titre, noms et tailles exactes, sans empreintes
  contradictoires. L'ancienne marge de taille de 5 % est supprimée.
- Les fiches des copies regroupées restent accessibles dans les détails et dans
  `alternatives` en JSON. Les régions, révisions, disques et fichiers différents
  restent distincts. Le rapprochement sans hash est une présomption, pas une
  certification d'identité binaire.

### Limites explicites

MiNERVA n'expose pas d'empreinte de contenu exploitable dans le catalogue lu : il
est exclu du filtre « Hash source Redump reconnu ». Deux entrées IA/MiNERVA au
même titre peuvent rester visibles faute de preuve d'identité. La déduplication
ne maintient pas d'historique entre pages indépendantes. Les filtres de langue
exigent un marqueur explicite ; le pays seul ne garantit pas la langue. Une
archive non reconnue reste un contenu à vérifier, même si son nom correspond.

Les collections IA configurées via `providers.ia_redump.ia_collections` restent
un bonus de classement, pas des sources indépendantes ni une preuve de conformité.
