# Migration 0.1 → 0.2

- Lancer les wrappers existants ou `./run.sh` ; aucun déplacement des ROMs, changement de SRM ni redémarrage Steam.
- La configuration actuelle est lue ; elle n'est écrite que lors d'un enregistrement de paramètres. La clé locale est conservée. Sa valeur anciennement présente dans les sources et le handoff a été retirée ; son renouvellement doit être effectué dans le compte SteamGridDB.
- Le refresh global IA n'est plus nécessaire. `providers refresh` concerne maintenant l'index Redump. `list-available` est remplacé par `search --page` ; les anciens identifiants IA peuvent être inspectés directement.
- `download` exige `--file` ou `--all`. Les anciens exemples sans sélection échouent volontairement avec une explication.
- Les fichiers historiques partiellement téléchargés avec une extension ISO ne sont pas importés comme `.part` automatiquement : sans provenance et hash, les distinguer d'une ROM complète serait dangereux. Utiliser `verify` et déplacer manuellement un fichier douteux avant de relancer une sélection.
- Un fichier final de mauvaise empreinte reste intact ; l'application demande une action explicite. Un fragment orphelin est conservé sous `.part.saved-*`. Un fragment de mauvaise empreinte est isolé sous `.part.invalid-*` ; la reprise suivante repart de zéro, sans effacer la preuve de l’échec.
- La conversion ne supprime plus les sources et nécessite le type CD/DVD pour ISO. Des fichiers `.converting` laissés par un échec restent disponibles pour diagnostic et ne sont pas écrasés.
- Les tâches en cours lors d'un arrêt brutal sont marquées en pause au prochain démarrage du moteur. Une seule instance exécute les transferts ; `jobs list` fonctionne pendant l'exécution GUI.
- Le cache historique des jaquettes nommées par titre reste sur disque ; la nouvelle nomenclature hashée évite les collisions. Les anciennes jaquettes ne sont pas supprimées.
- `chdman` n'est pas installé sur la machine auditée. Le programme le signale ; installer les outils MAME pour effectuer de vraies conversions.
