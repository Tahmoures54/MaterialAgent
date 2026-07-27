# ui/license_dialog.py
"""
iMat License Activation Dialog – CUSTOMER side.
Compatible with utils/license.py.

Provides:
- ActivationDialog (the GUI)
- LicenseDialog alias (for backward compatibility with ui/__init__.py)
- get_license_info() helper
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QFrame, QWidget
)
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtGui import QFont, QClipboard, QDesktopServices

from utils.license import (
    get_machine_id,
    validate_license,
    validate_license_detailed,
    save_license,
    load_license,
    get_license_status,
    get_license_type,
    get_remaining_days,
    is_license_valid,
    get_license_features,
)

VENDOR_WHATSAPP = "989160684552"
VENDOR_WEBSITE = "www.imat.io"


class ActivationDialog(QDialog):
    """License activation dialog shown to the customer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("iMat – License Activation")
        self.setFixedSize(560, 580)
        self.setModal(True)
        self._apply_style()
        self._init_ui()
        self._refresh_status()

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog { background-color: #0F141A; }
            QLabel { color: #8B97A7; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; }
            QLabel#title { color: #FFFFFF; font-size: 18px; font-weight: 800; }
            QLabel#sub { color: #5C6B7A; font-size: 11px; }
            QLabel#statusBox {
                font-size: 13px; font-weight: 700; padding: 14px;
                border-radius: 8px; }
            QLineEdit {
                background-color: #1A222C; border: 1px solid #283340; border-radius: 8px;
                padding: 12px; font-size: 13px; color: #E6EDF3; }
            QLineEdit:focus { border: 1px solid #3B82F6; }
            QLineEdit:read-only { color: #B8C2CE; }
            QPushButton { border: none; border-radius: 8px; padding: 12px 16px;
                font-size: 13px; font-weight: 700; color: white; }
            QPushButton#primary { background-color: #3B82F6; }
            QPushButton#primary:hover { background-color: #2563EB; }
            QPushButton#success { background-color: #16A34A; }
            QPushButton#success:hover { background-color: #15803D; }
            QPushButton#ghost { background-color: transparent; color: #8B97A7; border: 1px solid #283340; }
            QPushButton#ghost:hover { background-color: #1A222C; color: #E6EDF3; }
            QPushButton#icon { background-color: #283340; color: #B8C2CE; padding: 12px; }
            QPushButton#icon:hover { background-color: #344150; color: white; }
            QFrame#divider { background-color: #1E2832; max-height: 1px; min-height: 1px; }
        """)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        # Header
        head = QHBoxLayout()
        logo = QLabel("🔑"); logo.setFont(QFont("Arial", 26)); logo.setFixedWidth(46)
        head.addWidget(logo)
        tb = QVBoxLayout(); tb.setSpacing(2)
        t1 = QLabel("Activate iMat"); t1.setObjectName("title")
        t2 = QLabel("EPC Edition  •  License Activation"); t2.setObjectName("sub")
        tb.addWidget(t1); tb.addWidget(t2)
        head.addLayout(tb); head.addStretch()
        root.addLayout(head)

        d = QFrame(); d.setObjectName("divider"); root.addWidget(d)

        # Status box
        self.status_box = QLabel("")
        self.status_box.setObjectName("statusBox")
        self.status_box.setWordWrap(True)
        self.status_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.status_box)

        # Step 1
        root.addWidget(QLabel("STEP 1  —  SEND THIS MACHINE ID TO THE VENDOR"))
        mid_row = QHBoxLayout(); mid_row.setSpacing(10)
        self.mid_edit = QLineEdit(get_machine_id())
        self.mid_edit.setReadOnly(True)
        self.mid_edit.setStyleSheet(
            "font-family:'Consolas',monospace; font-size:15px; letter-spacing:2px;"
            "color:#4ADE80; font-weight:bold;")
        mid_row.addWidget(self.mid_edit)
        cp = QPushButton("📋"); cp.setObjectName("icon")
        cp.setToolTip("Copy Machine ID")
        cp.clicked.connect(self._copy_mid)
        mid_row.addWidget(cp)
        root.addLayout(mid_row)

        req = QPushButton("💬  Request License via WhatsApp")
        req.setObjectName("success")
        req.setCursor(Qt.CursorShape.PointingHandCursor)
        req.clicked.connect(self._request_license)
        root.addWidget(req)

        d2 = QFrame(); d2.setObjectName("divider"); root.addWidget(d2)

        # Step 2
        root.addWidget(QLabel("STEP 2  —  ENTER THE LICENSE KEY YOU RECEIVED"))
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("e.g.  a1b2c3d4e5f6g7h8-20261231-a8f3c2d1e0")
        self.key_edit.setStyleSheet("font-family:'Consolas',monospace; letter-spacing:1px;")
        self.key_edit.returnPressed.connect(self._activate)
        root.addWidget(self.key_edit)

        act = QPushButton("✓  Activate License")
        act.setObjectName("primary")
        act.setCursor(Qt.CursorShape.PointingHandCursor)
        act.clicked.connect(self._activate)
        root.addWidget(act)

        root.addStretch()

        # Footer
        foot = QHBoxLayout()
        web = QLabel(f"🌐  {VENDOR_WEBSITE}")
        web.setStyleSheet("color:#5C6B7A; font-size:11px;")
        foot.addWidget(web)
        foot.addStretch()
        close = QPushButton("Continue")
        close.setObjectName("ghost")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.accept)
        foot.addWidget(close)
        root.addLayout(foot)

    def _refresh_status(self):
        status = get_license_status()
        if not status.get("activated"):
            self._set_status(
                "⚠️  No license activated — please activate to unlock all features.",
                "#F59E0B", "#3A2E12")
            return
        if status.get("valid"):
            days = status.get("days_remaining", 0)
            lic_type = get_license_type(status.get("license_key", "")).capitalize()
            days_display = "Unlimited" if days > 3650 else f"{days} days"
            if status.get("in_grace_period"):
                self._set_status(
                    f"⏳  License in GRACE PERIOD — renew soon!  ({lic_type})",
                    "#F59E0B", "#3A2E12")
            else:
                self._set_status(
                    f"✅  Active  •  {lic_type}  •  {days_display} remaining",
                    "#4ADE80", "#0F2A18")
                self.key_edit.setText(status.get("license_key", ""))
        else:
            msg = status.get("message", "License is invalid.")
            self._set_status(f"❌  {msg}", "#F87171", "#2A1212")

    def _set_status(self, text, fg, bg):
        self.status_box.setText(text)
        self.status_box.setStyleSheet(
            f"#statusBox {{ color:{fg}; background-color:{bg}; "
            f"border:1px solid {fg}; }}")

    def _copy_mid(self):
        QApplication.clipboard().setText(self.mid_edit.text(), QClipboard.Mode.Clipboard)
        QMessageBox.information(self, "Copied",
                                "Machine ID copied.\nSend it to the vendor to get your license.")

    def _request_license(self):
        mid = self.mid_edit.text()
        msg = (f"Hello, I would like to purchase an iMat license.%0A%0A"
               f"My Machine ID is:%0A*{mid}*%0A%0A"
               f"Please send me a license key. Thank you!")
        QDesktopServices.openUrl(QUrl(f"https://wa.me/{VENDOR_WHATSAPP}?text={msg}"))

    def _activate(self):
        key = self.key_edit.text().strip()
        machine_id = get_machine_id()
        if not key:
            QMessageBox.warning(self, "Empty Key", "Please enter your license key.")
            return
        detail = validate_license_detailed(key, machine_id)
        if detail["valid"]:
            if save_license(key):
                lic_type = detail.get("license_type", "standard").capitalize()
                days = detail.get("days_remaining", 0)
                QMessageBox.information(
                    self, "Activated 🎉",
                    f"License activated successfully!\n\n"
                    f"Type: {lic_type}\n"
                    f"Valid for: {days} days\n\n"
                    f"Thank you for choosing iMat!")
                self._refresh_status()
                self.accept()
            else:
                QMessageBox.critical(self, "Save Failed",
                                     "License is valid but could not be saved to disk.")
        else:
            reason = detail.get("message", "Invalid license.")
            extra = ""
            if not detail["machine_match"]:
                extra = ("\n\nThis key was issued for a different machine.\n"
                         "Make sure you sent the correct Machine ID to the vendor.")
            elif detail["expired"]:
                extra = "\n\nThis license has expired. Please renew."
            elif not detail["signature_valid"]:
                extra = ("\n\nThe key appears altered or mistyped.\n"
                         "Please copy it exactly as received.")
            QMessageBox.critical(self, "Activation Failed", f"{reason}{extra}")


# ==================================================================
# Backward compatibility aliases for ui/__init__.py
# ==================================================================

# The original code expected a LicenseDialog class.
LicenseDialog = ActivationDialog

def get_license_info():
    """
    Return a summary of current license info.
    Used by other parts of the app (e.g., start dialog, about).
    """
    status = get_license_status()
    features = get_license_features(status.get("license_type", "unknown"))
    return {
        "activated": status.get("activated", False),
        "valid": status.get("valid", False),
        "type": status.get("license_type", "unknown"),
        "days_remaining": status.get("days_remaining", 0),
        "in_grace_period": status.get("in_grace_period", False),
        "features": features,
    }


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = ActivationDialog()
    dlg.show()
    sys.exit(app.exec())