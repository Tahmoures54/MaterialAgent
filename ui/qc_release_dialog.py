# ui/qc_release_dialog.py
"""
QC Release Dialog – iMat Material Control System (EPC Edition).

Quality Control release management with:
- Searchable quarantine item listing
- Bulk QC release (Accept/Reject)
- Partial quantity release
- QC inspection notes and remarks
- Release history tracking
- Certificate/document linking
- Visual status indicators
- Multi-level filtering
- Batch processing
- QC inspector assignment
- Release report generation
- WhatsApp notification for rejected items
"""

import os
import tempfile
import webbrowser
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, 
    QComboBox, QPushButton, QMessageBox, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox,
    QCheckBox, QTextEdit, QGroupBox, QSplitter, QWidget,
    QAbstractItemView, QMenu, QFileDialog, QApplication,
    QStatusBar, QToolBar, QDateEdit, QProgressBar
)
from PyQt6.QtCore import Qt, QDate, QUrl, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QDesktopServices, QAction

from sqlalchemy import func, or_
from db.database import SessionLocal, get_db_session
from db.models import Stock, Product, Location, Document, DocumentLine
from logic.stock_logic import change_qc_status, get_stock_record
from ui.logo_widget import LogoWidget
from utils.excel_export import export_to_excel
from utils.pdf_export import export_to_pdf

# ==================================================================
# Constants
# ==================================================================

# QC Status definitions
QC_STATUSES = {
    "QUARANTINE": {
        "label": "Quarantine",
        "icon": "⚠️",
        "bg": QColor("#FFE0B2"),
        "fg": QColor("#E65100"),
        "description": "Awaiting QC inspection"
    },
    "ACCEPTED": {
        "label": "Accepted",
        "icon": "✅",
        "bg": QColor("#C8E6C9"),
        "fg": QColor("#1B5E20"),
        "description": "Passed QC - available for issue"
    },
    "REJECTED": {
        "label": "Rejected",
        "icon": "❌",
        "bg": QColor("#FFCDD2"),
        "fg": QColor("#B71C1C"),
        "description": "Failed QC - not usable"
    },
}

# QC Release actions
RELEASE_ACTIONS = {
    "ACCEPTED": {
        "label": "Accept (Move to Available Stock)",
        "icon": "✅",
        "color": "#2E7D32",
        "description": "Material passes inspection and is available for issue"
    },
    "REJECTED": {
        "label": "Reject (Move to Rejected Stock)",
        "icon": "❌",
        "color": "#C62828",
        "description": "Material fails inspection - quarantine or return"
    },
}

# Inspection types
INSPECTION_TYPES = [
    "Visual Inspection",
    "Dimensional Check",
    "Material Test Certificate Review",
    "Non-Destructive Testing (NDT)",
    "Positive Material Identification (PMI)",
    "Pressure Test",
    "Hardness Test",
    "Coating Inspection",
    "Document Review",
    "Receiving Inspection",
]

# ==================================================================
# QC Release Dialog
# ==================================================================

class QCReleaseDialog(QDialog):
    """
    Quality Control release dialog for managing quarantine stock.
    
    Features:
    - View all quarantine items
    - Accept or reject with partial quantities
    - Inspection notes and documentation
    - Release history
    - Batch processing
    """

    qc_released = pyqtSignal(str, str)  # item_code, new_status

    def __init__(self, parent=None, user_role: str = "viewer"):
        """
        Initialize the QC Release dialog.
        
        Args:
            parent: Parent widget
            user_role: Current user's role
        """
        super().__init__(parent)
        self.user_role = user_role
        self.parent = parent
        self.db = SessionLocal()
        self.current_user = self._get_username()
        
        # State
        self.all_quarantine_items: List[Dict] = []
        self.filtered_items: List[Dict] = []
        
        # Window setup
        self.setWindowTitle("iMat – QC Release (Quarantine Management)")
        self.setMinimumSize(1200, 750)
        self.setModal(True)
        
        # Build UI
        self._init_ui()
        
        # Load data
        self._load_quarantine_items()
        
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

        title = QLabel("🔍 QC Release Manager")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("Inspect and release materials from quarantine")
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
        self.action_refresh.triggered.connect(self._load_quarantine_items)
        toolbar.addSeparator()

        self.action_accept = toolbar.addAction("✅ Accept Selected")
        self.action_accept.setToolTip("Accept selected items (move to available stock)")
        self.action_accept.triggered.connect(lambda: self._release_items("ACCEPTED"))
        
        self.action_reject = toolbar.addAction("❌ Reject Selected")
        self.action_reject.setToolTip("Reject selected items (move to rejected stock)")
        self.action_reject.triggered.connect(lambda: self._release_items("REJECTED"))
        toolbar.addSeparator()

        self.action_accept_all = toolbar.addAction("✅ Accept All")
        self.action_accept_all.setToolTip("Accept all quarantine items")
        self.action_accept_all.triggered.connect(lambda: self._release_all("ACCEPTED"))
        toolbar.addSeparator()

        self.action_export = toolbar.addAction("📥 Export")
        self.action_export.triggered.connect(self._export_excel)
        
        self.action_print = toolbar.addAction("🖨️ Print")
        self.action_print.triggered.connect(self._print_report)
        toolbar.addSeparator()

        self.action_whatsapp = toolbar.addAction("💬 Notify Rejected")
        self.action_whatsapp.setToolTip("Send WhatsApp notification for rejected items")
        self.action_whatsapp.triggered.connect(self._notify_whatsapp)

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
        self.search_input.setPlaceholderText("Search by item code, description, heat no...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(250)
        self.search_input.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.search_input)

        # Location filter
        filter_layout.addWidget(QLabel("Location:"))
        self.location_combo = QComboBox()
        self.location_combo.addItem("All Locations")
        self.location_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.location_combo)

        # Discipline filter
        filter_layout.addWidget(QLabel("Discipline:"))
        self.discipline_combo = QComboBox()
        self.discipline_combo.addItem("All")
        self.discipline_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.discipline_combo)

        # Days in quarantine
        filter_layout.addWidget(QLabel("Days in Quarantine:"))
        self.days_combo = QComboBox()
        self.days_combo.addItems(["All", "> 7 days", "> 14 days", "> 30 days", "> 60 days", "> 90 days"])
        self.days_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.days_combo)

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
            "Item Code", "Description", "Discipline", "Heat No",
            "Location", "Quantity", "Received Date", "Days in QC",
            "Cert No", "QC Status", "Inspector", "Remarks"
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
        col_widths = [110, 180, 90, 100, 100, 70, 90, 70, 100, 80, 80, 120]
        for i, w in enumerate(col_widths):
            self.table.setColumnWidth(i, w)

        parent_layout.addWidget(self.table)

        # Quick release panel (at bottom)
        quick_frame = QFrame()
        quick_frame.setStyleSheet("""
            QFrame {
                background: #FAFAFA;
                border-top: 2px solid #B2DFDB;
            }
        """)
        quick_layout = QHBoxLayout(quick_frame)
        quick_layout.setContentsMargins(15, 10, 15, 10)
        quick_layout.setSpacing(10)

        quick_layout.addWidget(QLabel("Quick Release:"))

        self.quick_qty_spin = QDoubleSpinBox()
        self.quick_qty_spin.setRange(0.01, 999999.99)
        self.quick_qty_spin.setDecimals(2)
        self.quick_qty_spin.setValue(1.0)
        self.quick_qty_spin.setToolTip("Quantity to release (0 = full quantity)")
        quick_layout.addWidget(QLabel("Qty:"))
        quick_layout.addWidget(self.quick_qty_spin)

        self.quick_inspection_combo = QComboBox()
        self.quick_inspection_combo.addItems(INSPECTION_TYPES)
        quick_layout.addWidget(QLabel("Type:"))
        quick_layout.addWidget(self.quick_inspection_combo)

        self.quick_notes_edit = QLineEdit()
        self.quick_notes_edit.setPlaceholderText("Quick notes (optional)")
        self.quick_notes_edit.setMaximumWidth(200)
        quick_layout.addWidget(self.quick_notes_edit)

        btn_quick_accept = QPushButton("✅ Quick Accept")
        btn_quick_accept.setStyleSheet(self._get_button_style("success"))
        btn_quick_accept.clicked.connect(lambda: self._quick_release("ACCEPTED"))
        quick_layout.addWidget(btn_quick_accept)

        btn_quick_reject = QPushButton("❌ Quick Reject")
        btn_quick_reject.setStyleSheet(self._get_button_style("danger"))
        btn_quick_reject.clicked.connect(lambda: self._quick_release("REJECTED"))
        quick_layout.addWidget(btn_quick_reject)

        quick_layout.addStretch()

        parent_layout.addWidget(quick_frame)

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage(
            "Ready – Select items and use Accept/Reject buttons to process QC release"
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
    # Style Methods
    # ==================================================================

    def _get_button_style(self, button_type: str) -> str:
        """Get button stylesheet."""
        styles = {
            "success": """
                QPushButton {
                    background-color: #2E7D32;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #1B5E20; }
                QPushButton:disabled { background-color: #999; }
            """,
            "danger": """
                QPushButton {
                    background-color: #C62828;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #B71C1C; }
                QPushButton:disabled { background-color: #999; }
            """,
            "primary": """
                QPushButton {
                    background-color: #00897B;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #00695C; }
            """,
            "neutral": """
                QPushButton {
                    background-color: #757575;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #616161; }
            """,
        }
        return styles.get(button_type, styles["neutral"])

    # ==================================================================
    # Role Permissions
    # ==================================================================

    def _apply_role_permissions(self):
        """Apply role-based restrictions."""
        if self.user_role == "viewer":
            self.action_accept.setEnabled(False)
            self.action_reject.setEnabled(False)
            self.action_accept_all.setEnabled(False)
            self.status_bar.showMessage("Read-only mode – Viewing quarantine items")

    def _get_username(self) -> str:
        """Get current username."""
        try:
            if self.parent and hasattr(self.parent, 'current_user'):
                return self.parent.current_user
        except Exception:
            pass
        return "unknown"

    # ==================================================================
    # Data Loading
    # ==================================================================

    def _load_quarantine_items(self):
        """Load all quarantine items from database."""
        self.status_bar.showMessage("Loading quarantine items...")
        QApplication.processEvents()

        try:
            today = date.today()

            # Get all quarantine stock
            stocks = self.db.query(Stock).filter(
                Stock.qc_status == "QUARANTINE",
                Stock.quantity > 0
            ).order_by(Stock.received_date.desc()).all()

            self.all_quarantine_items = []
            for stock in stocks:
                product = self.db.query(Product).filter_by(item_code=stock.item_code).first()
                location = self.db.query(Location).filter_by(id=stock.location_id).first()

                # Calculate days in quarantine
                days_in_qc = (today - stock.received_date).days if stock.received_date else 0

                # Find related document
                doc_line = self.db.query(DocumentLine).filter(
                    DocumentLine.item_code == stock.item_code,
                    DocumentLine.heat_no == stock.heat_no,
                    DocumentLine.location_id == stock.location_id
                ).first()

                cert_no = doc_line.cert_no if doc_line else stock.tag_no or ""

                self.all_quarantine_items.append({
                    "stock_id": stock.id,
                    "item_code": stock.item_code,
                    "description": product.description if product else "",
                    "discipline": product.discipline if product else "",
                    "material_class": product.material_class if product else "",
                    "heat_no": stock.heat_no,
                    "location_id": stock.location_id,
                    "location_code": location.code if location else "",
                    "quantity": stock.quantity,
                    "allocated_qty": stock.allocated_qty,
                    "available_qty": stock.available_qty,
                    "received_date": stock.received_date,
                    "days_in_qc": days_in_qc,
                    "cert_no": cert_no,
                    "tag_no": stock.tag_no,
                    "serial_no": stock.serial_no,
                    "batch_no": stock.batch_no,
                    "expiry_date": stock.expiry_date,
                    "qc_status": stock.qc_status,
                })

            self._load_filter_options()
            self._apply_filters()
            self.status_bar.showMessage(
                f"Loaded {len(self.all_quarantine_items)} quarantine items", 3000
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load quarantine items:\n{str(e)}")

    def _load_filter_options(self):
        """Load filter options."""
        # Locations
        locations = sorted(set(
            item["location_code"] for item in self.all_quarantine_items 
            if item["location_code"]
        ))
        self.location_combo.blockSignals(True)
        self.location_combo.clear()
        self.location_combo.addItem("All Locations")
        for loc in locations:
            self.location_combo.addItem(loc)
        self.location_combo.blockSignals(False)

        # Disciplines
        disciplines = sorted(set(
            item["discipline"] for item in self.all_quarantine_items 
            if item["discipline"]
        ))
        self.discipline_combo.blockSignals(True)
        self.discipline_combo.clear()
        self.discipline_combo.addItem("All")
        for d in disciplines:
            self.discipline_combo.addItem(d)
        self.discipline_combo.blockSignals(False)

    def _apply_filters(self):
        """Apply filters to quarantine items."""
        search_text = self.search_input.text().strip().lower()
        loc_filter = self.location_combo.currentText()
        disc_filter = self.discipline_combo.currentText()
        days_filter = self.days_combo.currentText()

        if loc_filter == "All Locations":
            loc_filter = None
        if disc_filter == "All":
            disc_filter = None

        self.filtered_items = []
        for item in self.all_quarantine_items:
            # Search filter
            if search_text:
                searchable = (
                    f"{item['item_code']} {item['description']} "
                    f"{item['heat_no']} {item['location_code']}"
                ).lower()
                if search_text not in searchable:
                    continue

            # Location filter
            if loc_filter and item["location_code"] != loc_filter:
                continue

            # Discipline filter
            if disc_filter and item["discipline"] != disc_filter:
                continue

            # Days filter
            if days_filter != "All":
                threshold = int(days_filter.split()[1])  # Extract number
                if item["days_in_qc"] <= threshold:
                    continue

            self.filtered_items.append(item)

        self._display_items()
        self.count_label.setText(f"Items: {len(self.filtered_items)}")

    def _display_items(self):
        """Display filtered items in the table."""
        self.table.setRowCount(len(self.filtered_items))

        for row, item in enumerate(self.filtered_items):
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

            # Quantity
            qty_item = QTableWidgetItem(f"{item['quantity']:.2f}")
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 5, qty_item)

            # Received Date
            date_str = item["received_date"].strftime("%Y-%m-%d") if item["received_date"] else ""
            self.table.setItem(row, 6, QTableWidgetItem(date_str))

            # Days in QC
            days = item["days_in_qc"]
            days_item = QTableWidgetItem(f"{days} days")
            days_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if days > 30:
                days_item.setForeground(QColor("#D32F2F"))
            elif days > 14:
                days_item.setForeground(QColor("#E65100"))
            self.table.setItem(row, 7, days_item)

            # Cert No
            self.table.setItem(row, 8, QTableWidgetItem(item.get("cert_no", "")))

            # QC Status
            qc_item = QTableWidgetItem(f"⚠️ QUARANTINE")
            qc_item.setBackground(QColor("#FFE0B2"))
            qc_item.setForeground(QColor("#E65100"))
            qc_item.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            self.table.setItem(row, 9, qc_item)

            # Inspector (placeholder - can be filled when releasing)
            self.table.setItem(row, 10, QTableWidgetItem(""))

            # Remarks
            self.table.setItem(row, 11, QTableWidgetItem(""))

    # ==================================================================
    # Context Menu
    # ==================================================================

    def _show_context_menu(self, pos):
        """Show context menu on table."""
        menu = QMenu(self)
        menu.addAction("✅ Accept Selected", lambda: self._release_items("ACCEPTED"))
        menu.addAction("❌ Reject Selected", lambda: self._release_items("REJECTED"))
        menu.addSeparator()
        menu.addAction("🔍 View Details", self._view_item_details)
        menu.addAction("📋 Copy Item Code", self._copy_selected_code)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ==================================================================
    # Release Actions
    # ==================================================================

    def _get_selected_items(self) -> List[Dict]:
        """Get selected items from table."""
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            return []

        return [self.filtered_items[row] for row in sorted(selected_rows)]

    def _quick_release(self, new_status: str):
        """Quick release using the bottom panel."""
        if self.user_role == "viewer":
            QMessageBox.warning(self, "Access Denied", "You cannot perform QC release.")
            return

        selected = self._get_selected_items()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select items to release.")
            return

        qty = self.quick_qty_spin.value()
        inspection_type = self.quick_inspection_combo.currentText()
        notes = self.quick_notes_edit.text().strip()

        self._process_release(selected, new_status, qty, inspection_type, notes)

    def _release_items(self, new_status: str):
        """Release selected items with confirmation dialog."""
        if self.user_role == "viewer":
            QMessageBox.warning(self, "Access Denied", "You cannot perform QC release.")
            return

        selected = self._get_selected_items()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select items to release.")
            return

        # Show release dialog
        dlg = QCReleaseConfirmDialog(
            self, selected, new_status, self.current_user
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            release_data = dlg.get_release_data()
            self._process_release(
                release_data["items"],
                release_data["new_status"],
                release_data.get("quantity", 0),
                release_data.get("inspection_type", ""),
                release_data.get("notes", "")
            )

    def _release_all(self, new_status: str):
        """Release all quarantine items."""
        if self.user_role == "viewer":
            QMessageBox.warning(self, "Access Denied", "You cannot perform QC release.")
            return

        if not self.filtered_items:
            QMessageBox.information(self, "No Items", "No quarantine items to release.")
            return

        confirm = QMessageBox.question(
            self, f"Confirm {new_status} All",
            f"Are you sure you want to {new_status.lower()} ALL {len(self.filtered_items)} "
            f"quarantine items?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._process_release(
            self.filtered_items, new_status, 0,
            "Bulk Release", "Bulk QC release - all items"
        )

    def _process_release(self, items: List[Dict], new_status: str, 
                         qty: float, inspection_type: str, notes: str):
        """
        Process QC release for items.
        
        Args:
            items: List of item dictionaries
            new_status: Target QC status (ACCEPTED or REJECTED)
            qty: Quantity to release (0 = full quantity)
            inspection_type: Type of inspection performed
            notes: Inspector notes
        """
        if not items:
            return

        try:
            success_count = 0
            error_count = 0
            errors = []

            for item in items:
                try:
                    release_qty = qty if qty > 0 else item["quantity"]
                    
                    if release_qty > item["quantity"]:
                        errors.append(
                            f"{item['item_code']}: Release qty ({release_qty}) "
                            f"exceeds available ({item['quantity']})"
                        )
                        error_count += 1
                        continue

                    change_qc_status(
                        db=self.db,
                        item_code=item["item_code"],
                        heat_no=item["heat_no"],
                        location_id=item["location_id"],
                        old_status="QUARANTINE",
                        new_status=new_status,
                        qty=release_qty
                    )

                    # Update stock with inspection notes (if model supports it)
                    stock = get_stock_record(
                        self.db, item["item_code"], item["heat_no"],
                        item["location_id"], new_status
                    )
                    if stock and hasattr(stock, 'remarks'):
                        stock.remarks = (
                            f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] "
                            f"{inspection_type} by {self.current_user}"
                        )
                        if notes:
                            stock.remarks += f" - {notes}"

                    success_count += 1
                    self.qc_released.emit(item["item_code"], new_status)

                except ValueError as e:
                    errors.append(f"{item['item_code']}: {str(e)}")
                    error_count += 1

            self.db.commit()

            # Show result
            status_config = QC_STATUSES.get(new_status, {})
            result_msg = f"QC Release Complete\n\n"
            result_msg += f"✅ {success_count} item(s) {new_status.lower()}\n"
            
            if error_count > 0:
                result_msg += f"❌ {error_count} error(s):\n"
                for err in errors[:5]:
                    result_msg += f"  • {err}\n"
                if len(errors) > 5:
                    result_msg += f"  ... and {len(errors) - 5} more errors"

            QMessageBox.information(
                self, "QC Release Result", result_msg
            )

            self._load_quarantine_items()
            self.status_bar.showMessage(
                f"{success_count} items {new_status.lower()}", 5000
            )

        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"QC release failed:\n{str(e)}")

    def _view_item_details(self):
        """View details of selected item."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an item.")
            return

        item = self.filtered_items[row]

        details = f"""
        <h3>Quarantine Item Details</h3>
        <table style="width: 100%; line-height: 1.8;">
            <tr><td><b>Item Code:</b></td><td>{item['item_code']}</td></tr>
            <tr><td><b>Description:</b></td><td>{item.get('description', 'N/A')}</td></tr>
            <tr><td><b>Discipline:</b></td><td>{item.get('discipline', 'N/A')}</td></tr>
            <tr><td><b>Heat No:</b></td><td>{item.get('heat_no', 'N/A')}</td></tr>
            <tr><td><b>Location:</b></td><td>{item.get('location_code', 'N/A')}</td></tr>
            <tr><td><b>Quantity:</b></td><td>{item['quantity']:.2f}</td></tr>
            <tr><td><b>Received:</b></td><td>{item.get('received_date', 'N/A')}</td></tr>
            <tr><td><b>Days in QC:</b></td><td>{item['days_in_qc']} days</td></tr>
            <tr><td><b>Certificate:</b></td><td>{item.get('cert_no', 'N/A')}</td></tr>
            <tr><td><b>Tag No:</b></td><td>{item.get('tag_no', 'N/A')}</td></tr>
        </table>
        <hr>
        <p style="color: #E65100; font-weight: bold;">
            ⚠️ This item is in QUARANTINE and requires QC inspection.
        </p>
        """

        QMessageBox.information(self, f"Item Details - {item['item_code']}", details)

    def _copy_selected_code(self):
        """Copy selected item code to clipboard."""
        row = self.table.currentRow()
        if row < 0:
            return

        code = self.table.item(row, 0).text()
        QApplication.clipboard().setText(code)
        self.status_bar.showMessage(f"Copied: {code}", 3000)

    # ==================================================================
    # Export & Share
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
        if not self.filtered_items:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export QC Report", "qc_report.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            headers, data = self._collect_data()
            export_to_excel(data, headers, file_path, sheet_name="QC Report")
            self.status_bar.showMessage(f"Exported to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _print_report(self):
        """Print report."""
        if not self.filtered_items:
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
            <title>QC Quarantine Report</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial; margin: 20px; }}
                h1 {{ color: #004D40; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
                th {{ background: #004D40; color: white; padding: 8px; text-align: left; }}
                td {{ padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px; }}
                .quarantine {{ background: #FFE0B2; }}
            </style>
        </head>
        <body>
            <h1>🔍 QC Quarantine Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            <p>Total Items: {len(self.filtered_items)}</p>
            <table>
                <tr>
                    <th>Item Code</th><th>Description</th><th>Heat No</th>
                    <th>Location</th><th>Quantity</th><th>Days in QC</th>
                </tr>
        """

        for item in self.filtered_items:
            html += f"""
                <tr class="quarantine">
                    <td>{item['item_code']}</td>
                    <td>{item.get('description', '')}</td>
                    <td>{item.get('heat_no', '')}</td>
                    <td>{item.get('location_code', '')}</td>
                    <td>{item['quantity']:.2f}</td>
                    <td>{item['days_in_qc']} days</td>
                </tr>
            """

        html += """
            </table>
        </body>
        </html>
        """
        return html

    def _notify_whatsapp(self):
        """Send WhatsApp notification for rejected items."""
        rejected = [
            item for item in self.filtered_items 
            if item.get("qc_status") == "REJECTED"
        ]

        if not rejected:
            QMessageBox.information(self, "No Rejected Items", 
                                  "No rejected items to notify about.")
            return

        lines = []
        lines.append("*⚠️ QC Rejection Notification*")
        lines.append(f"*Rejected Items:* {len(rejected)}")
        lines.append("")

        for item in rejected[:10]:
            lines.append(
                f"• {item['item_code']} – {item.get('description', 'N/A')} "
                f"(Qty: {item['quantity']:.0f})"
            )

        if len(rejected) > 10:
            lines.append(f"... and {len(rejected) - 10} more items")

        lines.append("")
        lines.append("Please review and take necessary action.")
        lines.append(f"Generated by iMat – {datetime.now().strftime('%Y-%m-%d')}")

        message = "%0A".join(lines)
        wa_url = f"https://wa.me/989160684552?text={message}"
        webbrowser.open(wa_url)
        self.status_bar.showMessage("WhatsApp notification prepared", 3000)

    def closeEvent(self, event):
        """Handle dialog close."""
        self.db.close()
        super().closeEvent(event)


# ==================================================================
# QC Release Confirm Dialog
# ==================================================================

class QCReleaseConfirmDialog(QDialog):
    """Confirmation dialog for QC release with details."""

    def __init__(self, parent=None, items: List[Dict] = None, 
                 new_status: str = "ACCEPTED", username: str = ""):
        """
        Initialize the confirmation dialog.
        
        Args:
            parent: Parent widget
            items: Items to release
            new_status: Target status
            username: Current username
        """
        super().__init__(parent)
        self.items = items or []
        self.new_status = new_status
        self.username = username

        status_config = RELEASE_ACTIONS.get(new_status, RELEASE_ACTIONS["ACCEPTED"])
        self.setWindowTitle(f"Confirm QC Release – {status_config['label']}")
        self.setMinimumWidth(550)
        self.setModal(True)

        self._init_ui()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        status_config = RELEASE_ACTIONS.get(self.new_status, RELEASE_ACTIONS["ACCEPTED"])

        # Header
        header = QLabel(
            f"<h2>{status_config['icon']} {status_config['label']}</h2>"
            f"<p>{status_config['description']}</p>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # Items summary
        items_text = f"<b>{len(self.items)} item(s) selected for QC release:</b>"
        for item in self.items[:5]:
            items_text += (
                f"<br>• {item['item_code']} – {item.get('description', 'N/A')} "
                f"(Qty: {item['quantity']:.2f})"
            )
        if len(self.items) > 5:
            items_text += f"<br>... and {len(self.items) - 5} more items"

        items_label = QLabel(items_text)
        items_label.setWordWrap(True)
        items_label.setStyleSheet("""
            background: #F5F5F5;
            border-radius: 4px;
            padding: 10px;
        """)
        layout.addWidget(items_label)

        # Form
        form = QFormLayout()
        form.setSpacing(8)

        # Quantity (0 = full quantity)
        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setRange(0, 999999.99)
        self.qty_spin.setDecimals(2)
        self.qty_spin.setValue(0)
        self.qty_spin.setToolTip("0 = release full quantity for each item")
        form.addRow("Quantity (0 = full):", self.qty_spin)

        # Inspection type
        self.inspection_combo = QComboBox()
        self.inspection_combo.addItems(INSPECTION_TYPES)
        form.addRow("Inspection Type:", self.inspection_combo)

        # Inspector
        self.inspector_edit = QLineEdit(self.username)
        form.addRow("Inspector:", self.inspector_edit)

        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        self.notes_edit.setPlaceholderText("Inspection notes and remarks...")
        form.addRow("Notes:", self.notes_edit)

        layout.addLayout(form)

        # Certificates
        cert_check = QCheckBox("Certificates verified and attached")
        cert_check.setChecked(True)
        layout.addWidget(cert_check)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_confirm = QPushButton(
            f"{status_config['icon']} Confirm {self.new_status}"
        )
        btn_confirm.setStyleSheet(f"""
            QPushButton {{
                background-color: {status_config['color']};
                color: white;
                border: none;
                padding: 10px 24px;
                font-weight: bold;
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{ filter: brightness(1.1); }}
        """)
        btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(btn_confirm)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                border: none;
                padding: 10px 24px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #616161; }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def get_release_data(self) -> Dict:
        """Get release data from the form."""
        return {
            "items": self.items,
            "new_status": self.new_status,
            "quantity": self.qty_spin.value(),
            "inspection_type": self.inspection_combo.currentText(),
            "inspector": self.inspector_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
        }