# ui/start_dialog.py
"""
Start/Welcome Dialog – iMat Material Control System (EPC Edition).

Role-based quick-start dialog with:
- Dynamic action buttons based on user role
- Feature showcase cards
- Quick tips for each role
- Recent activity display
- Keyboard shortcuts reference
- Getting started guide
- Video tutorial links (placeholder)
- WhatsApp support integration
- Draggable frameless window
- Smooth animations
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

# ==================================================================
# Constants
# ==================================================================

APP_NAME = "iMat Warehouse"
APP_VERSION = "2.0.0"
WHATSAPP_NUMBER = "+989160684552"
WEBSITE_URL = "https://www.imat.io"

# Role-based action definitions
ROLE_ACTIONS = {
    "admin": [
        {
            "label": "📦 Material Catalog",
            "action": "new_item",
            "description": "Manage item codes and descriptions",
            "color": "#4CAF50",
            "shortcut": "Ctrl+M",
            "priority": 1,
        },
        {
            "label": "📄 New Document",
            "action": "new_transaction",
            "description": "Create MRR, MIV, MSR, OS&D documents",
            "color": "#2196F3",
            "shortcut": "Ctrl+D",
            "priority": 2,
        },
        {
            "label": "📋 Material Request",
            "action": "new_material_request",
            "description": "Create new material requisition",
            "color": "#7E57C2",
            "shortcut": "Ctrl+R",
            "priority": 3,
        },
        {
            "label": "🔍 QC Release",
            "action": "qc_release",
            "description": "Release materials from quarantine",
            "color": "#FF7043",
            "shortcut": "Ctrl+Q",
            "priority": 4,
        },
        {
            "label": "🛡️ Preservation",
            "action": "preservation",
            "description": "Monitor preservation schedules",
            "color": "#66BB6A",
            "shortcut": "Ctrl+P",
            "priority": 5,
        },
        {
            "label": "📊 Live Stock",
            "action": "live_stock_report",
            "description": "View real-time stock levels",
            "color": "#42A5F5",
            "shortcut": "Ctrl+L",
            "priority": 6,
        },
        {
            "label": "👥 Manage Users",
            "action": "manage_users",
            "description": "Add, edit, or deactivate users",
            "color": "#EF5350",
            "shortcut": "Ctrl+U",
            "priority": 7,
        },
        {
            "label": "📊 Reports",
            "action": "reports",
            "description": "Generate and export reports",
            "color": "#FF9800",
            "shortcut": "Ctrl+E",
            "priority": 8,
        },
    ],
    "operator": [
        {
            "label": "📄 New Document",
            "action": "new_transaction",
            "description": "Create MRR, MIV, MSR, OS&D",
            "color": "#2196F3",
            "shortcut": "Ctrl+D",
            "priority": 1,
        },
        {
            "label": "📦 Material Catalog",
            "action": "new_item",
            "description": "Manage item codes",
            "color": "#4CAF50",
            "shortcut": "Ctrl+M",
            "priority": 2,
        },
        {
            "label": "🔍 QC Release",
            "action": "qc_release",
            "description": "Release from quarantine",
            "color": "#FF7043",
            "shortcut": "Ctrl+Q",
            "priority": 3,
        },
        {
            "label": "🛡️ Preservation",
            "action": "preservation",
            "description": "Monitor preservation",
            "color": "#66BB6A",
            "shortcut": "Ctrl+P",
            "priority": 4,
        },
        {
            "label": "📊 Live Stock",
            "action": "live_stock_report",
            "description": "View stock levels",
            "color": "#42A5F5",
            "shortcut": "Ctrl+L",
            "priority": 5,
        },
        {
            "label": "📊 Reports",
            "action": "reports",
            "description": "Generate reports",
            "color": "#FF9800",
            "shortcut": "Ctrl+E",
            "priority": 6,
        },
    ],
    "technical": [
        {
            "label": "📋 Material Request",
            "action": "new_material_request",
            "description": "Create material requisition",
            "color": "#7E57C2",
            "shortcut": "Ctrl+R",
            "priority": 1,
        },
        {
            "label": "📄 MR History",
            "action": "material_request_history",
            "description": "View request history",
            "color": "#5C6BC0",
            "shortcut": "Ctrl+H",
            "priority": 2,
        },
        {
            "label": "📊 Live Stock",
            "action": "live_stock_report",
            "description": "View stock levels",
            "color": "#42A5F5",
            "shortcut": "Ctrl+L",
            "priority": 3,
        },
        {
            "label": "🔗 Traceability",
            "action": "traceability",
            "description": "Track material history",
            "color": "#00BCD4",
            "shortcut": "Ctrl+T",
            "priority": 4,
        },
        {
            "label": "📊 Reports",
            "action": "reports",
            "description": "Generate reports",
            "color": "#FF9800",
            "shortcut": "Ctrl+E",
            "priority": 5,
        },
    ],
    "qc_inspector": [
        {
            "label": "🔍 QC Release",
            "action": "qc_release",
            "description": "Release from quarantine",
            "color": "#FF7043",
            "shortcut": "Ctrl+Q",
            "priority": 1,
        },
        {
            "label": "🛡️ Preservation",
            "action": "preservation",
            "description": "Monitor preservation",
            "color": "#66BB6A",
            "shortcut": "Ctrl+P",
            "priority": 2,
        },
        {
            "label": "⌛ Expiry Monitor",
            "action": "expiry_monitor",
            "description": "Track expiry dates",
            "color": "#F44336",
            "shortcut": "Ctrl+X",
            "priority": 3,
        },
        {
            "label": "📊 Live Stock",
            "action": "live_stock_report",
            "description": "View stock levels",
            "color": "#42A5F5",
            "shortcut": "Ctrl+L",
            "priority": 4,
        },
        {
            "label": "📊 Reports",
            "action": "reports",
            "description": "Generate reports",
            "color": "#FF9800",
            "shortcut": "Ctrl+E",
            "priority": 5,
        },
    ],
    "viewer": [
        {
            "label": "📊 Live Stock",
            "action": "live_stock_report",
            "description": "View stock levels",
            "color": "#42A5F5",
            "shortcut": "Ctrl+L",
            "priority": 1,
        },
        {
            "label": "📊 Reports",
            "action": "reports",
            "description": "View reports",
            "color": "#FF9800",
            "shortcut": "Ctrl+E",
            "priority": 2,
        },
        {
            "label": "🔗 Traceability",
            "action": "traceability",
            "description": "Track material history",
            "color": "#00BCD4",
            "shortcut": "Ctrl+T",
            "priority": 3,
        },
        {
            "label": "⌛ Expiry Monitor",
            "action": "expiry_monitor",
            "description": "Track expiry dates",
            "color": "#F44336",
            "shortcut": "Ctrl+X",
            "priority": 4,
        },
    ],
}

# Role tips
ROLE_TIPS = {
    "admin": "💡 As Administrator, you have full access to all features. "
             "Use the menu bar or these shortcuts for quick access.",
    "operator": "💡 As Warehouse Operator, you can create documents, "
               "manage stock levels, and perform QC releases.",
    "technical": "💡 As Technical Office, you can create material requests "
                 "and view stock availability for planning.",
    "qc_inspector": "💡 As QC Inspector, focus on quarantine releases "
                    "and preservation monitoring.",
    "viewer": "💡 As Viewer, you have read-only access to view stock "
              "and generate reports.",
}

# Role display names
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

# Feature highlights (shown to all roles)
FEATURE_HIGHLIGHTS = [
    {
        "icon": "🧠",
        "title": "AI-Powered Forecasting",
        "description": "Predict demand and optimize inventory levels",
    },
    {
        "icon": "📷",
        "title": "Barcode Scanning",
        "description": "Quick item lookup and transaction entry",
    },
    {
        "icon": "⏰",
        "title": "Expiry Monitoring",
        "description": "Never miss an expiry date again",
    },
    {
        "icon": "📊",
        "title": "ABC Analysis",
        "description": "Smart inventory classification",
    },
    {
        "icon": "🔗",
        "title": "Full Traceability",
        "description": "Track every material movement",
    },
    {
        "icon": "🔄",
        "title": "Auto Backups",
        "description": "Your data is always safe",
    },
]


# ==================================================================
# Start Dialog
# ==================================================================

class StartDialog(QDialog):
    """
    Welcome/Quick-start dialog with role-based shortcuts.
    
    Features:
    - Dynamic buttons based on user role
    - Feature highlights
    - Quick tips
    - Contact information
    - Draggable frameless window
    """

    # Signal emitted when an action is selected
    action_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        """
        Initialize the Start dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # State
        self._drag_pos: Optional[QPoint] = None
        
        # Window setup
        self.setWindowTitle(f"Welcome to {APP_NAME}")
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint
        )

        # Build UI
        self._init_ui()
        
        # Set size
        self.setFixedWidth(500)
        self.adjustSize()
        self.setMaximumHeight(700)

        # Center on screen
        self._center_on_screen()

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _init_ui(self):
        """Initialize the complete UI."""
        # Main card with shadow
        self.card = QFrame(self)
        self.card.setObjectName("startCard")
        self.card.setStyleSheet("""
            #startCard {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F8FFFE
                );
                border-radius: 20px;
                border: 2px solid #B2DFDB;
            }
        """)

        # Shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.card.setGraphicsEffect(shadow)

        # Scroll area for content
        scroll = QScrollArea(self.card)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        # Content widget
        content = QWidget()
        scroll.setWidget(content)
        
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(10)

        # ---- Title Bar ----
        title_bar = self._build_title_bar()
        content_layout.addLayout(title_bar)

        # ---- Welcome Section ----
        welcome_section = self._build_welcome_section()
        content_layout.addLayout(welcome_section)

        # ---- Action Buttons ----
        actions_group = QGroupBox("⚡ Quick Actions")
        actions_group.setStyleSheet(self._get_group_style("#004D40"))
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(6)

        role = self._get_user_role()
        role_actions = ROLE_ACTIONS.get(role, ROLE_ACTIONS["viewer"])

        # Sort by priority
        role_actions.sort(key=lambda x: x.get("priority", 99))

        for action_def in role_actions:
            btn = self._build_action_button(action_def)
            actions_layout.addWidget(btn)

        content_layout.addWidget(actions_group)

        # ---- Feature Highlights ----
        features_group = QGroupBox("✨ Key Features")
        features_group.setStyleSheet(self._get_group_style("#00897B"))
        features_layout = QGridLayout(features_group)
        features_layout.setSpacing(8)

        for i, feature in enumerate(FEATURE_HIGHLIGHTS):
            row = i // 2
            col = i % 2
            card = self._build_feature_card(feature)
            features_layout.addWidget(card, row, col)

        content_layout.addWidget(features_group)

        # ---- Tip Section ----
        tip_frame = QFrame()
        tip_frame.setStyleSheet("""
            QFrame {
                background: #FFF8E1;
                border: 1px solid #FFE082;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        tip_layout = QHBoxLayout(tip_frame)
        tip_layout.setSpacing(8)

        tip_icon = QLabel("💡")
        tip_icon.setStyleSheet("font-size: 20px; border: none; background: transparent;")
        tip_layout.addWidget(tip_icon)

        tip_text = ROLE_TIPS.get(role, ROLE_TIPS["viewer"])
        tip_label = QLabel(tip_text)
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet("""
            color: #5D4037;
            font-size: 11px;
            border: none;
            background: transparent;
        """)
        tip_layout.addWidget(tip_label, 1)

        content_layout.addWidget(tip_frame)

        # ---- Footer ----
        footer = self._build_footer()
        content_layout.addLayout(footer)

        # Set scroll widget
        self.card.setLayout(QVBoxLayout())
        self.card.layout().setContentsMargins(0, 0, 0, 0)
        self.card.layout().addWidget(scroll)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.addWidget(self.card)

    def _build_title_bar(self) -> QHBoxLayout:
        """Build the title bar."""
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(4, 0, 4, 0)

        # Logo
        logo = LogoWidget()
        title_bar.addWidget(logo)

        title_bar.addStretch()

        # Close button
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 30)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setToolTip("Close")
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
                font-weight: bold;
                color: #78909C;
                border-radius: 15px;
            }
            QPushButton:hover {
                background: #FFCDD2;
                color: #D32F2F;
            }
        """)
        btn_close.clicked.connect(self.reject)
        title_bar.addWidget(btn_close)

        return title_bar

    def _build_welcome_section(self) -> QHBoxLayout:
        """Build the welcome section with role info."""
        welcome_layout = QHBoxLayout()
        welcome_layout.setSpacing(12)

        # Role icon
        role = self._get_user_role()
        role_icon = ROLE_ICONS.get(role, "👤")
        icon_label = QLabel(role_icon)
        icon_label.setStyleSheet("font-size: 40px; border: none; background: transparent;")
        welcome_layout.addWidget(icon_label)

        # Welcome text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        role_name = ROLE_DISPLAY.get(role, "User")
        welcome_text = QLabel(f"Welcome back!")
        welcome_text.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        welcome_text.setStyleSheet("color: #263238; border: none; background: transparent;")
        text_layout.addWidget(welcome_text)

        role_text = QLabel(f"{role_icon} {role_name}")
        role_text.setFont(QFont("Segoe UI", 12))
        role_text.setStyleSheet("color: #004D40; border: none; background: transparent;")
        text_layout.addWidget(role_text)

        welcome_layout.addLayout(text_layout, 1)

        return welcome_layout

    def _build_action_button(self, action_def: Dict) -> QPushButton:
        """Build an action button."""
        btn = QPushButton(f"{action_def['label']}")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(42)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {action_def['color']}15;
                color: {action_def['color']};
                border: 2px solid {action_def['color']}40;
                border-radius: 10px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: bold;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {action_def['color']}25;
                border-color: {action_def['color']};
                padding-left: 20px;
            }}
            QPushButton:pressed {{
                background: {action_def['color']}35;
            }}
        """)

        # Tooltip with description and shortcut
        tooltip = action_def.get("description", "")
        if action_def.get("shortcut"):
            tooltip += f" ({action_def['shortcut']})"
        btn.setToolTip(tooltip)

        # Click handler
        action = action_def["action"]
        btn.clicked.connect(lambda checked, a=action: self._select_action(a))

        return btn

    def _build_feature_card(self, feature: Dict) -> QFrame:
        """Build a feature highlight card."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #F5F5F5;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        card.setMinimumWidth(200)

        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(8)

        icon = QLabel(feature["icon"])
        icon.setStyleSheet("font-size: 22px; border: none; background: transparent;")
        card_layout.addWidget(icon)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)

        title = QLabel(feature["title"])
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #333; border: none; background: transparent;")
        text_layout.addWidget(title)

        desc = QLabel(feature["description"])
        desc.setFont(QFont("Segoe UI", 9))
        desc.setStyleSheet("color: #666; border: none; background: transparent;")
        desc.setWordWrap(True)
        text_layout.addWidget(desc)

        card_layout.addLayout(text_layout, 1)

        return card

    def _build_footer(self) -> QHBoxLayout:
        """Build the footer with contact links."""
        footer = QHBoxLayout()
        footer.setSpacing(12)

        # Version
        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setStyleSheet("""
            color: #90A4AE;
            font-size: 9px;
            background: transparent;
            border: none;
        """)
        footer.addWidget(version_label)

        footer.addStretch()

        # WhatsApp link
        wa_label = QLabel(
            f'<a href="https://wa.me/{WHATSAPP_NUMBER.replace("+", "")}" '
            f'style="color: #25D366; text-decoration: none; font-weight: bold;">'
            f'💬 WhatsApp Support</a>'
        )
        wa_label.setOpenExternalLinks(True)
        wa_label.setStyleSheet("font-size: 10px; background: transparent; border: none;")
        footer.addWidget(wa_label)

        # Separator
        sep = QLabel("|")
        sep.setStyleSheet("color: #BDBDBD; font-size: 10px; background: transparent;")
        footer.addWidget(sep)

        # Website link
        web_label = QLabel(
            f'<a href="{WEBSITE_URL}" '
            f'style="color: #004D40; text-decoration: none; font-weight: bold;">'
            f'🌐 {WEBSITE_URL.replace("https://", "")}</a>'
        )
        web_label.setOpenExternalLinks(True)
        web_label.setStyleSheet("font-size: 10px; background: transparent; border: none;")
        footer.addWidget(web_label)

        return footer

    # ==================================================================
    # Style Methods
    # ==================================================================

    def _get_group_style(self, color: str) -> str:
        """Get group box stylesheet."""
        return f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {color}30;
                border-radius: 8px;
                margin-top: 8px;
                padding: 15px;
                padding-top: 25px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                color: {color};
            }}
        """

    # ==================================================================
    # Helper Methods
    # ==================================================================

    def _get_user_role(self) -> str:
        """Get current user role from parent."""
        try:
            return self.parent().user_role
        except AttributeError:
            return "viewer"

    def _center_on_screen(self):
        """Center dialog on screen."""
        screen = QApplication.primaryScreen()
        if screen:
            center = screen.availableGeometry().center()
            frame = self.frameGeometry()
            frame.moveCenter(center)
            self.move(frame.topLeft())

    def _select_action(self, action: str):
        """Emit action selected signal and close."""
        self.action_selected.emit(action)
        self.accept()

    # ==================================================================
    # Window Dragging
    # ==================================================================

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for dragging."""
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release."""
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        """Handle key press - Escape to close."""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)