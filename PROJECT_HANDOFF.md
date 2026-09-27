# romget — reprise courte

Version de travail : **0.2.0**, refonte du 27 septembre 2026.

1. Lire `CURRENT_STATE.md` pour les résultats et limites actuels.
2. Lire `docs/ARCHITECTURE.md` pour les décisions et responsabilités.
3. Lire `docs/TECH_DEBT.md` pour la dette technique et la TODO prioritaire.
4. Lire `docs/AUDIT_STATUS.md` pour la couverture de l'audit.
5. Exécuter les tests ciblés avant de modifier un service.

Décisions utilisateur : PS2 d'abord ; architecture extensible ; corriger l'intégrité avant les ajouts ; optimiser le contexte/token IA. Ne pas arrêter Steam. Préserver les variantes et mods, notamment GT4 Europe et Spec II.

Le handoff 0.1, **historique et expurgé du secret**, est conservé dans `docs/history/PROJECT_HANDOFF_0.1.md`. Son ancien statut « MVP fonctionnel » et ses instructions ne décrivent pas la version actuelle. L'audit initial est archivé dans `docs/audits/2026-09-27-baseline.md`.

La clé SteamGridDB se configure localement ; ne jamais la recopier dans un document ou log.
