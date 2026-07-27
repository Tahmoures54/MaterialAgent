# main_window.py
"""
Main application window for iMat Material Control System (EPC Edition).
Complete with role-based menus, search, export, AI tools, and theme support.
Includes offline multilingual inventory assistant.
"""

import os
import sys
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import (
    QThread, pyqtSignal, QPropertyAnimation, QEasingCurve,
    QTimer, Qt, QUrl, QSize
)
from PyQt6.QtGui import (
    QColor, QFont, QDesktopServices, QIcon, QAction,
    QKeySequence, QPixmap, QPalette
)
from PyQt6.QtWidgets import (
    QMainWindow, QDialog, QMessageBox, QInputDialog, QFileDialog,
    QTableWidget, QTableWidgetItem, QGraphicsOpacityEffect, QApplication,
    QMenu, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget,
    QProgressBar, QStatusBar, QFrame, QHeaderView, QLineEdit,
    QComboBox, QFormLayout, QDateEdit, QGroupBox, QScrollArea,
    QGridLayout, QDoubleSpinBox, QToolBar, QToolButton, QSplitter,
    QCheckBox, QSpinBox, QTextEdit, QListWidget, QListWidgetItem,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QDialogButtonBox,
    QAbstractItemView, QSizePolicy, QSpacerItem
)

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db.database import (
    SessionLocal, get_engine, init_db, backup_database,
    get_database_info, change_database
)
from db.models import (
    Product, Stock, Location, Document, User, Transaction,
    MaterialRequest, InventorySummary, ProjectInfo, DocumentLine
)
from config.config_manager import config

from utils.logger import setup_logger
from utils.excel_export import export_to_excel
from utils.pdf_export import export_to_pdf
from utils.html_export import (
    export_document_to_html, save_html_to_file, preview_html_in_browser
)
from utils.license import is_license_valid, load_license, get_machine_id
from utils.trial import get_trial_status

from ai.optimizer import InventoryOptimizer
from ai.predictor import DemandPredictor, load_demand_history
from ai.llm_helper import LLMHelper, get_llm_instance
from ui.assistant_dialog import AssistantDialog  # ← added for offline assistant

from sqlalchemy import func, or_, and_

logger = setup_logger(__name__)

# ==================================================================
# Constants
# ==================================================================
APP_NAME = "iMat Warehouse"
APP_VERSION = "2.0.0"
ORGANIZATION_NAME = "iMat International"
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'aimat.db'))

TRIAL_ROW_LIMIT = 10
DEMO_STATUS = "Demo (limited)"
TRIAL_STATUS = "Trial ({days_left} days left)"
FULL_LICENSE_STATUS = "Full License"


# ==================================================================
# Main Window Class
# ==================================================================

class MainWindow(QMainWindow):
    """Main application window with full EPC material control capabilities."""

    def __init__(self, user_role: str = "viewer", username: str = "", parent=None):
        super().__init__(parent)

        # User info
        self.user_role = user_role
        self.current_user = username

        # Database
        self.DB_PATH = DB_PATH
        self.total_records = 0
        self.filtered_records = 0

        # UI state
        self._search_timer = None
        self._db_timer = None
        self._db_pulse_anim = None
        self._db_opacity_effect = None
        self.barcode_dialog = None
        self.start_dialog = None
        self.current_theme = config.get('default_theme', 'light')

        # Initialize
        self._init_window()
        self._init_ui()
        self._init_connections()
        self._init_database()
        self._load_initial_data()
        self._apply_theme()
        self._show_start_dialog()

    # ==================================================================
    # Initialization Methods
    # ==================================================================

    def _init_window(self):
        """Initialize window properties."""
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} - Material Control System (EPC)")
        self.setGeometry(100, 100, 1400, 850)
        self.setMinimumSize(1024, 600)

        # Center on screen
        screen = QApplication.primaryScreen()
        if screen:
            center = screen.availableGeometry().center()
            frame = self.frameGeometry()
            frame.moveCenter(center)
            self.move(frame.topLeft())

    def _init_ui(self):
        """Build the complete user interface."""
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self._build_menu_bar()
        self._build_toolbar()
        self._build_search_panel()
        self._build_progress_bar()
        self._build_main_table()
        self._build_prediction_bar()
        self._build_status_bar()

    def _init_connections(self):
        """Initialize signal-slot connections."""
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(400)
        self._search_timer.timeout.connect(self._perform_search)

        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.qc_combo.currentTextChanged.connect(self._on_filter_changed)
        self.discipline_combo.currentTextChanged.connect(self._on_filter_changed)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)
        self.table.doubleClicked.connect(self._on_table_double_clicked)

        self._db_timer = QTimer(self)
        self._db_timer.timeout.connect(self.check_db_connection)
        self._db_timer.start(5000)

    def _init_database(self):
        """Initialize database and check connection."""
        try:
            self.check_db_connection()
            self._load_filter_options()
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            QMessageBox.critical(
                self, "Database Error",
                f"Failed to connect to database:\n{str(e)}"
            )

    def _load_initial_data(self):
        """Load initial data into the table."""
        self.on_search()

    def _show_start_dialog(self):
        """Show the welcome/start dialog."""
        if config.get('ui.show_start_dialog', True):
            from ui.start_dialog import StartDialog
            self.start_dialog = StartDialog(self)
            self.start_dialog.action_selected.connect(self._handle_start_action)
            QTimer.singleShot(500, self.start_dialog.show)

    # ==================================================================
    # UI Construction Methods
    # ==================================================================

    def _build_menu_bar(self):
        """Build role-based menu bar."""
        menubar = self.menuBar()
        menubar.setStyleSheet(self._get_menu_style())

        # ===== System Menu =====
        sys_menu = menubar.addMenu("⚙️ &System")
        self._add_menu_action(sys_menu, "📂 Change Database...",
                             self.on_change_database, ["admin"])
        self._add_menu_action(sys_menu, "💾 Backup Database",
                             self.on_backup_now, ["admin"])
        self._add_menu_action(sys_menu, "⚙️ Auto‑Backup Settings...",
                             self.on_auto_backup_settings, ["admin"])
        sys_menu.addSeparator()
        self.action_settings = self._add_menu_action(sys_menu, "&Settings",
                                                     self.on_settings, ["admin"])
        sys_menu.addSeparator()
        self._add_menu_action(sys_menu, "E&xit", self.close,
                             ["admin", "operator", "technical", "qc_inspector", "viewer"])

        # ===== Material Control Menu =====
        mat_menu = menubar.addMenu("📦 &Material Control")
        self._add_menu_action(mat_menu, "📦 Material Coding (Products)",
                             self.on_open_product_coding,
                             ["admin", "operator", "technical"],
                             "Manage item codes, descriptions, disciplines, and units")
        self._add_menu_action(mat_menu, "🏢 Warehouse & Locations",
                             self.on_open_locations,
                             ["admin", "operator"])
        mat_menu.addSeparator()
        self._add_menu_action(mat_menu, "📄 New Document (MRR/MIV/MSR/OS&D)",
                             self.on_open_document_dialog,
                             ["admin", "operator", "technical"])
        self._add_menu_action(mat_menu, "📋 Transactions Manager",
                             self.on_open_transaction_dialog,
                             ["admin", "operator", "technical"])
        mat_menu.addSeparator()
        self._add_menu_action(mat_menu, "⌛ Expiry Date Monitor",
                             self.on_expiry_monitor,
                             ["admin", "operator", "technical", "qc_inspector"])
        self._add_menu_action(mat_menu, "📊 Reorder Point Calculator",
                             self.on_reorder_calculator,
                             ["admin", "operator", "technical"])

        # ===== Technical Office Menu =====
        tech_menu = menubar.addMenu("📐 &Technical Office")
        self._add_menu_action(tech_menu, "📋 New Material Request (MR)",
                             self.on_new_material_request,
                             ["admin", "technical"])
        self._add_menu_action(tech_menu, "📄 MR History",
                             self.on_material_request_history,
                             ["admin", "technical"])
        tech_menu.addSeparator()
        self._add_menu_action(tech_menu, "📄 MSR History",
                             lambda: self._open_reports_window("msr_history"),
                             ["admin", "technical"])
        tech_menu.addSeparator()
        self._add_menu_action(tech_menu, "📊 Live Stock Dashboard",
                             self.on_live_stock_report,
                             ["admin", "technical", "operator", "qc_inspector", "viewer"])
        self._add_menu_action(tech_menu, "🔗 Material Traceability",
                             self.on_traceability_report,
                             ["admin", "technical", "operator", "qc_inspector", "viewer"])

        # ===== Quality Control Menu =====
        qc_menu = menubar.addMenu("✅ &Quality Control")
        self._add_menu_action(qc_menu, "🔍 QC Release (Quarantine → Accepted)",
                             self.on_qc_release,
                             ["admin", "operator", "qc_inspector"])
        self._add_menu_action(qc_menu, "🛡️ Preservation Dashboard",
                             self.on_preservation_dashboard,
                             ["admin", "operator", "qc_inspector"])
        self._add_menu_action(qc_menu, "⌛ Expiry Date Monitor",
                             self.on_expiry_monitor,
                             ["admin", "operator", "qc_inspector"])

        # ===== Reports & Export Menu =====
        reports_menu = menubar.addMenu("📊 &Reports & Export")
        self._add_menu_action(reports_menu, "📊 Report Manager",
                             self.on_report_manager,
                             ["admin", "operator", "technical", "qc_inspector", "viewer"])
        reports_menu.addSeparator()
        self.action_export_excel = self._add_menu_action(
            reports_menu, "📥 Export Stock Table to Excel",
            self.on_export_excel,
            ["admin", "operator", "technical", "qc_inspector"]
        )
        self.action_export_pdf = self._add_menu_action(
            reports_menu, "📑 Export Stock Table to PDF",
            self.on_export_pdf,
            ["admin", "operator", "technical", "qc_inspector"]
        )
        self._add_menu_action(reports_menu, "📄 Export Document to HTML",
                             self.on_export_document_html,
                             ["admin", "operator", "technical"])
        self._add_menu_action(reports_menu, "📄 Document History Report",
                             self.on_document_history_report,
                             ["admin", "operator", "technical", "qc_inspector", "viewer"])

        # ===== Tools Menu =====
        tools_menu = menubar.addMenu("🛠️ &Tools")
        self._add_menu_action(tools_menu, "🔮 AI Demand Prediction",
                             self.on_ai_predict,
                             ["admin", "operator", "technical"])
        self._add_menu_action(tools_menu, "📊 ABC Analysis",
                             self.on_abc_analysis,
                             ["admin", "operator", "technical"])
        self._add_menu_action(tools_menu, "📈 EOQ Calculator",
                             self.on_optimize_eoq,
                             ["admin", "operator", "technical"])
        self._add_menu_action(tools_menu, "📊 Reorder Point Calculator",
                             self.on_reorder_calculator,
                             ["admin", "operator", "technical"])
        tools_menu.addSeparator()
        self.action_barcode = self._add_menu_action(
            tools_menu, "📷 Connect Barcode Reader",
            self.on_toggle_barcode,
            ["admin", "operator", "technical", "qc_inspector"]
        )
        self.action_barcode.setCheckable(True)

        # ✅ دستیار هوشمند (جدید) - در منوی Tools
        self._add_menu_action(tools_menu, "💬 Inventory Assistant",
                             self.on_open_assistant,
                             ["admin", "operator", "technical", "qc_inspector", "viewer"],
                             "Ask questions about stock, items, and locations (offline)")

        # ===== Teamwork Menu =====
        team_menu = menubar.addMenu("👥 &Teamwork")
        self._add_menu_action(team_menu, "👤 Manage Users & Roles",
                             self.on_manage_users, ["admin"])
        team_menu.addSeparator()
        self._add_menu_action(team_menu, "🏢 Company & Project Info",
                             self.on_company_project_info, ["admin"])

        # ===== Help Menu =====
        help_menu = menubar.addMenu("❓ &Help")
        self._add_menu_action(help_menu, "📖 User Manual",
                             self.on_open_help,
                             ["admin", "operator", "technical", "qc_inspector", "viewer"])
        self._add_menu_action(help_menu, "📋 Quick Start Guide",
                             self.on_quick_guide,
                             ["admin", "operator", "technical", "qc_inspector", "viewer"])
        help_menu.addSeparator()
        self._add_menu_action(help_menu, "🔑 License Management",
                             self.on_activate_license,
                             ["admin", "operator", "technical", "qc_inspector", "viewer"])
        self._add_menu_action(help_menu, "ℹ️ &About",
                             self.on_about,
                             ["admin", "operator", "technical", "qc_inspector", "viewer"])

    def _add_menu_action(self, menu, text, handler, allowed_roles, tooltip=""):
        """Add a role-restricted action to a menu."""
        action = QAction(text, self)
        action.triggered.connect(handler)

        if self.user_role not in allowed_roles:
            action.setEnabled(False)
            action.setToolTip(f"Requires role: {', '.join(allowed_roles)}. {tooltip}")
        else:
            if tooltip:
                action.setToolTip(tooltip)

        menu.addAction(action)
        return action

    def _build_toolbar(self):
        """Build the main toolbar (only logo + spacer + optional license + theme)."""
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(24, 24))
        self.toolbar.setStyleSheet(self._get_toolbar_style())
        self.addToolBar(self.toolbar)

        # Logo
        from ui.logo_widget import LogoWidget
        self.logo_widget = LogoWidget()
        self.toolbar.addWidget(self.logo_widget)
        self.toolbar.addSeparator()

        # Spacer (pushes following items to the right)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)

        # License button (only visible if not full access)
        self.buy_license_top_btn = QPushButton("🛒 Buy License")
        self.buy_license_top_btn.setStyleSheet(self._get_license_button_style())
        self.buy_license_top_btn.clicked.connect(self.on_activate_license)
        self.buy_license_top_btn.setVisible(not self._is_full_access())
        self.toolbar.addWidget(self.buy_license_top_btn)

        # Theme toggle
        btn_theme = QPushButton("🌓 Theme")
        btn_theme.setToolTip("Toggle light/dark theme")
        btn_theme.clicked.connect(self._toggle_theme)
        self.toolbar.addWidget(btn_theme)

    def _build_search_panel(self):
        """Build the search and filter panel including New Document (+) and Help buttons."""
        search_frame = QFrame()
        search_frame.setStyleSheet(self._get_search_frame_style())
        frame_layout = QHBoxLayout(search_frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)
        frame_layout.setSpacing(10)

        # Search input
        frame_layout.addWidget(QLabel("🔍 Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Quick Search: Item Code, Heat No, Description..."
        )
        self.search_input.setMinimumWidth(300)
        self.search_input.setClearButtonEnabled(True)
        frame_layout.addWidget(self.search_input)

        # QC Status filter
        frame_layout.addWidget(QLabel("QC Status:"))
        self.qc_combo = QComboBox()
        self.qc_combo.addItems(["All Statuses", "QUARANTINE", "ACCEPTED", "REJECTED"])
        self.qc_combo.setToolTip("Filter by Quality Control Status")
        frame_layout.addWidget(self.qc_combo)

        # Discipline filter
        frame_layout.addWidget(QLabel("Discipline:"))
        self.discipline_combo = QComboBox()
        self.discipline_combo.setToolTip("Filter by Engineering Discipline")
        frame_layout.addWidget(self.discipline_combo)

        # ---- New Document button (small +) ----
        self.start_btn = QPushButton("+")
        self.start_btn.setFixedSize(28, 28)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #00897B;
                color: white;
                border-radius: 14px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #00695C;
            }
        """)
        self.start_btn.setToolTip("Create a new MRR, MIV, MSR or OS&D document")
        self.start_btn.clicked.connect(self.on_open_document_dialog)
        frame_layout.addWidget(self.start_btn)

        # Help button
        help_btn = QPushButton("?")
        help_btn.setFixedSize(28, 28)
        help_btn.setToolTip("Quick usage guide")
        help_btn.setStyleSheet(self._get_help_button_style())
        help_btn.clicked.connect(self.on_quick_guide)
        frame_layout.addWidget(help_btn)

        # ✅ دستیار هوشمند (دکمه در نوار جستجو)
        assistant_btn = QPushButton("💬")
        assistant_btn.setFixedSize(28, 28)
        assistant_btn.setToolTip("Open Inventory Assistant (offline, multilingual)")
        assistant_btn.setStyleSheet(self._get_help_button_style())
        assistant_btn.clicked.connect(self.on_open_assistant)
        frame_layout.addWidget(assistant_btn)

        # ---- Original search action buttons ----
        reset_btn = QPushButton("🔄 Reset")
        refresh_btn = QPushButton("↻ Refresh")
        self.share_btn = QPushButton("📤 Share Data")

        neutral_style = self._get_neutral_button_style()
        for btn in (reset_btn, refresh_btn, self.share_btn):
            btn.setStyleSheet(neutral_style)

        reset_btn.clicked.connect(self.reset_search)
        refresh_btn.clicked.connect(self.refresh_data)
        self.share_btn.clicked.connect(self.on_share_excel)

        frame_layout.addWidget(reset_btn)
        frame_layout.addWidget(refresh_btn)
        frame_layout.addWidget(self.share_btn)
        frame_layout.addStretch()

        self.main_layout.addWidget(search_frame)

    def _build_progress_bar(self):
        """Build the progress bar."""
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(4)
        self.progress.setTextVisible(False)
        self.main_layout.addWidget(self.progress)

    def _build_main_table(self):
        """Build the main data table."""
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.setStyleSheet(self._get_table_style())

        headers = [
            "Item Code", "Description", "Discipline", "Material Class",
            "Heat No / Batch", "Location", "QC Status",
            "Total Qty", "Allocated Qty", "Available Qty",
            "Preservation Due"
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.main_layout.addWidget(self.table)

    def _build_prediction_bar(self):
        """Build the AI prediction bar."""
        pred_frame = QFrame()
        pred_frame.setFrameShape(QFrame.Shape.StyledPanel)
        pred_frame.setStyleSheet(self._get_prediction_frame_style())
        pred_layout = QHBoxLayout(pred_frame)
        pred_layout.setContentsMargins(10, 5, 10, 5)

        pred_title = QLabel("🔮 AI Insights:")
        pred_title.setStyleSheet("font-weight: bold; color: #006666;")
        self.prediction_value = QLabel("Select a material to predict demand...")
        self.prediction_value.setStyleSheet("color: #333; font-style: italic;")

        pred_layout.addWidget(pred_title)
        pred_layout.addWidget(self.prediction_value, 1)
        self.main_layout.addWidget(pred_frame)

    def _build_status_bar(self):
        """Build the status bar with all indicators."""
        self.setStatusBar(QStatusBar())
        status = self.statusBar()
        status.setStyleSheet(self._get_status_bar_style())
        status.setSizeGripEnabled(True)

        # Left side - Database indicator
        left_widget = QWidget()
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        # DB indicator dot
        indicator_container = QWidget()
        indicator_container.setFixedWidth(12)
        container_layout = QHBoxLayout(indicator_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.db_indicator = QLabel("●")
        self.db_indicator.setFixedSize(8, 8)
        self.db_indicator.setToolTip("Database connection status")
        self.db_indicator.setStyleSheet(
            "background-color: #FF0000; border-radius: 4px; border: 1px solid #8B0000;"
        )
        container_layout.addWidget(self.db_indicator)
        left_layout.addWidget(indicator_container)

        # DB Path
        db_loc_label = QLabel("DB:")
        db_loc_label.setStyleSheet("color: #555; font-size: 11px; font-weight: bold;")
        left_layout.addWidget(db_loc_label)

        self.db_path_label = QLabel(self.DB_PATH)
        self.db_path_label.setStyleSheet("color: #555; font-size: 11px;")
        left_layout.addWidget(self.db_path_label)

        status.addWidget(left_widget)

        # Record count
        self.record_count_label = QLabel("Records: 0 | Filtered: 0")
        self.record_count_label.setStyleSheet(
            "color: #333; font-size: 11px; margin-left: 20px;"
        )
        status.addWidget(self.record_count_label)

        # Spacer
        status.addPermanentWidget(QWidget(), 1)

        # User role
        role_display = {
            "admin": "Administrator",
            "operator": "Warehouse Operator",
            "technical": "Technical Office",
            "viewer": "Viewer",
            "qc_inspector": "QC Inspector"
        }
        self.user_role_label = QLabel(
            f"👤 {self.current_user} ({role_display.get(self.user_role, self.user_role)})"
        )
        self.user_role_label.setStyleSheet("font-size: 11px; margin-right: 10px;")
        status.addPermanentWidget(self.user_role_label)

        # License status button
        self.buy_license_status_btn = QPushButton("🛒 Buy License")
        self.buy_license_status_btn.setStyleSheet(self._get_license_button_style())
        self.buy_license_status_btn.clicked.connect(self.on_activate_license)
        self.buy_license_status_btn.setVisible(not self._is_full_access())
        status.addPermanentWidget(self.buy_license_status_btn)

        # License status label
        self.license_status_label = QLabel(self._get_license_status_text())
        self.license_status_label.setStyleSheet(
            "font-weight: bold; font-size: 11px; margin-left: 10px;"
        )
        status.addPermanentWidget(self.license_status_label)

        # Ready indicator
        self.ready_label = QLabel("✅ System Ready")
        self.ready_label.setStyleSheet(
            "color: green; font-size: 11px; margin-left: 10px; margin-right: 10px;"
        )
        status.addPermanentWidget(self.ready_label)

        # Setup DB pulse animation
        self._setup_db_indicator_animation()

    def _setup_db_indicator_animation(self):
        """Setup pulse animation for database indicator."""
        self._db_opacity_effect = QGraphicsOpacityEffect()
        self._db_opacity_effect.setOpacity(1.0)
        self.db_indicator.setGraphicsEffect(self._db_opacity_effect)

        self._db_pulse_anim = QPropertyAnimation(self._db_opacity_effect, b"opacity")
        self._db_pulse_anim.setDuration(1200)
        self._db_pulse_anim.setStartValue(1.0)
        self._db_pulse_anim.setEndValue(0.25)
        self._db_pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._db_pulse_anim.setLoopCount(-1)

    # ==================================================================
    # Style Methods
    # ==================================================================

    def _get_menu_style(self):
        return """
            QMenuBar {
                background-color: #004D40;
                color: white;
                font-weight: bold;
                padding: 4px;
                font-size: 12px;
            }
            QMenuBar::item:selected {
                background-color: #00695C;
            }
            QMenu {
                background-color: #004D40;
                color: white;
                border: 1px solid #00695C;
            }
            QMenu::item:selected {
                background-color: #00695C;
            }
            QMenu::item:disabled {
                color: #888888;
                background-color: transparent;
            }
            QMenu::separator {
                height: 1px;
                background: #00695C;
                margin: 4px 8px;
            }
        """

    def _get_toolbar_style(self):
        return """
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
            QToolButton:hover {
                background: #B2DFDB;
            }
        """

    def _get_button_style(self):
        return """
            QPushButton {
                background-color: #00897B;
                color: white;
                border-radius: 4px;
                font-weight: bold;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #00695C;
            }
        """

    def _get_help_button_style(self):
        return """
            QPushButton {
                background-color: #E0E0E0;
                color: #333;
                border: 1px solid #CCC;
                border-radius: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
        """

    def _get_license_button_style(self):
        return """
            QPushButton {
                background-color: #FF8C00;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #FF7F50;
            }
        """

    def _get_search_frame_style(self):
        return """
            QFrame {
                background: transparent;
                margin: 0px 10px;
            }
        """

    def _get_neutral_button_style(self):
        return """
            QPushButton {
                background-color: #F5F5F5;
                color: #333;
                border: 1px solid #CCC;
                padding: 7px 10px;
                font-weight: bold;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
                border-color: #AAA;
            }
        """

    def _get_table_style(self):
        return """
            QTableWidget {
                background: white;
                gridline-color: #E0E0E0;
            }
            QTableWidget::item:selected {
                background-color: #B2EBF2;
                color: #000000;
            }
            QTableWidget::item:hover {
                background-color: #E0F7FA;
            }
            QHeaderView::section {
                background-color: #B2DFDB;
                color: #004D40;
                font-weight: bold;
                padding: 6px;
                border: none;
            }
        """

    def _get_prediction_frame_style(self):
        return "background-color: #F5FFFA; border: 1px solid #B0C4DE;"

    def _get_status_bar_style(self):
        return "QStatusBar { border-top: 1px solid #ccc; }"

    # ==================================================================
    # License & Access Control
    # ==================================================================

    def _is_full_access(self) -> bool:
        """Check if user has full license access."""
        if is_license_valid():
            return True
        try:
            session = SessionLocal()
            trial = get_trial_status(session)
            session.close()
            return trial.get('active', False)
        except Exception:
            return False

    def _get_license_status_text(self) -> str:
        """Get license status display text."""
        if is_license_valid():
            return FULL_LICENSE_STATUS
        try:
            session = SessionLocal()
            trial = get_trial_status(session)
            session.close()
            if trial['active']:
                return TRIAL_STATUS.format(days_left=trial['days_left'])
            return DEMO_STATUS
        except Exception:
            return "License unknown"

    def update_license_ui(self):
        """Update license-related UI elements."""
        full = self._is_full_access()
        self.buy_license_top_btn.setVisible(not full)
        self.buy_license_status_btn.setVisible(not full)
        self.license_status_label.setText(self._get_license_status_text())

    def _check_license_for_feature(self, feature_name: str = "This feature") -> bool:
        """Check license and prompt if not full access."""
        if self._is_full_access():
            return True
        reply = QMessageBox.question(
            self, "License Required",
            f"{feature_name} requires a full license.\n\nActivate now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.on_activate_license()
        return self._is_full_access()

    # ==================================================================
    # Search & Display Methods
    # ==================================================================

    def _on_search_text_changed(self, text: str):
        """Handle search text changes with debounce."""
        self._search_timer.start()

    def _on_filter_changed(self):
        """Handle filter combo changes."""
        self.on_search()

    def _perform_search(self):
        """Execute the search in a background thread."""
        search_text = self.search_input.text().strip()
        qc_status = self.qc_combo.currentText()
        discipline = self.discipline_combo.currentText()

        if qc_status == "All Statuses":
            qc_status = None
        if discipline == "All":
            discipline = None

        limit = None if self._is_full_access() else TRIAL_ROW_LIMIT

        self.search_thread = StockSearchThread(search_text, qc_status, discipline, limit)
        self.search_thread.finished_signal.connect(self._display_results)
        self.search_thread.progress_signal.connect(self.progress.setVisible)
        self.search_thread.start()
        self.progress.setVisible(True)

    def on_search(self):
        """Public method to trigger search."""
        self._perform_search()

    def refresh_data(self):
        """Refresh all data."""
        self._load_filter_options()
        self.on_search()

    def reset_search(self):
        """Reset all search filters."""
        self.search_input.clear()
        self.qc_combo.setCurrentText("All Statuses")
        self.discipline_combo.setCurrentText("All")
        self.on_search()

    def _load_filter_options(self):
        """Load filter dropdown options from database."""
        session = SessionLocal()
        try:
            disciplines = session.query(Product.discipline).distinct().order_by(
                Product.discipline
            ).all()
            self.discipline_combo.blockSignals(True)
            self.discipline_combo.clear()
            self.discipline_combo.addItem("All")
            for (d,) in disciplines:
                if d:
                    self.discipline_combo.addItem(d)
            self.discipline_combo.blockSignals(False)

            self.total_records = session.query(Stock).filter(
                Stock.quantity > 0
            ).count()
        except Exception as e:
            logger.error(f"Failed to load filter options: {e}")
        finally:
            session.close()

    def _display_results(self, data: List[Dict[str, Any]]):
        """Display search results in the table."""
        self.progress.setVisible(False)
        self.filtered_records = len(data) if data else 0
        self.record_count_label.setText(
            f"Records: {self.total_records} | Filtered: {self.filtered_records}"
        )

        if not data:
            self.table.setRowCount(0)
            self.statusBar().showMessage("No stock records found", 3000)
            return

        self.table.setRowCount(len(data))
        for row_idx, rec in enumerate(data):
            self.table.setItem(row_idx, 0, QTableWidgetItem(rec.get("item_code", "")))
            self.table.setItem(row_idx, 1, QTableWidgetItem(rec.get("description", "")))
            self.table.setItem(row_idx, 2, QTableWidgetItem(rec.get("discipline", "")))
            self.table.setItem(row_idx, 3, QTableWidgetItem(rec.get("material_class", "")))
            self.table.setItem(row_idx, 4, QTableWidgetItem(rec.get("heat_no", "")))
            self.table.setItem(row_idx, 5, QTableWidgetItem(rec.get("location", "")))

            # QC Status with color
            qc_item = QTableWidgetItem(rec.get("qc_status", ""))
            qc_status = rec.get("qc_status", "")
            if qc_status == "QUARANTINE":
                qc_item.setBackground(QColor("#FFE0B2"))
            elif qc_status == "ACCEPTED":
                qc_item.setBackground(QColor("#C8E6C9"))
            elif qc_status == "REJECTED":
                qc_item.setBackground(QColor("#FFCDD2"))
            self.table.setItem(row_idx, 6, qc_item)

            self.table.setItem(row_idx, 7, QTableWidgetItem(str(rec.get("total_qty", 0))))
            self.table.setItem(row_idx, 8, QTableWidgetItem(str(rec.get("allocated_qty", 0))))
            self.table.setItem(row_idx, 9, QTableWidgetItem(str(rec.get("available_qty", 0))))
            self.table.setItem(row_idx, 10, QTableWidgetItem(rec.get("preservation_due", "")))

        self.table.resizeColumnsToContents()
        self.statusBar().showMessage(f"{len(data)} records loaded", 3000)

    # ==================================================================
    # Context Menu & Table Interaction
    # ==================================================================

    def _on_table_context_menu(self, pos):
        """Show context menu on right-click."""
        row = self.table.currentRow()
        if row < 0:
            return

        item_code = self.table.item(row, 0).text()
        menu = QMenu(self)

        menu.addAction("📋 Copy Row Details", lambda: self._copy_row_details(row))
        menu.addSeparator()
        menu.addAction("📦 Edit Item", lambda: self._edit_item(item_code))
        menu.addAction("🔮 Predict Demand", lambda: self._predict_item_demand(item_code))
        menu.addSeparator()
        menu.addAction("📤 Export Selected to Excel", lambda: self._export_selected_rows())
        menu.addAction("📋 Copy Item Code", lambda: self._copy_to_clipboard(item_code))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_table_double_clicked(self, index):
        """Handle double-click on table row."""
        item_code = self.table.item(index.row(), 0).text()
        from ui.product_dialog import ProductDialog
        dlg = ProductDialog(self, item_code=item_code, user_role=self.user_role)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_data()

    def _copy_row_details(self, row: int):
        """Copy selected row details to clipboard."""
        cols = self.table.columnCount()
        lines = []
        for col in range(cols):
            header = self.table.horizontalHeaderItem(col).text()
            item = self.table.item(row, col)
            if item:
                lines.append(f"{header}: {item.text()}")
        QApplication.clipboard().setText("\n".join(lines))
        self.statusBar().showMessage("Row details copied to clipboard", 3000)

    def _edit_item(self, item_code: str):
        """Open product dialog for editing."""
        from ui.product_dialog import ProductDialog
        dlg = ProductDialog(self, item_code=item_code, user_role=self.user_role)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_data()

    def _predict_item_demand(self, item_code: str):
        """Run AI demand prediction for an item."""
        if not self._check_license_for_feature("AI Prediction"):
            return
        try:
            session = SessionLocal()
            data = load_demand_history(item_code, session)
            session.close()
            predictor = DemandPredictor(data)
            result = predictor.predict_with_confidence()
            self.prediction_value.setText(
                f"📊 {item_code}: {result['predicted_total']:.0f} units needed "
                f"(CI: {result['confidence_interval']})"
            )
        except Exception as e:
            self.prediction_value.setText("Prediction failed")
            logger.error(f"AI Prediction error: {e}")

    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage("Copied to clipboard", 3000)

    def _export_selected_rows(self):
        """Export selected rows to Excel."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select rows to export.")
            return
        self.on_export_excel()

    def get_selected_item_code(self) -> Optional[str]:
        """Get the item code of the selected row."""
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.text() if item else None

    # ==================================================================
    # Core Operation Methods
    # ==================================================================

    def on_start(self, checked: bool = False):
        """Show start dialog."""
        self._show_start_dialog()

    def show_start_dialog(self):
        """Show the start dialog."""
        if self.start_dialog:
            self.start_dialog.show()

    def _handle_start_action(self, action: str):
        """Handle actions from the start dialog."""
        actions = {
            "new_item": self.on_open_product_coding,
            "new_transaction": self.on_open_document_dialog,
            "new_material_request": self.on_new_material_request,
            "material_request_history": self.on_material_request_history,
            "qc_release": self.on_qc_release,
            "preservation": self.on_preservation_dashboard,
            "live_stock_report": self.on_live_stock_report,
        }
        handler = actions.get(action)
        if handler:
            handler()

    def on_open_product_coding(self, checked: bool = False):
        """Open the product coding dialog."""
        from ui.product_dialog import ProductDialog
        dlg = ProductDialog(self, user_role=self.user_role)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_data()

    def on_open_locations(self, checked: bool = False):
        """Open the location management dialog."""
        if not self._check_license_for_feature("Location Management"):
            return
        from ui.location_dialog import LocationDialog
        dlg = LocationDialog(self, user_role=self.user_role)
        dlg.exec()

    def on_open_document_dialog(self, checked: bool = False):
        """Open the document creation dialog."""
        allowed_roles = ["admin", "operator", "technical"]
        if self.user_role not in allowed_roles:
            QMessageBox.warning(
                self, "Access Denied",
                "Only Admin, Operator, and Technical Office can create documents."
            )
            return
        if not self._check_license_for_feature("Document Processing"):
            return
        from ui.document_dialog import DocumentDialog
        dlg = DocumentDialog(self, default_type=None, user_role=self.user_role)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_data()

    def on_open_transaction_dialog(self, checked: bool = False):
        """Open the transaction manager."""
        from ui.transaction_dialog import TransactionDialog
        dlg = TransactionDialog(self, user_role=self.user_role)
        dlg.exec()
        self.refresh_data()

    def on_new_msr(self, checked: bool = False):
        """Create new MSR document."""
        allowed_roles = ["admin", "operator", "technical"]
        if self.user_role not in allowed_roles:
            QMessageBox.warning(
                self, "Access Denied",
                "Only Admin, Operator, and Technical Office can create MSR."
            )
            return
        if not self._check_license_for_feature("MSR Creation"):
            return
        from ui.document_dialog import DocumentDialog
        dlg = DocumentDialog(self, default_type="MSR", user_role=self.user_role)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_data()

    def on_qc_release(self, checked: bool = False):
        """Open QC release dialog."""
        if self.user_role not in ["admin", "operator", "qc_inspector"]:
            QMessageBox.warning(
                self, "Access Denied",
                "Only Admin, Operator, and QC Inspector can perform QC release."
            )
            return
        from ui.qc_release_dialog import QCReleaseDialog
        dlg = QCReleaseDialog(self, user_role=self.user_role)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_data()

    def on_preservation_dashboard(self, checked: bool = False):
        """Open preservation dashboard."""
        from ui.preservation_dialog import PreservationDialog
        dlg = PreservationDialog(self, user_role=self.user_role)
        dlg.exec()

    def on_live_stock_report(self, checked: bool = False):
        """Open live stock view."""
        from ui.stock_view_dialog import StockViewDialog
        dlg = StockViewDialog(self, user_role=self.user_role)
        dlg.exec()

    def on_traceability_report(self, checked: bool = False):
        """Open traceability report."""
        self._open_reports_window("traceability")

    def on_document_history_report(self, checked: bool = False):
        """Open document history report."""
        self._open_reports_window("document_history")

    def _open_reports_window(self, report_type: str):
        """Open reports window with specified type."""
        try:
            from ui.reports_window import ReportsWindow
            win = ReportsWindow(self, report_type=report_type, user_role=self.user_role)
            win.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not generate report:\n{str(e)}")

    def on_new_material_request(self, checked: bool = False):
        """Open new material request dialog."""
        allowed_roles = ["admin", "technical"]
        if self.user_role not in allowed_roles:
            QMessageBox.warning(
                self, "Access Denied",
                "Only Admin and Technical Office can create material requests."
            )
            return
        if not self._check_license_for_feature("Material Request"):
            return
        from ui.material_request_dialog import MaterialRequestDialog
        dlg = MaterialRequestDialog(self, user_role=self.user_role)
        dlg.exec()

    def on_material_request_history(self, checked: bool = False):
        """Open material request history."""
        allowed_roles = ["admin", "technical"]
        if self.user_role not in allowed_roles:
            QMessageBox.warning(
                self, "Access Denied",
                "Only Admin and Technical Office can view material requests."
            )
            return
        from ui.material_request_history_dialog import MaterialRequestHistoryDialog
        dlg = MaterialRequestHistoryDialog(self, user_role=self.user_role)
        dlg.exec()

    def on_report_manager(self, checked: bool = False):
        """Open unified report manager."""
        from ui.report_manager import ReportManagerDialog
        dlg = ReportManagerDialog(self, user_role=self.user_role)
        dlg.exec()

    def on_expiry_monitor(self, checked: bool = False):
        """Open expiry date monitor."""
        from ui.expiry_monitor_dialog import ExpiryMonitorDialog
        dlg = ExpiryMonitorDialog(self, user_role=self.user_role)
        dlg.exec()

    def on_reorder_calculator(self, checked: bool = False):
        """Open reorder point calculator."""
        from ui.reorder_dialog import ReorderDialog
        dlg = ReorderDialog(self, user_role=self.user_role)
        dlg.exec()

    def on_ai_predict(self, checked: bool = False):
        """Run AI prediction on selected item."""
        if not self._check_license_for_feature("AI Prediction"):
            return
        item_code = self.get_selected_item_code()
        if not item_code:
            QMessageBox.warning(self, "Select Item", "Please select an item from the table first.")
            return
        self._predict_item_demand(item_code)

    def on_abc_analysis(self, checked: bool = False):
        """Open ABC analysis dialog."""
        from ui.abc_analysis_dialog import ABCAnalysisDialog
        dlg = ABCAnalysisDialog(self, user_role=self.user_role)
        dlg.exec()

    def on_optimize_eoq(self, checked: bool = False):
        """Open EOQ optimization dialog."""
        QMessageBox.information(
            self, "EOQ Calculator",
            "EOQ optimization will be available in the next version.\n\n"
            "For now, you can use the Reorder Point Calculator from the Tools menu."
        )

    def on_manage_users(self, checked: bool = False):
        """Open user management dialog."""
        if self.user_role != "admin":
            QMessageBox.warning(self, "Access Denied", "Only administrators can manage users.")
            return
        from ui.user_management_dialog import UserManagementDialog
        dlg = UserManagementDialog(self, user_role=self.user_role)
        dlg.exec()

    def on_company_project_info(self, checked: bool = False):
        """Open company/project info dialog."""
        if self.user_role != "admin":
            QMessageBox.warning(self, "Access Denied", "Only administrators can modify settings.")
            return
        from ui.user_management_dialog import UserManagementDialog
        dlg = UserManagementDialog(self, user_role=self.user_role)
        dlg.exec()

    # ==================================================================
    # Export Methods
    # ==================================================================

    def on_share_excel(self, checked: bool = False):
        """Share/export to Excel."""
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export to Excel", "", "Excel Files (*.xlsx)"
        )
        if file_path:
            headers, data = self._collect_table_data()
            export_to_excel(data, headers, file_path)
            self.statusBar().showMessage(f"Exported to {file_path}", 5000)

    def on_export_excel(self, checked: bool = False):
        """Export to Excel (menu action)."""
        self.on_share_excel()

    def on_export_pdf(self, checked: bool = False):
        """Export to PDF."""
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export to PDF", "", "PDF Files (*.pdf)"
        )
        if file_path:
            headers, data = self._collect_table_data()
            export_to_pdf(data, headers, file_path)
            self.statusBar().showMessage(f"PDF saved to {file_path}", 5000)

    def on_export_document_html(self, checked: bool = False):
        """Export a document to HTML."""
        doc_no, ok = QInputDialog.getText(
            self, "Export Document", "Enter Document Number:"
        )
        if not ok or not doc_no.strip():
            return

        session = SessionLocal()
        try:
            doc = session.query(Document).filter_by(doc_no=doc_no.strip()).first()
            if not doc:
                QMessageBox.warning(self, "Not Found", f"Document '{doc_no}' not found.")
                return

            header = {
                "doc_no": doc.doc_no,
                "doc_type": doc.doc_type,
                "doc_date": str(doc.doc_date),
                "po_no": doc.po_no or "",
                "reference_no": doc.reference_no or "",
                "remarks": doc.remarks or "",
                "created_by": doc.created_by or "",
                "created_at": str(doc.created_at) if doc.created_at else "",
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "from_location_id": str(doc.from_location_id or ""),
                "to_location_id": str(doc.to_location_id or ""),
            }
            lines = [{
                "item_code": l.item_code,
                "heat_no": l.heat_no or "",
                "location_id": l.location_id,
                "qty": l.qty,
                "unit": l.unit or "EA",
                "iso_drawing_no": l.iso_drawing_no or "",
            } for l in doc.lines]

            html_content = export_document_to_html(header, lines)

            choice_dlg = QDialog(self)
            choice_dlg.setWindowTitle("Export Options")
            layout = QVBoxLayout(choice_dlg)
            layout.addWidget(QLabel(f"Document {doc_no} is ready. Choose an action:"))

            btn_preview = QPushButton("🌐 Preview in Browser")
            btn_save = QPushButton("💾 Save as HTML File")
            btn_cancel = QPushButton("Cancel")

            def on_preview():
                preview_html_in_browser(html_content)
                self.statusBar().showMessage("Document opened in browser", 5000)
                choice_dlg.accept()

            def on_save():
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "Save HTML", f"{doc_no}.html", "HTML Files (*.html)"
                )
                if file_path:
                    save_html_to_file(html_content, file_path)
                    self.statusBar().showMessage(f"Exported to {file_path}", 5000)
                choice_dlg.accept()

            btn_preview.clicked.connect(on_preview)
            btn_save.clicked.connect(on_save)
            btn_cancel.clicked.connect(choice_dlg.reject)

            layout.addWidget(btn_preview)
            layout.addWidget(btn_save)
            layout.addWidget(btn_cancel)
            choice_dlg.exec()

        except Exception as e:
            logger.exception("Export HTML failed")
            QMessageBox.critical(self, "Error", f"Could not export document:\n{str(e)}")
        finally:
            session.close()

    def _collect_table_data(self):
        """Collect table data for export."""
        headers = [
            self.table.horizontalHeaderItem(c).text()
            for c in range(self.table.columnCount())
        ]
        data = []
        for r in range(self.table.rowCount()):
            row_dict = {}
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                row_dict[headers[c]] = item.text() if item else ""
            data.append(row_dict)
        return headers, data

    # ==================================================================
    # Barcode Methods
    # ==================================================================

    def on_toggle_barcode(self, checked: bool):
        """Toggle barcode reader dialog."""
        if checked:
            from ui.barcode_dialog import BarcodeDialog
            self.barcode_dialog = BarcodeDialog(self, parent=self, user_role=self.user_role)
            self.barcode_dialog.show()
            self.action_barcode.setText("📷 Disconnect Barcode Reader")
        else:
            if self.barcode_dialog:
                self.barcode_dialog.close()
                self.barcode_dialog = None
            self.action_barcode.setText("📷 Connect Barcode Reader")

    # ==================================================================
    # License & System Methods
    # ==================================================================

    def on_activate_license(self, checked: bool = False):
        """Open license activation dialog."""
        from ui.license_dialog import LicenseDialog
        dlg = LicenseDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.update_license_ui()

    def on_change_database(self, checked: bool = False):
        """Change active database file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Database", "", "SQLite Database (*.db);;All Files (*)"
        )
        if file_path:
            from db.database import change_database
            if change_database(file_path):
                self.DB_PATH = file_path
                self.db_path_label.setText(f"DB: {file_path}")
                self.refresh_data()
                QMessageBox.information(self, "Success", "Database changed successfully.")

    def on_backup_now(self, checked: bool = False):
        """Create a manual backup."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Backup Database", "aimat_backup.db", "SQLite Database (*.db)"
        )
        if file_path:
            result = backup_database(file_path)
            if result:
                QMessageBox.information(
                    self, "Backup Complete",
                    f"Database backed up to:\n{result}"
                )
            else:
                QMessageBox.critical(self, "Backup Failed", "Could not create backup.")

    def on_auto_backup_settings(self, checked: bool = False):
        """Open auto-backup settings."""
        from ui.auto_backup_dialog import AutoBackupDialog
        dlg = AutoBackupDialog(self)
        dlg.exec()

    def on_settings(self, checked: bool = False):
        """Open settings dialog."""
        QMessageBox.information(
            self, "Settings",
            "Settings dialog will be implemented in the next version.\n\n"
            "For now, you can configure:\n"
            "• Company & Project Info (Teamwork menu)\n"
            "• Auto-Backup Settings (System menu)\n"
            "• Theme toggle (Toolbar)"
        )

    def on_share_database(self, checked: bool = False):
        """Share database file."""
        QMessageBox.information(
            self, "Share Database",
            f"Database location:\n{self.DB_PATH}\n\n"
            "You can copy this file to share or backup."
        )

    def on_open_help(self, checked: bool = False):
        """Open user manual in browser."""
        help_path = os.path.join(
            os.path.dirname(__file__), '..', 'resources', 'help_fa.html'
        )
        if os.path.exists(help_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(help_path)))
        else:
            QMessageBox.information(
                self, "Help",
                "Help file not found.\n\n"
                "Visit: www.imat.io\n"
                "WhatsApp: +98 916 068 4552"
            )

    def on_quick_guide(self, checked: bool = False):
        """Show quick start guide."""
        QMessageBox.information(
            self, "Quick Start Guide",
            "1️⃣ Create Admin Account on first launch\n"
            "2️⃣ Set up Material Coding (Item Codes)\n"
            "3️⃣ Define Warehouse Locations\n"
            "4️⃣ Create Documents (MRR, MIV, MSR, OS&D)\n"
            "5️⃣ Process Transactions\n"
            "6️⃣ Use AI Tools for optimization\n\n"
            "📖 Full manual: Help → User Manual\n"
            "💬 Support: WhatsApp +98 916 068 4552"
        )

    def on_about(self, checked: bool = False):
        """Show about dialog."""
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h2>{APP_NAME} v{APP_VERSION}</h2>"
            f"<p>Intelligent Material Control System</p>"
            f"<p><i>Where Inventory Meets AI</i></p>"
            f"<hr>"
            f"<p>🌐 <a href='https://www.imat.io'>www.imat.io</a></p>"
            f"<p>💬 WhatsApp: +98 916 068 4552</p>"
            f"<p>📧 support@imat.io</p>"
            f"<hr>"
            f"<p>© 2025 iMat International</p>"
        )

    # ==================================================================
    # Theme Methods
    # ==================================================================

    def _apply_theme(self):
        """Apply the current theme."""
        theme_path = os.path.join(
            os.path.dirname(__file__), '..', 'config', 'theme_config.json'
        )
        if os.path.exists(theme_path):
            try:
                with open(theme_path, 'r', encoding='utf-8') as f:
                    themes = json.load(f)
                theme = themes.get(self.current_theme, themes.get("light", {}))

                palette = self.palette()
                bg = QColor(theme.get("bg", "#f5f5f5"))
                fg = QColor(theme.get("fg", "#212121"))

                palette.setColor(QPalette.ColorRole.Window, bg)
                palette.setColor(QPalette.ColorRole.WindowText, fg)
                palette.setColor(QPalette.ColorRole.Base, QColor(theme.get("input_bg", "#ffffff")))
                palette.setColor(QPalette.ColorRole.Text, QColor(theme.get("input_fg", "#000000")))
                palette.setColor(QPalette.ColorRole.Button, QColor(theme.get("button_bg", "#e0e0e0")))
                palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme.get("button_fg", "#000000")))
                palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.get("highlight", "#4CAF50")))

                self.setPalette(palette)
            except Exception as e:
                logger.error(f"Failed to apply theme: {e}")

    def _toggle_theme(self):
        """Toggle between light and dark themes."""
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        config.set('default_theme', self.current_theme)
        config.save_json()
        self._apply_theme()

    # ==================================================================
    # Database Connection Methods
    # ==================================================================

    def check_db_connection(self):
        """Check database connection status."""
        try:
            session = SessionLocal()
            connection = session.get_bind().connect()
            connection.close()
            self.total_records = session.query(Stock).count()
            session.close()

            self.db_indicator.setStyleSheet(
                "background-color: #4CAF50; border-radius: 4px; border: 1px solid #388E3C;"
            )

            if self._db_pulse_anim and self._db_pulse_anim.state() != QPropertyAnimation.State.Running:
                self._db_pulse_anim.start()

            self.ready_label.setText("✅ System Ready")
            self.ready_label.setStyleSheet(
                "color: green; font-size: 11px; margin-left: 10px; margin-right: 10px;"
            )
        except Exception:
            if self._db_pulse_anim and self._db_pulse_anim.state() == QPropertyAnimation.State.Running:
                self._db_pulse_anim.stop()
            if self._db_opacity_effect:
                self._db_opacity_effect.setOpacity(1.0)

            self.db_indicator.setStyleSheet(
                "background-color: #F44336; border-radius: 4px; border: 1px solid #C62828;"
            )
            self.ready_label.setText("❌ DB Error")
            self.ready_label.setStyleSheet(
                "color: red; font-size: 11px; margin-left: 10px; margin-right: 10px;"
            )

    # ==================================================================
    # ✅ NEW: Inventory Assistant Methods
    # ==================================================================

    def on_open_assistant(self, checked: bool = False):
        """Open the offline inventory assistant dialog."""
        dlg = AssistantDialog(self)
        dlg.exec()

    # ==================================================================
    # Close Event
    # ==================================================================

    def closeEvent(self, event):
        """Handle application close."""
        if config.get('ui.confirm_on_exit', True):
            reply = QMessageBox.question(
                self, "Exit iMat",
                "Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        if self._db_timer:
            self._db_timer.stop()
        if self._search_timer:
            self._search_timer.stop()

        event.accept()


# ==================================================================
# Background Search Thread
# ==================================================================

class StockSearchThread(QThread):
    """Background thread for searching inventory."""
    finished_signal = pyqtSignal(list)
    progress_signal = pyqtSignal(bool)

    def __init__(self, search_text: str, qc_status: Optional[str],
                 discipline: Optional[str], limit: Optional[int] = None):
        super().__init__()
        self.search_text = search_text
        self.qc_status = qc_status
        self.discipline = discipline
        self.limit = limit

    def run(self):
        """Execute the search query."""
        self.progress_signal.emit(True)
        results = []
        try:
            session = SessionLocal()
            query = session.query(
                Stock.item_code,
                Product.description,
                Product.discipline,
                Product.material_class,
                Stock.heat_no,
                Location.code.label("loc_code"),
                Stock.qc_status,
                Stock.quantity.label("total_qty"),
                Stock.allocated_qty,
                Stock.next_preservation_due
            ).join(Product, Stock.item_code == Product.item_code)\
             .join(Location, Stock.location_id == Location.id)\
             .filter(Stock.quantity > 0)

            if self.search_text:
                sf = f"%{self.search_text}%"
                query = query.filter(
                    or_(
                        Stock.item_code.ilike(sf),
                        Product.description.ilike(sf),
                        Stock.heat_no.ilike(sf),
                        Location.code.ilike(sf)
                    )
                )
            if self.qc_status:
                query = query.filter(Stock.qc_status == self.qc_status)
            if self.discipline:
                query = query.filter(Product.discipline == self.discipline)

            query = query.order_by(Stock.item_code)
            if self.limit:
                query = query.limit(self.limit)

            for r in query.all():
                results.append({
                    "item_code": r.item_code,
                    "description": r.description or "",
                    "discipline": r.discipline or "",
                    "material_class": r.material_class or "",
                    "heat_no": r.heat_no,
                    "location": r.loc_code,
                    "qc_status": r.qc_status,
                    "total_qty": r.total_qty or 0,
                    "allocated_qty": r.allocated_qty or 0,
                    "available_qty": (r.total_qty or 0) - (r.allocated_qty or 0),
                    "preservation_due": str(r.next_preservation_due) if r.next_preservation_due else "Not Required",
                })
            session.close()
        except Exception as e:
            logger.exception(f"Search thread error: {e}")
        finally:
            self.finished_signal.emit(results)