"""Configuration TOML validée et persistante ; compatibilité avec la version 0.1."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli_w

from cochwa.consoles import CONSOLES, DEFAULT_CONSOLE
from cochwa.infrastructure.storage import atomic_write


def _xdg_dir(env_key, fallback, name="cochwa", legacy="romget"):
    """Dossier XDG de l'application ; repli sur l'ancien nom s'il existe déjà."""
    base = Path(os.environ.get(env_key, fallback))
    new, old = base / name, base / legacy
    return old if old.exists() and not new.exists() else new


DEFAULT_CONFIG_DIR = _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config")
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.toml"
DEFAULT_CACHE_DIR = _xdg_dir("XDG_CACHE_HOME", Path.home() / ".cache")
DEFAULT_STATE_DIR = _xdg_dir("XDG_STATE_HOME", Path.home() / ".local/state")


@dataclass
class ProviderConfig:
    name: str
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)

    @property
    def cache_dir(self):
        return Path(self.options.get("cache_dir", DEFAULT_CACHE_DIR)).expanduser()

    @property
    def datfile_url(self):
        return self.options.get("datfile_url", "http://redump.org/datfile/ps2/")

    @property
    def ia_page_size(self):
        return int(self.options.get("ia_page_size", 20))

    @property
    def ia_collections(self):
        """Collections IA de confiance, boostées au classement (voir docs/SOURCES.md)."""
        return list(self.options.get("ia_collections", []))


def _default_console_dirs():
    """Dossiers ROMs par défaut : registre pour la console par défaut, None ailleurs.

    None = console non configurée (l'UI invite alors à choisir un dossier).
    """
    return {
        console.id: (Path(console.roms_dir).expanduser() if console is DEFAULT_CONSOLE else None)
        for console in CONSOLES
    }


def _default_console_launchers():
    """Lanceurs par défaut : registre pour la console par défaut, None ailleurs."""
    return {
        console.id: (Path(console.launcher).expanduser() if console is DEFAULT_CONSOLE else None)
        for console in CONSOLES
    }


class Config:
    """Configuration validée ; chemins indexés par console.id (registre consoles.py).

    Les propriétés ps2_dir / switch_dir / launcher / switch_launcher sont
    conservées pour compatibilité (CLI, tests, outils).
    """

    def __init__(
        self,
        *,
        console_dirs=None,
        console_launchers=None,
        ps2_dir=None,
        switch_dir=None,
        launcher=None,
        switch_launcher=None,
        download_dir=None,
        steam_method="srm",
        steamgrid_api_key="",
        srm_flatpak="com.steamgriddb.steam-rom-manager",
        providers=None,
        state_dir=None,
        source=None,
    ):
        self.console_dirs = (
            dict(console_dirs) if console_dirs is not None else _default_console_dirs()
        )
        self.console_launchers = (
            dict(console_launchers)
            if console_launchers is not None
            else _default_console_launchers()
        )
        # Alias historiques du constructeur (tests, outils, version 0.1).
        if ps2_dir is not None:
            self.console_dirs["ps2"] = Path(ps2_dir)
        if switch_dir is not None:
            self.console_dirs["switch"] = Path(switch_dir)
        if launcher is not None:
            self.console_launchers["ps2"] = Path(launcher)
        if switch_launcher is not None:
            self.console_launchers["switch"] = Path(switch_launcher)
        self.download_dir = Path(download_dir) if download_dir is not None else None
        self.steam_method = steam_method
        self.steamgrid_api_key = steamgrid_api_key
        self.srm_flatpak = srm_flatpak
        self.providers = (
            providers
            if providers is not None
            else {
                "ia_redump": ProviderConfig("ia_redump"),
                "minerva": ProviderConfig("minerva"),
                "ia_switch": ProviderConfig("ia_switch"),
            }
        )
        self.state_dir = Path(state_dir) if state_dir is not None else DEFAULT_STATE_DIR
        self.source = source

    # --- Compatibilité : accès directs historiques -------------------------

    @property
    def ps2_dir(self):
        return self.console_dirs.get("ps2")

    @ps2_dir.setter
    def ps2_dir(self, value):
        self.console_dirs["ps2"] = Path(value) if value else None

    @property
    def switch_dir(self):
        return self.console_dirs.get("switch")

    @switch_dir.setter
    def switch_dir(self, value):
        self.console_dirs["switch"] = Path(value) if value else None

    @property
    def launcher(self):
        return self.console_launchers.get("ps2")

    @launcher.setter
    def launcher(self, value):
        self.console_launchers["ps2"] = Path(value) if value else None

    @property
    def switch_launcher(self):
        return self.console_launchers.get("switch")

    @switch_launcher.setter
    def switch_launcher(self, value):
        self.console_launchers["switch"] = Path(value) if value else None

    # --- Accès génériques par console ---------------------------------------

    @property
    def download_path(self):
        """Destination des téléchargements : download_dir sinon ps2_dir."""
        return self.download_dir or self.ps2_dir

    def roms_dir(self, console):
        """Dossier ROMs de la console ; None si la console n'est pas configurée."""
        return self.console_dirs.get(console.id)

    def set_roms_dir(self, console, path):
        self.console_dirs[console.id] = Path(path) if path else None

    def launcher_for(self, console):
        """Script de lancement de la console ; None si non configuré."""
        return self.console_launchers.get(console.id)

    def set_launcher(self, console, path):
        self.console_launchers[console.id] = Path(path) if path else None

    @property
    def cache_dir(self):
        return self.providers.get("ia_redump", ProviderConfig("ia_redump")).cache_dir

    @property
    def datfile_url(self):
        return self.providers.get("ia_redump", ProviderConfig("ia_redump")).datfile_url

    @classmethod
    def load(cls, path: Path | None = None):
        path = Path(path or DEFAULT_CONFIG_FILE).expanduser()
        if not path.exists():
            config = cls(source=path)
            config.save()
            return config
        with path.open("rb") as stream:
            data = tomllib.load(stream)
        cfg = cls(source=path)
        for section in ("roms", "steam", "app", "providers"):
            if not isinstance(data.get(section, {}), dict):
                raise ValueError(f"Section {section} invalide")

        def value(section, key, default):
            result = data.get(section, {}).get(key, default)
            if not isinstance(result, str):
                raise ValueError(f"{section}.{key} doit être du texte")
            return result

        # Chemins par console : [roms] <id>_dir et [app] <id>_launcher.
        for console in CONSOLES:
            cid = console.id
            current_dir = cfg.console_dirs.get(cid)
            raw_dir = value("roms", f"{cid}_dir", str(current_dir or "")).strip()
            cfg.console_dirs[cid] = Path(raw_dir).expanduser().absolute() if raw_dir else None
            # Alias legacy : [app] launcher = lanceur de la console par défaut.
            default_launcher = cfg.console_launchers.get(cid)
            app = data.get("app", {})
            raw_launcher = app.get(f"{cid}_launcher")
            if raw_launcher is None and console is DEFAULT_CONSOLE:
                raw_launcher = app.get("launcher", str(default_launcher or ""))
            elif raw_launcher is None:
                raw_launcher = str(default_launcher or "")
            if not isinstance(raw_launcher, str):
                raise ValueError(f"app.{cid}_launcher doit être du texte")
            raw_launcher = raw_launcher.strip()
            cfg.console_launchers[cid] = (
                Path(raw_launcher).expanduser().absolute() if raw_launcher else None
            )
        download_dir = value("roms", "download_dir", "").strip()
        cfg.download_dir = Path(download_dir).expanduser().absolute() if download_dir else None
        cfg.state_dir = Path(value("app", "state_dir", str(cfg.state_dir))).expanduser().absolute()
        cfg.steam_method = value("steam", "method", "srm")
        if cfg.steam_method != "srm":
            raise ValueError("Seule la méthode Steam srm est prise en charge")
        cfg.steamgrid_api_key = value("steam", "steamgrid_api_key", "")
        cfg.srm_flatpak = value("steam", "srm_flatpak", cfg.srm_flatpak)
        for name, options in data.get("providers", {}).items():
            if not isinstance(options, dict):
                raise ValueError(f"Provider {name} invalide")
            options = options.copy()
            enabled = options.pop("enabled", True)
            if type(enabled) is not bool:
                raise ValueError("enabled doit être un booléen")
            for option in ("cache_dir", "datfile_url"):
                if option in options and (
                    not isinstance(options[option], str) or not options[option].strip()
                ):
                    raise ValueError(f"providers.{name}.{option} doit être du texte non vide")
            if "ia_page_size" in options and (type(options["ia_page_size"]) is not int):
                raise ValueError("ia_page_size doit être un entier")
            if "ia_collections" in options:
                collections = options["ia_collections"]
                if not isinstance(collections, list) or not all(
                    isinstance(c, str) and c.strip() for c in collections
                ):
                    raise ValueError(
                        f"providers.{name}.ia_collections doit être une liste de textes non vides"
                    )
            provider = ProviderConfig(name, enabled, options)
            if not 1 <= provider.ia_page_size <= 200:
                raise ValueError("ia_page_size doit être compris entre 1 et 200")
            if not isinstance(provider.datfile_url, str) or not provider.datfile_url.startswith(
                ("http://", "https://")
            ):
                raise ValueError("URL datfile invalide")
            cfg.providers[name] = provider
        return cfg

    def save(self, path: Path | None = None):
        target = Path(path or self.source or DEFAULT_CONFIG_FILE)
        # Preserve unrelated sections/options from a valid existing config.
        data = {}
        if target.exists():
            with target.open("rb") as stream:
                data = tomllib.load(stream)
        roms = data.setdefault("roms", {})
        for cid, folder in self.console_dirs.items():
            if folder:
                roms[f"{cid}_dir"] = str(folder)
            else:
                roms.pop(f"{cid}_dir", None)
        if self.download_dir:
            roms["download_dir"] = str(self.download_dir)
        else:
            roms.pop("download_dir", None)
        data.setdefault("steam", {}).update(
            method=self.steam_method,
            steamgrid_api_key=self.steamgrid_api_key,
            srm_flatpak=self.srm_flatpak,
        )
        app = data.setdefault("app", {})
        for cid, script in self.console_launchers.items():
            if script:
                app[f"{cid}_launcher"] = str(script)
            else:
                app.pop(f"{cid}_launcher", None)
        app.pop("launcher", None)  # alias legacy migré vers <id>_launcher
        app["state_dir"] = str(self.state_dir)
        data["providers"] = {
            name: {"enabled": p.enabled, **p.options} for name, p in self.providers.items()
        }
        atomic_write(target, tomli_w.dumps(data).encode())
        self.source = target

    def get_provider(self, name):
        return self.providers.get(name)
