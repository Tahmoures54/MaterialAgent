# license_generator.py
"""
iMat License Generator – VENDOR TOOL ONLY (STANDALONE)
No external project dependencies – everything is self-contained.
Compatible with the customer's utils/license.py logic.
"""

import sys
import os
import hashlib
import base64
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QMessageBox, QComboBox,
    QFrame
)
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtGui import QFont, QClipboard, QDesktopServices


# ==================================================================
# Embedded License Logic (identical to utils/license.py)
# ==================================================================

_SECRET_PARTS_B64 = [
    "QWlNYXQyMDI1",          # "AiMat2025"
    "IUAjJCVeJiooKQ==",      # "!@#$%^&*()"
    "RVBDX0VkaXRpb24="       # "EPC_Edition"
]
SECRET_KEY = "".join(base64.b64decode(p).decode() for p in _SECRET_PARTS_B64)

# Updated global market plans
LICENSE_TYPES = {
    "trial":       {"duration_days": 14,     "max_records": 200,   "max_users": 1},
    "standard":    {"duration_days": 365,    "max_records": 5000,  "max_users": 2},
    "professional": {"duration_days": 365,   "max_records": 50000, "max_users": 5},
    "enterprise":  {"duration_days": 99999,  "max_records": -1,    "max_users": -1},
}

# Plan descriptions – shown in generator, includes pricing for your reference
PLAN_DESCRIPTIONS = {
    "trial": (
        "🆓 FREE – 14-day full-feature trial\n"
        "👥 1 user  •  📦 200 records\n"
        "✨ ALL Professional features unlocked (AI, ABC, EOQ, reports...)\n"
        "No credit card required"
    ),
    "standard": (
        "💲 $99 / year\n"
        "👥 2 users  •  📦 5,000 records\n"
        "✅ Inventory, documents, barcode, Excel/PDF, expiry, QC, preservation"
    ),
    "professional": (
        "💲 $299 / year\n"
        "👥 5 users  •  📦 50,000 records\n"
        "✅ All Standard features +\n"
        "   • AI demand prediction\n"
        "   • ABC analysis\n"
        "   • EOQ calculator\n"
        "   • Advanced reports\n"
        "   • Multi-user support"
    ),
    "enterprise": (
        "💲 $999 one-time (lifetime license)\n"
        "👥 Unlimited users  •  📦 Unlimited records\n"
        "✅ All Professional features +\n"
        "   • REST API access\n"
        "   • Custom branding\n"
        "   • 24/7 priority support\n"
        "   • Lifetime free updates"
    ),
}

GRACE_PERIOD_DAYS = 7


def generate_license_key(machine_id, license_type="standard", expiry_days=365, secret_key=SECRET_KEY):
    expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y%m%d")
    data = f"{machine_id}|{expiry_date}|{license_type}|{secret_key}"
    signature = hashlib.sha256(data.encode()).hexdigest()[:10]
    return f"{machine_id}-{expiry_date}-{signature}"


def validate_license(license_key, machine_id):
    try:
        parts = license_key.split('-')
        if len(parts) != 3:
            return False
        stored_machine, expiry_str, signature = parts
        if stored_machine != machine_id:
            return False
        expiry_date = datetime.strptime(expiry_str, "%Y%m%d")
        if datetime.now() > expiry_date + timedelta(days=GRACE_PERIOD_DAYS):
            return False
        for lic_type in LICENSE_TYPES:
            data = f"{stored_machine}|{expiry_str}|{lic_type}|{SECRET_KEY}"
            expected_sig = hashlib.sha256(data.encode()).hexdigest()[:10]
            if signature == expected_sig:
                return True
        return False
    except Exception:
        return False


# ==================================================================
# GUI
# ==================================================================

VENDOR_WHATSAPP = "989160684552"


class LicenseGeneratorDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("iMat – License Generator (Vendor)")
        self.setFixedSize(620, 780)  # taller to fit new descriptions
        self.setModal(True)

        self._clip_timer = QTimer(self)
        self._clip_timer.setSingleShot(True)
        self._clip_timer.timeout.connect(
            lambda: QApplication.clipboard().setText("", QClipboard.Mode.Clipboard))

        self._apply_style()
        self._init_ui()

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog { background-color: #0F141A; }
            QLabel { color: #8B97A7; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; }
            QLabel#title { color: #FFFFFF; font-size: 18px; font-weight: 800; }
            QLabel#sub { color: #5C6B7A; font-size: 11px; }
            QLabel#planDesc {
                color: #B8C2CE; font-size: 11px; font-weight: 400;
                background-color: #1A222C; border: 1px solid #283340; border-radius: 6px;
                padding: 12px; line-height: 1.4;
            }
            QLineEdit, QSpinBox, QComboBox {
                background-color: #1A222C; border: 1px solid #283340; border-radius: 8px;
                padding: 10px 12px; font-size: 13px; color: #E6EDF3; }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #3B82F6; }
            QComboBox::drop-down { width: 28px; border: none; }
            QComboBox::down-arrow { width: 0; height: 0;
                border-left: 5px solid transparent; border-right: 5px solid transparent;
                border-top: 6px solid #8B97A7; margin-right: 10px; }
            QComboBox QAbstractItemView { background-color: #1A222C; border: 1px solid #283340;
                selection-background-color: #3B82F6; color: #E6EDF3; }
            QSpinBox::up-button, QSpinBox::down-button { width: 0; }
            QPushButton { border: none; border-radius: 8px; padding: 12px 16px;
                font-size: 13px; font-weight: 700; color: white; }
            QPushButton#primary { background-color: #3B82F6; }
            QPushButton#primary:hover { background-color: #2563EB; }
            QPushButton#success { background-color: #16A34A; }
            QPushButton#success:hover { background-color: #15803D; }
            QPushButton#ghost { background-color: transparent; color: #8B97A7; border: 1px solid #283340; }
            QPushButton#ghost:hover { background-color: #1A222C; color: #E6EDF3; }
            QPushButton#icon { background-color: #283340; color: #B8C2CE; padding: 10px 12px; }
            QPushButton#icon:hover { background-color: #344150; color: white; }
            QFrame#divider { background-color: #1E2832; max-height: 1px; min-height: 1px; }
        """)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        # Header
        head = QHBoxLayout()
        logo = QLabel("🔐"); logo.setFont(QFont("Arial", 26)); logo.setFixedWidth(46)
        head.addWidget(logo)
        tb = QVBoxLayout(); tb.setSpacing(2)
        t1 = QLabel("License Generator"); t1.setObjectName("title")
        t2 = QLabel("iMat EPC Edition  •  Vendor Tool"); t2.setObjectName("sub")
        tb.addWidget(t1); tb.addWidget(t2)
        head.addLayout(tb); head.addStretch()
        root.addLayout(head)

        d = QFrame(); d.setObjectName("divider"); root.addWidget(d)

        form = QGridLayout()
        form.setHorizontalSpacing(12); form.setVerticalSpacing(8)
        form.setColumnStretch(0, 1)
        r = 0

        form.addWidget(QLabel("CUSTOMER MACHINE ID  (paste from customer)"), r, 0, 1, 2); r += 1
        self.mid_edit = QLineEdit()
        self.mid_edit.setPlaceholderText("e.g.  a1b2c3d4e5f6g7h8")
        self.mid_edit.setStyleSheet("font-family: 'Consolas', monospace; letter-spacing: 1px;")
        form.addWidget(self.mid_edit, r, 0, 1, 2); r += 1

        form.addWidget(QLabel("LICENSE TYPE"), r, 0)
        form.addWidget(QLabel("VALIDITY"), r, 1); r += 1
        self.type_combo = QComboBox()
        for k, v in LICENSE_TYPES.items():
            records_label = "Unlimited" if v["max_records"] == -1 else str(v["max_records"])
            users_label = "Unlimited" if v["max_users"] == -1 else str(v["max_users"])
            self.type_combo.addItem(f"{k.capitalize()}  •  {records_label} records  •  {users_label} users", k)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addWidget(self.type_combo, r, 0)
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 99999)
        self.days_spin.setValue(LICENSE_TYPES["standard"]["duration_days"])
        self.days_spin.setSuffix(" days")
        self.days_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form.addWidget(self.days_spin, r, 1); r += 1

        # Plan description label
        self.plan_desc_label = QLabel("")
        self.plan_desc_label.setObjectName("planDesc")
        self.plan_desc_label.setWordWrap(True)
        form.addWidget(self.plan_desc_label, r, 0, 1, 2); r += 1

        form.addWidget(QLabel("SECRET KEY"), r, 0, 1, 2); r += 1
        self.secret_edit = QLineEdit(SECRET_KEY)
        self.secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret_edit.setPlaceholderText("Signing secret (must match the app)")
        form.addWidget(self.secret_edit, r, 0, 1, 2); r += 1
        root.addLayout(form)

        idx = list(LICENSE_TYPES.keys()).index("standard") if "standard" in LICENSE_TYPES else 0
        self.type_combo.setCurrentIndex(idx)

        gen = QPushButton("⚡  Generate License Key")
        gen.setObjectName("primary")
        gen.setCursor(Qt.CursorShape.PointingHandCursor)
        gen.clicked.connect(self._generate)
        root.addWidget(gen)

        root.addWidget(QLabel("GENERATED LICENSE KEY"))
        rr = QHBoxLayout(); rr.setSpacing(10)
        self.result_edit = QLineEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setPlaceholderText("— no key generated yet —")
        self.result_edit.setStyleSheet(
            "font-family:'Consolas',monospace; font-size:14px; font-weight:bold;"
            "color:#4ADE80; letter-spacing:1px; padding:14px 12px;")
        rr.addWidget(self.result_edit)
        cp = QPushButton("📋"); cp.setObjectName("icon")
        cp.setToolTip("Copy key (auto-clears in 30s)")
        cp.clicked.connect(lambda: self._copy(self.result_edit.text(), True))
        rr.addWidget(cp)
        root.addLayout(rr)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color:#5C6B7A; font-size:11px;")
        root.addWidget(self.status_lbl)

        root.addStretch()

        acts = QHBoxLayout(); acts.setSpacing(10)
        wa = QPushButton("💬  Send via WhatsApp"); wa.setObjectName("success")
        wa.setCursor(Qt.CursorShape.PointingHandCursor)
        wa.clicked.connect(self._send_whatsapp)
        acts.addWidget(wa); acts.addStretch()
        cl = QPushButton("Close"); cl.setObjectName("ghost")
        cl.clicked.connect(self.reject)
        acts.addWidget(cl)
        root.addLayout(acts)

        self._on_type_changed()

    def _on_type_changed(self):
        k = self.type_combo.currentData()
        if k in LICENSE_TYPES:
            self.days_spin.setValue(LICENSE_TYPES[k]["duration_days"])
        if k in PLAN_DESCRIPTIONS:
            self.plan_desc_label.setText(PLAN_DESCRIPTIONS[k])
        else:
            self.plan_desc_label.setText("")

    def _generate(self):
        mid = self.mid_edit.text().strip()
        days = self.days_spin.value()
        secret = self.secret_edit.text().strip()
        lic_type = self.type_combo.currentData()

        if not mid:
            QMessageBox.warning(self, "Error", "Customer Machine ID is required.")
            return
        if not secret:
            QMessageBox.warning(self, "Error", "Secret key cannot be empty.")
            return

        try:
            key = generate_license_key(mid, lic_type, days, secret)
            self.result_edit.setText(key)

            if validate_license(key, mid):
                self.status_lbl.setText("✅ Self-test passed — key validates on the target machine.")
                self.status_lbl.setStyleSheet("color:#4ADE80; font-size:11px;")
            else:
                self.status_lbl.setText("❌ Self-test FAILED — key will NOT validate! Check secret key.")
                self.status_lbl.setStyleSheet("color:#F87171; font-size:11px; font-weight:bold;")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed:\n{e}")

    def _copy(self, text, sensitive=False):
        if text:
            QApplication.clipboard().setText(text, QClipboard.Mode.Clipboard)
            QMessageBox.information(self, "Copied", "Copied to clipboard.")
            if sensitive:
                self._clip_timer.start(30000)
        else:
            QMessageBox.warning(self, "Nothing to Copy", "No text.")

    def _send_whatsapp(self):
        key = self.result_edit.text()
        if not key:
            QMessageBox.warning(self, "No Key", "Generate a key first.")
            return
        reply = QMessageBox.warning(
            self, "Security Notice",
            "The WhatsApp link contains the customer's license.\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        lic = self.type_combo.currentText().split("  •")[0]
        mid = self.mid_edit.text()
        days = self.days_spin.value()
        msg = (f"Your iMat License Key:%0A%0A*{key}*%0A%0A"
               f"Machine ID: {mid}%0A"
               f"License: {lic}%0AValidity: {days} days%0A%0A"
               f"Thank you for choosing iMat!%0Awww.imat.io")
        QDesktopServices.openUrl(QUrl(f"https://wa.me/{VENDOR_WHATSAPP}?text={msg}"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    LicenseGeneratorDialog().show()
    sys.exit(app.exec())