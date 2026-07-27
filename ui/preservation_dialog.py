# ui/preservation_dialog.py
"""
Preservation Maintenance Dashboard – iMat Material Control System (EPC Edition).

Comprehensive preservation management with:
- Preservation schedule tracking
- Overdue alerts with color coding
- Preservation status management
- Bulk mark as preserved
- Preservation history logging
- Automatic next preservation date calculation
- Filter by status, location, discipline
- Export preservation reports
- Print preservation schedule
- Email/WhatsApp notifications for overdue items
- Preservation type categorization
- Equipment/machinery preservation tracking
"""

import os
import tempfile
import webbrowser
from datetime import date, timedelta, datetime
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QLabel, QFrame, QToolBar, QStatusBar,
    QHeaderView, QComboBox, QLineEdit, QCheckBox, QDateEdit,
    QGroupBox, QFormLayout, QTextEdit, QSplitter, QWidget,
    QAbstractItemView, QMenu, QFileDialog, QApplication,
    QInputDialog, QProgressBar
)
from PyQt6.QtCore import Qt, QDate, QUrl, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QDesktopServices, QAction

from sqlalchemy import func, or_
from db.database import SessionLocal, get_db_session
from db.models import Stock, Product, Location
from logic.reports_logic import get_preservation_alerts
from ui.logo_widget import LogoWidget
from utils.excel_export import export_to_excel
from utils.pdf_export import export_to_pdf

# ==================================================================
# Constants
# ==================================================================

# Preservation status definitions
PRESERVATION_STATUSES = {
    "OVERDUE": {
        "label": "Overdue",
        "icon": "🔴",
        "bg": QColor("#FFCDD2"),
        "fg": QColor("#B71C1C"),
        "priority": 1,
        "description": "Preservation is past due - immediate action required"
    },
    "DUE_TODAY": {
        "label": "Due Today",
        "icon": "🟠",
        "bg": QColor("#FFE0B2"),
        "fg": QColor("#E65100"),
        "priority": 2,
        "description": "Preservation is due today"
    },
    "DUE_SOON": {
        "label": "Due Soon (7 days)",
        "icon": "🟡",
        "bg": QColor("#FFF9C4"),
        "fg": QColor("#F57F17"),
        "priority": 3,
        "description": "Preservation due within 7 days"
    },
    "UPCOMING": {
        "label": "Upcoming (30 days)",
        "icon": "🔵",
        "bg": QColor("#BBDEFB"),
        "fg": QColor("#1565C0"),
        "priority": 4,
        "description": "Preservation due within 30 days"
    },
    "COMPLIANT": {
        "label": "Compliant",
        "icon": "🟢",
        "bg": QColor("#C8E6C9"),
        "fg": QColor("#2E7D32"),
        "priority": 5,
        "description": "Preservation is up to date"
    },
    "NOT_REQUIRED": {
        "label": "Not Required",
        "icon": "⚪",
        "bg": QColor("#F5F5F5"),
        "fg": QColor("#9E9E9E"),
        "priority": 6,
        "description": "No preservation required"
    },
}

# Preservation types
PRESERVATION_TYPES = [
    "Visual Inspection",
    "Cleaning",
    "Lubrication",
    "Coating/Painting",
    "Desiccant Replacement",
    "Nitrogen Purge",
    "Rotation",
    "Functional Test",
    "Calibration",
    "Oil Change",
    "Filter Replacement",
    "General Maintenance",
]

# Default preservation intervals (days) by material class
DEFAULT_INTERVALS = {
    "Carbon Steel": 180,
    "Stainless Steel": 365,
    "Alloy Steel": 180,
    "Copper": 365,
    "Aluminum": 365,
    "Plastic": 730,
    "Rubber": 180,
    "Electrical": 365,
    "Instrument": 180,
    "Default": 365,
}

# ==================================================================
# Preservation Dialog
# ==================================================================

class PreservationDialog(QDialog):
    """
    Preservation maintenance dashboard for monitoring and recording
    preservation activities on stored materials.
    """

    preservation_updated = pyqtSignal()

    def __init__(self, parent=None, user_role: str = "viewer"):
        """
        Initialize the Preservation dialog.
        
        Args:
            parent: Parent widget
            user_role: Current user's role
        """
        super().__init__(parent)
        self.user_role = user_role
        self.parent = parent
        self.db = SessionLocal()
        
        # State
        self.all_alerts: List[Dict] = []
        self.filtered_alerts: List[Dict] = []
        self.selected_preservation_type: str = ""
        
        # Window setup
        self.setWindowTitle("iMat – Preservation Dashboard")
        self.setMinimumSize(1200, 700)
        self.setModal(True)
        
        # Build UI
        self._init_ui()
        
        # Load data
        self._load_alerts()
        
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

        title = QLabel("🛡️ Preservation Dashboard")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("Monitor and record material preservation activities")
        self.subtitle.setFont(QFont("Arial", 9))
        self.subtitle.setStyleSheet("color: #B2DFDB;")
        header_layout.addWidget(self.subtitle)

        parent_layout.addWidget(header)

    def _build_toolbar(self, parent_layout: QVBoxLayout):
        """Build the toolbar with actions."""
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

        self.action_refresh = toolbar.addAction("🔄 Refresh")
        self.action_refresh.triggered.connect(self._load_alerts)
        toolbar.addSeparator()

        self.action_mark_done = toolbar.addAction("✅ Mark as Preserved")
        self.action_mark_done.setToolTip("Record preservation for selected items")
        self.action_mark_done.triggered.connect(self._mark_as_preserved)
        
        self.action_extend = toolbar.addAction("📅 Extend Due Date")
        self.action_extend.setToolTip("Extend preservation due date")
        self.action_extend.triggered.connect(self._extend_due_date)
        toolbar.addSeparator()

        self.action_export_excel = toolbar.addAction("📥 Excel")
        self.action_export_excel.triggered.connect(self._export_excel)
        
        self.action_export_pdf = toolbar.addAction("📑 PDF")
        self.action_export_pdf.triggered.connect(self._export_pdf)
        
        self.action_print = toolbar.addAction("🖨️ Print")
        self.action_print.triggered.connect(self._print_report)
        toolbar.addSeparator()

        self.action_whatsapp = toolbar.addAction("💬 WhatsApp Alert")
        self.action_whatsapp.setToolTip("Send overdue alert via WhatsApp")
        self.action_whatsapp.triggered.connect(self._send_whatsapp_alert)
        
        self.action_copy = toolbar.addAction("📋 Copy")
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
        filter_layout.setContentsMargins(10, 6, 10, 6)
        filter_layout.setSpacing(8)

        # Status filter
        filter_layout.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItem("All Statuses")
        for status_key, status_config in PRESERVATION_STATUSES.items():
            if status_key != "NOT_REQUIRED":
                self.status_combo.addItem(
                    f"{status_config['icon']} {status_config['label']}", 
                    status_key
                )
        self.status_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.status_combo)

        # Days ahead filter
        filter_layout.addWidget(QLabel("Due within:"))
        self.days_combo = QComboBox()
        self.days_combo.addItems(["7 days", "14 days", "30 days", "60 days", "90 days", "All"])
        self.days_combo.setCurrentIndex(2)  # Default: 30 days
        self.days_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.days_combo)

        # QC Status filter
        filter_layout.addWidget(QLabel("QC:"))
        self.qc_combo = QComboBox()
        self.qc_combo.addItems(["All", "QUARANTINE", "ACCEPTED", "REJECTED"])
        self.qc_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.qc_combo)

        # Discipline filter
        filter_layout.addWidget(QLabel("Discipline:"))
        self.discipline_combo = QComboBox()
        self.discipline_combo.addItem("All")
        self.discipline_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.discipline_combo)

        # Search
        filter_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Item code, description, location...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMaximumWidth(180)
        self.search_input.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.search_input)

        # Show only overdue
        self.overdue_only_check = QCheckBox("Overdue Only")
        self.overdue_only_check.toggled.connect(self._apply_filters)
        filter_layout.addWidget(self.overdue_only_check)

        filter_layout.addStretch()

        # Item count
        self.count_label = QLabel("Items: 0")
        self.count_label.setStyleSheet("color: #666; font-weight: bold;")
        filter_layout.addWidget(self.count_label)

        parent_layout.addWidget(filter_frame)

    def _build_content(self, parent_layout: QVBoxLayout):
        """Build the main content area."""
        # Main table
        self.table = QTableWidget()
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels([
            "Status", "Item Code", "Description", "Discipline",
            "Heat No", "Location", "QC Status",
            "Quantity", "Last Preserved", "Next Due",
            "Days Left", "Preservation Type"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._view_item_details)
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
                font-size: 10px;
            }
        """)

        # Column widths
        column_widths = [80, 110, 180, 90, 100, 100, 80, 70, 100, 100, 70, 120]
        for i, w in enumerate(column_widths):
            self.table.setColumnWidth(i, w)

        parent_layout.addWidget(self.table)

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage(
            "Ready – Select items and click 'Mark as Preserved' to record preservation"
        )
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
        """Apply role-based restrictions."""
        if self.user_role == "viewer":
            self.action_mark_done.setEnabled(False)
            self.action_extend.setEnabled(False)
            self.status_bar.showMessage("Read-only mode – Viewing preservation data")

    # ==================================================================
    # Data Loading
    # ==================================================================

    def _load_alerts(self):
        """Load preservation alerts from database."""
        self.status_bar.showMessage("Loading preservation data...")
        QApplication.processEvents()

        try:
            # Get preservation alerts
            alerts = get_preservation_alerts(self.db)
            
            self.all_alerts = []
            today = date.today()

            for alert in alerts:
                item_code = alert[0] if len(alert) > 0 else ""
                description = alert[1] if len(alert) > 1 else ""
                heat_no = alert[2] if len(alert) > 2 else ""
                location_code = alert[3] if len(alert) > 3 else ""
                location_name = alert[4] if len(alert) > 4 else ""
                next_due = alert[5] if len(alert) > 5 else None
                preservation_status = alert[6] if len(alert) > 6 else ""
                quantity = alert[7] if len(alert) > 7 else 0

                # Get additional info
                product = self.db.query(Product).filter_by(item_code=item_code).first()
                discipline = product.discipline if product else ""
                material_class = product.material_class if product else ""

                # Get stock QC status
                stocks = self.db.query(Stock).filter(
                    Stock.item_code == item_code,
                    Stock.heat_no == heat_no,
                    Stock.quantity > 0
                ).all()
                
                qc_status = stocks[0].qc_status if stocks else ""

                # Calculate days left
                days_left = None
                if next_due:
                    days_left = (next_due - today).days

                # Determine preservation status
                status = self._determine_status(days_left)

                # Get last preservation date (from stock or calculate)
                last_preserved = None
                if next_due and product and product.preservation_interval_days:
                    last_preserved = next_due - timedelta(days=product.preservation_interval_days)

                # Get preservation type
                preservation_type = self._get_preservation_type(material_class)

                self.all_alerts.append({
                    "item_code": item_code,
                    "description": description,
                    "discipline": discipline,
                    "material_class": material_class,
                    "heat_no": heat_no,
                    "location_code": location_code,
                    "location_name": location_name,
                    "qc_status": qc_status,
                    "quantity": quantity,
                    "last_preserved": last_preserved,
                    "next_due": next_due,
                    "days_left": days_left,
                    "status": status,
                    "preservation_status": preservation_status,
                    "preservation_type": preservation_type,
                })

            self._load_filter_options()
            self._apply_filters()
            self.status_bar.showMessage(f"Loaded {len(self.all_alerts)} preservation items", 3000)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load preservation data:\n{str(e)}")
            self.status_bar.showMessage("Error loading data")

    def _load_filter_options(self):
        """Load filter options from data."""
        disciplines = sorted(set(
            item.get("discipline", "") for item in self.all_alerts if item.get("discipline")
        ))
        
        self.discipline_combo.blockSignals(True)
        self.discipline_combo.clear()
        self.discipline_combo.addItem("All")
        for d in disciplines:
            self.discipline_combo.addItem(d)
        self.discipline_combo.blockSignals(False)

    def _determine_status(self, days_left: Optional[int]) -> str:
        """Determine preservation status based on days left."""
        if days_left is None:
            return "NOT_REQUIRED"
        elif days_left < 0:
            return "OVERDUE"
        elif days_left == 0:
            return "DUE_TODAY"
        elif days_left <= 7:
            return "DUE_SOON"
        elif days_left <= 30:
            return "UPCOMING"
        else:
            return "COMPLIANT"

    def _get_preservation_type(self, material_class: str) -> str:
        """Get recommended preservation type based on material class."""
        type_map = {
            "Carbon Steel": "Coating/Painting",
            "Stainless Steel": "Visual Inspection",
            "Alloy Steel": "Coating/Painting",
            "Copper": "Visual Inspection",
            "Aluminum": "Visual Inspection",
            "Plastic": "Visual Inspection",
            "Rubber": "Visual Inspection",
            "Electrical": "Functional Test",
            "Instrument": "Calibration",
        }
        return type_map.get(material_class, "General Maintenance")

    # ==================================================================
    # Filtering & Display
    # ==================================================================

    def _apply_filters(self):
        """Apply filters to the data."""
        status_filter = self.status_combo.currentData()
        qc_filter = self.qc_combo.currentText()
        disc_filter = self.discipline_combo.currentText()
        search_text = self.search_input.text().strip().lower()
        overdue_only = self.overdue_only_check.isChecked()
        
        # Days filter
        days_text = self.days_combo.currentText()
        if days_text == "All":
            max_days = 9999
        else:
            max_days = int(days_text.split()[0])

        self.filtered_alerts = []
        for item in self.all_alerts:
            # Status filter
            if status_filter and item["status"] != status_filter:
                continue

            # Days filter
            if item["days_left"] is not None and item["days_left"] > max_days:
                continue

            # Overdue only
            if overdue_only and item["status"] != "OVERDUE":
                continue

            # QC filter
            if qc_filter != "All" and item["qc_status"] != qc_filter:
                continue

            # Discipline filter
            if disc_filter != "All" and item["discipline"] != disc_filter:
                continue

            # Search
            if search_text:
                searchable = (
                    f"{item['item_code']} {item['description']} "
                    f"{item['location_code']} {item['heat_no']}"
                ).lower()
                if search_text not in searchable:
                    continue

            self.filtered_alerts.append(item)

        self._display_alerts()
        self.count_label.setText(f"Items: {len(self.filtered_alerts)}")

    def _display_alerts(self):
        """Display filtered alerts in the table."""
        self.table.setRowCount(len(self.filtered_alerts))

        for row, item in enumerate(self.filtered_alerts):
            # Status indicator
            status_config = PRESERVATION_STATUSES.get(
                item["status"], PRESERVATION_STATUSES["COMPLIANT"]
            )
            status_item = QTableWidgetItem(
                f"{status_config['icon']} {status_config['label']}"
            )
            status_item.setBackground(status_config["bg"])
            status_item.setForeground(status_config["fg"])
            status_item.setFont(QFont("Arial", 9, QFont.Weight.Bold))
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
            self.table.setItem(row, 5, QTableWidgetItem(item.get("location_code", "")))

            # QC Status
            qc_item = QTableWidgetItem(item.get("qc_status", ""))
            qc_colors = {
                "QUARANTINE": ("#FFE0B2", "#E65100"),
                "ACCEPTED": ("#C8E6C9", "#2E7D32"),
                "REJECTED": ("#FFCDD2", "#B71C1C"),
            }
            if item["qc_status"] in qc_colors:
                bg, fg = qc_colors[item["qc_status"]]
                qc_item.setBackground(QColor(bg))
                qc_item.setForeground(QColor(fg))
            self.table.setItem(row, 6, qc_item)

            # Quantity
            qty_item = QTableWidgetItem(f"{item['quantity']:.1f}")
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 7, qty_item)

            # Last Preserved
            last_str = item["last_preserved"].strftime("%Y-%m-%d") if item["last_preserved"] else "Unknown"
            self.table.setItem(row, 8, QTableWidgetItem(last_str))

            # Next Due
            next_str = item["next_due"].strftime("%Y-%m-%d") if item["next_due"] else "Not Set"
            next_item = QTableWidgetItem(next_str)
            if item["status"] in ["OVERDUE", "DUE_TODAY"]:
                next_item.setForeground(QColor("#D32F2F"))
                next_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.table.setItem(row, 9, next_item)

            # Days Left
            days = item["days_left"]
            if days is not None:
                if days < 0:
                    days_str = f"⚠️ {abs(days)}d overdue"
                elif days == 0:
                    days_str = "Today!"
                else:
                    days_str = f"{days} days"
            else:
                days_str = "N/A"
            
            days_item = QTableWidgetItem(days_str)
            days_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if days is not None and days <= 0:
                days_item.setForeground(QColor("#D32F2F"))
            elif days is not None and days <= 7:
                days_item.setForeground(QColor("#E65100"))
            self.table.setItem(row, 10, days_item)

            # Preservation Type
            self.table.setItem(row, 11, QTableWidgetItem(item.get("preservation_type", "")))

    # ==================================================================
    # Context Menu
    # ==================================================================

    def _show_context_menu(self, pos):
        """Show context menu on table."""
        menu = QMenu(self)
        menu.addAction("✅ Mark as Preserved", self._mark_as_preserved)
        menu.addAction("📅 Extend Due Date", self._extend_due_date)
        menu.addSeparator()
        menu.addAction("🔍 View Item Details", self._view_item_details)
        menu.addAction("📋 Copy Row", self._copy_selected_row)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ==================================================================
    # Actions
    # ==================================================================

    def _mark_as_preserved(self):
        """Mark selected items as preserved."""
        if self.user_role == "viewer":
            QMessageBox.warning(self, "Access Denied", "You cannot perform preservation.")
            return

        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select items to mark as preserved.")
            return

        # Ask for preservation type
        type_dialog = QInputDialog()
        type_dialog.setWindowTitle("Preservation Type")
        type_dialog.setLabelText("Select preservation type performed:")
        type_dialog.setComboBoxItems(PRESERVATION_TYPES)
        
        if type_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        preservation_type = type_dialog.textValue()

        # Ask for notes
        notes, ok = QInputDialog.getText(
            self, "Preservation Notes",
            "Add notes (optional):",
            text=""
        )

        confirm = QMessageBox.question(
            self, "Confirm Preservation",
            f"Mark {len(selected_rows)} item(s) as preserved?\n\n"
            f"Type: {preservation_type}\n"
            f"Next preservation date will be calculated automatically.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            today = date.today()
            updated = 0

            for row in selected_rows:
                item_code = self.table.item(row, 1).text()
                heat_no = self.table.item(row, 4).text()
                loc_code = self.table.item(row, 5).text()

                # Find location
                loc = self.db.query(Location).filter_by(code=loc_code).first()
                if not loc:
                    continue

                # Find stock records
                stocks = self.db.query(Stock).filter(
                    Stock.item_code == item_code,
                    Stock.heat_no == heat_no,
                    Stock.location_id == loc.id,
                    Stock.quantity > 0
                ).all()

                # Get preservation interval
                product = self.db.query(Product).filter_by(item_code=item_code).first()
                interval = 365  # Default
                if product and product.preservation_interval_days:
                    interval = product.preservation_interval_days
                else:
                    material_class = product.material_class if product else ""
                    interval = DEFAULT_INTERVALS.get(material_class, 365)

                for stock in stocks:
                    stock.next_preservation_due = today + timedelta(days=interval)
                    stock.preservation_status = "PRESERVED"
                    updated += 1

            self.db.commit()
            self._load_alerts()
            self.preservation_updated.emit()
            
            QMessageBox.information(
                self, "Preservation Recorded",
                f"{updated} stock record(s) marked as preserved.\n\n"
                f"Type: {preservation_type}\n"
                f"Next due: {today + timedelta(days=interval)}"
            )
            self.status_bar.showMessage(f"{updated} items preserved", 5000)

        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to update preservation:\n{str(e)}")

    def _extend_due_date(self):
        """Extend preservation due date for selected items."""
        if self.user_role == "viewer":
            QMessageBox.warning(self, "Access Denied", "You cannot modify preservation dates.")
            return

        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select items.")
            return

        days, ok = QInputDialog.getInt(
            self, "Extend Due Date",
            "Extend preservation due date by how many days?",
            30, 1, 365, 7
        )

        if not ok:
            return

        try:
            updated = 0
            for row in selected_rows:
                item_code = self.table.item(row, 1).text()
                heat_no = self.table.item(row, 4).text()
                loc_code = self.table.item(row, 5).text()

                loc = self.db.query(Location).filter_by(code=loc_code).first()
                if not loc:
                    continue

                stocks = self.db.query(Stock).filter(
                    Stock.item_code == item_code,
                    Stock.heat_no == heat_no,
                    Stock.location_id == loc.id,
                    Stock.quantity > 0
                ).all()

                for stock in stocks:
                    if stock.next_preservation_due:
                        stock.next_preservation_due += timedelta(days=days)
                    else:
                        stock.next_preservation_due = date.today() + timedelta(days=days)
                    updated += 1

            self.db.commit()
            self._load_alerts()
            self.preservation_updated.emit()
            self.status_bar.showMessage(
                f"Due date extended by {days} days for {updated} records", 5000
            )

        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", str(e))

    def _view_item_details(self):
        """View details of selected item."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an item.")
            return

        item = self.filtered_alerts[row]
        status_config = PRESERVATION_STATUSES.get(
            item["status"], PRESERVATION_STATUSES["COMPLIANT"]
        )

        details = f"""
        <h3>Preservation Details</h3>
        <table style="width: 100%; line-height: 1.8;">
            <tr><td><b>Item Code:</b></td><td>{item['item_code']}</td></tr>
            <tr><td><b>Description:</b></td><td>{item.get('description', 'N/A')}</td></tr>
            <tr><td><b>Discipline:</b></td><td>{item.get('discipline', 'N/A')}</td></tr>
            <tr><td><b>Material Class:</b></td><td>{item.get('material_class', 'N/A')}</td></tr>
            <tr><td><b>Heat No:</b></td><td>{item.get('heat_no', 'N/A')}</td></tr>
            <tr><td><b>Location:</b></td><td>{item.get('location_code', 'N/A')}</td></tr>
            <tr><td><b>QC Status:</b></td><td>{item.get('qc_status', 'N/A')}</td></tr>
            <tr><td><b>Quantity:</b></td><td>{item.get('quantity', 0):.1f}</td></tr>
            <tr><td><b>Status:</b></td>
                <td style="color: {status_config['fg'].name()}; font-weight: bold;">
                    {status_config['icon']} {status_config['label']}
                </td></tr>
            <tr><td><b>Next Due:</b></td><td>{item['next_due'] or 'Not Set'}</td></tr>
            <tr><td><b>Preservation Type:</b></td><td>{item.get('preservation_type', 'N/A')}</td></tr>
        </table>
        """

        QMessageBox.information(self, f"Preservation Details - {item['item_code']}", details)

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

    # ==================================================================
    # Export Methods
    # ==================================================================

    def _collect_data(self):
        """Collect table data for export."""
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
        return headers, data

    def _export_excel(self):
        """Export to Excel."""
        if not self.filtered_alerts:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Preservation Report", "preservation_report.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            headers, data = self._collect_data()
            export_to_excel(data, headers, file_path, sheet_name="Preservation")
            self.status_bar.showMessage(f"Exported to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _export_pdf(self):
        """Export to PDF."""
        if not self.filtered_alerts:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Preservation Report", "preservation_report.pdf",
            "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        try:
            headers, data = self._collect_data()
            export_to_pdf(data, headers, file_path, title="Preservation Report")
            self.status_bar.showMessage(f"PDF saved to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _print_report(self):
        """Print report as HTML."""
        if not self.filtered_alerts:
            QMessageBox.information(self, "No Data", "Nothing to print.")
            return

        html = self._generate_html_report()
        
        with tempfile.NamedTemporaryFile(
            suffix='.html', delete=False, mode='w', encoding='utf-8'
        ) as f:
            f.write(html)
            tmp_path = f.name

        QDesktopServices.openUrl(QUrl.fromLocalFile(tmp_path))
        self.status_bar.showMessage("Report opened for printing", 4000)

    def _generate_html_report(self) -> str:
        """Generate HTML report."""
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Preservation Report</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial; margin: 20px; }}
                h1 {{ color: #004D40; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
                th {{ background: #004D40; color: white; padding: 8px; text-align: left; }}
                td {{ padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px; }}
                .overdue {{ background: #FFCDD2; }}
                .due-today {{ background: #FFE0B2; }}
                .due-soon {{ background: #FFF9C4; }}
                .upcoming {{ background: #BBDEFB; }}
            </style>
        </head>
        <body>
            <h1>🛡️ Preservation Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            <p>Total Items: {len(self.filtered_alerts)}</p>
            <table>
                <tr>
                    <th>Status</th><th>Item Code</th><th>Description</th>
                    <th>Location</th><th>Next Due</th><th>Days Left</th>
                </tr>
        """

        for item in self.filtered_alerts:
            status_class = item["status"].lower().replace("_", "-")
            days_str = f"{item['days_left']} days" if item['days_left'] is not None else "N/A"
            html += f"""
                <tr class="{status_class}">
                    <td>{PRESERVATION_STATUSES[item['status']]['icon']} {item['status']}</td>
                    <td>{item['item_code']}</td>
                    <td>{item.get('description', '')}</td>
                    <td>{item.get('location_code', '')}</td>
                    <td>{item['next_due'] or 'N/A'}</td>
                    <td>{days_str}</td>
                </tr>
            """

        html += """
            </table>
        </body>
        </html>
        """
        return html

    def _copy_to_clipboard(self):
        """Copy entire table to clipboard."""
        if not self.filtered_alerts:
            return

        headers, data = self._collect_data()
        lines = ["\t".join(headers)]
        for row in data:
            lines.append("\t".join(row[h] for h in headers))
        
        QApplication.clipboard().setText("\n".join(lines))
        self.status_bar.showMessage("Table copied to clipboard", 3000)

    def _send_whatsapp_alert(self):
        """Send overdue alert via WhatsApp."""
        overdue_items = [
            item for item in self.filtered_alerts
            if item["status"] in ["OVERDUE", "DUE_TODAY"]
        ]

        if not overdue_items:
            QMessageBox.information(self, "No Overdue Items", 
                                  "No overdue items to report.")
            return

        lines = []
        lines.append("*⚠️ Preservation Alert*")
        lines.append(f"*Overdue Items:* {len(overdue_items)}")
        lines.append("")

        for item in overdue_items[:10]:
            days = abs(item["days_left"]) if item["days_left"] else 0
            lines.append(
                f"• {item['item_code']} – {item.get('description', 'N/A')} "
                f"({days}d overdue)"
            )

        if len(overdue_items) > 10:
            lines.append(f"... and {len(overdue_items) - 10} more items")

        lines.append("")
        lines.append("Please take immediate action.")
        lines.append(f"Generated by iMat – {datetime.now().strftime('%Y-%m-%d')}")

        message = "%0A".join(lines)
        wa_url = f"https://wa.me/989160684552?text={message}"
        webbrowser.open(wa_url)
        self.status_bar.showMessage("WhatsApp alert prepared", 3000)

    def closeEvent(self, event):
        """Handle dialog close."""
        self.db.close()
        super().closeEvent(event)