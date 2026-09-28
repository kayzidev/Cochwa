# Refonte 0.2 — suivi compact

Décisions : conserver Python et les wrappers existants ; paquet `cochwa/` à la racine (un layout `src/` n'est pas requis et casserait les wrappers existants). Séparer modèles, infrastructure, services et interfaces. Aucun accès d'écriture aux ROMs réelles pendant les tests. Conversion sans suppression des sources. Steam reste contrôlé par l'utilisateur.

**Évolutions** : GUI réécrit en PySide6 (session 8, Tkinter supprimé) ; paquet renommé de `romget/` vers `cochwa/` (session 9) avec alias de compatibilité ; architecture multiconsole (PS2 + Switch actifs depuis session 12) ; providers modulaires + SearchProfile (session 13).

Ordre : intégrité des transferts et conversion → recherche/config/cache communs → bibliothèque et file persistante → CLI/GUI → installation/docs/tests.

Les intégrations directes Steam restent distinctes de l'ouverture SRM.

Optimisation du contexte IA : lire CURRENT_STATE.md puis ce suivi ; rechercher les symboles avec rg ; exécuter d'abord les tests du module concerné ; conserver preuves et décisions dans les fichiers, sans recopier logs/rapports entiers dans les échanges. Pas de duplication de travail par agents.
