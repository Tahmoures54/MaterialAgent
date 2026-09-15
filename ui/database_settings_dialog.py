# ui/database_settings_dialog.py
"""
Database engine settings dialog (SQLite ↔ SQL Server).

Writes to ConfigManager / app_config.json. Restart is required after switching engines.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QGroupBox, QMessageBox,
    QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from config.config_manager import config


class DatabaseSettingsDialog(QDialog):
    """Configure SQLite path or SQL Server connection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database Settings")
        self.setMinimumWidth(480)
        self._build_ui()
        self._load_from_config()

    def _build_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Database Engine")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #004D40;")
        root.addWidget(title)

        note = QLabel(
            "Changes are saved to configuration. Restart the application after switching engines."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #607D8B; margin-bottom: 8px;")
        root.addWidget(note)

        form = QFormLayout()
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("SQLite (offline / single-user)", "sqlite")
        self.engine_combo.addItem("SQL Server (network / multi-user)", "sqlserver")
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        form.addRow("Engine:", self.engine_combo)
        root.addLayout(form)

        # SQLite group
        self.sqlite_group = QGroupBox("SQLite")
        sq = QFormLayout(self.sqlite_group)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("aimat.db")
        sq.addRow("Database file:", self.path_edit)
        root.addWidget(self.sqlite_group)

        # SQL Server group
        self.ss_group = QGroupBox("SQL Server")
        ss = QFormLayout(self.ss_group)
        self.server_edit = QLineEdit()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(1433)
        self.db_name_edit = QLineEdit()
        self.user_edit = QLineEdit()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.trusted_chk = QCheckBox("Windows Authentication (Trusted Connection)")
        self.encrypt_chk = QCheckBox("Encrypt")
        self.trust_cert_chk = QCheckBox("Trust server certificate")
        self.driver_edit = QLineEdit()
        self.driver_edit.setText("ODBC Driver 17 for SQL Server")

        ss.addRow("Server:", self.server_edit)
        ss.addRow("Port:", self.port_spin)
        ss.addRow("Database:", self.db_name_edit)
        ss.addRow("Username:", self.user_edit)
        ss.addRow("Password:", self.pass_edit)
        ss.addRow("", self.trusted_chk)
        ss.addRow("", self.encrypt_chk)
        ss.addRow("", self.trust_cert_chk)
        ss.addRow("ODBC Driver:", self.driver_edit)
        root.addWidget(self.ss_group)

        self.trusted_chk.toggled.connect(self._on_trusted_toggled)

        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        btn_save.setStyleSheet(
            "QPushButton { background: #004D40; color: white; padding: 8px 18px; border-radius: 6px; }"
            "QPushButton:hover { background: #00695C; }"
        )
        btn_save.clicked.connect(self._save)
        buttons.addWidget(btn_cancel)
        buttons.addWidget(btn_save)
        root.addLayout(buttons)

        self._on_engine_changed()

    def _on_engine_changed(self):
        is_ss = self.engine_combo.currentData() == "sqlserver"
        self.sqlite_group.setVisible(not is_ss)
        self.ss_group.setVisible(is_ss)

    def _on_trusted_toggled(self, checked: bool):
        self.user_edit.setEnabled(not checked)
        self.pass_edit.setEnabled(not checked)

    def _load_from_config(self):
        engine = (config.get("database.engine") or "sqlite").lower()
        idx = self.engine_combo.findData(engine if engine in ("sqlite", "sqlserver") else "sqlite")
        if idx >= 0:
            self.engine_combo.setCurrentIndex(idx)

        self.path_edit.setText(str(config.get("database.path") or "aimat.db"))

        ss = config.get("database.sqlserver") or {}
        self.server_edit.setText(str(ss.get("server") or "localhost"))
        self.port_spin.setValue(int(ss.get("port") or 1433))
        self.db_name_edit.setText(str(ss.get("database") or "iMat"))
        self.user_edit.setText(str(ss.get("username") or ""))
        self.pass_edit.setText(str(ss.get("password") or ""))
        self.trusted_chk.setChecked(bool(ss.get("trusted_connection", False)))
        self.encrypt_chk.setChecked(bool(ss.get("encrypt", True)))
        self.trust_cert_chk.setChecked(bool(ss.get("trust_server_certificate", True)))
        self.driver_edit.setText(str(ss.get("driver") or "ODBC Driver 17 for SQL Server"))
        self._on_trusted_toggled(self.trusted_chk.isChecked())
        self._on_engine_changed()

    def _save(self):
        engine = self.engine_combo.currentData()
        config.set("database.engine", engine)
        config.set("database.path", self.path_edit.text().strip() or "aimat.db")

        if engine == "sqlserver":
            if not self.server_edit.text().strip() or not self.db_name_edit.text().strip():
                QMessageBox.warning(self, "Validation", "Server and database name are required.")
                return
            if not self.trusted_chk.isChecked() and not self.user_edit.text().strip():
                QMessageBox.warning(self, "Validation", "Username is required unless Trusted Connection is enabled.")
                return

        config.set("database.sqlserver", {
            "enabled": engine == "sqlserver",
            "driver": self.driver_edit.text().strip() or "ODBC Driver 17 for SQL Server",
            "server": self.server_edit.text().strip(),
            "port": self.port_spin.value(),
            "database": self.db_name_edit.text().strip(),
            "username": self.user_edit.text().strip(),
            "password": self.pass_edit.text(),
            "trusted_connection": self.trusted_chk.isChecked(),
            "encrypt": self.encrypt_chk.isChecked(),
            "trust_server_certificate": self.trust_cert_chk.isChecked(),
            "connection_timeout": 30,
            "pool_size": 10,
            "max_overflow": 20,
        })

        if not config.save_json():
            QMessageBox.critical(self, "Error", "Could not write configuration file.")
            return

        QMessageBox.information(
            self,
            "Saved",
            "Database settings saved.\n\nPlease restart iMat for the new connection to take effect.",
        )
        self.accept()
