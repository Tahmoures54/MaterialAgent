"""
MainWindow UI Builder (EPC Material Control Edition).
Handles all UI construction for the main application window.
This is the UI builder class used by MainWindow for separation of concerns.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QComboBox, QLabel, QProgressBar,
    QTableWidget, QStatusBar, QFrame, QMenu,
    QGraphicsDropShadowEffect, QHeaderView,
    QToolBar, QToolButton, QSizePolicy,
    QSpacerItem, QApplication, QStyle, QMessageBox
)
from PyQt6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont, QAction, QPalette, QIcon
from ui.logo_widget import LogoWidget


class MainWindowUIBuilder:
    """
    Builder class for MainWindow UI components.
    Separates UI construction from business logic.
    """

    # ==================================================================
    # Style Constants
    # ==================================================================
    
    STYLE = {
        "menubar": """
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
        """,
        
        "toolbar": """
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
                font-size: 11px;
            }
            QToolButton:hover {
                background: #B2DFDB;
            }
            QToolButton:pressed {
                background: #80CBC4;
            }
        """,
        
        "add_button": """
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
        """,
        
        "help_button": """
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
        """,
        
        "license_button": """
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
        """,
        
        "search_frame": """
            QFrame {
                background: transparent;
                margin: 0px 10px;
            }
        """,
        
        "neutral_button": """
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
        """,
        
        "danger_button": """
            QPushButton {
                background-color: #D9534F;
                color: white;
                border: none;
                padding: 7px 10px;
                font-weight: bold;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #C9302C;
            }
        """,
        
        "success_button": """
            QPushButton {
                background-color: #5CB85C;
                color: white;
                border: none;
                padding: 7px 10px;
                font-weight: bold;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #449D44;
            }
        """,
        
        "prediction_frame": """
            QFrame {
                background-color: #F5FFFA;
                border: 1px solid #B0C4DE;
                border-top: 2px solid #B2DFDB;
            }
        """,
        
        "status_bar": """
            QStatusBar {
                background: #ECEFF1;
                border-top: 1px solid #CFD8DC;
                font-size: 10px;
            }
        """,
        
        "db_indicator_offline": """
            QLabel {
                background-color: #FF0000;
                border-radius: 4px;
                border: 1px solid #8B0000;
            }
        """,
        
        "db_indicator_online": """
            QLabel {
                background-color: #4CAF50;
                border-radius: 4px;
                border: 1px solid #388E3C;
            }
        """,
        
        "table": """
            QTableWidget {
                background: white;
                gridline-color: #E0E0E0;
                font-size: 11px;
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
                font-size: 11px;
            }
        """,
        
        "input_style": """
            QLineEdit {
                border: 1px solid #B0BEC5;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 2px solid #004D40;
                background-color: #FAFAFA;
            }
        """,
        
        "combo_style": """
            QComboBox {
                border: 1px solid #B0BEC5;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
                background-color: white;
                min-width: 120px;
            }
            QComboBox:focus {
                border: 2px solid #004D40;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #B0BEC5;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 1px solid #B0BEC5;
                selection-background-color: #004D40;
                selection-color: white;
            }
        """,
    }

    # ==================================================================
    # Constructor
    # ==================================================================

    def __init__(self, main_window):
        """
        Initialize the UI builder.
        
        Args:
            main_window: Reference to the MainWindow instance
        """
        self.mw = main_window

    # ==================================================================
    # Main Build Method
    # ==================================================================

    def build(self) -> None:
        """Build the complete main window UI."""
        central = QWidget()
        self.mw.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Build all components in order
        self._build_menubar()
        self._build_top_bar(main_layout)
        self._build_search_panel(main_layout)
        self._build_progress_bar(main_layout)
        self._build_main_table(main_layout)
        self._build_prediction_bar(main_layout)
        self._build_statusbar()

    # ==================================================================
    # Menu Bar Construction
    # ==================================================================

    def _build_menubar(self) -> None:
        """Build the role-based menu bar."""
        mw = self.mw
        menubar = mw.menuBar()
        menubar.setStyleSheet(self.STYLE["menubar"])

        # ===== System Menu =====
        sys_menu = menubar.addMenu("⚙️ &System")
        self._add_action(sys_menu, "📂 Change Database...", mw.on_change_database,
                        ["admin"], "Switch to a different database file")
        self._add_action(sys_menu, "💾 Backup Now", mw.on_backup_now,
                        ["admin"], "Create a manual backup of the database")
        self._add_action(sys_menu, "⚙️ Auto‑Backup Settings...", mw.on_auto_backup_settings,
                        ["admin"], "Configure automatic backup settings")
        sys_menu.addSeparator()
        mw.action_settings = self._add_action(sys_menu, "&Settings", mw.on_settings,
                                              ["admin"], "Application settings")
        sys_menu.addSeparator()
        self._add_action(sys_menu, "E&xit", mw.close,
                        ["admin", "operator", "technical", "qc_inspector", "viewer"],
                        "Exit the application")

        # ===== Material Control Menu =====
        mat_menu = menubar.addMenu("📦 &Material Control")
        self._add_action(mat_menu, "📦 Material Coding (Products)", 
                        mw.on_open_product_coding,
                        ["admin", "operator", "technical"],
                        "Manage item codes, descriptions, disciplines, and units")
        self._add_action(mat_menu, "🏢 Warehouse & Locations", 
                        mw.on_open_locations,
                        ["admin", "operator"],
                        "Manage warehouse structure and locations")
        mat_menu.addSeparator()
        self._add_action(mat_menu, "📄 New Document (MRR/MIV/MSR/OS&D)", 
                        mw.on_open_document_dialog,
                        ["admin", "operator", "technical"],
                        "Create material receipt, issue, requisition or damage report")
        self._add_action(mat_menu, "📋 Transactions Manager", 
                        mw.on_open_transaction_dialog,
                        ["admin", "operator", "technical"],
                        "View and manage all transactions")
        mat_menu.addSeparator()
        self._add_action(mat_menu, "⌛ Expiry Date Monitor", 
                        mw.on_expiry_monitor,
                        ["admin", "operator", "technical", "qc_inspector"],
                        "Track items approaching or past their expiry date")
        self._add_action(mat_menu, "📊 Reorder Point Calculator", 
                        mw.on_reorder_calculator,
                        ["admin", "operator", "technical"],
                        "Calculate safety stock and reorder points")

        # ===== Technical Office Menu =====
        tech_menu = menubar.addMenu("📐 &Technical Office")
        self._add_action(tech_menu, "📋 New Material Request (MR)", 
                        mw.on_new_material_request,
                        ["admin", "technical"],
                        "Create a new material request")
        self._add_action(tech_menu, "📄 MR History", 
                        mw.on_material_request_history,
                        ["admin", "technical"],
                        "View material request history")
        tech_menu.addSeparator()
        self._add_action(tech_menu, "📄 MSR History", 
                        lambda: mw._open_reports_window("msr_history"),
                        ["admin", "technical"],
                        "View material store requisition history")
        tech_menu.addSeparator()
        self._add_action(tech_menu, "📊 Live Stock Dashboard", 
                        mw.on_live_stock_report,
                        ["admin", "technical", "operator", "qc_inspector", "viewer"],
                        "View real-time stock levels")
        self._add_action(tech_menu, "🔗 Material Traceability", 
                        mw.on_traceability_report,
                        ["admin", "technical", "operator", "qc_inspector", "viewer"],
                        "Trace material by heat number")

        # ===== Quality Control Menu =====
        qc_menu = menubar.addMenu("✅ &Quality Control")
        self._add_action(qc_menu, "🔍 QC Release (Quarantine → Accepted)", 
                        mw.on_qc_release,
                        ["admin", "operator", "qc_inspector"],
                        "Release materials from quarantine")
        self._add_action(qc_menu, "🛡️ Preservation Dashboard", 
                        mw.on_preservation_dashboard,
                        ["admin", "operator", "qc_inspector"],
                        "Monitor preservation schedules")
        self._add_action(qc_menu, "⌛ Expiry Date Monitor", 
                        mw.on_expiry_monitor,
                        ["admin", "operator", "qc_inspector"],
                        "Track items approaching or past expiry")

        # ===== Reports & Export Menu =====
        reports_menu = menubar.addMenu("📊 &Reports & Export")
        self._add_action(reports_menu, "📊 Report Manager", 
                        mw.on_report_manager,
                        ["admin", "operator", "technical", "qc_inspector", "viewer"],
                        "Open the unified reports and export center")
        reports_menu.addSeparator()
        mw.action_export_excel = self._add_action(reports_menu, 
                                                  "📥 Export Stock Table to Excel", 
                                                  mw.on_export_excel,
                                                  ["admin", "operator", "technical", "qc_inspector"],
                                                  "Export current view to Excel")
        mw.action_export_pdf = self._add_action(reports_menu, 
                                                "📑 Export Stock Table to PDF", 
                                                mw.on_export_pdf,
                                                ["admin", "operator", "technical", "qc_inspector"],
                                                "Export current view to PDF")
        self._add_action(reports_menu, "📄 Export Document to HTML", 
                        mw.on_export_document_html,
                        ["admin", "operator", "technical"],
                        "Export a document to HTML format")
        self._add_action(reports_menu, "📄 Document History Report", 
                        mw.on_document_history_report,
                        ["admin", "operator", "technical", "qc_inspector", "viewer"],
                        "View document history")

        # ===== Tools Menu =====
        tools_menu = menubar.addMenu("🛠️ &Tools")
        self._add_action(tools_menu, "🔮 AI Demand Prediction", 
                        mw.on_ai_predict,
                        ["admin", "operator", "technical"],
                        "Predict future demand using AI")
        self._add_action(tools_menu, "📊 ABC Analysis", 
                        mw.on_abc_analysis,
                        ["admin", "operator", "technical"],
                        "Classify inventory by importance")
        self._add_action(tools_menu, "📈 EOQ Calculator", 
                        mw.on_optimize_eoq,
                        ["admin", "operator", "technical"],
                        "Calculate Economic Order Quantity")
        self._add_action(tools_menu, "📊 Reorder Point Calculator", 
                        mw.on_reorder_calculator,
                        ["admin", "operator", "technical"],
                        "Calculate safety stock and reorder points")
        tools_menu.addSeparator()
        mw.action_barcode = self._add_action(tools_menu, "📷 Connect Barcode Reader", 
                                             mw.on_toggle_barcode,
                                             ["admin", "operator", "technical", "qc_inspector"],
                                             "Toggle barcode scanner")
        mw.action_barcode.setCheckable(True)

        # ===== Teamwork Menu =====
        team_menu = menubar.addMenu("👥 &Teamwork")
        self._add_action(team_menu, "👤 Manage Users & Roles", 
                        mw.on_manage_users,
                        ["admin"],
                        "Add, edit, or deactivate users")
        team_menu.addSeparator()
        self._add_action(team_menu, "🏢 Company & Project Info", 
                        mw.on_company_project_info,
                        ["admin"],
                        "Configure company and project information")

        # ===== Help Menu =====
        help_menu = menubar.addMenu("❓ &Help")
        self._add_action(help_menu, "📖 User Manual", 
                        mw.on_open_help,
                        ["admin", "operator", "technical", "qc_inspector", "viewer"],
                        "Open the user manual and documentation")
        self._add_action(help_menu, "📋 Quick Start Guide", 
                        mw.on_quick_guide,
                        ["admin", "operator", "technical", "qc_inspector", "viewer"],
                        "View quick start guide")
        help_menu.addSeparator()
        self._add_action(help_menu, "🔑 License Management", 
                        mw.on_activate_license,
                        ["admin", "operator", "technical", "qc_inspector", "viewer"],
                        "Activate or manage your license")
        self._add_action(help_menu, "ℹ️ &About", 
                        mw.on_about,
                        ["admin", "operator", "technical", "qc_inspector", "viewer"],
                        "About iMat")

    def _add_action(self, menu, text, handler, allowed_roles, tooltip=""):
        """
        Add a role-restricted action to a menu.
        
        Args:
            menu: QMenu to add action to
            text: Display text
            handler: Callback function
            allowed_roles: List of roles that can access this action
            tooltip: Optional tooltip text
        
        Returns:
            QAction object
        """
        action = QAction(text, self.mw)
        action.triggered.connect(handler)
        
        if self.mw.user_role not in allowed_roles:
            action.setEnabled(False)
            role_list = ', '.join(allowed_roles)
            action.setToolTip(f"Requires role: {role_list}. {tooltip}")
        else:
            if tooltip:
                action.setToolTip(tooltip)
        
        menu.addAction(action)
        return action

    # ==================================================================
    # Top Bar Construction (logo + New Item + Buy License)
    # ==================================================================

    def _build_top_bar(self, parent_layout: QVBoxLayout) -> None:
        """Build the top toolbar area with logo and New Item button."""
        mw = self.mw
        
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(10, 8, 10, 8)
        top_bar.setSpacing(8)

        # Logo widget
        mw.logo_widget = LogoWidget()
        top_bar.addWidget(mw.logo_widget)
        top_bar.addStretch()

        # New Item button
        btn_new_item = QPushButton("📦 New Item")
        btn_new_item.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new_item.setStyleSheet(self.STYLE["add_button"])
        btn_new_item.setToolTip("Add a new item to the coding")
        btn_new_item.clicked.connect(mw.on_open_product_coding)
        top_bar.addWidget(btn_new_item)

        # Buy License button (only visible if not full access)
        mw.buy_license_top_btn = QPushButton("🛒 Buy License")
        mw.buy_license_top_btn.setStyleSheet(self.STYLE["license_button"])
        mw.buy_license_top_btn.clicked.connect(mw.on_activate_license)
        mw.buy_license_top_btn.setVisible(not mw._is_full_access())
        top_bar.addWidget(mw.buy_license_top_btn)

        parent_layout.addLayout(top_bar)

    # ==================================================================
    # Search Panel Construction
    # ==================================================================

    def _build_search_panel(self, parent_layout: QVBoxLayout) -> None:
        """Build the search and filter panel with action buttons."""
        mw = self.mw
        
        search_frame = QFrame()
        search_frame.setStyleSheet(self.STYLE["search_frame"])
        frame_layout = QHBoxLayout(search_frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)
        frame_layout.setSpacing(10)

        # Search input
        lbl_search = QLabel("🔍 Search:")
        lbl_search.setStyleSheet("font-weight: bold; color: #333;")
        frame_layout.addWidget(lbl_search)
        
        mw.search_input = QLineEdit()
        mw.search_input.setPlaceholderText(
            "Quick Search: Item Code, Heat No, Description, Location..."
        )
        mw.search_input.setMinimumWidth(300)
        mw.search_input.setClearButtonEnabled(True)
        mw.search_input.setStyleSheet(self.STYLE["input_style"])
        frame_layout.addWidget(mw.search_input)

        # QC Status filter
        lbl_qc = QLabel("QC Status:")
        lbl_qc.setStyleSheet("font-weight: bold; color: #333; margin-left: 10px;")
        frame_layout.addWidget(lbl_qc)
        
        mw.qc_combo = QComboBox()
        mw.qc_combo.addItems(["All Statuses", "QUARANTINE", "ACCEPTED", "REJECTED"])
        mw.qc_combo.setToolTip("Filter by Quality Control Status")
        mw.qc_combo.setStyleSheet(self.STYLE["combo_style"])
        frame_layout.addWidget(mw.qc_combo)

        # Discipline filter
        lbl_disc = QLabel("Discipline:")
        lbl_disc.setStyleSheet("font-weight: bold; color: #333; margin-left: 10px;")
        frame_layout.addWidget(lbl_disc)
        
        mw.discipline_combo = QComboBox()
        mw.discipline_combo.setToolTip("Filter by Engineering Discipline")
        mw.discipline_combo.setStyleSheet(self.STYLE["combo_style"])
        frame_layout.addWidget(mw.discipline_combo)

        # ---- New Document button (small +) ----
        mw.start_btn = QPushButton("+")
        mw.start_btn.setFixedSize(28, 28)
        mw.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mw.start_btn.setStyleSheet("""
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
        mw.start_btn.setToolTip("Create a new MRR, MIV, MSR or OS&D document")
        mw.start_btn.clicked.connect(mw.on_open_document_dialog)
        frame_layout.addWidget(mw.start_btn)

        # Help button
        help_btn = QPushButton("?")
        help_btn.setFixedSize(28, 28)
        help_btn.setToolTip("Quick usage guide")
        help_btn.setStyleSheet(self.STYLE["help_button"])
        help_btn.clicked.connect(mw.on_quick_guide)
        frame_layout.addWidget(help_btn)

        # ---- Original search action buttons ----
        reset_btn = QPushButton("🔄 Reset")
        refresh_btn = QPushButton("↻ Refresh")
        mw.share_btn = QPushButton("📤 Share Data")

        for btn in (reset_btn, refresh_btn, mw.share_btn):
            btn.setStyleSheet(self.STYLE["neutral_button"])
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        reset_btn.clicked.connect(mw.reset_search)
        reset_btn.setToolTip("Clear all filters")
        
        refresh_btn.clicked.connect(mw.refresh_data)
        refresh_btn.setToolTip("Refresh data from database")
        
        mw.share_btn.clicked.connect(mw.on_share_excel)
        mw.share_btn.setToolTip("Export current view to Excel")

        frame_layout.addWidget(reset_btn)
        frame_layout.addWidget(refresh_btn)
        frame_layout.addWidget(mw.share_btn)
        frame_layout.addStretch()

        parent_layout.addWidget(search_frame)

    # ==================================================================
    # Progress Bar Construction
    # ==================================================================

    def _build_progress_bar(self, parent_layout: QVBoxLayout) -> None:
        """Build the progress bar."""
        self.mw.progress = QProgressBar()
        self.mw.progress.setVisible(False)
        self.mw.progress.setMaximumHeight(4)
        self.mw.progress.setTextVisible(False)
        self.mw.progress.setStyleSheet("""
            QProgressBar {
                background-color: #E0E0E0;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #004D40;
                border-radius: 2px;
            }
        """)
        parent_layout.addWidget(self.mw.progress)

    # ==================================================================
    # Main Table Construction
    # ==================================================================

    def _build_main_table(self, parent_layout: QVBoxLayout) -> None:
        """Build the main data table."""
        mw = self.mw
        
        mw.table = QTableWidget()
        mw.table.setAlternatingRowColors(True)
        mw.table.setSortingEnabled(True)
        mw.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        mw.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        mw.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        mw.table.verticalHeader().setVisible(False)
        mw.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        mw.table.setStyleSheet(self.STYLE["table"])

        # Column headers
        headers = [
            "Item Code", "Description", "Discipline", "Material Class",
            "Heat No / Batch", "Location", "QC Status",
            "Total Qty", "Allocated Qty", "Available Qty",
            "Preservation Due"
        ]
        mw.table.setColumnCount(len(headers))
        mw.table.setHorizontalHeaderLabels(headers)
        
        # Configure header
        header_view = mw.table.horizontalHeader()
        header_view.setStretchLastSection(True)
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        # Set initial column widths
        column_widths = {
            0: 120,   # Item Code
            1: 200,   # Description
            2: 100,   # Discipline
            3: 120,   # Material Class
            4: 130,   # Heat No
            5: 120,   # Location
            6: 100,   # QC Status
            7: 80,    # Total Qty
            8: 80,    # Allocated Qty
            9: 80,    # Available Qty
            10: 130,  # Preservation Due
        }
        for col, width in column_widths.items():
            mw.table.setColumnWidth(col, width)

        parent_layout.addWidget(mw.table)

    # ==================================================================
    # Prediction Bar Construction
    # ==================================================================

    def _build_prediction_bar(self, parent_layout: QVBoxLayout) -> None:
        """Build the AI prediction bar at the bottom."""
        mw = self.mw
        
        pred_frame = QFrame()
        pred_frame.setFrameShape(QFrame.Shape.StyledPanel)
        pred_frame.setStyleSheet(self.STYLE["prediction_frame"])
        pred_layout = QHBoxLayout(pred_frame)
        pred_layout.setContentsMargins(10, 5, 10, 5)

        pred_title = QLabel("🔮 AI Insights:")
        pred_title.setStyleSheet("font-weight: bold; color: #006666;")
        mw.prediction_value = QLabel("Select a material to predict demand...")
        mw.prediction_value.setStyleSheet("color: #333; font-style: italic;")

        pred_layout.addWidget(pred_title)
        pred_layout.addWidget(mw.prediction_value, 1)
        pred_layout.addStretch()
        parent_layout.addWidget(pred_frame)

    # ==================================================================
    # Status Bar Construction
    # ==================================================================

    def _build_statusbar(self) -> None:
        """Build the status bar with indicators."""
        mw = self.mw
        
        mw.setStatusBar(QStatusBar())
        status = mw.statusBar()
        status.setStyleSheet(self.STYLE["status_bar"])
        status.setSizeGripEnabled(True)

        # ---- Left side: Database indicator and path ----
        left_widget = QWidget()
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        # DB connection indicator (colored dot)
        indicator_container = QWidget()
        indicator_container.setFixedWidth(12)
        container_layout = QHBoxLayout(indicator_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        mw.db_indicator = QLabel("●")
        mw.db_indicator.setFixedSize(8, 8)
        mw.db_indicator.setToolTip("Database connection status")
        mw.db_indicator.setStyleSheet(self.STYLE["db_indicator_offline"])
        mw.db_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(mw.db_indicator)
        left_layout.addWidget(indicator_container)

        # DB Path label
        db_loc_label = QLabel("DB:")
        db_loc_label.setStyleSheet("color: #555; font-size: 11px; font-weight: bold;")
        left_layout.addWidget(db_loc_label)

        mw.db_path_label = QLabel(mw.DB_PATH)
        mw.db_path_label.setStyleSheet("color: #555; font-size: 11px;")
        mw.db_path_label.setToolTip("Database file location")
        left_layout.addWidget(mw.db_path_label)

        status.addWidget(left_widget)

        # ---- Center: Record count ----
        mw.record_count_label = QLabel("Records: 0 | Filtered: 0")
        mw.record_count_label.setStyleSheet(
            "color: #333; font-size: 11px; margin-left: 20px;"
        )
        status.addWidget(mw.record_count_label)

        # ---- Spacer ----
        status.addPermanentWidget(QWidget(), 1)

        # ---- Right side: User info, License, Ready indicator ----
        
        # User role
        role_display = {
            "admin": "Administrator",
            "operator": "Warehouse Operator",
            "technical": "Technical Office",
            "viewer": "Viewer",
            "qc_inspector": "QC Inspector"
        }
        role_name = role_display.get(mw.user_role, mw.user_role)
        mw.user_role_label = QLabel(f"👤 {mw.current_user} ({role_name})")
        mw.user_role_label.setStyleSheet("font-size: 11px; margin-right: 10px;")
        status.addPermanentWidget(mw.user_role_label)

        # License button
        mw.buy_license_status_btn = QPushButton("🛒 Buy License")
        mw.buy_license_status_btn.setStyleSheet(self.STYLE["license_button"])
        mw.buy_license_status_btn.clicked.connect(mw.on_activate_license)
        mw.buy_license_status_btn.setVisible(not mw._is_full_access())
        status.addPermanentWidget(mw.buy_license_status_btn)

        # License status
        mw.license_status_label = QLabel()
        mw.license_status_label.setStyleSheet(
            "font-weight: bold; font-size: 11px; margin-left: 10px;"
        )
        status.addPermanentWidget(mw.license_status_label)

        # Ready indicator
        mw.ready_label = QLabel("✅ System Ready")
        mw.ready_label.setStyleSheet(
            "color: green; font-size: 11px; margin-left: 10px; margin-right: 10px;"
        )
        status.addPermanentWidget(mw.ready_label)

        # Setup database check timer
        mw.db_timer = QTimer(mw)
        mw.db_timer.timeout.connect(mw.check_db_connection)
        mw.db_timer.start(5000)  # Check every 5 seconds

    # ==================================================================
    # Context Menu Builder
    # ==================================================================

    def build_context_menu(self, pos, item_code: str, row: int) -> QMenu:
        """
        Build context menu for table right-click.
        
        Args:
            pos: Click position
            item_code: Selected item code
            row: Selected row index
            
        Returns:
            QMenu object
        """
        mw = self.mw
        menu = QMenu(mw)
        menu.setStyleSheet(self.STYLE["menubar"])
        
        # Copy actions
        menu.addAction("📋 Copy Row Details", lambda: mw._copy_row_details(row))
        menu.addAction("📋 Copy Item Code", lambda: mw._copy_to_clipboard(item_code))
        menu.addSeparator()
        
        # Item actions
        menu.addAction("📦 Edit Item in Coding", lambda: mw._edit_item(item_code))
        menu.addAction("🔮 Predict Demand for This Item", lambda: mw._predict_item_demand(item_code))
        menu.addSeparator()
        
        # Export actions
        menu.addAction("📤 Export Selected Rows to Excel", lambda: mw._export_selected_rows())
        menu.addAction("📑 Export All to PDF", mw.on_export_pdf)
        
        return menu

    # ==================================================================
    # Status Update Methods
    # ==================================================================

    def update_db_indicator(self, online: bool) -> None:
        """
        Update database connection indicator.
        
        Args:
            online: True if database is connected
        """
        if online:
            self.mw.db_indicator.setStyleSheet(self.STYLE["db_indicator_online"])
            self.mw.db_indicator.setToolTip("Database connected")
        else:
            self.mw.db_indicator.setStyleSheet(self.STYLE["db_indicator_offline"])
            self.mw.db_indicator.setToolTip("Database disconnected!")

    def update_record_count(self, total: int, filtered: int) -> None:
        """
        Update record count display.
        
        Args:
            total: Total records in database
            filtered: Currently filtered records
        """
        self.mw.record_count_label.setText(
            f"Records: {total} | Filtered: {filtered}"
        )

    def update_ready_status(self, ready: bool, message: str = "") -> None:
        """
        Update ready status indicator.
        
        Args:
            ready: True if system is ready
            message: Optional status message
        """
        if ready:
            self.mw.ready_label.setText("✅ System Ready")
            self.mw.ready_label.setStyleSheet(
                "color: green; font-size: 11px; margin-left: 10px; margin-right: 10px;"
            )
        else:
            self.mw.ready_label.setText(f"❌ {message}" if message else "❌ Error")
            self.mw.ready_label.setStyleSheet(
                "color: red; font-size: 11px; margin-left: 10px; margin-right: 10px;"
            )

    def update_license_status(self, status_text: str) -> None:
        """
        Update license status display.
        
        Args:
            status_text: License status text
        """
        self.mw.license_status_label.setText(status_text)

    # ==================================================================
    # Theme Methods
    # ==================================================================

    def apply_theme(self, theme_name: str) -> None:
        """
        Apply a theme to the application.
        
        Args:
            theme_name: Theme name ('light', 'dark', 'high_contrast')
        """
        import json
        import os
        
        theme_path = os.path.join(
            os.path.dirname(__file__), '..', 'config', 'theme_config.json'
        )
        if os.path.exists(theme_path):
            try:
                with open(theme_path, 'r', encoding='utf-8') as f:
                    themes = json.load(f)
                theme = themes.get(theme_name, themes.get("light", {}))
                
                app = QApplication.instance()
                palette = app.palette()
                
                # Apply colors
                palette.setColor(QPalette.ColorRole.Window, QColor(theme.get("bg", "#f5f5f5")))
                palette.setColor(QPalette.ColorRole.WindowText, QColor(theme.get("fg", "#212121")))
                palette.setColor(QPalette.ColorRole.Base, QColor(theme.get("input_bg", "#ffffff")))
                palette.setColor(QPalette.ColorRole.Text, QColor(theme.get("input_fg", "#000000")))
                palette.setColor(QPalette.ColorRole.Button, QColor(theme.get("button_bg", "#e0e0e0")))
                palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme.get("button_fg", "#000000")))
                palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.get("highlight", "#4CAF50")))
                palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
                
                app.setPalette(palette)
                
                # Update table alternating colors
                alt_color = theme.get("table_alt_bg", "#fafafa")
                self.mw.table.setStyleSheet(
                    self.STYLE["table"] + f"""
                    QTableWidget {{
                        alternate-background-color: {alt_color};
                    }}
                    """
                )
                
            except Exception as e:
                print(f"Failed to apply theme: {e}")

    # ==================================================================
    # Utility Methods
    # ==================================================================

    def show_message(self, title: str, message: str, icon: str = "info") -> None:
        """
        Show a message box.
        
        Args:
            title: Dialog title
            message: Message text
            icon: Icon type ('info', 'warning', 'critical', 'question')
        """
        icons = {
            "info": QMessageBox.Icon.Information,
            "warning": QMessageBox.Icon.Warning,
            "critical": QMessageBox.Icon.Critical,
            "question": QMessageBox.Icon.Question,
        }
        msg_box = QMessageBox(self.mw)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icons.get(icon, QMessageBox.Icon.Information))
        msg_box.exec()

    def show_status_message(self, message: str, timeout: int = 3000) -> None:
        """
        Show a temporary status bar message.
        
        Args:
            message: Message text
            timeout: Display duration in milliseconds
        """
        self.mw.statusBar().showMessage(message, timeout)

    def set_busy(self, busy: bool) -> None:
        """
        Set application busy state.
        
        Args:
            busy: True to show busy indicator
        """
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()
        self.mw.progress.setVisible(busy)


# ==================================================================
# Module Exports
# ==================================================================

__all__ = ['MainWindowUIBuilder']