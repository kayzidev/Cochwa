"""Intégration Steam — déclenche un re-parse de Steam ROM Manager."""

from __future__ import annotations

import shutil
import subprocess


def trigger_srm_reparse(flatpak_id: str = "com.steamgriddb.steam-rom-manager") -> bool:
    """Indique à l'utilisateur de re-parser dans SRM.

    SRM n'a pas d'API CLI pour déclencher un parse automatique. On ouvre
    simplement l'application et on guide l'utilisateur.
    """
    if shutil.which("flatpak") is None:
        print("[steam] flatpak non trouvé")
        return False

    # Vérifie que SRM est installé
    try:
        result = subprocess.run(
            ["flatpak", "info", flatpak_id],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"[steam] {flatpak_id} non installé")
            return False
    except Exception:
        return False

    # Lance SRM si pas déjà lancé
    try:
        ps = subprocess.run(
            ["pgrep", "-f", flatpak_id],
            capture_output=True,
            text=True,
            check=False,
        )
        if ps.returncode != 0:
            subprocess.Popen(
                ["flatpak", "run", flatpak_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print("[steam] SRM lancé")
        else:
            print("[steam] SRM déjà lancé")
    except Exception as e:
        print(f"[steam] erreur lancement SRM : {e}")
        return False

    print()
    print("Pour ajouter les nouvelles ROMs à Steam :")
    print("  1. Dans SRM → onglet 'Parsers'")
    print("  2. Clique 'Parse'")
    print("  3. Vérifie les nouveaux jeux dans l'onglet 'Preview'")
    print("  4. Clique 'Save apps to Steam'")
    print("  5. Redémarre Steam (manuel)")
    return True
