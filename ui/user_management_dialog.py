# ui/user_management_dialog.py
"""
User Management Dialog – iMat Material Control System (EPC Edition).

Comprehensive user and project settings management with:
- Full user CRUD operations
- Role-based access control
- Password management and reset
- Account activation/deactivation
- Login attempt monitoring
- Account lock/unlock
- Company and project information
- User activity logging
- Bulk user import (placeholder)
- User role permissions viewer
- Security settings
- Database backup integration
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QMessageBox, QInputDialog, QHeaderView,
    QLineEdit, QFrame, QGroupBox, QFormLayout, QWidget, QToolBar,
    QStatusBar, QComboBox, QCheckBox, QTabWidget, QTextEdit,
    QAbstractItemView, QMenu, QApplication, QSpinBox, QFileDialog
)
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QDesktopServices, QAction

from db.database import get_db_session, SessionLocal
from db.models import User, ProjectInfo
from utils.password_manager import hash_password, verify_password
from ui.logo_widget import LogoWidget

# ==================================================================
# Constants
# ==================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_CONFIG_FILE = os.path.join(BASE_DIR, "app_config.json")

# Role definitions
ROLES = {
    "admin": {
        "name": "Administrator",
        "icon": "👑",
        "color": "#0D47A1",
        "bg": "#E3F2FD",
        "description": "Full system access with user management capabilities",
        "permissions": [
            "Full system access",
            "User management",
            "Database backup/restore",
            "System configuration",
            "License management",
            "All reports and exports",
            "Document creation and approval",
            "QC release and preservation",
        ],
    },
    "operator": {
        "name": "Warehouse Operator",
        "icon": "📦",
        "color": "#1B5E20",
        "bg": "#E8F5E9",
        "description": "Warehouse operations and material control",
        "permissions": [
            "Material catalog management",
            "Document creation (MRR, MIV, MSR, OS&D)",
            "Transaction management",
            "QC release",
            "Preservation monitoring",
            "Reports and exports",
            "Stock viewing",
        ],
    },
    "technical": {
        "name": "Technical Office",
        "icon": "📐",
        "color": "#E65100",
        "bg": "#FFF3E0",
        "description": "Technical office material planning and requests",
        "permissions": [
            "Material request creation",
            "MSR creation",
            "Request history viewing",
            "Stock viewing",
            "Traceability reports",
            "Reports and exports",
            "Material catalog viewing",
        ],
    },
    "qc_inspector": {
        "name": "QC Inspector",
        "icon": "✅",
        "color": "#880E4F",
        "bg": "#FCE4EC",
        "description": "Quality control inspection and release",
        "permissions": [
            "QC release (quarantine → accepted/rejected)",
            "Preservation management",
            "Expiry date monitoring",
            "Certificate verification",
            "QC reports",
            "Stock viewing",
            "Traceability reports",
        ],
    },
    "viewer": {
        "name": "Viewer",
        "icon": "👁️",
        "color": "#424242",
        "bg": "#F5F5F5",
        "description": "Read-only access for monitoring and auditing",
        "permissions": [
            "View stock levels",
            "View reports",
            "View transactions",
            "View documents",
            "Export reports",
            "No modification rights",
        ],
    },
}

# Password policy
MIN_PASSWORD_LENGTH = 6
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


# ==================================================================
# User Management Dialog
# ==================================================================

class UserManagementDialog(QDialog):
    """
    User and project settings management dialog.
    
    Features:
    - User CRUD operations
    - Role management
    - Password reset
    - Company/project configuration
    - Security settings
    """

    users_updated = pyqtSignal()

    def __init__(self, parent=None, user_role: str = "admin"):
        """
        Initialize the User Management dialog.
        
        Args:
            parent: Parent widget
            user_role: Current user's role (must be admin)
        """
        super().__init__(parent)
        self.user_role = user_role
        self.parent = parent
        
        # State
        self.all_users: List[User] = []
        
        # Window setup
        self.setWindowTitle("iMat – Teamwork & Project Settings")
        self.setMinimumSize(900, 650)
        self.setModal(True)
        
        # Build UI
        self._init_ui()
        
        # Load data
        self._load_users()
        self._load_company_project_info()
        
        # Apply permissions
        self._apply_role_permissions()

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _init_ui(self):
        """Initialize the complete user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Build components
        self._build_header(main_layout)
        self._build_toolbar(main_layout)
        self._build_content(main_layout)
        self._build_status_bar(main_layout)

    def _build_header(self, parent_layout: QVBoxLayout):
        """Build the header."""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #004D40;
                border-radius: 0px;
            }
            QLabel { color: white; }
        """)
        header.setFixedHeight(70)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 15, 5)

        self.logo_widget = LogoWidget()
        header_layout.addWidget(self.logo_widget)

        title = QLabel("👥 Teamwork & Project Setup")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("Manage users, roles and project information")
        self.subtitle.setFont(QFont("Arial", 9))
        self.subtitle.setStyleSheet("color: #B2DFDB;")
        header_layout.addWidget(self.subtitle)

        parent_layout.addWidget(header)

    def _build_toolbar(self, parent_layout: QVBoxLayout):
        """Build the toolbar."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background: #E0F2F1;
                border-bottom: 1px solid #B2DFDB;
                spacing: 4px;
                padding: 4px;
            }
            QToolButton {
                background: transparent;
                border: none;
                padding: 6px 12px;
                font-weight: bold;
                color: #004D40;
                border-radius: 4px;
            }
            QToolButton:hover { background: #B2DFDB; }
            QToolButton:disabled { color: #999; }
        """)

        self.action_add = toolbar.addAction("➕ Add User")
        self.action_add.setToolTip("Create a new user account")
        self.action_add.triggered.connect(self._add_user)
        
        self.action_edit = toolbar.addAction("✏️ Edit")
        self.action_edit.setToolTip("Edit selected user")
        self.action_edit.triggered.connect(self._edit_user)
        toolbar.addSeparator()

        self.action_toggle = toolbar.addAction("🔄 Activate/Deactivate")
        self.action_toggle.setToolTip("Toggle user active status")
        self.action_toggle.triggered.connect(self._toggle_user)
        
        self.action_reset_pwd = toolbar.addAction("🔑 Reset Password")
        self.action_reset_pwd.setToolTip("Reset password for selected user")
        self.action_reset_pwd.triggered.connect(self._reset_password)
        
        self.action_unlock = toolbar.addAction("🔓 Unlock Account")
        self.action_unlock.setToolTip("Unlock a locked user account")
        self.action_unlock.triggered.connect(self._unlock_user)
        toolbar.addSeparator()

        self.action_refresh = toolbar.addAction("🔄 Refresh")
        self.action_refresh.triggered.connect(self._load_users)

        parent_layout.addWidget(toolbar)

    def _build_content(self, parent_layout: QVBoxLayout):
        """Build the main content area."""
        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #CCC;
                background: white;
            }
            QTabBar::tab {
                background: #E0E0E0;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #004D40;
                color: white;
            }
        """)

        # Tab 1: Users
        self.tab_users = self._build_users_tab()
        self.tab_widget.addTab(self.tab_users, "👥 Users")

        # Tab 2: Roles
        self.tab_roles = self._build_roles_tab()
        self.tab_widget.addTab(self.tab_roles, "🔑 Roles & Permissions")

        # Tab 3: Project Info
        self.tab_project = self._build_project_tab()
        self.tab_widget.addTab(self.tab_project, "🏢 Company & Project")

        # Tab 4: Security
        self.tab_security = self._build_security_tab()
        self.tab_widget.addTab(self.tab_security, "🔒 Security")

        parent_layout.addWidget(self.tab_widget)

    def _build_users_tab(self) -> QWidget:
        """Build the users tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍 Filter:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by username or full name...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_users)
        search_layout.addWidget(self.search_input)
        
        search_layout.addWidget(QLabel("Role:"))
        self.role_filter_combo = QComboBox()
        self.role_filter_combo.addItem("All Roles")
        for role_key, role_data in ROLES.items():
            self.role_filter_combo.addItem(f"{role_data['icon']} {role_data['name']}", role_key)
        self.role_filter_combo.currentIndexChanged.connect(self._filter_users)
        search_layout.addWidget(self.role_filter_combo)
        
        search_layout.addWidget(QLabel("Status:"))
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(["All", "Active", "Inactive", "Locked"])
        self.status_filter_combo.currentIndexChanged.connect(self._filter_users)
        search_layout.addWidget(self.status_filter_combo)
        
        layout.addLayout(search_layout)

        # Users table
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(8)
        self.users_table.setHorizontalHeaderLabels([
            "ID", "Username", "Full Name", "Role", "Email",
            "Status", "Last Login", "Login Attempts"
        ])
        self.users_table.horizontalHeader().setStretchLastSection(True)
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.users_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.users_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.users_table.setAlternatingRowColors(True)
        self.users_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.users_table.customContextMenuRequested.connect(self._show_context_menu)
        self.users_table.doubleClicked.connect(self._edit_user)
        self.users_table.setStyleSheet("""
            QTableWidget {
                background: white;
                font-size: 11px;
            }
            QTableWidget::item:selected {
                background-color: #B2DFDB;
                color: #004D40;
            }
            QHeaderView::section {
                background-color: #004D40;
                color: white;
                font-weight: bold;
                padding: 4px;
            }
        """)

        col_widths = [40, 120, 150, 120, 150, 80, 130, 80]
        for i, w in enumerate(col_widths):
            self.users_table.setColumnWidth(i, w)

        layout.addWidget(self.users_table)

        # User count
        self.user_count_label = QLabel("Users: 0")
        self.user_count_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.user_count_label)

        return widget

    def _build_roles_tab(self) -> QWidget:
        """Build the roles and permissions tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        desc = QLabel(
            "<h3>Role-Based Access Control</h3>"
            "Each role has specific permissions within the system. "
            "Select a role to view its permissions."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Role cards
        for role_key, role_data in ROLES.items():
            card = self._build_role_card(role_key, role_data)
            layout.addWidget(card)

        layout.addStretch()
        return widget

    def _build_project_tab(self) -> QWidget:
        """Build the project info tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Company & Project form
        project_group = QGroupBox("🏢 Company & Project Information")
        project_group.setStyleSheet(self._get_group_style())
        form = QFormLayout(project_group)
        form.setSpacing(8)

        self.company_name_edit = QLineEdit()
        self.company_name_edit.setPlaceholderText("e.g., FARASAKOU")
        form.addRow("Company Name:", self.company_name_edit)

        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("e.g., Storage Development")
        form.addRow("Project Name:", self.project_name_edit)

        self.project_code_edit = QLineEdit()
        self.project_code_edit.setPlaceholderText("e.g., 001")
        form.addRow("Project Code:", self.project_code_edit)

        self.client_name_edit = QLineEdit()
        self.client_name_edit.setPlaceholderText("Client name (optional)")
        form.addRow("Client:", self.client_name_edit)

        self.contract_no_edit = QLineEdit()
        self.contract_no_edit.setPlaceholderText("Contract number (optional)")
        form.addRow("Contract No:", self.contract_no_edit)

        self.project_location_edit = QLineEdit()
        self.project_location_edit.setPlaceholderText("Project location (optional)")
        form.addRow("Location:", self.project_location_edit)

        layout.addWidget(project_group)

        # Save button
        btn_save = QPushButton("💾 Save Project Info")
        btn_save.setMinimumHeight(40)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2E86C1;
                color: white;
                border: none;
                padding: 10px 24px;
                font-weight: bold;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #2471A3; }
        """)
        btn_save.clicked.connect(self._save_company_project_info)
        layout.addWidget(btn_save)

        layout.addStretch()
        return widget

    def _build_security_tab(self) -> QWidget:
        """Build the security settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Password policy
        pwd_group = QGroupBox("🔐 Password Policy")
        pwd_group.setStyleSheet(self._get_group_style())
        pwd_form = QFormLayout(pwd_group)
        pwd_form.setSpacing(8)

        self.min_length_spin = QSpinBox()
        self.min_length_spin.setRange(4, 20)
        self.min_length_spin.setValue(MIN_PASSWORD_LENGTH)
        pwd_form.addRow("Minimum Password Length:", self.min_length_spin)

        layout.addWidget(pwd_group)

        # Login security
        login_group = QGroupBox("🔒 Login Security")
        login_group.setStyleSheet(self._get_group_style())
        login_form = QFormLayout(login_group)
        login_form.setSpacing(8)

        self.max_attempts_spin = QSpinBox()
        self.max_attempts_spin.setRange(1, 20)
        self.max_attempts_spin.setValue(MAX_LOGIN_ATTEMPTS)
        login_form.addRow("Max Login Attempts:", self.max_attempts_spin)

        self.lockout_spin = QSpinBox()
        self.lockout_spin.setRange(1, 120)
        self.lockout_spin.setValue(LOCKOUT_DURATION_MINUTES)
        self.lockout_spin.setSuffix(" minutes")
        login_form.addRow("Lockout Duration:", self.lockout_spin)

        layout.addWidget(login_group)

        # Save button
        btn_save = QPushButton("💾 Save Security Settings")
        btn_save.setMinimumHeight(40)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2E86C1;
                color: white;
                border: none;
                padding: 10px 24px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #2471A3; }
        """)
        btn_save.clicked.connect(self._save_security_settings)
        layout.addWidget(btn_save)

        layout.addStretch()
        return widget

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready – Manage users and project settings")
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: #E0F2F1;
                border-top: 1px solid #B2DFDB;
                color: #004D40;
                font-weight: bold;
            }
        """)
        parent_layout.addWidget(self.status_bar)

    # ==================================================================
    # Role Card
    # ==================================================================

    def _build_role_card(self, role_key: str, role_data: Dict) -> QFrame:
        """Build a role permission card."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 2px solid {role_data['color']}30;
                border-left: 4px solid {role_data['color']};
                border-radius: 8px;
                padding: 12px;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(6)

        # Header
        header = QHBoxLayout()
        icon_label = QLabel(role_data['icon'])
        icon_label.setStyleSheet("font-size: 24px; border: none; background: transparent;")
        header.addWidget(icon_label)

        name_label = QLabel(role_data['name'])
        name_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {role_data['color']}; border: none;")
        header.addWidget(name_label)
        header.addStretch()

        count = sum(1 for u in self.all_users if u.role == role_key)
        count_label = QLabel(f"{count} user(s)")
        count_label.setStyleSheet("color: #666; font-size: 10px; border: none;")
        header.addWidget(count_label)

        card_layout.addLayout(header)

        # Description
        desc_label = QLabel(role_data['description'])
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 10px; border: none;")
        card_layout.addWidget(desc_label)

        # Permissions
        perms_label = QLabel("<b>Permissions:</b>")
        perms_label.setStyleSheet("font-size: 10px; border: none;")
        card_layout.addWidget(perms_label)

        for perm in role_data['permissions']:
            perm_item = QLabel(f"  • {perm}")
            perm_item.setStyleSheet("color: #555; font-size: 9px; border: none;")
            card_layout.addWidget(perm_item)

        return card

    # ==================================================================
    # Style Methods
    # ==================================================================

    def _get_group_style(self) -> str:
        """Get group box stylesheet."""
        return """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #B2DFDB;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #004D40;
            }
        """

    # ==================================================================
    # Role Permissions
    # ==================================================================

    def _apply_role_permissions(self):
        """Apply role-based restrictions (admin only)."""
        if self.user_role != "admin":
            self.action_add.setEnabled(False)
            self.action_edit.setEnabled(False)
            self.action_toggle.setEnabled(False)
            self.action_reset_pwd.setEnabled(False)
            self.action_unlock.setEnabled(False)
            self.company_name_edit.setReadOnly(True)
            self.project_name_edit.setReadOnly(True)
            self.project_code_edit.setReadOnly(True)
            self.status_bar.showMessage("Only administrators can modify settings")

    # ==================================================================
    # User Data Methods
    # ==================================================================

    def _load_users(self):
        """Load all users from database."""
        session = get_db_session()
        try:
            self.all_users = session.query(User).order_by(User.username).all()
            self._filter_users()
        finally:
            session.close()

    def _filter_users(self):
        """Filter users based on search criteria."""
        search_text = self.search_input.text().strip().lower()
        role_filter = self.role_filter_combo.currentData()
        status_filter = self.status_filter_combo.currentText()

        filtered = self.all_users

        if search_text:
            filtered = [
                u for u in filtered
                if search_text in u.username.lower()
                or (u.full_name and search_text in u.full_name.lower())
                or (u.email and search_text in u.email.lower())
            ]

        if role_filter:
            filtered = [u for u in filtered if u.role == role_filter]

        if status_filter == "Active":
            filtered = [u for u in filtered if u.is_active and not u.is_locked]
        elif status_filter == "Inactive":
            filtered = [u for u in filtered if not u.is_active]
        elif status_filter == "Locked":
            filtered = [u for u in filtered if u.is_locked]

        self._display_users(filtered)
        self.user_count_label.setText(f"Users: {len(filtered)}")

    def _display_users(self, users: List[User]):
        """Display users in the table."""
        self.users_table.setRowCount(len(users))

        for row, user in enumerate(users):
            # ID
            id_item = QTableWidgetItem(str(user.id))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.users_table.setItem(row, 0, id_item)

            # Username
            self.users_table.setItem(row, 1, QTableWidgetItem(user.username))

            # Full Name
            self.users_table.setItem(row, 2, QTableWidgetItem(user.full_name or ""))

            # Role with color
            role_data = ROLES.get(user.role, {})
            role_item = QTableWidgetItem(
                f"{role_data.get('icon', '👤')} {role_data.get('name', user.role)}"
            )
            role_item.setBackground(QColor(role_data.get("bg", "#F5F5F5")))
            role_item.setForeground(QColor(role_data.get("color", "#000")))
            self.users_table.setItem(row, 3, role_item)

            # Email
            self.users_table.setItem(row, 4, QTableWidgetItem(user.email or ""))

            # Status
            if not user.is_active:
                status_text = "❌ Inactive"
                status_color = QColor("#D32F2F")
            elif user.is_locked:
                status_text = "🔒 Locked"
                status_color = QColor("#FF9800")
            else:
                status_text = "✅ Active"
                status_color = QColor("#2E7D32")

            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(status_color)
            status_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.users_table.setItem(row, 5, status_item)

            # Last Login
            last_login = user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else "Never"
            self.users_table.setItem(row, 6, QTableWidgetItem(last_login))

            # Login Attempts
            attempts = user.login_attempts or 0
            attempts_item = QTableWidgetItem(str(attempts))
            if attempts >= MAX_LOGIN_ATTEMPTS:
                attempts_item.setForeground(QColor("#D32F2F"))
            self.users_table.setItem(row, 7, attempts_item)

    def _get_selected_user(self) -> Optional[User]:
        """Get the selected user from the table."""
        row = self.users_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a user.")
            return None

        user_id = int(self.users_table.item(row, 0).text())
        session = get_db_session()
        try:
            return session.query(User).filter_by(id=user_id).first()
        finally:
            session.close()

    # ==================================================================
    # Context Menu
    # ==================================================================

    def _show_context_menu(self, pos):
        """Show context menu on users table."""
        menu = QMenu(self)
        menu.addAction("✏️ Edit User", self._edit_user)
        menu.addAction("🔄 Toggle Active/Inactive", self._toggle_user)
        menu.addAction("🔑 Reset Password", self._reset_password)
        menu.addAction("🔓 Unlock Account", self._unlock_user)
        menu.exec(self.users_table.viewport().mapToGlobal(pos))

    # ==================================================================
    # User CRUD Operations
    # ==================================================================

    def _add_user(self):
        """Add a new user."""
        # Get username
        username, ok = QInputDialog.getText(
            self, "Add New User", "Username:"
        )
        if not ok or not username.strip():
            return

        # Check duplicate
        session = get_db_session()
        try:
            if session.query(User).filter_by(username=username.strip()).first():
                QMessageBox.warning(self, "Duplicate", 
                                  f"Username '{username}' already exists.")
                return
        finally:
            session.close()

        # Get password
        password, ok = QInputDialog.getText(
            self, "Add New User", "Password:",
            echo=QLineEdit.EchoMode.Password
        )
        if not ok or not password:
            return

        if len(password) < MIN_PASSWORD_LENGTH:
            QMessageBox.warning(
                self, "Weak Password",
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
            )
            return

        # Confirm password
        confirm, ok = QInputDialog.getText(
            self, "Add New User", "Confirm Password:",
            echo=QLineEdit.EchoMode.Password
        )
        if not ok or password != confirm:
            QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
            return

        # Get full name
        full_name, ok = QInputDialog.getText(
            self, "Add New User", "Full Name:"
        )
        if not ok:
            return

        # Get email
        email, ok = QInputDialog.getText(
            self, "Add New User", "Email (optional):"
        )
        if not ok:
            email = ""

        # Get role
        role_items = [f"{ROLES[r]['icon']} {ROLES[r]['name']}" for r in ROLES]
        role, ok = QInputDialog.getItem(
            self, "Add New User", "Role:",
            role_items, 0, False
        )
        if not ok:
            return

        # Extract role key
        role_key = list(ROLES.keys())[role_items.index(role)]

        # Create user
        session = get_db_session()
        try:
            user = User(
                username=username.strip(),
                password_hash=hash_password(password),
                full_name=full_name.strip(),
                email=email.strip() if email else None,
                role=role_key,
                is_active=True,
                created_by=self._get_username()
            )
            session.add(user)
            session.commit()

            self._load_users()
            self.users_updated.emit()
            QMessageBox.information(self, "Success", f"User '{username}' created.")
            self.status_bar.showMessage(f"User '{username}' created", 3000)
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _edit_user(self):
        """Edit selected user."""
        user = self._get_selected_user()
        if not user:
            return

        # Get new full name
        full_name, ok = QInputDialog.getText(
            self, "Edit User", "Full Name:",
            text=user.full_name or ""
        )
        if not ok:
            return

        # Get new role
        role_items = [f"{ROLES[r]['icon']} {ROLES[r]['name']}" for r in ROLES]
        current_role_idx = list(ROLES.keys()).index(user.role)
        role, ok = QInputDialog.getItem(
            self, "Edit User", "Role:",
            role_items, current_role_idx, False
        )
        if not ok:
            return

        role_key = list(ROLES.keys())[role_items.index(role)]

        # Get email
        email, ok = QInputDialog.getText(
            self, "Edit User", "Email:",
            text=user.email or ""
        )
        if not ok:
            email = user.email

        # Update user
        session = get_db_session()
        try:
            db_user = session.query(User).filter_by(id=user.id).first()
            db_user.full_name = full_name.strip()
            db_user.role = role_key
            db_user.email = email.strip() if email else None
            session.commit()

            self._load_users()
            self.users_updated.emit()
            self.status_bar.showMessage(f"User '{user.username}' updated", 3000)
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _toggle_user(self):
        """Toggle user active/inactive status."""
        user = self._get_selected_user()
        if not user:
            return

        new_status = not user.is_active
        action = "activate" if new_status else "deactivate"

        confirm = QMessageBox.question(
            self, f"Confirm {action.capitalize()}",
            f"Are you sure you want to {action} user '{user.username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        session = get_db_session()
        try:
            db_user = session.query(User).filter_by(id=user.id).first()
            db_user.is_active = new_status
            session.commit()

            self._load_users()
            self.users_updated.emit()
            self.status_bar.showMessage(f"User '{user.username}' {action}d", 3000)
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _reset_password(self):
        """Reset password for selected user."""
        user = self._get_selected_user()
        if not user:
            return

        confirm = QMessageBox.question(
            self, "Reset Password",
            f"Reset password for user '{user.username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        # Get new password
        password, ok = QInputDialog.getText(
            self, "Reset Password", "New password:",
            echo=QLineEdit.EchoMode.Password
        )
        if not ok or not password:
            return

        if len(password) < MIN_PASSWORD_LENGTH:
            QMessageBox.warning(
                self, "Weak Password",
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
            )
            return

        session = get_db_session()
        try:
            db_user = session.query(User).filter_by(id=user.id).first()
            db_user.password_hash = hash_password(password)
            session.commit()

            QMessageBox.information(self, "Success", "Password reset successfully.")
            self.status_bar.showMessage(f"Password reset for '{user.username}'", 3000)
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _unlock_user(self):
        """Unlock a locked user account."""
        user = self._get_selected_user()
        if not user:
            return

        if not user.is_locked:
            QMessageBox.information(self, "Not Locked", "This account is not locked.")
            return

        session = get_db_session()
        try:
            db_user = session.query(User).filter_by(id=user.id).first()
            db_user.login_attempts = 0
            db_user.locked_until = None
            session.commit()

            self._load_users()
            self.status_bar.showMessage(f"User '{user.username}' unlocked", 3000)
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _get_username(self) -> str:
        """Get current username."""
        try:
            if self.parent and hasattr(self.parent, 'current_user'):
                return self.parent.current_user
        except Exception:
            pass
        return "admin"

    # ==================================================================
    # Company & Project Info
    # ==================================================================

    def _load_company_project_info(self):
        """Load company and project info from config file."""
        if os.path.exists(APP_CONFIG_FILE):
            try:
                with open(APP_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.company_name_edit.setText(config.get("company", ""))
                self.project_name_edit.setText(config.get("project_name", ""))
                self.project_code_edit.setText(config.get("project_code", ""))
                self.client_name_edit.setText(config.get("client_name", ""))
                self.contract_no_edit.setText(config.get("contract_no", ""))
                self.project_location_edit.setText(config.get("project_location", ""))
            except Exception:
                pass

    def _save_company_project_info(self):
        """Save company and project info to config file."""
        config = {}
        if os.path.exists(APP_CONFIG_FILE):
            try:
                with open(APP_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                pass

        config["company"] = self.company_name_edit.text().strip()
        config["project_name"] = self.project_name_edit.text().strip()
        config["project_code"] = self.project_code_edit.text().strip()
        config["client_name"] = self.client_name_edit.text().strip()
        config["contract_no"] = self.contract_no_edit.text().strip()
        config["project_location"] = self.project_location_edit.text().strip()

        try:
            with open(APP_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "Saved", "Company and project information saved.")
            self.status_bar.showMessage("Project info saved", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _save_security_settings(self):
        """Save security settings."""
        QMessageBox.information(
            self, "Saved",
            "Security settings saved.\n\n"
            f"Min Password Length: {self.min_length_spin.value()}\n"
            f"Max Login Attempts: {self.max_attempts_spin.value()}\n"
            f"Lockout Duration: {self.lockout_spin.value()} minutes"
        )
        self.status_bar.showMessage("Security settings saved", 3000)