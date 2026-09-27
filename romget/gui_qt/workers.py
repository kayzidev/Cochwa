"""Pont threads → GUI : remplace le Dispatcher Tkinter par des signaux Qt.

Les workers (recherche, jaquettes, scan, conversions) ne touchent jamais les
widgets ; les résultats arrivent par connexions en file (thread GUI).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThreadPool, Signal


class _Task(QObject):
    success = Signal(object)
    error = Signal(str)

    def __init__(self, work):
        super().__init__()
        self._work = work

    def run(self):
        try:
            self.success.emit(self._work())
        except Exception as exc:
            self.error.emit(str(exc))


class Worker(QObject):
    """Soumet des callables au pool ; les callbacks sont livrés dans le thread GUI."""

    def __init__(self, parent=None, threads=4):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(threads)
        self._tasks = set()

    def submit(self, work, on_success=None, on_error=None):
        task = _Task(work)
        self._tasks.add(task)  # garde la référence jusqu'à livraison
        if on_success:
            task.success.connect(on_success)
        task.error.connect(on_error or (lambda message: None))
        task.success.connect(lambda *_: self._tasks.discard(task))
        task.error.connect(lambda *_: self._tasks.discard(task))
        self.pool.start(task.run)


class CoverService(QObject):
    """Jaquettes via le service existant ; cache mémoire + disque, dédup par titre de base."""

    loaded = Signal(str, object)  # titre de base, chemin ou None

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.results = {}  # titre de base -> Path ou None (cache négatif inclus)
        self.pending = set()
        self.worker = Worker(self)

    def request(self, title, ia_identifier=None):
        from romget.api.steamgriddb import download_cover

        base = title.split("(")[0].strip()
        if base in self.results or base in self.pending:
            return
        if not self.config.steamgrid_api_key and not ia_identifier:
            self.results[base] = None
            return
        self.pending.add(base)

        def work():
            try:
                return download_cover(
                    self.config.steamgrid_api_key,
                    base,
                    cache_dir=self.config.cache_dir / "covers",
                    ia_identifier=ia_identifier,
                )
            except Exception:
                return None

        def deliver(path):
            self.pending.discard(base)
            self.results[base] = path
            self.loaded.emit(base, path)

        self.worker.submit(work, deliver)
