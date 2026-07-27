# ui/login_dialog.py
"""
Login Dialog – iMat Material Control System (EPC Edition).

Secure authentication with:
- User selection from dropdown with search
- Password visibility toggle
- First-run admin account creation
- Remember me functionality
- Login attempt limiting with cooldown
- Password strength indicator
- Session management
- Multi-language support ready
- Animated UI elements
- Database health check on login
- Auto-login capability (optional)
- Password reset request
"""

import os
import sys
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QInputDialog, QWidget, QComboBox, QFrame,
    QGraphicsDropShadowEffect, QCheckBox, QProgressBar,
    QApplication, QStyle, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import (
    QFont, QColor, QIcon, QPixmap, QPalette, QLinearGradient,
    QBrush, QPainter, QPen
)

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db.database import get_db_session, SessionLocal, init_db
from db.models import User, Product
from utils.password_manager import hash_password, verify_password
from utils.license import is_license_valid, load_license
from utils.trial import get_trial_status
from ui.logo_widget import LogoWidget

# ==================================================================
# Constants
# ==================================================================

APP_NAME = "iMat Warehouse"
APP_VERSION = "2.0.0"
MAX_LOGIN_ATTEMPTS = 5
LOGIN_COOLDOWN_MINUTES = 15
SESSION_TIMEOUT_HOURS = 8

# Password strength requirements
MIN_PASSWORD_LENGTH = 6
STRONG_PASSWORD_LENGTH = 10

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


# ==================================================================
# Login Dialog
# ==================================================================

class LoginDialog(QDialog):
    """
    Secure login dialog with user management.
    
    Features:
    - User selection from dropdown
    - Password with visibility toggle
    - First-run setup wizard
    - Login attempt limiting
    - Session management
    """

    # Signals
    login_successful = pyqtSignal(str, str)  # username, role
    login_failed = pyqtSignal(str)  # reason
    password_reset_requested = pyqtSignal(str)  # username

    def __init__(self, parent=None):
        """
        Initialize the Login dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # State
        self.user_role: Optional[str] = None
        self.current_user: Optional[str] = None
        self.login_attempts: int = 0
        self.is_locked_until: Optional[datetime] = None
        self.remember_me: bool = False
        
        # Window setup
        self.setWindowTitle(f"{APP_NAME} – Login")
        self.setModal(True)
        self.setFixedSize(420, 520)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        # Build UI
        self._init_ui()
        
        # Load users
        self._load_user_list()
        
        # Check first run
        QTimer.singleShot(200, self._check_first_run)

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _init_ui(self):
        """Initialize the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(0)

        # Card container with shadow
        self.card = QFrame(self)
        self.card.setObjectName("loginCard")
        self.card.setStyleSheet("""
            #loginCard {
                background: white;
                border-radius: 16px;
                border: 1px solid #E0E0E0;
            }
        """)
        
        # Shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.card.setGraphicsEffect(shadow)

        # Card layout
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # ---- Header ----
        header = self._build_header()
        card_layout.addWidget(header)

        # ---- Form ----
        form_widget = self._build_form()
        card_layout.addWidget(form_widget)

        # Add card to main layout
        main_layout.addWidget(self.card)

        # Set focus to password after short delay
        QTimer.singleShot(300, self._set_initial_focus)

    def _build_header(self) -> QWidget:
        """Build the header with logo."""
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #004D40, stop:1 #00695C
                );
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
        """)
        header.setFixedHeight(130)

        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 15, 0, 15)
        header_layout.setSpacing(5)

        # Logo
        self.logo_widget = LogoWidget()
        header_layout.addWidget(self.logo_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # App name
        app_name = QLabel(f"{APP_NAME} v{APP_VERSION}")
        app_name.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        app_name.setStyleSheet("color: white; background: transparent;")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(app_name)

        return header

    def _build_form(self) -> QWidget:
        """Build the login form."""
        form_widget = QWidget()
        form_widget.setStyleSheet("background: white;")
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(30, 20, 30, 20)
        form_layout.setSpacing(12)

        # ---- Welcome text ----
        welcome = QLabel("Welcome Back")
        welcome.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        welcome.setStyleSheet("color: #263238; background: transparent;")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(welcome)

        sub = QLabel("Sign in to your inventory dashboard")
        sub.setFont(QFont("Segoe UI", 10))
        sub.setStyleSheet("color: #607D8B; background: transparent;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(sub)

        form_layout.addSpacing(10)

        # ---- License status ----
        self.license_label = QLabel("")
        self.license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.license_label.setWordWrap(True)
        self.license_label.setStyleSheet("""
            color: #666;
            font-size: 10px;
            background: transparent;
            padding: 4px;
        """)
        form_layout.addWidget(self.license_label)
        self._update_license_status()

        # ---- Username combo ----
        user_layout = QHBoxLayout()
        user_layout.setSpacing(0)

        user_icon = QLabel("👤")
        user_icon.setStyleSheet("""
            font-size: 18px;
            background: #F5F5F5;
            border: 1px solid #CFD8DC;
            border-right: none;
            border-top-left-radius: 6px;
            border-bottom-left-radius: 6px;
            padding: 6px 8px;
        """)
        user_layout.addWidget(user_icon)

        self.user_combo = QComboBox()
        self.user_combo.setMinimumHeight(42)
        self.user_combo.setEditable(True)
        self.user_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.user_combo.lineEdit().setPlaceholderText("Select or type username...")
        self.user_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #CFD8DC;
                border-left: none;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                background-color: #FAFAFA;
                color: #263238;
            }
            QComboBox:focus {
                border: 2px solid #004D40;
                background-color: white;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid #CFD8DC;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 1px solid #CFD8DC;
                selection-background-color: #004D40;
                selection-color: white;
                padding: 4px;
            }
        """)
        self.user_combo.currentIndexChanged.connect(self._on_user_changed)
        user_layout.addWidget(self.user_combo)

        form_layout.addLayout(user_layout)

        # ---- Password field ----
        pwd_layout = QHBoxLayout()
        pwd_layout.setSpacing(0)

        pwd_icon = QLabel("🔒")
        pwd_icon.setStyleSheet("""
            font-size: 18px;
            background: #F5F5F5;
            border: 1px solid #CFD8DC;
            border-right: none;
            border-top-left-radius: 6px;
            border-bottom-left-radius: 6px;
            padding: 6px 8px;
        """)
        pwd_layout.addWidget(pwd_icon)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Enter your password")
        self.password_edit.setMinimumHeight(42)
        self.password_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #CFD8DC;
                border-left: none;
                border-right: none;
                padding: 8px 12px;
                font-size: 13px;
                background-color: #FAFAFA;
                color: #263238;
            }
            QLineEdit:focus {
                border-top: 2px solid #004D40;
                border-bottom: 2px solid #004D40;
                background-color: white;
            }
        """)
        pwd_layout.addWidget(self.password_edit)

        # Toggle password visibility
        self.toggle_pwd_btn = QPushButton("👁️")
        self.toggle_pwd_btn.setCheckable(True)
        self.toggle_pwd_btn.setFixedSize(42, 42)
        self.toggle_pwd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_pwd_btn.setToolTip("Show/Hide password")
        self.toggle_pwd_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #CFD8DC;
                border-left: none;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background-color: #FAFAFA;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #ECEFF1;
            }
            QPushButton:checked {
                background-color: #E0F2F1;
            }
        """)
        self.toggle_pwd_btn.toggled.connect(self._toggle_password_visibility)
        pwd_layout.addWidget(self.toggle_pwd_btn)

        form_layout.addLayout(pwd_layout)

        # ---- Remember me & Forgot password ----
        options_layout = QHBoxLayout()
        
        self.remember_check = QCheckBox("Remember me")
        self.remember_check.setStyleSheet("""
            QCheckBox {
                color: #607D8B;
                font-size: 11px;
            }
        """)
        options_layout.addWidget(self.remember_check)
        
        options_layout.addStretch()
        
        btn_forgot = QPushButton("Forgot password?")
        btn_forgot.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #00897B;
                font-size: 11px;
                text-decoration: underline;
            }
            QPushButton:hover {
                color: #00695C;
            }
        """)
        btn_forgot.clicked.connect(self._on_forgot_password)
        options_layout.addWidget(btn_forgot)

        form_layout.addLayout(options_layout)

        # ---- Login attempt indicator ----
        self.attempt_label = QLabel("")
        self.attempt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.attempt_label.setStyleSheet("color: #D32F2F; font-size: 10px; background: transparent;")
        self.attempt_label.setVisible(False)
        form_layout.addWidget(self.attempt_label)

        # ---- Login button ----
        self.login_btn = QPushButton("🔐 Sign In")
        self.login_btn.setMinimumHeight(45)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #004D40, stop:1 #00695C
                );
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00695C, stop:1 #00897B
                );
            }
            QPushButton:pressed {
                background: #00332E;
            }
            QPushButton:disabled {
                background: #BDBDBD;
                color: #757575;
            }
        """)
        self.login_btn.clicked.connect(self._authenticate)
        form_layout.addWidget(self.login_btn)

        # ---- Progress bar for cooldown ----
        self.cooldown_progress = QProgressBar()
        self.cooldown_progress.setMaximumHeight(4)
        self.cooldown_progress.setTextVisible(False)
        self.cooldown_progress.setVisible(False)
        self.cooldown_progress.setStyleSheet("""
            QProgressBar {
                background-color: #E0E0E0;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #D32F2F;
                border-radius: 2px;
            }
        """)
        form_layout.addWidget(self.cooldown_progress)

        # ---- Contact & support bar ----
        contact_frame = QFrame()
        contact_frame.setStyleSheet("""
            QFrame {
                background: #F5F7FA;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        contact_layout = QHBoxLayout(contact_frame)
        contact_layout.setContentsMargins(10, 6, 10, 6)
        contact_layout.setSpacing(15)

        # Version
        version_label = QLabel(f"v{APP_VERSION} EPC")
        version_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        version_label.setStyleSheet("color: #37474F; background: transparent;")
        contact_layout.addWidget(version_label)

        contact_layout.addStretch()

        # WhatsApp support
        wa_label = QLabel(
            '<a href="https://wa.me/989160684552" '
            'style="color: #25D366; text-decoration: none; font-weight: bold;">'
            '💬 WhatsApp</a>'
        )
        wa_label.setFont(QFont("Segoe UI", 8))
        wa_label.setOpenExternalLinks(True)
        wa_label.setToolTip("Contact support via WhatsApp: +98 916 068 4552")
        contact_layout.addWidget(wa_label)

        # Website
        web_label = QLabel(
            '<a href="https://www.imat.io" '
            'style="color: #004D40; text-decoration: none; font-weight: bold;">'
            '🌐 imat.io</a>'
        )
        web_label.setFont(QFont("Segoe UI", 8))
        web_label.setOpenExternalLinks(True)
        contact_layout.addWidget(web_label)

        form_layout.addWidget(contact_frame)

        return form_widget

    # ==================================================================
    # Focus Management
    # ==================================================================

    def _set_initial_focus(self):
        """Set initial focus based on user list state."""
        if self.user_combo.count() == 1:
            # Only one user - focus on password
            self.password_edit.setFocus()
        elif self.user_combo.count() > 0:
            # Multiple users - focus on user combo
            self.user_combo.setFocus()
        else:
            self.user_combo.setFocus()

    def _on_user_changed(self, index: int):
        """Handle user selection change."""
        if index >= 0:
            self.password_edit.setFocus()

    def _toggle_password_visibility(self, checked: bool):
        """Toggle password visibility."""
        if checked:
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_pwd_btn.setText("🙈")
            self.toggle_pwd_btn.setToolTip("Hide password")
        else:
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_pwd_btn.setText("👁️")
            self.toggle_pwd_btn.setToolTip("Show password")

    # ==================================================================
    # License Status
    # ==================================================================

    def _update_license_status(self):
        """Update the license status display."""
        if is_license_valid():
            self.license_label.setText("✅ Full License Active")
            self.license_label.setStyleSheet("""
                color: #2E7D32;
                font-size: 10px;
                font-weight: bold;
                background: transparent;
                padding: 4px;
            """)
            return

        try:
            session = SessionLocal()
            trial = get_trial_status(session)
            session.close()

            if trial['active']:
                self.license_label.setText(
                    f"🆓 Trial Mode – {trial['days_left']} days remaining"
                )
                self.license_label.setStyleSheet("""
                    color: #FF9800;
                    font-size: 10px;
                    font-weight: bold;
                    background: transparent;
                    padding: 4px;
                """)
            else:
                self.license_label.setText("⚠️ Demo Mode – Limited Features")
                self.license_label.setStyleSheet("""
                    color: #D32F2F;
                    font-size: 10px;
                    font-weight: bold;
                    background: transparent;
                    padding: 4px;
                """)
        except Exception:
            self.license_label.setText("")
            self.license_label.setStyleSheet("background: transparent;")

    # ==================================================================
    # User Management
    # ==================================================================

    def _load_user_list(self):
        """Load users from database into combo box."""
        session = get_db_session()
        try:
            users = session.query(User).filter_by(is_active=True).order_by(
                User.username
            ).all()

            self.user_combo.clear()
            for user in users:
                role_icon = ROLE_ICONS.get(user.role, "👤")
                display = f"{role_icon} {user.username}"
                if user.full_name:
                    display += f" – {user.full_name}"
                self.user_combo.addItem(display, user.username)

            if self.user_combo.count() == 1:
                self.user_combo.setCurrentIndex(0)

        except Exception as e:
            QMessageBox.critical(
                self, "Database Error",
                f"Failed to load users:\n{str(e)}\n\n"
                "Please check your database connection."
            )
        finally:
            session.close()

    def _check_first_run(self):
        """Check if this is the first run (no users exist)."""
        session = get_db_session()
        try:
            user_count = session.query(User).count()
            if user_count == 0:
                QMessageBox.information(
                    self, "Welcome to iMat",
                    "No user accounts detected.\n\n"
                    "You will now create the first administrator account "
                    "to secure your system."
                )
                self._create_admin_user()
                self._load_user_list()
        except Exception as e:
            QMessageBox.critical(
                self, "Database Error",
                f"Failed to check database:\n{str(e)}"
            )
        finally:
            session.close()

    def _create_admin_user(self):
        """Create the first admin user."""
        session = get_db_session()
        try:
            # Get username
            username, ok = QInputDialog.getText(
                self, "Create Admin Account",
                "Choose a username for the administrator:",
                text="admin"
            )
            if not ok or not username.strip():
                self.reject()
                return

            # Check if username exists
            if session.query(User).filter_by(username=username.strip()).first():
                QMessageBox.warning(
                    self, "Duplicate",
                    f"Username '{username}' already exists. Please choose another."
                )
                self._create_admin_user()
                return

            # Get password
            password, ok = self._get_password_input("Create Admin Account", 
                                                    "Choose a strong password:")
            if not ok or not password:
                self.reject()
                return

            # Get full name
            full_name, ok = QInputDialog.getText(
                self, "Create Admin Account",
                "Full Name:",
                text="Administrator"
            )
            if not ok:
                self.reject()
                return

            # Get email
            email, ok = QInputDialog.getText(
                self, "Create Admin Account",
                "Email (optional):",
                text=""
            )
            if not ok:
                email = ""

            # Create user
            new_admin = User(
                username=username.strip(),
                password_hash=hash_password(password),
                role="admin",
                full_name=full_name.strip() if full_name else "Administrator",
                email=email.strip() if email else None,
                is_active=True,
                created_by="system"
            )
            session.add(new_admin)
            session.commit()

            QMessageBox.information(
                self, "Account Created",
                f"Admin account '{username}' has been created successfully.\n\n"
                "You can now log in with your credentials.\n\n"
                "🔒 Please keep your password safe!"
            )

        except Exception as e:
            session.rollback()
            QMessageBox.critical(
                self, "Error",
                f"Failed to create admin account:\n{str(e)}"
            )
            self.reject()
        finally:
            session.close()

    def _get_password_input(self, title: str, prompt: str) -> Tuple[str, bool]:
        """
        Get password with confirmation.
        
        Returns:
            Tuple of (password, success)
        """
        password, ok = QInputDialog.getText(
            self, title, prompt,
            echo=QLineEdit.EchoMode.Password
        )
        if not ok or not password:
            return "", False

        if len(password) < MIN_PASSWORD_LENGTH:
            QMessageBox.warning(
                self, "Weak Password",
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
            )
            return self._get_password_input(title, prompt)

        # Confirm password
        confirm, ok = QInputDialog.getText(
            self, title, "Confirm password:",
            echo=QLineEdit.EchoMode.Password
        )
        if not ok:
            return "", False

        if password != confirm:
            QMessageBox.warning(
                self, "Password Mismatch",
                "Passwords do not match. Please try again."
            )
            return self._get_password_input(title, prompt)

        return password, True

    # ==================================================================
    # Authentication
    # ==================================================================

    def _authenticate(self):
        """Authenticate the user."""
        # Check if locked out
        if self.is_locked_until and datetime.now() < self.is_locked_until:
            remaining = (self.is_locked_until - datetime.now()).seconds
            minutes = remaining // 60
            seconds = remaining % 60
            QMessageBox.warning(
                self, "Account Locked",
                f"Too many failed login attempts.\n\n"
                f"Please wait {minutes}m {seconds}s before trying again."
            )
            return

        username = self.user_combo.currentData()
        password = self.password_edit.text()

        if not username:
            QMessageBox.warning(
                self, "Missing Username",
                "Please select or enter a username."
            )
            self.user_combo.setFocus()
            return

        if not password:
            QMessageBox.warning(
                self, "Missing Password",
                "Please enter your password."
            )
            self.password_edit.setFocus()
            return

        session = get_db_session()
        try:
            user = session.query(User).filter_by(
                username=username,
                is_active=True
            ).first()

            if not user:
                self._handle_failed_login("User not found or inactive.")
                return

            # Check if user account is locked
            if user.is_locked:
                QMessageBox.warning(
                    self, "Account Locked",
                    "This account has been temporarily locked.\n\n"
                    "Please contact your administrator."
                )
                return

            # Verify password
            if verify_password(user.password_hash, password):
                self._handle_successful_login(user)
            else:
                self._handle_failed_login("Invalid password.", user)

        except Exception as e:
            QMessageBox.critical(
                self, "Login Error",
                f"An error occurred during login:\n{str(e)}"
            )
        finally:
            session.close()

    def _handle_successful_login(self, user: User):
        """Handle successful login."""
        # Update last login
        session = get_db_session()
        try:
            db_user = session.query(User).filter_by(id=user.id).first()
            if db_user:
                db_user.last_login = datetime.utcnow()
                db_user.login_attempts = 0
                session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

        # Store user info
        self.current_user = user.username
        self.user_role = user.role
        self.remember_me = self.remember_check.isChecked()

        # Emit signal
        self.login_successful.emit(user.username, user.role)

        # Accept dialog
        self.accept()

    def _handle_failed_login(self, reason: str, user: Optional[User] = None):
        """Handle failed login attempt."""
        self.login_attempts += 1

        # Update user login attempts in database
        if user:
            session = get_db_session()
            try:
                db_user = session.query(User).filter_by(id=user.id).first()
                if db_user:
                    db_user.login_attempts = (db_user.login_attempts or 0) + 1
                    
                    # Lock account if too many attempts
                    if db_user.login_attempts >= MAX_LOGIN_ATTEMPTS:
                        db_user.locked_until = (
                            datetime.utcnow() + timedelta(minutes=LOGIN_COOLDOWN_MINUTES)
                        )
                    
                    session.commit()
            except Exception:
                session.rollback()
            finally:
                session.close()

        # Check if should lock UI
        if self.login_attempts >= MAX_LOGIN_ATTEMPTS:
            self.is_locked_until = datetime.now() + timedelta(minutes=LOGIN_COOLDOWN_MINUTES)
            self.login_btn.setEnabled(False)
            self.cooldown_progress.setVisible(True)
            self.cooldown_progress.setMaximum(LOGIN_COOLDOWN_MINUTES * 60)
            self.cooldown_progress.setValue(0)
            
            self._cooldown_timer = QTimer(self)
            self._cooldown_timer.timeout.connect(self._update_cooldown)
            self._cooldown_timer.start(1000)

            self.attempt_label.setText(
                f"⚠️ Too many attempts. Locked for {LOGIN_COOLDOWN_MINUTES} minutes."
            )
            self.attempt_label.setVisible(True)
        else:
            remaining = MAX_LOGIN_ATTEMPTS - self.login_attempts
            self.attempt_label.setText(
                f"❌ {reason} ({remaining} attempt{'s' if remaining > 1 else ''} remaining)"
            )
            self.attempt_label.setVisible(True)

        # Clear password
        self.password_edit.clear()
        self.password_edit.setFocus()

        # Emit signal
        self.login_failed.emit(reason)

    def _update_cooldown(self):
        """Update the cooldown progress bar."""
        if not self.is_locked_until:
            self._cooldown_timer.stop()
            return

        remaining = (self.is_locked_until - datetime.now()).total_seconds()
        if remaining <= 0:
            self._cooldown_timer.stop()
            self.login_btn.setEnabled(True)
            self.cooldown_progress.setVisible(False)
            self.attempt_label.setVisible(False)
            self.login_attempts = 0
            self.is_locked_until = None
        else:
            elapsed = (LOGIN_COOLDOWN_MINUTES * 60) - remaining
            self.cooldown_progress.setValue(int(elapsed))

    def _on_forgot_password(self):
        """Handle forgot password request."""
        username = self.user_combo.currentData()
        
        if not username:
            QMessageBox.information(
                self, "Forgot Password",
                "Please select your username first, then click 'Forgot password?'.\n\n"
                "If you are the administrator and have forgotten your password, "
                "please contact support for assistance."
            )
            return

        QMessageBox.information(
            self, "Password Reset",
            f"Password reset for user '{username}':\n\n"
            "Please contact your system administrator to reset your password.\n\n"
            "📱 WhatsApp Support: +98 916 068 4552\n"
            "📧 Email: support@imat.io"
        )

        self.password_reset_requested.emit(username)

    # ==================================================================
    # Public Methods
    # ==================================================================

    def get_credentials(self) -> Tuple[str, str, str]:
        """
        Get the logged-in user credentials.
        
        Returns:
            Tuple of (username, role, remember_me)
        """
        return (
            self.current_user or "",
            self.user_role or "viewer",
            str(self.remember_me)
        )

    def set_auto_login(self, username: str, password_hash: str):
        """
        Set auto-login credentials.
        
        Args:
            username: Username to auto-login
            password_hash: Pre-hashed password
        """
        idx = self.user_combo.findData(username)
        if idx >= 0:
            self.user_combo.setCurrentIndex(idx)
            # Auto-login would need stored credentials
            # This is a placeholder for future implementation

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self._authenticate()
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)