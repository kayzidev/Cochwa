# Catalogue des émulateurs

Références consultées le 27 septembre 2026. Le catalogue embarqué est une sélection
de projets identifiables disposant de documentation et de sources officielles ;
il ne prétend pas recenser chaque fork ni garantir la compatibilité de chaque jeu.
Les projets expérimentaux sont signalés dans leur fiche. Aucun logiciel, BIOS,
firmware ou clé n’est téléchargé automatiquement.

| Projet | Consoles | Source officielle |
| --- | --- | --- |
| PCSX2 | PlayStation 2 | [Projet](https://pcsx2.net/) |
| Ryubing / Ryujinx | Switch | [Projet](https://docs.ryujinx.app/) |
| Dolphin | GameCube, Wii | [Projet](https://dolphin-emu.org/) |
| PPSSPP | PSP | [Projet](https://www.ppsspp.org/) |
| DuckStation | PlayStation | [Projet](https://www.duckstation.org/) |
| RPCS3 | PlayStation 3 | [Projet](https://rpcs3.net/) |
| Vita3K | PS Vita | [Projet](https://vita3k.org/) |
| Cemu | Wii U | [Projet](https://cemu.info/) |
| Azahar | Nintendo 3DS | [Projet](https://azahar-emu.org/) |
| melonDS | Nintendo DS, Nintendo DSi | [Projet](https://melonds.kuribo64.net/) |
| mGBA | Game Boy, Game Boy Color, Game Boy Advance | [Projet](https://mgba.io/) |
| SameBoy | Game Boy, Game Boy Color | [Projet](https://sameboy.github.io/) |
| Mupen64Plus | Nintendo 64 | [Projet](https://mupen64plus.org/) |
| Mesen | NES, Super Nintendo, Game Boy, Game Boy Advance, PC Engine, Master System, Game Gear, WonderSwan | [Projet](https://github.com/SourMesen/Mesen2) |
| Snes9x | Super Nintendo | [Projet](https://github.com/snes9xgit/snes9x) |
| Flycast | Dreamcast, Naomi, Atomiswave | [Projet](https://github.com/flyinghead/flycast) |
| Mednafen | Saturn, PlayStation, PC Engine, Neo Geo Pocket, WonderSwan | [Projet](https://mednafen.github.io/) |
| ares | Nintendo 64, NES, Super Nintendo, Mega Drive, Master System, Game Gear, PC Engine | [Projet](https://ares-emu.net/) |
| xemu | Xbox | [Projet](https://xemu.app/) |
| Xenia | Xbox 360 | [Projet](https://xenia.jp/) |
| MAME | Arcade | [Projet](https://www.mamedev.org/) |
| RetroArch | Multiconsole | [Projet](https://www.retroarch.com/) |

La détection Linux inspecte PATH, les déploiements Flatpak usuels utilisateur/système
et les lanceurs Cochwa déjà configurés. Aucun programme n’est exécuté pendant la détection.
Les installations portables ou ailleurs s’ajoutent via « Choisir un exécutable ».
Le registre `state_dir/emulators.json` conserve ces chemins, avec écriture atomique
et verrou. « Oublier » retire seulement le chemin personnalisé ; les fichiers restent
en place, et une installation système peut être à nouveau détectée.

« Disponible » indique un exécutable détecté. « Lanceur configuré » indique un script
de jeu existant ; le raccourci ouvre la bibliothèque correspondante. La disponibilité
du BIOS, du firmware, des clés et la compatibilité matérielle ne sont pas testées.
Le bouton Ouvrir lance un tableau d’arguments sans shell et écrit un journal local.
Les lanceurs utilisés par les ROMs et Steam ROM Manager ne sont jamais changés
automatiquement par l’ajout d’un émulateur.

Collections sont stockées dans `state_dir/collections.json`, sous verrou et par
console. Les titres absents restent dans les listes pour les disques déconnectés.
Un renommage du fichier ROM peut demander une nouvelle sélection du jeu.
