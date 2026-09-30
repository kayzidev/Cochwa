# Règles UI pour Cochwa

Pour toute création ou modification de page PySide6 :

- Organiser les groupes d’actions et les ressources en cartes avec une grille adaptative : deux colonnes quand l’espace le permet, une colonne à petite largeur.
- Réserver les boutons larges à une action principale justifiée. Garder les actions secondaires compactes et groupées.
- Vérifier l’interface à 800 × 600 et à 1280 × 860, ainsi que la navigation clavier et les noms accessibles des contrôles.
- Garder les requêtes réseau et travaux longs hors du thread graphique. Afficher les données du cache sans attendre la mise à jour.
- Lorsqu’une nouvelle plateforme est ajoutée, vérifier que Recommandés affiche 20 à 30 jeux distincts et que Top affiche tous les jeux disposant d’une note critique IGDB, avec un défilement ou une pagination fluide.
