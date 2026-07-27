# ui/stock_view_dialog.py
"""
Live Stock Dashboard – iMat Material Control System (EPC Edition).

Real-time inventory visibility with:
- Comprehensive stock listing with filters
- QC status color coding
- Location hierarchy display
- Available vs allocated quantities
- Preservation status indicators
- Expiry date tracking
- Quick search and filter
- Export to Excel/PDF
- Print stock report
- WhatsApp sharing
- Auto-refresh capability
- Stock movement history
- Low stock alerts
"""

import os
import tempfile
import webbrowser
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QFrame, QToolBar, QStatusBar, QHeaderView,
    QComboBox, QLineEdit, QCheckBox, QFileDialog, QApplication,
    QAbstractItemView, QMenu, QSplitter, QWidget, QGroupBox,
    QFormLayout, QDoubleSpinBox, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl, QSize
from PyQt6.QtGui import QFont, QColor, QDesktopServices, QAction

from sqlalchemy import func, or_
from db.database import SessionLocal, get_db_session
from db.models import Stock, Product, Location, Transaction
from logic.reports_logic import get_current_inventory
from ui.logo_widget import LogoWidget
from utils.excel_export import export_to_excel
from utils.pdf_export import export_to_pdf

# ==================================================================
# Constants
# ==================================================================

# Auto-refresh interval (seconds)
AUTO_REFRESH_INTERVAL = 30

# QC Status definitions
QC_STATUS_COLORS = {
    "QUARANTINE": {"bg": "#FFE0B2", "fg": "#E65100", "icon": "⚠️"},
    "ACCEPTED": {"bg": "#C8E6C9", "fg": "#2E7D32", "icon": "✅"},
    "REJECTED": {"bg": "#FFCDD2", "fg": "#B71C1C", "icon": "❌"},
}

# Stock level indicators
STOCK_LEVELS = {
    "out_of_stock": {"color": "#D32F2F", "icon": "🔴", "label": "Out of Stock"},
    "critical": {"color": "#E65100", "icon": "🟠", "label": "Critical"},
    "low": {"color": "#F57F17", "icon": "🟡", "label": "Low Stock"},
    "adequate": {"color": "#2E7D32", "icon": "🟢", "label": "Adequate"},
    "overstock": {"color": "#1565C0", "icon": "🔵", "label": "Overstock"},
}

# ==================================================================
# Stock View Dialog
# ==================================================================

class StockViewDialog(QDialog):
    """
    Live stock dashboard with real-time inventory visibility.
    
    Features:
    - Comprehensive stock listing
    - Multiple filters
    - Export and share capabilities
    - Auto-refresh
    """

    stock_data_refreshed = pyqtSignal(int)  # record count

    def __init__(self, parent=None, user_role: str = "viewer"):
        """
        Initialize the Stock View dialog.
        
        Args:
            parent: Parent widget
            user_role: Current user's role
        """
        super().__init__(parent)
        self.user_role = user_role
        self.parent = parent
        self.db = SessionLocal()
        
        # State
        self.all_stock_data: List[Dict] = []
        self.filtered_data: List[Dict] = []
        self.auto_refresh_enabled = False
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.timeout.connect(self._refresh_data)
        
        # Window setup
        self.setWindowTitle("iMat – Live Stock Dashboard")
        self.setMinimumSize(1200, 700)
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

        title = QLabel("📊 Live Stock Dashboard")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("Real-time inventory visibility and tracking")
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
        self.action_refresh.setToolTip("Refresh stock data")
        self.action_refresh.triggered.connect(self._refresh_data)
        toolbar.addSeparator()

        self.action_auto_refresh = toolbar.addAction("⏱️ Auto-Refresh")
        self.action_auto_refresh.setCheckable(True)
        self.action_auto_refresh.setToolTip(f"Auto-refresh every {AUTO_REFRESH_INTERVAL}s")
        self.action_auto_refresh.toggled.connect(self._toggle_auto_refresh)
        toolbar.addSeparator()

        self.action_export_excel = toolbar.addAction("📥 Excel")
        self.action_export_excel.triggered.connect(self._export_excel)
        
        self.action_export_pdf = toolbar.addAction("📑 PDF")
        self.action_export_pdf.triggered.connect(self._export_pdf)
        
        self.action_print = toolbar.addAction("🖨️ Print")
        self.action_print.triggered.connect(self._print_report)
        toolbar.addSeparator()

        self.action_copy = toolbar.addAction("📋 Copy")
        self.action_copy.triggered.connect(self._copy_to_clipboard)
        
        self.action_whatsapp = toolbar.addAction("💬 WhatsApp")
        self.action_whatsapp.triggered.connect(self._share_whatsapp)
        
        self.action_email = toolbar.addAction("📧 Email")
        self.action_email.triggered.connect(self._share_email)

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

        # Search
        filter_layout.addWidget(QLabel("🔍:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by item code, description, heat no, location...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(250)
        self.search_input.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.search_input)

        # QC Status filter
        filter_layout.addWidget(QLabel("QC:"))
        self.qc_combo = QComboBox()
        self.qc_combo.addItems(["All Statuses", "QUARANTINE", "ACCEPTED", "REJECTED"])
        self.qc_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.qc_combo)

        # Discipline filter
        filter_layout.addWidget(QLabel("Discipline:"))
        self.discipline_combo = QComboBox()
        self.discipline_combo.addItem("All")
        self.discipline_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.discipline_combo)

        # Location filter
        filter_layout.addWidget(QLabel("Location:"))
        self.location_combo = QComboBox()
        self.location_combo.addItem("All Locations")
        self.location_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.location_combo)

        # Low stock only
        self.low_stock_check = QCheckBox("Low Stock Only")
        self.low_stock_check.toggled.connect(self._apply_filters)
        filter_layout.addWidget(self.low_stock_check)

        # Show zero quantity
        self.show_zero_check = QCheckBox("Show Zero Qty")
        self.show_zero_check.toggled.connect(self._apply_filters)
        filter_layout.addWidget(self.show_zero_check)

        filter_layout.addStretch()

        # Record count
        self.count_label = QLabel("Items: 0")
        self.count_label.setStyleSheet("color: #666; font-weight: bold;")
        filter_layout.addWidget(self.count_label)

        parent_layout.addWidget(filter_frame)

    def _build_content(self, parent_layout: QVBoxLayout):
        """Build the main content area."""
        # Summary bar
        summary_frame = QFrame()
        summary_frame.setStyleSheet("""
            QFrame {
                background: #E8F5E9;
                border-bottom: 1px solid #C8E6C9;
            }
            QLabel {
                font-size: 11px;
                font-weight: bold;
            }
        """)
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(10, 6, 10, 6)
        summary_layout.setSpacing(20)

        self.summary_total_label = QLabel("Total: 0")
        summary_layout.addWidget(self.summary_total_label)

        self.summary_quarantine_label = QLabel("⚠️ Quarantine: 0")
        self.summary_quarantine_label.setStyleSheet("color: #E65100;")
        summary_layout.addWidget(self.summary_quarantine_label)

        self.summary_accepted_label = QLabel("✅ Accepted: 0")
        self.summary_accepted_label.setStyleSheet("color: #2E7D32;")
        summary_layout.addWidget(self.summary_accepted_label)

        self.summary_rejected_label = QLabel("❌ Rejected: 0")
        self.summary_rejected_label.setStyleSheet("color: #C62828;")
        summary_layout.addWidget(self.summary_rejected_label)

        self.summary_value_label = QLabel("💰 Total Value: $0")
        summary_layout.addWidget(self.summary_value_label)

        summary_layout.addStretch()
        parent_layout.addWidget(summary_frame)

        # Main table
        self.table = QTableWidget()
        self.table.setColumnCount(13)
        self.table.setHorizontalHeaderLabels([
            "Item Code", "Description", "Discipline", "Heat No",
            "Location", "QC Status", "Total Qty", "Allocated",
            "Available", "Unit Cost", "Total Value",
            "Preservation Due", "Expiry Date"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
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
        col_widths = [110, 180, 90, 100, 100, 80, 70, 70, 70, 80, 90, 100, 100]
        for i, w in enumerate(col_widths):
            self.table.setColumnWidth(i, w)

        parent_layout.addWidget(self.table)

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready – Live stock data loaded")
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
        # All roles can view stock
        if self.user_role == "viewer":
            self.action_export_excel.setEnabled(True)
            self.action_export_pdf.setEnabled(True)
            self.status_bar.showMessage("Read-only mode – Viewing stock data")

    # ==================================================================
    # Data Loading
    # ==================================================================

    def _refresh_data(self):
        """Refresh stock data from database."""
        self.status_bar.showMessage("Loading stock data...")
        QApplication.processEvents()

        try:
            today = date.today()

            # Get all stock with quantity > 0 (or show all if zero is checked)
            query = self.db.query(
                Stock.item_code,
                Stock.heat_no,
                Stock.tag_no,
                Stock.serial_no,
                Stock.batch_no,
                Stock.location_id,
                Stock.qc_status,
                Stock.quantity,
                Stock.allocated_qty,
                Stock.expiry_date,
                Stock.next_preservation_due,
                Stock.received_date,
                Product.description,
                Product.discipline,
                Product.material_class,
                Product.category,
                Product.unit_of_measure,
                Product.unit_cost,
                Product.min_required_qty,
                Location.code.label('location_code'),
                Location.name.label('location_name'),
            ).join(Product, Stock.item_code == Product.item_code)\
             .join(Location, Stock.location_id == Location.id)

            if not self.show_zero_check.isChecked():
                query = query.filter(Stock.quantity > 0)

            results = query.order_by(Stock.item_code, Stock.heat_no).all()

            self.all_stock_data = []
            total_value = 0

            for row in results:
                available = row.quantity - row.allocated_qty
                unit_cost = row.unit_cost or 0
                item_value = available * unit_cost
                total_value += item_value

                # Determine stock level
                min_qty = row.min_required_qty or 0
                if available <= 0:
                    stock_level = "out_of_stock"
                elif available <= min_qty:
                    stock_level = "critical"
                elif available <= min_qty * 2:
                    stock_level = "low"
                elif available <= min_qty * 5:
                    stock_level = "adequate"
                else:
                    stock_level = "overstock"

                self.all_stock_data.append({
                    "item_code": row.item_code,
                    "description": row.description or "",
                    "discipline": row.discipline or "",
                    "material_class": row.material_class or "",
                    "category": row.category or "",
                    "unit": row.unit_of_measure or "EA",
                    "heat_no": row.heat_no,
                    "tag_no": row.tag_no or "",
                    "serial_no": row.serial_no or "",
                    "batch_no": row.batch_no or "",
                    "location_code": row.location_code or "",
                    "location_name": row.location_name or "",
                    "qc_status": row.qc_status,
                    "quantity": row.quantity,
                    "allocated_qty": row.allocated_qty,
                    "available_qty": available,
                    "unit_cost": unit_cost,
                    "total_value": item_value,
                    "min_required_qty": min_qty,
                    "stock_level": stock_level,
                    "expiry_date": row.expiry_date,
                    "next_preservation_due": row.next_preservation_due,
                    "received_date": row.received_date,
                })

            self._load_filter_options()
            self._apply_filters()
            
            # Update summary
            self._update_summary(total_value)
            
            self.stock_data_refreshed.emit(len(self.all_stock_data))
            self.status_bar.showMessage(
                f"Loaded {len(self.all_stock_data)} stock records", 3000
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load stock data:\n{str(e)}")

    def _load_filter_options(self):
        """Load filter options."""
        # Disciplines
        disciplines = sorted(set(
            item.get("discipline", "") for item in self.all_stock_data 
            if item.get("discipline")
        ))
        self.discipline_combo.blockSignals(True)
        self.discipline_combo.clear()
        self.discipline_combo.addItem("All")
        for d in disciplines:
            self.discipline_combo.addItem(d)
        self.discipline_combo.blockSignals(False)

        # Locations
        locations = sorted(set(
            item.get("location_code", "") for item in self.all_stock_data 
            if item.get("location_code")
        ))
        self.location_combo.blockSignals(True)
        self.location_combo.clear()
        self.location_combo.addItem("All Locations")
        for loc in locations:
            self.location_combo.addItem(loc)
        self.location_combo.blockSignals(False)

    def _apply_filters(self):
        """Apply filters to stock data."""
        search_text = self.search_input.text().strip().lower()
        qc_filter = self.qc_combo.currentText()
        disc_filter = self.discipline_combo.currentText()
        loc_filter = self.location_combo.currentText()
        low_stock_only = self.low_stock_check.isChecked()

        if qc_filter == "All Statuses":
            qc_filter = None
        if disc_filter == "All":
            disc_filter = None
        if loc_filter == "All Locations":
            loc_filter = None

        self.filtered_data = []
        for item in self.all_stock_data:
            # Search
            if search_text:
                searchable = (
                    f"{item['item_code']} {item['description']} "
                    f"{item['heat_no']} {item['location_code']}"
                ).lower()
                if search_text not in searchable:
                    continue

            # QC filter
            if qc_filter and item["qc_status"] != qc_filter:
                continue

            # Discipline filter
            if disc_filter and item["discipline"] != disc_filter:
                continue

            # Location filter
            if loc_filter and item["location_code"] != loc_filter:
                continue

            # Low stock only
            if low_stock_only and item["stock_level"] not in ["out_of_stock", "critical", "low"]:
                continue

            self.filtered_data.append(item)

        self._display_data()
        self.count_label.setText(f"Items: {len(self.filtered_data)}")

    def _display_data(self):
        """Display filtered data in the table."""
        self.table.setRowCount(len(self.filtered_data))

        for row, item in enumerate(self.filtered_data):
            # Item Code
            code_item = QTableWidgetItem(item["item_code"])
            code_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            self.table.setItem(row, 0, code_item)

            # Description
            self.table.setItem(row, 1, QTableWidgetItem(item.get("description", "")))

            # Discipline
            self.table.setItem(row, 2, QTableWidgetItem(item.get("discipline", "")))

            # Heat No
            self.table.setItem(row, 3, QTableWidgetItem(item.get("heat_no", "")))

            # Location
            self.table.setItem(row, 4, QTableWidgetItem(item.get("location_code", "")))

            # QC Status with color
            qc_item = QTableWidgetItem(item["qc_status"])
            qc_config = QC_STATUS_COLORS.get(item["qc_status"], {})
            if qc_config:
                qc_item.setBackground(QColor(qc_config.get("bg", "#FFF")))
                qc_item.setForeground(QColor(qc_config.get("fg", "#000")))
                qc_item.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            self.table.setItem(row, 5, qc_item)

            # Total Qty
            qty_item = QTableWidgetItem(f"{item['quantity']:.2f}")
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 6, qty_item)

            # Allocated
            alloc_item = QTableWidgetItem(f"{item['allocated_qty']:.2f}")
            alloc_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 7, alloc_item)

            # Available
            avail = item["available_qty"]
            avail_item = QTableWidgetItem(f"{avail:.2f}")
            avail_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            # Color based on stock level
            level_config = STOCK_LEVELS.get(item["stock_level"], {})
            if level_config:
                avail_item.setForeground(QColor(level_config["color"]))
                avail_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            
            self.table.setItem(row, 8, avail_item)

            # Unit Cost
            cost_item = QTableWidgetItem(f"${item['unit_cost']:,.2f}")
            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 9, cost_item)

            # Total Value
            value_item = QTableWidgetItem(f"${item['total_value']:,.2f}")
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 10, value_item)

            # Preservation Due
            pres_str = item["next_preservation_due"].strftime("%Y-%m-%d") if item["next_preservation_due"] else "N/A"
            pres_item = QTableWidgetItem(pres_str)
            if item["next_preservation_due"] and item["next_preservation_due"] <= date.today():
                pres_item.setForeground(QColor("#D32F2F"))
            self.table.setItem(row, 11, pres_item)

            # Expiry Date
            exp_str = item["expiry_date"].strftime("%Y-%m-%d") if item["expiry_date"] else "N/A"
            exp_item = QTableWidgetItem(exp_str)
            if item["expiry_date"] and item["expiry_date"] <= date.today():
                exp_item.setForeground(QColor("#D32F2F"))
            elif item["expiry_date"] and item["expiry_date"] <= date.today() + timedelta(days=30):
                exp_item.setForeground(QColor("#E65100"))
            self.table.setItem(row, 12, exp_item)

    def _update_summary(self, total_value: float):
        """Update the summary bar."""
        total_items = len(self.all_stock_data)
        
        quarantine_count = sum(
            1 for item in self.all_stock_data 
            if item["qc_status"] == "QUARANTINE"
        )
        accepted_count = sum(
            1 for item in self.all_stock_data 
            if item["qc_status"] == "ACCEPTED"
        )
        rejected_count = sum(
            1 for item in self.all_stock_data 
            if item["qc_status"] == "REJECTED"
        )

        self.summary_total_label.setText(f"Total Items: {total_items}")
        self.summary_quarantine_label.setText(f"⚠️ Quarantine: {quarantine_count}")
        self.summary_accepted_label.setText(f"✅ Accepted: {accepted_count}")
        self.summary_rejected_label.setText(f"❌ Rejected: {rejected_count}")
        self.summary_value_label.setText(f"💰 Total Value: ${total_value:,.2f}")

    # ==================================================================
    # Auto-Refresh
    # ==================================================================

    def _toggle_auto_refresh(self, enabled: bool):
        """Toggle auto-refresh."""
        self.auto_refresh_enabled = enabled
        if enabled:
            self.auto_refresh_timer.start(AUTO_REFRESH_INTERVAL * 1000)
            self.status_bar.showMessage(
                f"Auto-refresh enabled (every {AUTO_REFRESH_INTERVAL}s)", 3000
            )
        else:
            self.auto_refresh_timer.stop()
            self.status_bar.showMessage("Auto-refresh disabled", 3000)

    # ==================================================================
    # Context Menu
    # ==================================================================

    def _show_context_menu(self, pos):
        """Show context menu on table."""
        menu = QMenu(self)
        menu.addAction("🔍 View Details", self._view_item_details)
        menu.addAction("📋 Copy Row", self._copy_selected_row)
        menu.addAction("📋 Copy Item Code", self._copy_selected_code)
        menu.addSeparator()
        menu.addAction("📊 Show Movement History", self._show_movement_history)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _view_item_details(self):
        """View details of selected item."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an item.")
            return

        item = self.filtered_data[row]
        qc_config = QC_STATUS_COLORS.get(item["qc_status"], {})
        
        details = f"""
        <h3>Stock Details</h3>
        <table style="width: 100%; line-height: 1.8;">
            <tr><td><b>Item Code:</b></td><td>{item['item_code']}</td></tr>
            <tr><td><b>Description:</b></td><td>{item.get('description', 'N/A')}</td></tr>
            <tr><td><b>Discipline:</b></td><td>{item.get('discipline', 'N/A')}</td></tr>
            <tr><td><b>Category:</b></td><td>{item.get('category', 'N/A')}</td></tr>
            <tr><td><b>Heat No:</b></td><td>{item.get('heat_no', 'N/A')}</td></tr>
            <tr><td><b>Location:</b></td><td>{item.get('location_code', 'N/A')}</td></tr>
            <tr><td><b>QC Status:</b></td>
                <td style="color: {qc_config.get('fg', '#000')}; font-weight: bold;">
                    {qc_config.get('icon', '')} {item['qc_status']}
                </td></tr>
            <tr><td><b>Total Qty:</b></td><td>{item['quantity']:.2f}</td></tr>
            <tr><td><b>Allocated:</b></td><td>{item['allocated_qty']:.2f}</td></tr>
            <tr><td><b>Available:</b></td><td>{item['available_qty']:.2f}</td></tr>
            <tr><td><b>Unit Cost:</b></td><td>${item['unit_cost']:,.2f}</td></tr>
            <tr><td><b>Total Value:</b></td><td>${item['total_value']:,.2f}</td></tr>
        </table>
        """

        QMessageBox.information(self, f"Stock Details - {item['item_code']}", details)

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

    def _copy_selected_code(self):
        """Copy selected item code."""
        row = self.table.currentRow()
        if row < 0:
            return
        code = self.table.item(row, 0).text()
        QApplication.clipboard().setText(code)
        self.status_bar.showMessage(f"Copied: {code}", 3000)

    def _show_movement_history(self):
        """Show movement history for selected item."""
        row = self.table.currentRow()
        if row < 0:
            return

        item_code = self.table.item(row, 0).text()
        
        from logic.reports import get_movement_report
        data = get_movement_report(item_code)
        
        if data:
            text = "\n".join([
                f"{m['Date']} | {m['Type']} | {m['Doc No']} | "
                f"Qty: {m['Qty']} | {m['Location']}"
                for m in data[:20]
            ])
            QMessageBox.information(
                self, f"Movement History - {item_code}",
                f"Recent movements for {item_code}:\n\n{text}"
            )
        else:
            QMessageBox.information(self, "No Data", "No movement history found.")

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
        if not self.filtered_data:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Stock Report", "stock_report.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            headers, data = self._collect_data()
            export_to_excel(data, headers, file_path, sheet_name="Stock Report")
            self.status_bar.showMessage(f"Exported to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _export_pdf(self):
        """Export to PDF."""
        if not self.filtered_data:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Stock Report", "stock_report.pdf",
            "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        try:
            headers, data = self._collect_data()
            export_to_pdf(data, headers, file_path, title="Live Stock Report")
            self.status_bar.showMessage(f"PDF saved to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _print_report(self):
        """Print report."""
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
        self.status_bar.showMessage("Report opened for printing", 4000)

    def _generate_html_report(self) -> str:
        """Generate HTML report."""
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Live Stock Report</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial; margin: 20px; }}
                h1 {{ color: #004D40; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
                th {{ background: #004D40; color: white; padding: 8px; text-align: left; }}
                td {{ padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px; }}
                tr:nth-child(even) {{ background: #f9f9f9; }}
            </style>
        </head>
        <body>
            <h1>📊 Live Stock Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            <p>Total Items: {len(self.filtered_data)}</p>
            <table>
                <tr>
                    <th>Item Code</th><th>Description</th><th>Location</th>
                    <th>QC Status</th><th>Available</th><th>Value</th>
                </tr>
        """

        for item in self.filtered_data:
            html += f"""
                <tr>
                    <td>{item['item_code']}</td>
                    <td>{item.get('description', '')}</td>
                    <td>{item.get('location_code', '')}</td>
                    <td>{item['qc_status']}</td>
                    <td>{item['available_qty']:.2f}</td>
                    <td>${item['total_value']:,.2f}</td>
                </tr>
            """

        html += """
            </table>
        </body>
        </html>
        """
        return html

    def _copy_to_clipboard(self):
        """Copy table to clipboard."""
        if not self.filtered_data:
            return

        headers, data = self._collect_data()
        lines = ["\t".join(headers)]
        for row in data:
            lines.append("\t".join(row[h] for h in headers))
        
        QApplication.clipboard().setText("\n".join(lines))
        self.status_bar.showMessage("Table copied to clipboard", 3000)

    def _share_whatsapp(self):
        """Share summary via WhatsApp."""
        lines = []
        lines.append("*📊 Live Stock Summary*")
        lines.append(f"Total Items: {len(self.all_stock_data)}")
        lines.append(f"Filtered: {len(self.filtered_data)}")
        lines.append("")
        
        # Summary by QC
        qc_counts = {"QUARANTINE": 0, "ACCEPTED": 0, "REJECTED": 0}
        total_value = 0
        for item in self.filtered_data:
            qc_counts[item["qc_status"]] = qc_counts.get(item["qc_status"], 0) + 1
            total_value += item.get("total_value", 0)
        
        lines.append(f"⚠️ Quarantine: {qc_counts.get('QUARANTINE', 0)}")
        lines.append(f"✅ Accepted: {qc_counts.get('ACCEPTED', 0)}")
        lines.append(f"❌ Rejected: {qc_counts.get('REJECTED', 0)}")
        lines.append(f"💰 Total Value: ${total_value:,.2f}")
        lines.append("")
        lines.append(f"Generated by iMat – {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        message = "%0A".join(lines)
        wa_url = f"https://wa.me/989160684552?text={message}"
        webbrowser.open(wa_url)
        self.status_bar.showMessage("WhatsApp message prepared", 3000)

    def _share_email(self):
        """Share via email."""
        subject = "iMat Live Stock Report"
        body = (
            f"Live Stock Report%0D%0A%0D%0A"
            f"Total Items: {len(self.all_stock_data)}%0D%0A"
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}%0D%0A%0D%0A"
            f"Please find the attached stock report."
        )
        mailto = f"mailto:?subject={subject}&body={body}"
        QDesktopServices.openUrl(QUrl(mailto))
        self.status_bar.showMessage("Email client opened", 3000)

    def closeEvent(self, event):
        """Handle dialog close."""
        if self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.stop()
        self.db.close()
        super().closeEvent(event)