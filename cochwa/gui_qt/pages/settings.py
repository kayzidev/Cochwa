"""Paramètres : sections console générées depuis le registre, jaquettes, SRM."""

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

from cochwa.consoles import CONSOLES, DEFAULT_CONSOLE
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
        self.console_panels = {}
        self.console_toggles = {}

        # Sections console générées depuis le registre : dossier + lanceur.
        # La console par défaut est toujours dépliée ; les autres sont repliées
        # derrière un bouton (UX historique PS2/Switch).
        for console in CONSOLES:
            cid = console.id
            extensions = "/".join(e.lstrip(".").upper() for e in console.rom_extensions)
            panel, box = section(
                console.name,
                f"Jeux {extensions} et lanceur {console.emulator}.",
            )
            self.console_panels[cid] = panel
            form = self._make_form()
            if console is DEFAULT_CONSOLE:
                box.addLayout(form)
                self._form = form
                self._add_console_rows(console)
                self._row(
                    "download",
                    "Dossier de téléchargement",
                    str(app.config.download_dir or ""),
                    browse=self._pick_download,
                )
                self.values["download"].setPlaceholderText(
                    f"Utiliser le dossier {console.short_name or console.name}"
                )
            else:
                short = console.short_name or console.name
                toggle = QPushButton(f"Afficher la configuration {short}")
                toggle.setCheckable(True)
                box.addWidget(toggle)
                advanced = QWidget()
                advanced.setObjectName("formBody")
                advanced.setLayout(form)
                self._form = form
                self._add_console_rows(console)
                box.addWidget(advanced)
                advanced.hide()
                toggle.toggled.connect(advanced.setVisible)
                toggle.toggled.connect(
                    lambda checked, t=toggle, s=short: t.setText(
                        f"Masquer la configuration {s}"
                        if checked
                        else f"Afficher la configuration {s}"
                    )
                )
                self.console_toggles[cid] = toggle
            panel.setVisible(cid == self.app.console.id)
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
            "Métadonnées des jeux · IGDB",
            "IGDB complète automatiquement les fiches affichées. Configurez un Twitch Client ID et un Client Secret créés depuis une application Twitch Developer. Les identifiants restent dans votre configuration locale.",
        )
        self._form = self._make_form()
        box.addLayout(self._form)
        self._row("igdb_client_id", "Twitch Client ID", app.config.igdb_client_id)
        self._row(
            "igdb_client_secret",
            "Twitch Client Secret",
            app.config.igdb_client_secret,
            password=True,
        )
        self.values["igdb_client_id"].setPlaceholderText(
            "Facultatif · créer une application Twitch"
        )
        self.values["igdb_client_secret"].setPlaceholderText("Facultatif")
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

    def _add_console_rows(self, console):
        """Lignes dossier + lanceur d'une console (clés <id>_directory/<id>_launcher)."""
        cid = console.id
        self._row(
            f"{cid}_directory",
            "Dossier de jeux",
            str(self.app.config.console_dirs.get(cid) or ""),
            browse=lambda c=console: self._pick_directory(c),
        )
        self._row(
            f"{cid}_launcher",
            f"Lanceur {console.emulator}",
            str(self.app.config.console_launchers.get(cid) or ""),
            browse=lambda c=console: self._pick_launcher(c),
        )

    def activate(self):
        current = self.app.console.id
        for cid, panel in self.console_panels.items():
            panel.setVisible(cid == current)
        toggle = self.console_toggles.get(current)
        if toggle:
            toggle.setChecked(True)

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

    def _pick_directory(self, console):
        current = self.app.config.console_dirs.get(console.id)
        path = QFileDialog.getExistingDirectory(
            self,
            f"Dossier {console.short_name or console.name}",
            str(current or Path.home()),
        )
        if path:
            self.values[f"{console.id}_directory"].setText(path)

    def _pick_launcher(self, console):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Script ou exécutable {console.emulator} ({console.name})"
        )
        if path:
            self.values[f"{console.id}_launcher"].setText(path)

    def _pick_download(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Dossier de téléchargement",
            str(self.app.config.download_dir or self.app.config.ps2_dir),
        )
        if path:
            self.values["download"].setText(path)

    def save(self):
        config = self.app.config
        # Validation d'existence par console : un dossier inexistant n'est
        # toléré que s'il est inchangé et hors de la console active (disque
        # débranché). Vide = non configuré (console par défaut : inchangé).
        dirs = {}
        for console in CONSOLES:
            cid = console.id
            raw = self.values[f"{cid}_directory"].text().strip()
            if not raw:
                dirs[cid] = config.console_dirs.get(cid) if console is DEFAULT_CONSOLE else None
                continue
            folder = Path(raw).expanduser()
            if not folder.is_dir() and (
                cid == self.app.console.id or folder != config.console_dirs.get(cid)
            ):
                self.app.error(
                    f"Dossier {console.short_name or console.name} inexistant ; "
                    "vérifier son disque avant de continuer"
                )
                return
            dirs[cid] = folder.absolute()
        launchers = {}
        for console in CONSOLES:
            cid = console.id
            raw = self.values[f"{cid}_launcher"].text().strip()
            launchers[cid] = Path(raw).expanduser().absolute() if raw else None
        download = self.values["download"].text().strip()
        download_dir = None
        if download:
            download_dir = Path(download).expanduser()
            if not download_dir.is_dir():
                self.app.error("Dossier de téléchargement inexistant : " + download)
                return
            download_dir = download_dir.absolute()
        previous = (
            dict(config.console_dirs),
            dict(config.console_launchers),
            config.download_dir,
            config.steamgrid_api_key,
            config.igdb_client_id,
            config.igdb_client_secret,
        )
        try:
            config.console_dirs = dirs
            config.console_launchers = launchers
            config.download_dir = download_dir
            config.steamgrid_api_key = self.values["key"].text().strip()
            config.igdb_client_id = self.values["igdb_client_id"].text().strip()
            config.igdb_client_secret = self.values["igdb_client_secret"].text().strip()
            config.save()
            self.app.metadata.configure(config.igdb_client_id, config.igdb_client_secret)
            self.app.tab_library.ready.refresh()
            self.app.covers.results.clear()
            self.app.tab_library.refresh()
            self.save_status.setText("✓ Paramètres enregistrés")
            self.app.notify("Paramètres enregistrés", "success")
        except Exception as exc:
            (
                config.console_dirs,
                config.console_launchers,
                config.download_dir,
                config.steamgrid_api_key,
                config.igdb_client_id,
                config.igdb_client_secret,
            ) = previous
            self.app.metadata.configure(config.igdb_client_id, config.igdb_client_secret)
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
