# Refonte 0.2 — suivi compact

Décisions : conserver Python/Tkinter et les wrappers existants ; paquet `romget/` conservé à la racine (le passage à src/ casserait inutilement les wrappers). Séparer modèles, infrastructure, services et interfaces. Aucun accès d'écriture aux ROMs réelles pendant les tests. Conversion sans suppression des sources. Steam reste contrôlé par l'utilisateur.

Ordre : intégrité des transferts et conversion → recherche/config/cache communs → bibliothèque et file persistante → CLI/GUI → installation/docs/tests.

Les extensions de consoles sont en attente de préférence utilisateur. Les intégrations directes Steam restent distinctes de l'ouverture SRM.

Optimisation du contexte IA : lire CURRENT_STATE.md puis ce suivi ; rechercher les symboles avec rg ; exécuter d'abord les tests du module concerné ; conserver preuves et décisions dans les fichiers, sans recopier logs/rapports entiers dans les échanges. Pas de duplication de travail par agents.
