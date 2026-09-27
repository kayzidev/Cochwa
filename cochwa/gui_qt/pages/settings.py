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
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from cochwa.gui_qt.widgets import PageHeader, section


class SettingsPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(14)
        layout.addWidget(
            PageHeader(
                "À votre façon",
                "Dossiers, émulateurs et jaquettes : tout commence ici.",
                "PARAMÈTRES",
            )
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        content = QVBoxLayout(body)
        content.setContentsMargins(0, 0, 8, 0)
        content.setSpacing(16)
        self.values = {}

        panel, box = section("PlayStation 2", "Jeux, téléchargements et émulateur PlayStation 2.")
        self.ps2_panel = panel
        self._form = self._make_form()
        box.addLayout(self._form)
        self._row(
            "directory", "Dossier de jeux", str(app.config.ps2_dir), browse=self._pick_directory
        )
        self._row("launcher", "Lanceur PCSX2", str(app.config.launcher), browse=self._pick_launcher)
        self._row(
            "download",
            "Dossier de téléchargement",
            str(app.config.download_dir or ""),
            browse=self._pick_download,
        )
        self.values["download"].setPlaceholderText("Utiliser le dossier PS2")
        content.addWidget(panel)

        panel, box = section(
            "Jaquettes",
            "Connectez SteamGridDB pour enrichir votre bibliothèque. Une jaquette locale peut aussi être choisie depuis un jeu.",
        )
        self._form = self._make_form()
        box.addLayout(self._form)
        self._row("key", "Clé SteamGridDB", app.config.steamgrid_api_key, password=True)
        self.values["key"].setPlaceholderText("Facultatif")
        content.addWidget(panel)

        panel, box = section(
            "Nintendo Switch",
            "Jeux NSP/XCI, recherche Internet Archive et lanceur Ryubing.",
        )
        self.switch_panel = panel
        toggle = QPushButton("Afficher la configuration Switch")
        toggle.setCheckable(True)
        box.addWidget(toggle)
        advanced = QWidget()
        advanced.setObjectName("formBody")
        self.switch_settings = advanced
        self.switch_toggle = toggle
        self._form = self._make_form()
        advanced.setLayout(self._form)
        self._row(
            "switch_directory",
            "Dossier de jeux",
            str(app.config.switch_dir or ""),
            browse=self._pick_switch_directory,
        )
        self._row(
            "switch_launcher",
            "Lanceur Ryubing",
            str(app.config.switch_launcher or ""),
            browse=self._pick_switch_launcher,
        )
        box.addWidget(advanced)
        advanced.hide()
        toggle.toggled.connect(advanced.setVisible)
        toggle.toggled.connect(
            lambda checked: toggle.setText(
                "Masquer la configuration Switch" if checked else "Afficher la configuration Switch"
            )
        )
        content.addWidget(panel)

        panel, box = section(
            "Steam & diagnostic",
            "Préparez les préréglages et synchronisez vos jeux depuis Cochwa. Steam reste à fermer et rouvrir manuellement.",
        )
        setup = QPushButton("Configurer mes consoles dans Steam")
        setup.setObjectName("primary")
        setup.clicked.connect(self.setup_srm)
        box.addWidget(setup)
        actions = QHBoxLayout()
        srm = QPushButton("Ouvrir Steam ROM Manager")
        srm.clicked.connect(self.open_srm)
        actions.addWidget(srm)
        doctor = QPushButton("Diagnostic local")
        doctor.clicked.connect(self.diagnose)
        actions.addWidget(doctor)
        box.addLayout(actions)
        content.addWidget(panel)
        content.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, stretch=1)
        footer = QHBoxLayout()
        self.save_status = QLabel("Les modifications s’appliquent après enregistrement.")
        self.save_status.setObjectName("muted")
        self.save_status.setWordWrap(True)
        footer.addWidget(self.save_status, stretch=1)
        save = QPushButton("Enregistrer les modifications")
        save.setObjectName("primary")
        save.clicked.connect(self.save)
        footer.addWidget(save)
        layout.addLayout(footer)

    def activate(self):
        switch = self.app.console.id == "switch"
        self.ps2_panel.setVisible(not switch)
        self.switch_panel.setVisible(switch)
        self.switch_toggle.setChecked(switch)

    def setup_srm(self):
        from cochwa.gui_qt.srm_dialog import SRMDialog

        dialog = SRMDialog(self.app, self)
        dialog.show()
        return dialog

    def _make_form(self):
        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        return form

    def _row(self, key, label, value, browse=None, password=False):
        field = QLineEdit(value)
        field.setMinimumWidth(140)
        field.setAccessibleName(label)
        field.textChanged.connect(
            lambda: self.save_status.setText("Modifications non enregistrées")
        )
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
        if not root.is_dir() and (self.app.console.id == "ps2" or root != self.app.config.ps2_dir):
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
            self.save_status.setText("✓ Paramètres enregistrés")
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
