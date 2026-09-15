# ui/start_dialog.py
"""
Start/Welcome Dialog – iMat Material Control System (EPC Edition).
"""

import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGraphicsDropShadowEffect, QWidget, QScrollArea,
    QGridLayout, QGroupBox, QSizePolicy, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import (
    QFont, QColor, QMouseEvent, QIcon, QPixmap,
    QPainter, QPen, QBrush, QLinearGradient
)

from ui.logo_widget import LogoWidget, AnimatedDot

APP_NAME = "iMat Warehouse"
APP_VERSION = "2.2.0"
WHATSAPP_NUMBER = "+989160684552"
WEBSITE_URL = "https://www.imat.io"

ROLE_ACTIONS = {
    "admin": [
        {"label": "📦 Material Catalog", "action": "new_item", "description": "Manage item codes and descriptions", "color": "#4CAF50", "shortcut": "Ctrl+M", "priority": 1},
        {"label": "📄 New Document", "action": "new_transaction", "description": "Create MRR, MIV, MSR, OS&D documents", "color": "#2196F3", "shortcut": "Ctrl+D", "priority": 2},
        {"label": "📋 Material Request", "action": "new_material_request", "description": "Create new material requisition", "color": "#7E57C2", "shortcut": "Ctrl+R", "priority": 3},
        {"label": "🔍 QC Release", "action": "qc_release", "description": "Release materials from quarantine", "color": "#FF7043", "shortcut": "Ctrl+Q", "priority": 4},
        {"label": "🛡️ Preservation", "action": "preservation", "description": "Monitor preservation schedules", "color": "#66BB6A", "shortcut": "Ctrl+P", "priority": 5},
        {"label": "📊 Live Stock", "action": "live_stock_report", "description": "View real-time stock levels", "color": "#42A5F5", "shortcut": "Ctrl+L", "priority": 6},
        {"label": "👥 Manage Users", "action": "manage_users", "description": "Add, edit, or deactivate users", "color": "#EF5350", "shortcut": "Ctrl+U", "priority": 7},
        {"label": "📊 Reports", "action": "reports", "description": "Generate and export reports", "color": "#FF9800", "shortcut": "Ctrl+E", "priority": 8},
    ],
    "operator": [
        {"label": "📄 New Document", "action": "new_transaction", "description": "Create MRR, MIV, MSR, OS&D", "color": "#2196F3", "shortcut": "Ctrl+D", "priority": 1},
        {"label": "📦 Material Catalog", "action": "new_item", "description": "Manage item codes", "color": "#4CAF50", "shortcut": "Ctrl+M", "priority": 2},
        {"label": "🔍 QC Release", "action": "qc_release", "description": "Release from quarantine", "color": "#FF7043", "shortcut": "Ctrl+Q", "priority": 3},
        {"label": "🛡️ Preservation", "action": "preservation", "description": "Monitor preservation", "color": "#66BB6A", "shortcut": "Ctrl+P", "priority": 4},
        {"label": "📊 Live Stock", "action": "live_stock_report", "description": "View stock levels", "color": "#42A5F5", "shortcut": "Ctrl+L", "priority": 5},
        {"label": "📊 Reports", "action": "reports", "description": "Generate reports", "color": "#FF9800", "shortcut": "Ctrl+E", "priority": 6},
    ],
    "technical": [
        {"label": "📋 Material Request", "action": "new_material_request", "description": "Create material requisition", "color": "#7E57C2", "shortcut": "Ctrl+R", "priority": 1},
        {"label": "📄 MR History", "action": "material_request_history", "description": "View request history", "color": "#5C6BC0", "shortcut": "Ctrl+H", "priority": 2},
        {"label": "📊 Live Stock", "action": "live_stock_report", "description": "View stock levels", "color": "#42A5F5", "shortcut": "Ctrl+L", "priority": 3},
        {"label": "🔗 Traceability", "action": "traceability", "description": "Track material history", "color": "#00BCD4", "shortcut": "Ctrl+T", "priority": 4},
        {"label": "📊 Reports", "action": "reports", "description": "Generate reports", "color": "#FF9800", "shortcut": "Ctrl+E", "priority": 5},
    ],
    "qc_inspector": [
        {"label": "🔍 QC Release", "action": "qc_release", "description": "Release from quarantine", "color": "#FF7043", "shortcut": "Ctrl+Q", "priority": 1},
        {"label": "🛡️ Preservation", "action": "preservation", "description": "Monitor preservation", "color": "#66BB6A", "shortcut": "Ctrl+P", "priority": 2},
        {"label": "⌛ Expiry Monitor", "action": "expiry_monitor", "description": "Track expiry dates", "color": "#F44336", "shortcut": "Ctrl+X", "priority": 3},
        {"label": "📊 Live Stock", "action": "live_stock_report", "description": "View stock levels", "color": "#42A5F5", "shortcut": "Ctrl+L", "priority": 4},
        {"label": "📊 Reports", "action": "reports", "description": "Generate reports", "color": "#FF9800", "shortcut": "Ctrl+E", "priority": 5},
    ],
    "viewer": [
        {"label": "📊 Live Stock", "action": "live_stock_report", "description": "View stock levels", "color": "#42A5F5", "shortcut": "Ctrl+L", "priority": 1},
        {"label": "📊 Reports", "action": "reports", "description": "View reports", "color": "#FF9800", "shortcut": "Ctrl+E", "priority": 2},
        {"label": "🔗 Traceability", "action": "traceability", "description": "Track material history", "color": "#00BCD4", "shortcut": "Ctrl+T", "priority": 3},
        {"label": "⌛ Expiry Monitor", "action": "expiry_monitor", "description": "Track expiry dates", "color": "#F44336", "shortcut": "Ctrl+X", "priority": 4},
    ],
}

ROLE_TIPS = {
    "admin": "💡 As Administrator, you have full access. Use System → Settings to switch SQLite / SQL Server.",
    "operator": "💡 As Warehouse Operator, you can create documents, manage stock, and perform QC releases.",
    "technical": "💡 As Technical Office, create material requests and view stock for planning.",
    "qc_inspector": "💡 As QC Inspector, focus on quarantine releases and preservation monitoring.",
    "viewer": "💡 As Viewer, you have read-only access to stock and reports.",
}

ROLE_DISPLAY = {
    "admin": "Administrator",
    "operator": "Warehouse Operator",
    "technical": "Technical Office",
    "qc_inspector": "QC Inspector",
    "viewer": "Viewer",
}

ROLE_ICONS = {
    "admin": "👑",
    "operator": "📦",
    "technical": "📐",
    "qc_inspector": "✅",
    "viewer": "👁️",
}

FEATURE_HIGHLIGHTS = [
    {"icon": "🗄️", "title": "SQLite or SQL Server", "description": "Offline single-user or multi-user network mode"},
    {"icon": "🧠", "title": "AI-Powered Forecasting", "description": "Ensemble forecasts and intermittent demand support"},
    {"icon": "📷", "title": "Barcode Scanning", "description": "Quick item lookup and transaction entry"},
    {"icon": "⏰", "title": "Expiry Monitoring", "description": "Never miss an expiry date again"},
    {"icon": "📊", "title": "ABC Analysis", "description": "Smart inventory classification"},
    {"icon": "🔗", "title": "Full Traceability", "description": "Track every material movement"},
]


class StartDialog(QDialog):
    action_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos: Optional[QPoint] = None
        self.setWindowTitle(f"Welcome to {APP_NAME}")
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self._init_ui()
        self.setFixedWidth(500)
        self.adjustSize()
        self.setMaximumHeight(700)
        self._center_on_screen()

    def _init_ui(self):
        self.card = QFrame(self)
        self.card.setObjectName("startCard")
        self.card.setStyleSheet("""
            #startCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F8FFFE);
                border-radius: 20px; border: 2px solid #B2DFDB;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.card.setGraphicsEffect(shadow)

        scroll = QScrollArea(self.card)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(10)

        content_layout.addLayout(self._build_title_bar())
        content_layout.addLayout(self._build_welcome_section())

        actions_group = QGroupBox("⚡ Quick Actions")
        actions_group.setStyleSheet(self._get_group_style("#004D40"))
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(6)
        role = self._get_user_role()
        role_actions = sorted(ROLE_ACTIONS.get(role, ROLE_ACTIONS["viewer"]), key=lambda x: x.get("priority", 99))
        for action_def in role_actions:
            actions_layout.addWidget(self._build_action_button(action_def))
        content_layout.addWidget(actions_group)

        features_group = QGroupBox("✨ Key Features")
        features_group.setStyleSheet(self._get_group_style("#00897B"))
        features_layout = QGridLayout(features_group)
        features_layout.setSpacing(8)
        for i, feature in enumerate(FEATURE_HIGHLIGHTS):
            features_layout.addWidget(self._build_feature_card(feature), i // 2, i % 2)
        content_layout.addWidget(features_group)

        tip_frame = QFrame()
        tip_frame.setStyleSheet("QFrame { background: #FFF8E1; border: 1px solid #FFE082; border-radius: 8px; padding: 10px; }")
        tip_layout = QHBoxLayout(tip_frame)
        tip_icon = QLabel("💡")
        tip_icon.setStyleSheet("font-size: 20px; border: none; background: transparent;")
        tip_layout.addWidget(tip_icon)
        tip_label = QLabel(ROLE_TIPS.get(role, ROLE_TIPS["viewer"]))
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet("color: #5D4037; font-size: 11px; border: none; background: transparent;")
        tip_layout.addWidget(tip_label, 1)
        content_layout.addWidget(tip_frame)
        content_layout.addLayout(self._build_footer())

        self.card.setLayout(QVBoxLayout())
        self.card.layout().setContentsMargins(0, 0, 0, 0)
        self.card.layout().addWidget(scroll)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.addWidget(self.card)

    def _build_title_bar(self) -> QHBoxLayout:
        title_bar = QHBoxLayout()
        title_bar.addWidget(LogoWidget())
        title_bar.addStretch()
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 30)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 16px; font-weight: bold; color: #78909C; border-radius: 15px; } QPushButton:hover { background: #FFCDD2; color: #D32F2F; }")
        btn_close.clicked.connect(self.reject)
        title_bar.addWidget(btn_close)
        return title_bar

    def _build_welcome_section(self) -> QHBoxLayout:
        welcome_layout = QHBoxLayout()
        role = self._get_user_role()
        icon_label = QLabel(ROLE_ICONS.get(role, "👤"))
        icon_label.setStyleSheet("font-size: 40px; border: none; background: transparent;")
        welcome_layout.addWidget(icon_label)
        text_layout = QVBoxLayout()
        welcome_text = QLabel("Welcome back!")
        welcome_text.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        welcome_text.setStyleSheet("color: #263238; border: none; background: transparent;")
        text_layout.addWidget(welcome_text)
        role_text = QLabel(f"{ROLE_ICONS.get(role, '👤')} {ROLE_DISPLAY.get(role, 'User')}")
        role_text.setFont(QFont("Segoe UI", 12))
        role_text.setStyleSheet("color: #004D40; border: none; background: transparent;")
        text_layout.addWidget(role_text)
        ver = QLabel(f"{APP_NAME} v{APP_VERSION}")
        ver.setStyleSheet("color: #90A4AE; font-size: 11px; border: none; background: transparent;")
        text_layout.addWidget(ver)
        welcome_layout.addLayout(text_layout)
        welcome_layout.addStretch()
        return welcome_layout

    def _build_action_button(self, action_def: dict) -> QPushButton:
        btn = QPushButton(f"{action_def['label']}  ({action_def.get('shortcut', '')})")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(action_def.get("description", ""))
        color = action_def.get("color", "#004D40")
        btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left; padding: 10px 14px; border-radius: 8px;
                border: 1px solid {color}33; background: {color}12; color: #263238; font-weight: 600;
            }}
            QPushButton:hover {{ background: {color}28; border-color: {color}; }}
        """)
        action = action_def["action"]
        btn.clicked.connect(lambda checked=False, a=action: self._emit_action(a))
        return btn

    def _build_feature_card(self, feature: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet("QFrame { background: #FAFAFA; border: 1px solid #E0E0E0; border-radius: 8px; padding: 8px; }")
        layout = QVBoxLayout(card)
        layout.setSpacing(2)
        title = QLabel(f"{feature['icon']} {feature['title']}")
        title.setStyleSheet("font-weight: 700; color: #004D40; border: none; background: transparent;")
        desc = QLabel(feature["description"])
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #78909C; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(title)
        layout.addWidget(desc)
        return card

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        support = QLabel(f'<a href="https://wa.me/{WHATSAPP_NUMBER.lstrip("+")}" style="color:#004D40;">WhatsApp Support</a> · <a href="{WEBSITE_URL}" style="color:#004D40;">www.imat.io</a>')
        support.setOpenExternalLinks(True)
        support.setStyleSheet("font-size: 11px;")
        footer.addWidget(support)
        footer.addStretch()
        return footer

    def _get_group_style(self, color: str) -> str:
        return f"QGroupBox {{ font-weight: 700; color: {color}; border: 1px solid #E0E0E0; border-radius: 10px; margin-top: 10px; padding-top: 12px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; }}"

    def _get_user_role(self) -> str:
        parent = self.parent()
        if parent is not None and hasattr(parent, "user_role"):
            return (parent.user_role or "viewer").lower()
        return "viewer"

    def _emit_action(self, action: str):
        self.action_selected.emit(action)
        self.accept()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.center() - self.rect().center())

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
