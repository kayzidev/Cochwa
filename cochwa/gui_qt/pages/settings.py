"""Paramètres : dossiers, lanceur, clé SteamGridDB, SRM, diagnostic."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SettingsPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        heading = QLabel("Paramètres")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        form = QFormLayout()
        form.setSpacing(10)
        self.values = {}
        self._form = form
        self._row("directory", "Dossier PS2", str(app.config.ps2_dir), browse=self._pick_directory)
        self._row(
            "switch_directory",
            "Dossier Switch",
            str(app.config.switch_dir or ""),
            browse=self._pick_switch_directory,
        )
        self._row(
            "download",
            "Téléchargements (vide = dossier PS2)",
            str(app.config.download_dir or ""),
            browse=self._pick_download,
        )
        self._row("launcher", "Lanceur PCSX2", str(app.config.launcher), browse=self._pick_launcher)
        self._row(
            "switch_launcher",
            "Lanceur Switch (Ryubing)",
            str(app.config.switch_launcher or ""),
            browse=self._pick_switch_launcher,
        )
        self._row("key", "Clé SteamGridDB", app.config.steamgrid_api_key, password=True)
        layout.addLayout(form)

        save = QPushButton("✓ Enregistrer")
        save.setObjectName("primary")
        save.clicked.connect(self.save)
        layout.addWidget(save)

        hint = QLabel(
            "Steam ROM Manager : ouvrir SRM, Parse, Preview, Save apps to Steam.\n"
            "Le redémarrage de Steam reste manuel."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        srm = QPushButton("Ouvrir Steam ROM Manager")
        srm.clicked.connect(self.open_srm)
        layout.addWidget(srm)

        doctor = QPushButton("Diagnostic local")
        doctor.clicked.connect(self.diagnose)
        layout.addWidget(doctor)
        layout.addStretch(1)

        about = QLabel(
            "Cochwa n'héberge aucun contenu : il interroge des catalogues "
            "publics (Internet Archive, MiNERVA) et renvoie vers leurs pages."
        )
        about.setObjectName("muted")
        about.setWordWrap(True)
        layout.addWidget(about)

    def _row(self, key, label, value, browse=None, password=False):
        field = QLineEdit(value)
        if password:
            field.setEchoMode(QLineEdit.Password)
        self.values[key] = field
        if browse:
            wrapper = QHBoxLayout()
            wrapper.addWidget(field, stretch=1)
            button = QPushButton("Choisir…")
            button.clicked.connect(browse)
            wrapper.addWidget(button)
            self._form.addRow(label, wrapper)
        else:
            self._form.addRow(label, field)

    def _pick_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Dossier PS2", str(self.app.config.ps2_dir))
        if path:
            self.values["directory"].setText(path)

    def _pick_switch_directory(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Dossier Switch",
            str(self.app.config.switch_dir or Path.home()),
        )
        if path:
            self.values["switch_directory"].setText(path)

    def _pick_download(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Dossier de téléchargement",
            str(self.app.config.download_dir or self.app.config.ps2_dir),
        )
        if path:
            self.values["download"].setText(path)

    def _pick_launcher(self):
        path, _ = QFileDialog.getOpenFileName(self, "Script ou exécutable PCSX2")
        if path:
            self.values["launcher"].setText(path)

    def _pick_switch_launcher(self):
        path, _ = QFileDialog.getOpenFileName(self, "Script ou exécutable Ryubing (Switch)")
        if path:
            self.values["switch_launcher"].setText(path)

    def save(self):
        root = Path(self.values["directory"].text()).expanduser()
        if not root.is_dir():
            self.app.error("Choisir un dossier existant ; vérifier son disque avant de continuer")
            return
        switch = self.values["switch_directory"].text().strip()
        switch_dir = None
        if switch:
            switch_dir = Path(switch).expanduser()
            if not switch_dir.is_dir():
                self.app.error("Dossier Switch inexistant : " + switch)
                return
            switch_dir = switch_dir.absolute()
        switch_launcher = self.values["switch_launcher"].text().strip()
        switch_launcher = Path(switch_launcher).expanduser().absolute() if switch_launcher else None
        download = self.values["download"].text().strip()
        download_dir = None
        if download:
            download_dir = Path(download).expanduser()
            if not download_dir.is_dir():
                self.app.error("Dossier de téléchargement inexistant : " + download)
                return
            download_dir = download_dir.absolute()
        config = self.app.config
        previous = (
            config.ps2_dir,
            config.switch_dir,
            config.download_dir,
            config.launcher,
            config.switch_launcher,
            config.steamgrid_api_key,
        )
        try:
            config.ps2_dir = root.absolute()
            config.switch_dir = switch_dir
            config.download_dir = download_dir
            config.launcher = Path(self.values["launcher"].text()).expanduser().absolute()
            config.switch_launcher = switch_launcher
            config.steamgrid_api_key = self.values["key"].text().strip()
            config.save()
            self.app.covers.results.clear()
            self.app.tab_library.refresh()
            self.app.notify("Paramètres enregistrés", "success")
        except Exception as exc:
            (
                config.ps2_dir,
                config.switch_dir,
                config.download_dir,
                config.launcher,
                config.switch_launcher,
                config.steamgrid_api_key,
            ) = previous
            self.app.error(str(exc))

    def open_srm(self):
        from cochwa.steam import trigger_srm_reparse

        self.app.worker.submit(
            lambda: trigger_srm_reparse(self.app.config.srm_flatpak),
            lambda ok: self.app.notify(
                "SRM ouvert ; effectuer Parse puis Save dans SRM."
                if ok
                else "SRM indisponible ; vérifier Flatpak.",
                "info" if ok else "error",
            ),
        )

    def diagnose(self):
        from cochwa.cli import doctor

        data = doctor(self.app.config)
        dialog = QDialog(self)
        dialog.setWindowTitle("Diagnostic local")
        dialog.resize(760, 520)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
        layout.addWidget(text)
        dialog.exec()
