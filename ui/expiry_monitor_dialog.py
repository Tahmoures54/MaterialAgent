# ui/expiry_monitor_dialog.py
"""
Expiry Date Monitor – iMat Material Control System (EPC Edition).

Comprehensive expiry tracking with:
- Multi-threshold expiry alerts (Critical, Warning, OK)
- Color-coded visual indicators
- Filtering by date range, QC status, location, discipline
- Export to Excel, PDF, HTML
- Print expiry report
- Bulk actions (mark as disposed, extend expiry)
- Expiry trend analysis
- Dashboard summary with statistics
- Sound alerts for critical items (optional)
- Auto-refresh capability
"""

import os
import tempfile
import webbrowser
from datetime import date, timedelta, datetime
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox,
    QMessageBox, QFileDialog, QApplication, QFrame, QToolBar,
    QStatusBar, QLineEdit, QWidget, QComboBox, QCheckBox,
    QDateEdit, QGroupBox, QFormLayout, QSplitter, QTextEdit,
    QAbstractItemView, QMenu, QProgressBar, QTabWidget
)
from PyQt6.QtCore import Qt, QDate, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QAction, QDesktopServices

from sqlalchemy import func, or_, and_
from db.database import get_db_session, SessionLocal
from db.models import Stock, Product, Location, Transaction
from ui.logo_widget import LogoWidget
from utils.excel_export import export_to_excel
from utils.pdf_export import export_to_pdf

# Try to import sound library
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# ==================================================================
# Constants
# ==================================================================

# Expiry status thresholds (days)
CRITICAL_THRESHOLD = 0      # Already expired
WARNING_THRESHOLD = 30      # Expiring within 30 days
CAUTION_THRESHOLD = 90      # Expiring within 90 days

# Default filter threshold
DEFAULT_DAYS_THRESHOLD = 90

# Expiry status definitions
EXPIRY_STATUSES = {
    "EXPIRED": {
        "label": "Expired",
        "icon": "🔴",
        "bg": "#FFCDD2",
        "fg": "#B71C1C",
        "priority": 1,
        "description": "Already past expiry date - requires immediate action"
    },
    "CRITICAL": {
        "label": "Critical (7 days)",
        "icon": "🟠",
        "bg": "#FFE0B2",
        "fg": "#E65100",
        "priority": 2,
        "description": "Expiring within 7 days - urgent attention needed"
    },
    "WARNING": {
        "label": "Warning (30 days)",
        "icon": "🟡",
        "bg": "#FFF9C4",
        "fg": "#F57F17",
        "priority": 3,
        "description": "Expiring within 30 days - plan for replacement"
    },
    "CAUTION": {
        "label": "Caution (90 days)",
        "icon": "🔵",
        "bg": "#BBDEFB",
        "fg": "#1565C0",
        "priority": 4,
        "description": "Expiring within 90 days - monitor closely"
    },
    "OK": {
        "label": "OK",
        "icon": "🟢",
        "bg": "#C8E6C9",
        "fg": "#2E7D32",
        "priority": 5,
        "description": "Within safe expiry range"
    },
    "NO_EXPIRY": {
        "label": "No Expiry Date",
        "icon": "⚪",
        "bg": "#F5F5F5",
        "fg": "#757575",
        "priority": 6,
        "description": "No expiry date set"
    },
}

# Auto-refresh interval (seconds)
AUTO_REFRESH_INTERVAL = 60

# ==================================================================
# Expiry Monitor Dialog
# ==================================================================

class ExpiryMonitorDialog(QDialog):
    """
    Comprehensive expiry date monitoring and management dialog.
    
    Features:
    - Visual expiry status indicators
    - Multi-level filtering
    - Export capabilities
    - Bulk actions
    - Dashboard summary
    """

    # Signals
    data_refreshed = pyqtSignal(int)  # item count

    def __init__(self, parent=None, user_role: str = "viewer"):
        """
        Initialize the Expiry Monitor dialog.
        
        Args:
            parent: Parent widget
            user_role: Current user's role for access control
        """
        super().__init__(parent)
        self.user_role = user_role
        self.parent = parent
        
        # State
        self.days_threshold = DEFAULT_DAYS_THRESHOLD
        self.all_data: List[Dict] = []
        self.filtered_data: List[Dict] = []
        self.auto_refresh_enabled = False
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.timeout.connect(self._refresh_data)
        
        # Window setup
        self.setWindowTitle("iMat – Expiry Date Monitor")
        self.setMinimumSize(1100, 700)
        self.setModal(True)
        
        # Build UI
        self._init_ui()
        
        # Load data
        self._refresh_data()
        
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
        self._build_filter_panel(main_layout)
        self._build_content(main_layout)
        self._build_status_bar(main_layout)

    def _build_header(self, parent_layout: QVBoxLayout):
        """Build the header with logo and title."""
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

        title = QLabel("⌛ Expiry Date Monitor")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("Track and manage items approaching or past expiry")
        self.subtitle.setFont(QFont("Arial", 9))
        self.subtitle.setStyleSheet("color: #B2DFDB;")
        header_layout.addWidget(self.subtitle)

        parent_layout.addWidget(header)

    def _build_toolbar(self, parent_layout: QVBoxLayout):
        """Build the toolbar with action buttons."""
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
            QToolButton:hover {
                background: #B2DFDB;
            }
            QToolButton:disabled {
                color: #999;
            }
        """)

        # Refresh
        self.action_refresh = toolbar.addAction("🔄 Refresh")
        self.action_refresh.setToolTip("Refresh expiry data")
        self.action_refresh.triggered.connect(self._refresh_data)
        toolbar.addSeparator()

        # Auto-refresh toggle
        self.action_auto_refresh = toolbar.addAction("⏱️ Auto-Refresh")
        self.action_auto_refresh.setCheckable(True)
        self.action_auto_refresh.setToolTip("Toggle automatic refresh every 60 seconds")
        self.action_auto_refresh.toggled.connect(self._toggle_auto_refresh)
        toolbar.addSeparator()

        # Export actions
        self.action_export_excel = toolbar.addAction("📥 Excel")
        self.action_export_excel.setToolTip("Export to Excel")
        self.action_export_excel.triggered.connect(self._export_excel)
        
        self.action_export_pdf = toolbar.addAction("📑 PDF")
        self.action_export_pdf.setToolTip("Export to PDF")
        self.action_export_pdf.triggered.connect(self._export_pdf)
        
        self.action_print = toolbar.addAction("🖨️ Print")
        self.action_print.setToolTip("Print expiry report")
        self.action_print.triggered.connect(self._print_report)
        toolbar.addSeparator()

        # Bulk actions
        self.action_mark_disposed = toolbar.addAction("🗑️ Mark Disposed")
        self.action_mark_disposed.setToolTip("Mark selected items as disposed")
        self.action_mark_disposed.triggered.connect(self._mark_disposed)
        
        self.action_extend_expiry = toolbar.addAction("📅 Extend Expiry")
        self.action_extend_expiry.setToolTip("Extend expiry date for selected items")
        self.action_extend_expiry.triggered.connect(self._extend_expiry)
        toolbar.addSeparator()

        # Copy
        self.action_copy = toolbar.addAction("📋 Copy")
        self.action_copy.setToolTip("Copy table to clipboard")
        self.action_copy.triggered.connect(self._copy_to_clipboard)

        parent_layout.addWidget(toolbar)

    def _build_filter_panel(self, parent_layout: QVBoxLayout):
        """Build the filter panel."""
        filter_frame = QFrame()
        filter_frame.setStyleSheet("""
            QFrame {
                background: #F5F5F5;
                border-bottom: 1px solid #CCC;
            }
        """)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(10, 8, 10, 8)
        filter_layout.setSpacing(10)

        # Days threshold
        filter_layout.addWidget(QLabel("Show items expiring within:"))
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 365)
        self.days_spin.setValue(self.days_threshold)
        self.days_spin.setSuffix(" days")
        self.days_spin.setToolTip("Show items expiring within this many days")
        self.days_spin.valueChanged.connect(self._on_threshold_changed)
        filter_layout.addWidget(self.days_spin)

        filter_layout.addWidget(QLabel("  |  "))

        # Show expired only
        self.show_expired_check = QCheckBox("Show Expired Only")
        self.show_expired_check.setToolTip("Show only items that have already expired")
        self.show_expired_check.toggled.connect(self._apply_filters)
        filter_layout.addWidget(self.show_expired_check)

        # QC Status filter
        filter_layout.addWidget(QLabel("QC:"))
        self.qc_combo = QComboBox()
        self.qc_combo.addItems(["All", "QUARANTINE", "ACCEPTED", "REJECTED"])
        self.qc_combo.setToolTip("Filter by QC status")
        self.qc_combo.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.qc_combo)

        # Discipline filter
        filter_layout.addWidget(QLabel("Discipline:"))
        self.discipline_combo = QComboBox()
        self.discipline_combo.addItem("All")
        self.discipline_combo.setToolTip("Filter by discipline")
        self.discipline_combo.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.discipline_combo)

        # Search
        filter_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Item code, description, location...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMaximumWidth(200)
        self.search_input.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.search_input)

        filter_layout.addStretch()

        parent_layout.addWidget(filter_frame)

        # Load discipline options
        self._load_filter_options()

    def _build_content(self, parent_layout: QVBoxLayout):
        """Build the main content area with tabs."""
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

        # Tab 1: Expiry Table
        self.tab_table = self._build_table_tab()
        self.tab_widget.addTab(self.tab_table, "📊 Expiry List")

        # Tab 2: Summary Dashboard
        self.tab_dashboard = self._build_dashboard_tab()
        self.tab_widget.addTab(self.tab_dashboard, "📈 Summary Dashboard")

        parent_layout.addWidget(self.tab_widget)

    def _build_table_tab(self) -> QWidget:
        """Build the expiry table tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Main table
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "Status", "Item Code", "Description", "Discipline",
            "Heat No", "Location", "QC Status",
            "Quantity", "Expiry Date", "Days Left", "Remarks"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._on_item_double_clicked)
        self.table.setStyleSheet("""
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

        # Column widths
        column_widths = [80, 120, 200, 100, 100, 100, 80, 70, 100, 80, 120]
        for i, w in enumerate(column_widths):
            self.table.setColumnWidth(i, w)

        layout.addWidget(self.table)

        # Item count
        self.count_label = QLabel("Items: 0")
        self.count_label.setStyleSheet("color: #666; font-size: 10px; padding: 2px;")
        layout.addWidget(self.count_label)

        return widget

    def _build_dashboard_tab(self) -> QWidget:
        """Build the summary dashboard tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Summary text area
        self.dashboard_text = QTextEdit()
        self.dashboard_text.setReadOnly(True)
        self.dashboard_text.setStyleSheet("""
            QTextEdit {
                background: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 15px;
                font-size: 12px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(self.dashboard_text)

        # Quick stats
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(15)

        self.stat_cards = {}
        for status_key in ["EXPIRED", "CRITICAL", "WARNING", "CAUTION", "OK"]:
            card = self._build_stat_card(status_key)
            stats_layout.addWidget(card)
            self.stat_cards[status_key] = card

        layout.addLayout(stats_layout)

        return widget

    def _build_stat_card(self, status_key: str) -> QFrame:
        """Build a statistics card for a status category."""
        config = EXPIRY_STATUSES[status_key]
        
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {config['bg']};
                border: 2px solid {config['fg']};
                border-radius: 10px;
                padding: 10px;
            }}
            QLabel {{
                color: {config['fg']};
            }}
        """)
        card.setMinimumWidth(150)
        
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(4)
        
        icon_label = QLabel(config['icon'])
        icon_label.setStyleSheet(f"font-size: 24px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_label)
        
        title_label = QLabel(config['label'])
        title_label.setStyleSheet(f"font-weight: bold; font-size: 11px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        card_layout.addWidget(title_label)
        
        count_label = QLabel("0")
        count_label.setObjectName(f"count_{status_key}")
        count_label.setStyleSheet(f"font-size: 28px; font-weight: bold;")
        count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(count_label)
        
        return card

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready – Monitor expiry dates")
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
    # Role Permissions
    # ==================================================================

    def _apply_role_permissions(self):
        """Apply role-based access restrictions."""
        if self.user_role == "viewer":
            self.action_export_excel.setEnabled(False)
            self.action_export_pdf.setEnabled(False)
            self.action_mark_disposed.setEnabled(False)
            self.action_extend_expiry.setEnabled(False)
            self.status_bar.showMessage("Read-only mode – Viewing expiry data")

    # ==================================================================
    # Data Methods
    # ==================================================================

    def _load_filter_options(self):
        """Load filter options from database."""
        session = get_db_session()
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
        finally:
            session.close()

    def _refresh_data(self):
        """Refresh expiry data from database."""
        self.status_bar.showMessage("Loading expiry data...")
        QApplication.processEvents()

        session = get_db_session()
        try:
            today = date.today()
            cutoff_date = today + timedelta(days=self.days_threshold)

            query = session.query(
                Stock.item_code,
                Stock.heat_no,
                Stock.expiry_date,
                Stock.quantity,
                Stock.qc_status,
                Product.description,
                Product.discipline,
                Location.code.label('location_code')
            ).join(Product, Stock.item_code == Product.item_code)\
             .join(Location, Stock.location_id == Location.id)\
             .filter(
                 Stock.expiry_date != None,
                 Stock.expiry_date <= cutoff_date,
                 Stock.quantity > 0
             ).order_by(Stock.expiry_date)

            self.all_data = []
            for row in query.all():
                days_left = (row.expiry_date - today).days
                status = self._calculate_status(days_left)

                self.all_data.append({
                    "item_code": row.item_code,
                    "description": row.description or "",
                    "discipline": row.discipline or "",
                    "heat_no": row.heat_no,
                    "location": row.location_code or "",
                    "qc_status": row.qc_status,
                    "quantity": row.quantity,
                    "expiry_date": row.expiry_date,
                    "days_left": days_left,
                    "status": status,
                })

            self._apply_filters()
            self._update_dashboard()
            self.data_refreshed.emit(len(self.all_data))
            
            # Alert sound for critical items
            if self.all_data and any(
                d["status"] in ["EXPIRED", "CRITICAL"] for d in self.all_data
            ):
                self._play_alert_sound()

            self.status_bar.showMessage(
                f"Loaded {len(self.all_data)} items expiring within {self.days_threshold} days",
                5000
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load expiry data:\n{str(e)}")
        finally:
            session.close()

    def _calculate_status(self, days_left: int) -> str:
        """Calculate expiry status based on days remaining."""
        if days_left < 0:
            return "EXPIRED"
        elif days_left <= 7:
            return "CRITICAL"
        elif days_left <= 30:
            return "WARNING"
        elif days_left <= 90:
            return "CAUTION"
        else:
            return "OK"

    def _apply_filters(self):
        """Apply filters to the data and display."""
        self.filtered_data = self.all_data.copy()

        # Show expired only
        if self.show_expired_check.isChecked():
            self.filtered_data = [
                d for d in self.filtered_data
                if d["status"] == "EXPIRED"
            ]

        # QC filter
        qc_filter = self.qc_combo.currentText()
        if qc_filter != "All":
            self.filtered_data = [
                d for d in self.filtered_data
                if d["qc_status"] == qc_filter
            ]

        # Discipline filter
        disc_filter = self.discipline_combo.currentText()
        if disc_filter != "All":
            self.filtered_data = [
                d for d in self.filtered_data
                if d["discipline"] == disc_filter
            ]

        # Search text
        search_text = self.search_input.text().strip().lower()
        if search_text:
            self.filtered_data = [
                d for d in self.filtered_data
                if search_text in d["item_code"].lower()
                or search_text in d.get("description", "").lower()
                or search_text in d.get("location", "").lower()
                or search_text in d.get("heat_no", "").lower()
            ]

        self._display_data()
        self._update_dashboard()

    def _display_data(self):
        """Display filtered data in the table."""
        self.table.setRowCount(len(self.filtered_data))
        self.count_label.setText(f"Items: {len(self.filtered_data)}")

        for row, item in enumerate(self.filtered_data):
            status_config = EXPIRY_STATUSES.get(
                item["status"], EXPIRY_STATUSES["OK"]
            )

            # Status indicator
            status_item = QTableWidgetItem(
                f"{status_config['icon']} {status_config['label']}"
            )
            status_item.setBackground(QColor(status_config["bg"]))
            status_item.setForeground(QColor(status_config["fg"]))
            status_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.table.setItem(row, 0, status_item)

            # Item Code
            code_item = QTableWidgetItem(item["item_code"])
            code_item.setFont(QFont("Consolas", 10))
            self.table.setItem(row, 1, code_item)

            # Description
            self.table.setItem(row, 2, QTableWidgetItem(item.get("description", "")))

            # Discipline
            self.table.setItem(row, 3, QTableWidgetItem(item.get("discipline", "")))

            # Heat No
            self.table.setItem(row, 4, QTableWidgetItem(item.get("heat_no", "")))

            # Location
            self.table.setItem(row, 5, QTableWidgetItem(item.get("location", "")))

            # QC Status
            qc_item = QTableWidgetItem(item.get("qc_status", ""))
            qc_colors = {
                "QUARANTINE": ("#FFE0B2", "#E65100"),
                "ACCEPTED": ("#C8E6C9", "#2E7D32"),
                "REJECTED": ("#FFCDD2", "#B71C1C"),
            }
            if item.get("qc_status") in qc_colors:
                bg, fg = qc_colors[item["qc_status"]]
                qc_item.setBackground(QColor(bg))
                qc_item.setForeground(QColor(fg))
            self.table.setItem(row, 6, qc_item)

            # Quantity
            qty_item = QTableWidgetItem(f"{item['quantity']:.1f}")
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 7, qty_item)

            # Expiry Date
            date_str = item["expiry_date"].strftime("%Y-%m-%d") if item["expiry_date"] else ""
            self.table.setItem(row, 8, QTableWidgetItem(date_str))

            # Days Left
            days = item["days_left"]
            days_str = f"{days} days" if days >= 0 else f"EXPIRED ({abs(days)} days ago)"
            days_item = QTableWidgetItem(days_str)
            days_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if days < 0:
                days_item.setForeground(QColor("#D32F2F"))
            elif days <= 7:
                days_item.setForeground(QColor("#E65100"))
            self.table.setItem(row, 9, days_item)

            # Remarks
            remarks = ""
            if item["status"] == "EXPIRED":
                remarks = "⚠️ EXPIRED - Action Required"
            elif item["status"] == "CRITICAL":
                remarks = "🔴 Critical - Immediate action"
            elif item["status"] == "WARNING":
                remarks = "🟡 Plan for replacement"
            self.table.setItem(row, 10, QTableWidgetItem(remarks))

    def _update_dashboard(self):
        """Update the dashboard summary."""
        # Count by status
        status_counts = {}
        for status_key in EXPIRY_STATUSES:
            status_counts[status_key] = 0

        total_qty = 0
        for item in self.filtered_data:
            status = item["status"]
            if status in status_counts:
                status_counts[status] += 1
            total_qty += item["quantity"]

        # Update stat cards
        for status_key, card in self.stat_cards.items():
            count_label = card.findChild(QLabel, f"count_{status_key}")
            if count_label:
                count_label.setText(str(status_counts.get(status_key, 0)))

        # Dashboard text
        html = f"""
        <div style="font-family: 'Segoe UI', Arial; line-height: 1.8;">
            <h3 style="color: #004D40;">📈 Expiry Dashboard</h3>
            <p><b>Analysis Period:</b> Next {self.days_threshold} days</p>
            <p><b>Total Items:</b> {len(self.filtered_data)} | 
               <b>Total Quantity:</b> {total_qty:.1f}</p>
            <hr>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #004D40; color: white;">
                    <th style="padding: 8px;">Status</th>
                    <th style="padding: 8px;">Items</th>
                    <th style="padding: 8px;">% of Total</th>
                </tr>
        """

        for status_key in ["EXPIRED", "CRITICAL", "WARNING", "CAUTION", "OK"]:
            config = EXPIRY_STATUSES[status_key]
            count = status_counts[status_key]
            pct = (count / len(self.filtered_data) * 100) if self.filtered_data else 0

            html += f"""
                <tr style="background: {config['bg']}; color: {config['fg']};">
                    <td style="padding: 6px; font-weight: bold;">
                        {config['icon']} {config['label']}
                    </td>
                    <td style="padding: 6px; text-align: center;">{count}</td>
                    <td style="padding: 6px; text-align: center;">{pct:.1f}%</td>
                </tr>
            """

        html += """
            </table>
            <hr>
            <p style="font-size: 10px; color: #666;">
                💡 <b>Recommendation:</b> Items marked as EXPIRED or CRITICAL should be 
                reviewed immediately. Consider disposal, re-certification, or return to vendor.
            </p>
        </div>
        """

        self.dashboard_text.setHtml(html)

    # ==================================================================
    # Event Handlers
    # ==================================================================

    def _on_threshold_changed(self, value: int):
        """Handle days threshold change."""
        self.days_threshold = value
        self._refresh_data()

    def _toggle_auto_refresh(self, enabled: bool):
        """Toggle automatic data refresh."""
        self.auto_refresh_enabled = enabled
        if enabled:
            self.auto_refresh_timer.start(AUTO_REFRESH_INTERVAL * 1000)
            self.status_bar.showMessage(
                f"Auto-refresh enabled (every {AUTO_REFRESH_INTERVAL}s)", 3000
            )
        else:
            self.auto_refresh_timer.stop()
            self.status_bar.showMessage("Auto-refresh disabled", 3000)

    def _show_context_menu(self, pos):
        """Show context menu on table right-click."""
        row = self.table.currentRow()
        if row < 0:
            return

        menu = QMenu(self)
        menu.addAction("🔍 View Item Details", self._view_selected_item)
        menu.addSeparator()
        menu.addAction("🗑️ Mark as Disposed", self._mark_disposed)
        menu.addAction("📅 Extend Expiry Date", self._extend_expiry)
        menu.addSeparator()
        menu.addAction("📋 Copy Row", self._copy_selected_row)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_item_double_clicked(self, index):
        """Handle double-click on item."""
        self._view_selected_item()

    # ==================================================================
    # Actions
    # ==================================================================

    def _view_selected_item(self):
        """View details of selected item."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an item.")
            return

        item_code = self.table.item(row, 1).text()
        description = self.table.item(row, 2).text()
        expiry_date = self.table.item(row, 8).text()
        days_left = self.table.item(row, 9).text()

        QMessageBox.information(
            self, f"Item Details - {item_code}",
            f"<b>Item Code:</b> {item_code}<br>"
            f"<b>Description:</b> {description}<br>"
            f"<b>Expiry Date:</b> {expiry_date}<br>"
            f"<b>Days Left:</b> {days_left}<br>"
        )

    def _mark_disposed(self):
        """Mark selected items as disposed."""
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select items to mark as disposed.")
            return

        reply = QMessageBox.question(
            self, "Confirm Disposal",
            f"Mark {len(selected_rows)} item(s) as disposed?\n\n"
            "This will set the quantity to zero.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            session = get_db_session()
            try:
                for row in selected_rows:
                    item_code = self.table.item(row, 1).text()
                    heat_no = self.table.item(row, 4).text()
                    loc_code = self.table.item(row, 5).text()

                    # Find and update stock
                    loc = session.query(Location).filter_by(code=loc_code).first()
                    if loc:
                        stock = session.query(Stock).filter(
                            Stock.item_code == item_code,
                            Stock.heat_no == heat_no,
                            Stock.location_id == loc.id
                        ).first()
                        if stock:
                            stock.quantity = 0

                session.commit()
                self._refresh_data()
                self.status_bar.showMessage(f"{len(selected_rows)} items marked as disposed", 5000)
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Error", str(e))
            finally:
                session.close()

    def _extend_expiry(self):
        """Extend expiry date for selected items."""
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select items.")
            return

        # Ask for extension days
        from PyQt6.QtWidgets import QInputDialog
        days, ok = QInputDialog.getInt(
            self, "Extend Expiry",
            "Extend expiry by how many days?",
            30, 1, 365, 1
        )

        if not ok:
            return

        session = get_db_session()
        try:
            for row in selected_rows:
                item_code = self.table.item(row, 1).text()
                heat_no = self.table.item(row, 4).text()
                loc_code = self.table.item(row, 5).text()

                loc = session.query(Location).filter_by(code=loc_code).first()
                if loc:
                    stock = session.query(Stock).filter(
                        Stock.item_code == item_code,
                        Stock.heat_no == heat_no,
                        Stock.location_id == loc.id
                    ).first()
                    if stock and stock.expiry_date:
                        stock.expiry_date = stock.expiry_date + timedelta(days=days)

            session.commit()
            self._refresh_data()
            self.status_bar.showMessage(
                f"Expiry extended by {days} days for {len(selected_rows)} items", 5000
            )
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    def _copy_selected_row(self):
        """Copy selected row to clipboard."""
        row = self.table.currentRow()
        if row < 0:
            return

        cols = self.table.columnCount()
        lines = []
        for col in range(cols):
            header = self.table.horizontalHeaderItem(col).text()
            item = self.table.item(row, col)
            if item:
                lines.append(f"{header}: {item.text()}")

        QApplication.clipboard().setText("\n".join(lines))
        self.status_bar.showMessage("Row copied to clipboard", 3000)

    def _copy_to_clipboard(self):
        """Copy entire table to clipboard."""
        if self.table.rowCount() == 0:
            return

        headers = [
            self.table.horizontalHeaderItem(c).text()
            for c in range(self.table.columnCount())
        ]
        lines = ["\t".join(headers)]

        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                row_data = []
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    row_data.append(item.text() if item else "")
                lines.append("\t".join(row_data))

        QApplication.clipboard().setText("\n".join(lines))
        self.status_bar.showMessage("Table copied to clipboard", 3000)

    # ==================================================================
    # Export Methods
    # ==================================================================

    def _export_excel(self):
        """Export to Excel."""
        if not self.filtered_data:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Expiry Report", "expiry_report.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            headers = [
                self.table.horizontalHeaderItem(c).text()
                for c in range(self.table.columnCount())
            ]
            data = []
            for row in range(self.table.rowCount()):
                if not self.table.isRowHidden(row):
                    row_dict = {}
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        row_dict[headers[col]] = item.text() if item else ""
                    data.append(row_dict)

            export_to_excel(data, headers, file_path, sheet_name="Expiry Report")
            self.status_bar.showMessage(f"Exported to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _export_pdf(self):
        """Export to PDF."""
        if not self.filtered_data:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Expiry Report", "expiry_report.pdf",
            "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        try:
            headers = [
                self.table.horizontalHeaderItem(c).text()
                for c in range(self.table.columnCount())
            ]
            data = []
            for row in range(self.table.rowCount()):
                if not self.table.isRowHidden(row):
                    row_dict = {}
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        row_dict[headers[col]] = item.text() if item else ""
                    data.append(row_dict)

            export_to_pdf(data, headers, file_path, title="Expiry Date Report")
            self.status_bar.showMessage(f"PDF saved to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _print_report(self):
        """Print expiry report as HTML."""
        if not self.filtered_data:
            QMessageBox.information(self, "No Data", "Nothing to print.")
            return

        html = self._generate_html_report()

        with tempfile.NamedTemporaryFile(
            suffix='.html', delete=False, mode='w', encoding='utf-8'
        ) as f:
            f.write(html)
            tmp_path = f.name

        QDesktopServices.openUrl(QUrl.fromLocalFile(tmp_path))
        self.status_bar.showMessage("Report opened in browser for printing", 4000)

    def _generate_html_report(self) -> str:
        """Generate HTML report."""
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Expiry Date Report</title>
            <style>
                body { font-family: 'Segoe UI', Arial; margin: 20px; }
                h1 { color: #004D40; }
                table { border-collapse: collapse; width: 100%; margin-top: 10px; }
                th { background: #004D40; color: white; padding: 8px; text-align: left; }
                td { padding: 6px; border-bottom: 1px solid #ddd; }
                .expired { background: #FFCDD2; }
                .critical { background: #FFE0B2; }
                .warning { background: #FFF9C4; }
                .caution { background: #BBDEFB; }
            </style>
        </head>
        <body>
            <h1>⌛ Expiry Date Report</h1>
            <p>Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M") + """</p>
            <p>Items expiring within: """ + str(self.days_threshold) + """ days</p>
            <table>
                <tr>
                    <th>Status</th><th>Item Code</th><th>Description</th>
                    <th>Location</th><th>Expiry Date</th><th>Days Left</th>
                </tr>
        """

        for item in self.filtered_data:
            status_class = item["status"].lower()
            html += f"""
                <tr class="{status_class}">
                    <td>{EXPIRY_STATUSES[item['status']]['icon']} {item['status']}</td>
                    <td>{item['item_code']}</td>
                    <td>{item.get('description', '')}</td>
                    <td>{item.get('location', '')}</td>
                    <td>{item['expiry_date']}</td>
                    <td>{item['days_left']} days</td>
                </tr>
            """

        html += """
            </table>
        </body>
        </html>
        """

        return html

    # ==================================================================
    # Alert Sound
    # ==================================================================

    def _play_alert_sound(self):
        """Play alert sound for critical items."""
        if not PYGAME_AVAILABLE:
            return

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()

            import numpy as np
            sample_rate = 44100
            duration = 0.3
            frequency = 800

            t = np.linspace(0, duration, int(sample_rate * duration), False)
            tone = np.sin(frequency * 2 * np.pi * t)
            fade = np.linspace(1.0, 0.0, len(tone))
            tone = (tone * fade * 32767).astype(np.int16)

            sound = pygame.sndarray.make_sound(tone)
            sound.play()
        except Exception:
            pass

    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.stop()
        super().closeEvent(event)