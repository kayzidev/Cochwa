"""Index Redump atomique, synchronisé, avec fallback périmé explicite."""

from __future__ import annotations

import io
import json
import logging
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from cochwa.config import DEFAULT_CACHE_DIR
from cochwa.infrastructure.http import session
from cochwa.infrastructure.storage import write_json

DATFILE_URL = "http://redump.org/datfile/ps2/"
CACHE_FILE = DEFAULT_CACHE_DIR / "ps2_datfile.json"
DATFILE_TTL = 86400 * 7
log = logging.getLogger(__name__)


class RedumpDatfile:
    def __init__(self, cache_file=None, url=DATFILE_URL):
        self.cache_file = Path(cache_file or CACHE_FILE)
        self.url = url
        self.md5_to_title = {}
        self.titles = set()
        self.version = ""
        self.status = "absent"
        self._loaded = False
        self._next_attempt = 0
        self._lock = threading.RLock()

    def load(self, force=False):
        with self._lock:
            if not force and time.time() < self._next_attempt:
                return self._loaded
            if not force and self._load_cache():
                self._next_attempt = time.time() + 3600
                return True
            try:
                self._download_and_parse()
                self._loaded = True
                self.status = "fresh"
                try:
                    self._save_cache()
                except OSError:
                    log.warning("Index disponible en mémoire ; cache non enregistrable")
                self._next_attempt = time.time() + 3600
                return True
            except Exception as exc:
                log.warning("Datfile indisponible : %s", type(exc).__name__)
                self._next_attempt = time.time() + 300
                if self._load_cache(allow_stale=True):
                    return True
                self.status = "error"
                return self._loaded

    def _load_cache(self, allow_stale=False):
        try:
            data = json.loads(self.cache_file.read_text())
            stale = time.time() - data["saved_at"] > DATFILE_TTL
            if stale and not allow_stale:
                return False
            hashes = data["md5_to_title"]
            titles = data["titles"]
            if (
                not isinstance(hashes, dict)
                or not hashes
                or not all(isinstance(k, str) and isinstance(v, str) for k, v in hashes.items())
            ):
                return False
            if not isinstance(titles, list) or not all(isinstance(t, str) for t in titles):
                return False
            self.md5_to_title, self.titles = hashes, set(titles)
            self.version = str(data.get("version", ""))
            self._loaded = True
            self.status = "stale" if stale else "fresh"
            return True
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def _save_cache(self):
        write_json(
            self.cache_file,
            {
                "saved_at": time.time(),
                "version": self.version,
                "md5_to_title": self.md5_to_title,
                "titles": sorted(self.titles),
            },
        )

    def _download_and_parse(self):
        content = bytearray()
        with session().get(self.url, stream=True, timeout=(10, 30)) as response:
            response.raise_for_status()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 16 * 1024**2:
                    raise ValueError("Datfile compressé trop volumineux")
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entry = next((i for i in archive.infolist() if i.filename.endswith(".dat")), None)
            if entry is None or entry.file_size > 128 * 1024**2:
                raise ValueError("Datfile absent ou trop volumineux")
            xml = archive.read(entry)
        if b"<!ENTITY" in xml:
            raise ValueError("Entités XML interdites")
        root = ET.fromstring(xml)
        hashes = {}
        titles = set()
        for game in root.findall("game"):
            name = game.get("name", "")
            if name:
                titles.add(name)
            for rom in game.findall("rom"):
                md5 = rom.get("md5", "").lower()
                if len(md5) == 32 and name:
                    hashes[md5] = name
        if not hashes:
            raise ValueError("Index Redump vide")
        self.md5_to_title, self.titles = hashes, titles
        self.version = root.findtext("header/version") or ""

    def lookup_title_by_md5(self, md5):
        if not self._loaded:
            self.load()
        return self.md5_to_title.get((md5 or "").lower())

    def is_ps2_title(self, title):
        if not self._loaded:
            self.load()
        return title in self.titles


_instances = {}
_lock = threading.Lock()


def get_datfile(cache_dir=None, url=DATFILE_URL):
    path = Path(cache_dir) / "ps2_datfile.json" if cache_dir else CACHE_FILE
    key = (str(path), url)
    with _lock:
        if key not in _instances:
            _instances[key] = RedumpDatfile(path, url)
        result = _instances[key]
    result.load()
    return result
