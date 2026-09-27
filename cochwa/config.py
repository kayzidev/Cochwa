"""Configuration TOML validée et persistante ; compatibilité avec la version 0.1."""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


@dataclass
class Config:
    ps2_dir: Path = field(default_factory=lambda: Path.home() / "Games/roms/ps2")
    download_dir: Path | None = None  # None = télécharge dans ps2_dir
    steam_method: str = "srm"
    steamgrid_api_key: str = ""
    srm_flatpak: str = "com.steamgriddb.steam-rom-manager"
    providers: dict[str, ProviderConfig] = field(
        default_factory=lambda: {
            "ia_redump": ProviderConfig("ia_redump"),
            "minerva": ProviderConfig("minerva"),
        }
    )
    launcher: Path = field(default_factory=lambda: Path.home() / "Games/scripts/pcsx2/launch.sh")
    state_dir: Path = field(default_factory=lambda: DEFAULT_STATE_DIR)
    source: Path | None = field(default=None, repr=False)

    @property
    def download_path(self):
        """Destination des téléchargements : download_dir sinon ps2_dir."""
        return self.download_dir or self.ps2_dir

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

        cfg.ps2_dir = Path(value("roms", "ps2_dir", str(cfg.ps2_dir))).expanduser().absolute()
        download_dir = value("roms", "download_dir", "").strip()
        cfg.download_dir = Path(download_dir).expanduser().absolute() if download_dir else None
        cfg.launcher = Path(value("app", "launcher", str(cfg.launcher))).expanduser().absolute()
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
        data.setdefault("roms", {}).update(ps2_dir=str(self.ps2_dir))
        if self.download_dir:
            data["roms"]["download_dir"] = str(self.download_dir)
        else:
            data["roms"].pop("download_dir", None)
        data.setdefault("steam", {}).update(
            method=self.steam_method,
            steamgrid_api_key=self.steamgrid_api_key,
            srm_flatpak=self.srm_flatpak,
        )
        data.setdefault("app", {}).update(
            launcher=str(self.launcher), state_dir=str(self.state_dir)
        )
        data["providers"] = {
            name: {"enabled": p.enabled, **p.options} for name, p in self.providers.items()
        }
        atomic_write(target, _toml(data).encode())
        self.source = target

    def get_provider(self, name):
        return self.providers.get(name)


def _toml(data):
    def scalar(v):
        if isinstance(v, str):
            return json.dumps(v, ensure_ascii=False)
        if isinstance(v, bool):
            return str(v).lower()
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, list):
            return "[" + ", ".join(scalar(x) for x in v) + "]"
        raise ValueError(f"Type TOML non pris en charge : {type(v).__name__}")

    lines = []

    def table(values, path=()):
        if path:
            lines.extend(["", "[" + ".".join(json.dumps(x) for x in path) + "]"])
        for key, v in values.items():
            if not isinstance(v, dict):
                lines.append(f"{json.dumps(key)} = {scalar(v)}")
        for key, v in values.items():
            if isinstance(v, dict):
                table(v, (*path, key))

    table(data)
    return "\n".join(lines) + "\n"
