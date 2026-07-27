# ui/material_request_dialog.py
"""
Material Request Dialog – iMat Material Control System (EPC Edition).

Complete material request management for Technical Office with:
- Material request creation with auto-numbering
- Multi-currency support with exchange rates
- Excel import/export for bulk items
- Template download for standardized requests
- Print and preview functionality
- Item search with catalog lookup
- Cost estimation and budgeting
- Request status tracking
- Approval workflow integration
- WhatsApp sharing capability
- Copy/paste from Excel
- Drag-and-drop Excel import
"""

import os
import json
import tempfile
import webbrowser
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDateEdit, QTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QLabel, QDoubleSpinBox, QCompleter,
    QFrame, QStatusBar, QWidget, QAbstractItemView,
    QFileDialog, QTabWidget, QGroupBox, QCheckBox,
    QProgressBar, QApplication, QMenu, QToolBar,
    QSpinBox
)
from PyQt6.QtCore import Qt, QDate, QUrl, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QDesktopServices, QAction

from db.database import SessionLocal, get_db_session
from db.models import (
    Product, MaterialRequest, MaterialRequestLine, 
    Location, ProjectInfo
)
from ui.logo_widget import LogoWidget
from utils.excel_export import export_to_excel

# Try to import openpyxl for Excel operations
try:
    import openpyxl
    from openpyxl.styles import Font as XlFont, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

# ==================================================================
# Constants
# ==================================================================

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_CONFIG_FILE = os.path.join(BASE_DIR, "app_config.json")

# Discipline list
ALL_DISCIPLINES = [
    "Piping", "Mechanical", "Electrical", "Instrumentation", 
    "Civil", "Structural", "HVAC", "Fire Fighting", 
    "Plumbing", "Telecom", "Process", "Safety",
    "Welding", "NDT", "Insulation", "Painting",
    "Commissioning", "Scaffolding", "General"
]

# Currency list with symbols
ALL_CURRENCIES = {
    "USD": "$",
    "EUR": "€",
    "IRR": "﷼",
    "AED": "د.إ",
    "GBP": "£",
    "JPY": "¥",
    "CNY": "¥",
    "SAR": "﷼",
    "CAD": "C$",
    "AUD": "A$",
}

# Request types
REQUEST_TYPES = [
    "Normal",
    "Urgent",
    "Replacement",
    "Additional",
    "Contingency",
]

# Column indices
COL_ROW_NUM = 0
COL_ITEM_CODE = 1
COL_DESCRIPTION = 2
COL_SIZE1 = 3
COL_SIZE2 = 4
COL_MATERIAL = 5
COL_MATERIAL_CLASS = 6
COL_DISCIPLINE = 7
COL_CATEGORY = 8
COL_UNIT = 9
COL_SUBJECT = 10
COL_REQ_QTY = 11
COL_UNIT_PRICE = 12
COL_CURRENCY = 13
COL_TOTAL_COST = 14
COL_REMARKS = 15

# ==================================================================
# Material Request Dialog
# ==================================================================

class MaterialRequestDialog(QDialog):
    """
    Material Request creation and editing dialog for Technical Office.
    
    Features:
    - Create/edit material requests
    - Multi-currency support
    - Excel import/export
    - Template generation
    - Print and preview
    - WhatsApp sharing
    """

    request_saved = pyqtSignal(str)  # request number

    def __init__(self, parent=None, request_id: Optional[int] = None, 
                 user_role: str = "viewer"):
        """
        Initialize the Material Request dialog.
        
        Args:
            parent: Parent widget
            request_id: Optional request ID for editing
            user_role: Current user's role
        """
        super().__init__(parent)
        self.parent = parent
        self.request_id = request_id
        self.user_role = user_role
        self.edit_mode = request_id is not None
        self.product_dict: Dict[str, Tuple[str, str]] = {}  # code -> (desc, unit)
        
        # Window setup
        title = "Edit Material Request" if self.edit_mode else "New Material Request"
        self.setWindowTitle(f"iMat – {title}")
        self.setMinimumSize(1300, 800)
        
        # Build UI
        self._init_ui()
        
        # Load data
        self._load_product_dict()
        self._load_company_project_info()
        self._load_target_locations()
        
        if self.edit_mode:
            self._load_request()
        
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
        self._build_form(main_layout)
        self._build_items_table(main_layout)
        self._build_bottom_bar(main_layout)
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

        title_text = "📋 New Material Request (MR)" if not self.edit_mode else "📋 Edit Material Request"
        title = QLabel(title_text)
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("Technical Office – Material Requisition")
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

        self.action_save = toolbar.addAction("💾 Save")
        self.action_save.triggered.connect(self._save_request)
        toolbar.addSeparator()

        self.action_add_line = toolbar.addAction("➕ Add Line")
        self.action_add_line.triggered.connect(self._add_item_row)
        
        self.action_remove_line = toolbar.addAction("❌ Remove Line")
        self.action_remove_line.triggered.connect(self._remove_selected_item)
        toolbar.addSeparator()

        self.action_import = toolbar.addAction("📥 Import Excel")
        self.action_import.triggered.connect(self._import_from_excel)
        
        self.action_export = toolbar.addAction("📤 Export Excel")
        self.action_export.triggered.connect(self._export_to_excel)
        
        self.action_template = toolbar.addAction("📋 Template")
        self.action_template.triggered.connect(self._download_template)
        toolbar.addSeparator()

        self.action_print = toolbar.addAction("🖨️ Print")
        self.action_print.triggered.connect(self._print_request)
        
        self.action_whatsapp = toolbar.addAction("💬 Share WhatsApp")
        self.action_whatsapp.triggered.connect(self._share_whatsapp)
        toolbar.addSeparator()

        self.action_history = toolbar.addAction("📜 History")
        self.action_history.triggered.connect(self._open_history)

        parent_layout.addWidget(toolbar)

    def _build_form(self, parent_layout: QVBoxLayout):
        """Build the request header form."""
        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame {
                background: #F9F9F9;
                border-bottom: 1px solid #CCC;
            }
        """)
        form_layout = QHBoxLayout(form_frame)
        form_layout.setContentsMargins(15, 10, 15, 10)
        form_layout.setSpacing(20)

        # Left column
        left_form = QFormLayout()
        left_form.setSpacing(6)

        # MR Number (auto-generated)
        self.mr_no_edit = QLineEdit()
        self.mr_no_edit.setPlaceholderText("Auto-generated")
        self.mr_no_edit.setReadOnly(True)
        self.mr_no_edit.setStyleSheet("""
            QLineEdit {
                background-color: #E8F5E9;
                font-weight: bold;
                color: #004D40;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                padding: 6px;
                border: 1px solid #A5D6A7;
                border-radius: 4px;
            }
        """)
        left_form.addRow("MR Number:", self.mr_no_edit)

        # Company
        self.company_edit = QLineEdit()
        self.company_edit.setPlaceholderText("Company name")
        left_form.addRow("Company:", self.company_edit)

        # Project
        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText("Project name")
        left_form.addRow("Project:", self.project_edit)

        # WBS Code
        self.wbs_edit = QLineEdit()
        self.wbs_edit.setPlaceholderText("e.g., WBS-102-PIP")
        left_form.addRow("WBS Code:", self.wbs_edit)

        # Request Type
        self.request_type_combo = QComboBox()
        self.request_type_combo.addItems(REQUEST_TYPES)
        left_form.addRow("Request Type:", self.request_type_combo)

        form_layout.addLayout(left_form)

        # Right column
        right_form = QFormLayout()
        right_form.setSpacing(6)

        # Discipline
        self.discipline_combo = QComboBox()
        self.discipline_combo.setEditable(True)
        self.discipline_combo.addItems(ALL_DISCIPLINES)
        self.discipline_combo.setCurrentIndex(-1)
        completer = QCompleter(ALL_DISCIPLINES, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.discipline_combo.setCompleter(completer)
        right_form.addRow("Discipline:", self.discipline_combo)

        # Target Location
        self.target_location_combo = QComboBox()
        self.target_location_combo.setEditable(True)
        self.target_location_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        right_form.addRow("Target Location:", self.target_location_combo)

        # Required Date
        self.required_date = QDateEdit()
        self.required_date.setCalendarPopup(True)
        self.required_date.setDate(QDate.currentDate().addMonths(1))
        self.required_date.setDisplayFormat("yyyy-MM-dd")
        right_form.addRow("Required Date:", self.required_date)

        # ISO Drawing
        self.iso_drawing_edit = QLineEdit()
        self.iso_drawing_edit.setPlaceholderText("ISO Drawing / Reference No.")
        right_form.addRow("ISO Drawing:", self.iso_drawing_edit)

        # Remarks
        self.remarks_edit = QTextEdit()
        self.remarks_edit.setMaximumHeight(60)
        self.remarks_edit.setPlaceholderText("Additional remarks or notes...")
        right_form.addRow("Remarks:", self.remarks_edit)

        form_layout.addLayout(right_form)
        parent_layout.addWidget(form_frame)

    def _build_items_table(self, parent_layout: QVBoxLayout):
        """Build the items table."""
        # Label
        items_label = QLabel("📋 Requested Items")
        items_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        items_label.setStyleSheet("padding: 8px 15px; color: #004D40;")
        parent_layout.addWidget(items_label)

        # Table
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(16)
        self.items_table.setHorizontalHeaderLabels([
            "#", "Item Code", "Description", "Size1", "Size2",
            "Material", "Material Class", "Discipline", "Category",
            "Unit", "Subject", "Req Qty", "Unit Price", "Currency",
            "Total Cost", "Remarks"
        ])
        self.items_table.horizontalHeader().setStretchLastSection(True)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.items_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.items_table.setAlternatingRowColors(True)
        self.items_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.items_table.customContextMenuRequested.connect(self._show_context_menu)
        self.items_table.setStyleSheet("""
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
        column_widths = [35, 110, 160, 60, 60, 80, 90, 80, 80, 50, 100, 70, 80, 60, 90, 100]
        for i, w in enumerate(column_widths):
            self.items_table.setColumnWidth(i, w)

        parent_layout.addWidget(self.items_table)

    def _build_bottom_bar(self, parent_layout: QVBoxLayout):
        """Build the bottom action bar."""
        bottom_frame = QFrame()
        bottom_frame.setStyleSheet("""
            QFrame {
                background: #F5F5F5;
                border-top: 2px solid #B2DFDB;
            }
        """)
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(15, 10, 15, 10)
        bottom_layout.setSpacing(10)

        # Total cost
        self.total_cost_label = QLabel("Total Est. Cost: <b>0.00</b>")
        self.total_cost_label.setStyleSheet("""
            font-size: 14px;
            color: #004D40;
            font-weight: bold;
        """)
        bottom_layout.addWidget(self.total_cost_label)

        bottom_layout.addStretch()

        # Save button
        self.save_btn = QPushButton("💾 Save Request")
        self.save_btn.setMinimumHeight(40)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2E86C1;
                color: white;
                border: none;
                padding: 8px 24px;
                font-weight: bold;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #2471A3; }
            QPushButton:disabled { background-color: #999; }
        """)
        self.save_btn.clicked.connect(self._save_request)
        bottom_layout.addWidget(self.save_btn)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                border: none;
                padding: 8px 24px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #616161; }
        """)
        cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(cancel_btn)

        parent_layout.addWidget(bottom_frame)

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready – Fill in the request details and add items")
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
            for widget in self.findChildren((QLineEdit, QTextEdit)):
                if hasattr(widget, 'setReadOnly'):
                    widget.setReadOnly(True)
            for widget in self.findChildren(QComboBox):
                widget.setEnabled(False)
            self.required_date.setEnabled(False)
            self.action_save.setEnabled(False)
            self.action_add_line.setEnabled(False)
            self.action_remove_line.setEnabled(False)
            self.action_import.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.status_bar.showMessage("Read-only mode – You cannot modify requests")

    # ==================================================================
    # Data Loading
    # ==================================================================

    def _load_product_dict(self):
        """Load product catalog for item code lookup."""
        session = get_db_session()
        try:
            products = session.query(
                Product.item_code, Product.description, Product.unit_of_measure
            ).order_by(Product.item_code).all()
            
            self.product_dict.clear()
            for code, desc, unit in products:
                self.product_dict[code] = (desc or "", unit or "EA")
        finally:
            session.close()

    def _load_company_project_info(self):
        """Load company/project info from config."""
        if os.path.exists(APP_CONFIG_FILE):
            try:
                with open(APP_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.company_edit.setText(config.get("company", ""))
                self.project_edit.setText(config.get("project_name", ""))
            except Exception:
                pass

    def _load_target_locations(self):
        """Load target locations into combo."""
        session = get_db_session()
        try:
            locations = session.query(Location.code).order_by(Location.code).all()
            codes = [loc.code for loc in locations]
            self.target_location_combo.addItems(codes)
            
            completer = QCompleter(codes, self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.target_location_combo.setCompleter(completer)
        finally:
            session.close()

    def _load_request(self):
        """Load existing request for editing."""
        if not self.request_id:
            return

        session = get_db_session()
        try:
            req = session.query(MaterialRequest).get(self.request_id)
            if not req:
                return

            self.mr_no_edit.setText(req.request_no)
            self.company_edit.setText(req.company or "")
            self.project_edit.setText(req.project or "")
            self.wbs_edit.setText(req.wbs_code or "")
            
            idx = self.request_type_combo.findText(req.request_type or "Normal")
            if idx >= 0:
                self.request_type_combo.setCurrentIndex(idx)
            
            self.discipline_combo.setCurrentText(req.discipline or "")
            
            if req.target_location:
                idx = self.target_location_combo.findText(req.target_location.code)
                if idx >= 0:
                    self.target_location_combo.setCurrentIndex(idx)
            
            if req.required_date:
                self.required_date.setDate(QDate(
                    req.required_date.year,
                    req.required_date.month,
                    req.required_date.day
                ))
            
            self.iso_drawing_edit.setText(req.iso_drawing_no or "")
            self.remarks_edit.setPlainText(req.remarks or "")

            # Load lines
            for line in req.lines:
                self._add_item_row_with_data(line)

        except Exception as e:
            QMessageBox.warning(self, "Load Error", str(e))
        finally:
            session.close()

    # ==================================================================
    # Item Management
    # ==================================================================

    def _add_item_row(self):
        """Add a new empty item row."""
        self._add_item_row_with_data()

    def _add_item_row_with_data(self, line_data=None):
        """
        Add an item row with optional data.
        
        Args:
            line_data: Optional MaterialRequestLine data to populate
        """
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)

        # Row number
        self.items_table.setItem(row, COL_ROW_NUM, 
                                QTableWidgetItem(str(row + 1)))

        # Item Code (searchable combo)
        code_combo = QComboBox()
        code_combo.setEditable(True)
        code_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        code_combo.setMinimumWidth(120)
        
        display_list = []
        for code, (desc, unit) in self.product_dict.items():
            display = f"{code} – {desc}" if desc else code
            display_list.append(display)
        
        code_combo.addItems(display_list)
        completer = QCompleter(display_list, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        code_combo.setCompleter(completer)
        code_combo.currentTextChanged.connect(
            lambda text, r=row: self._on_item_selected(r, text)
        )
        self.items_table.setCellWidget(row, COL_ITEM_CODE, code_combo)

        # Read-only product fields
        for col in range(COL_DESCRIPTION, COL_UNIT + 1):
            item = QTableWidgetItem("")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.items_table.setItem(row, col, item)

        # Subject
        self.items_table.setItem(row, COL_SUBJECT, QTableWidgetItem(""))

        # Request Qty (spinbox)
        qty_spin = QDoubleSpinBox()
        qty_spin.setRange(0.01, 999999.99)
        qty_spin.setDecimals(2)
        qty_spin.setValue(1.0)
        qty_spin.valueChanged.connect(self._update_total_cost)
        self.items_table.setCellWidget(row, COL_REQ_QTY, qty_spin)

        # Unit Price (spinbox)
        price_spin = QDoubleSpinBox()
        price_spin.setRange(0.0, 9999999.99)
        price_spin.setDecimals(2)
        price_spin.setValue(0.0)
        price_spin.valueChanged.connect(self._update_total_cost)
        self.items_table.setCellWidget(row, COL_UNIT_PRICE, price_spin)

        # Currency (combo)
        currency_combo = QComboBox()
        currency_combo.setEditable(True)
        currency_combo.addItems(list(ALL_CURRENCIES.keys()))
        currency_combo.setCurrentText("USD")
        currency_combo.currentTextChanged.connect(self._update_total_cost)
        self.items_table.setCellWidget(row, COL_CURRENCY, currency_combo)

        # Total Cost (read-only)
        total_item = QTableWidgetItem("0.00")
        total_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.items_table.setItem(row, COL_TOTAL_COST, total_item)

        # Remarks
        self.items_table.setItem(row, COL_REMARKS, QTableWidgetItem(""))

        # Populate data if provided
        if line_data:
            code_combo.setCurrentText(line_data.item_code)
            
            fields = [
                (COL_DESCRIPTION, line_data.description),
                (COL_SIZE1, line_data.size1),
                (COL_SIZE2, line_data.size2),
                (COL_MATERIAL, line_data.material),
                (COL_MATERIAL_CLASS, line_data.material_class),
                (COL_DISCIPLINE, line_data.discipline),
                (COL_CATEGORY, line_data.category),
                (COL_UNIT, line_data.unit),
                (COL_SUBJECT, line_data.subject),
                (COL_REMARKS, line_data.remarks),
            ]
            for col, val in fields:
                if val:
                    item = self.items_table.item(row, col)
                    if item:
                        item.setText(val or "")
            
            qty_spin.setValue(line_data.qty)
            price_spin.setValue(line_data.unit_price or 0.0)
            currency_combo.setCurrentText(line_data.currency or "USD")

        self._renumber_rows()
        self._update_total_cost()

    def _on_item_selected(self, row: int, text: str):
        """Handle item code selection - auto-fill product details."""
        code = text.strip()
        if " – " in code:
            code = code.split(" – ", 1)[0].strip()

        session = get_db_session()
        try:
            product = session.query(Product).filter_by(item_code=code).first()
            if product:
                fields = {
                    COL_DESCRIPTION: product.description or "",
                    COL_SIZE1: product.size1 or "",
                    COL_SIZE2: product.size2 or "",
                    COL_MATERIAL: product.material or "",
                    COL_MATERIAL_CLASS: product.material_class or "",
                    COL_DISCIPLINE: product.discipline or "",
                    COL_CATEGORY: product.category or "",
                    COL_UNIT: product.unit_of_measure or "EA",
                }
                for col, val in fields.items():
                    item = self.items_table.item(row, col)
                    if item:
                        item.setText(val)
            else:
                for col in range(COL_DESCRIPTION, COL_UNIT + 1):
                    item = self.items_table.item(row, col)
                    if item:
                        item.setText("")
                unit_item = self.items_table.item(row, COL_UNIT)
                if unit_item:
                    unit_item.setText("EA")
        finally:
            session.close()

    def _remove_selected_item(self):
        """Remove selected item rows."""
        rows = set()
        for item in self.items_table.selectedItems():
            rows.add(item.row())
        
        for row in sorted(rows, reverse=True):
            self.items_table.removeRow(row)
        
        self._renumber_rows()
        self._update_total_cost()

    def _renumber_rows(self):
        """Renumber all rows."""
        for row in range(self.items_table.rowCount()):
            item = self.items_table.item(row, COL_ROW_NUM)
            if item:
                item.setText(str(row + 1))

    def _update_total_cost(self):
        """Update total cost label."""
        total_by_currency = {}
        
        for row in range(self.items_table.rowCount()):
            qty_widget = self.items_table.cellWidget(row, COL_REQ_QTY)
            price_widget = self.items_table.cellWidget(row, COL_UNIT_PRICE)
            currency_widget = self.items_table.cellWidget(row, COL_CURRENCY)
            
            if qty_widget and price_widget and currency_widget:
                qty = qty_widget.value()
                price = price_widget.value()
                currency = currency_widget.currentText()
                cost = qty * price
                
                total_by_currency[currency] = total_by_currency.get(currency, 0) + cost
                
                # Update row total
                total_item = self.items_table.item(row, COL_TOTAL_COST)
                if total_item:
                    symbol = ALL_CURRENCIES.get(currency, "")
                    total_item.setText(f"{symbol}{cost:,.2f}")

        if not total_by_currency:
            self.total_cost_label.setText("Total Est. Cost: <b>0.00</b>")
        elif len(total_by_currency) == 1:
            cur, val = list(total_by_currency.items())[0]
            symbol = ALL_CURRENCIES.get(cur, "")
            self.total_cost_label.setText(
                f"Total Est. Cost: <b>{symbol}{val:,.2f}</b>"
            )
        else:
            parts = []
            for cur, val in total_by_currency.items():
                symbol = ALL_CURRENCIES.get(cur, "")
                parts.append(f"{symbol}{val:,.2f}")
            self.total_cost_label.setText(
                f"Total Est. Cost: <b>{' + '.join(parts)}</b>"
            )

    def _show_context_menu(self, pos):
        """Show context menu on table."""
        menu = QMenu(self)
        menu.addAction("➕ Add Row", self._add_item_row)
        menu.addAction("❌ Remove Selected", self._remove_selected_item)
        menu.addSeparator()
        menu.addAction("📋 Copy Selected", self._copy_selected_rows)
        menu.exec(self.items_table.viewport().mapToGlobal(pos))

    def _copy_selected_rows(self):
        """Copy selected rows to clipboard."""
        selected = self.items_table.selectedItems()
        if not selected:
            return
        
        rows = set()
        for item in selected:
            rows.add(item.row())
        
        lines = []
        for row in sorted(rows):
            row_data = []
            for col in range(self.items_table.columnCount()):
                if col == COL_ITEM_CODE:
                    widget = self.items_table.cellWidget(row, col)
                    text = widget.currentText() if widget else ""
                elif col in (COL_REQ_QTY, COL_UNIT_PRICE):
                    widget = self.items_table.cellWidget(row, col)
                    text = str(widget.value()) if widget else ""
                elif col == COL_CURRENCY:
                    widget = self.items_table.cellWidget(row, col)
                    text = widget.currentText() if widget else ""
                else:
                    item = self.items_table.item(row, col)
                    text = item.text() if item else ""
                row_data.append(text)
            lines.append("\t".join(row_data))
        
        QApplication.clipboard().setText("\n".join(lines))
        self.status_bar.showMessage(f"{len(rows)} rows copied to clipboard", 3000)

    # ==================================================================
    # Save Request
    # ==================================================================

    def _validate_form(self) -> Tuple[bool, str]:
        """Validate the form before saving."""
        if not self.project_edit.text().strip():
            return False, "Project name is required."

        if self.items_table.rowCount() == 0:
            return False, "At least one item line is required."

        # Validate each line
        for row in range(self.items_table.rowCount()):
            code_combo = self.items_table.cellWidget(row, COL_ITEM_CODE)
            if code_combo:
                code = code_combo.currentText().strip()
                if " – " in code:
                    code = code.split(" – ", 1)[0].strip()
                if not code:
                    return False, f"Row {row + 1}: Item code is required."

        return True, ""

    def _save_request(self):
        """Save the material request."""
        valid, error = self._validate_form()
        if not valid:
            QMessageBox.warning(self, "Validation Error", error)
            return

        session = get_db_session()
        try:
            if self.edit_mode and self.request_id:
                req = session.query(MaterialRequest).get(self.request_id)
                if not req:
                    QMessageBox.critical(self, "Error", "Request not found.")
                    return
                
                # Clear existing lines
                for line in req.lines:
                    session.delete(line)
                session.flush()
            else:
                # Generate request number
                today_str = datetime.now().strftime("%Y%m%d")
                count = session.query(MaterialRequest).count() + 1
                
                req = MaterialRequest()
                req.request_no = f"MRQ-{today_str}-{count:04d}"
                req.requester = self._get_username()
                req.status = "PENDING"
                session.add(req)

            # Update header
            req.company = self.company_edit.text().strip()
            req.project = self.project_edit.text().strip()
            req.wbs_code = self.wbs_edit.text().strip()
            req.request_type = self.request_type_combo.currentText()
            req.discipline = self.discipline_combo.currentText()
            req.iso_drawing_no = self.iso_drawing_edit.text().strip()
            
            loc_text = self.target_location_combo.currentText().strip()
            if loc_text:
                loc = session.query(Location).filter_by(code=loc_text).first()
                req.target_location_id = loc.id if loc else None
            
            req.required_date = self.required_date.date().toPyDate()
            req.remarks = self.remarks_edit.toPlainText().strip()
            req.updated_at = datetime.utcnow()

            # Save lines
            for row in range(self.items_table.rowCount()):
                code_combo = self.items_table.cellWidget(row, COL_ITEM_CODE)
                item_code = code_combo.currentText().strip() if code_combo else ""
                if " – " in item_code:
                    item_code = item_code.split(" – ", 1)[0].strip()
                
                if not item_code:
                    continue

                qty_widget = self.items_table.cellWidget(row, COL_REQ_QTY)
                price_widget = self.items_table.cellWidget(row, COL_UNIT_PRICE)
                currency_widget = self.items_table.cellWidget(row, COL_CURRENCY)
                
                qty = qty_widget.value() if qty_widget else 0
                price = price_widget.value() if price_widget else 0.0
                currency = currency_widget.currentText() if currency_widget else "USD"

                line = MaterialRequestLine(
                    request_id=req.id,
                    line_number=row + 1,
                    item_code=item_code,
                    description=self._get_cell_text(row, COL_DESCRIPTION),
                    size1=self._get_cell_text(row, COL_SIZE1),
                    size2=self._get_cell_text(row, COL_SIZE2),
                    material=self._get_cell_text(row, COL_MATERIAL),
                    material_class=self._get_cell_text(row, COL_MATERIAL_CLASS),
                    discipline=self._get_cell_text(row, COL_DISCIPLINE),
                    category=self._get_cell_text(row, COL_CATEGORY),
                    unit=self._get_cell_text(row, COL_UNIT) or "EA",
                    subject=self._get_cell_text(row, COL_SUBJECT),
                    qty=qty,
                    unit_price=price,
                    currency=currency,
                    total_cost=round(qty * price, 2),
                    remarks=self._get_cell_text(row, COL_REMARKS)
                )
                session.add(line)

            session.commit()
            
            QMessageBox.information(
                self, "Success",
                f"Material request '{req.request_no}' saved successfully.\n\n"
                f"Lines: {len(req.lines)} | Status: {req.status}"
            )
            
            self.request_saved.emit(req.request_no)
            self.status_bar.showMessage(f"Request {req.request_no} saved", 5000)
            self.accept()

        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save request:\n{str(e)}")
        finally:
            session.close()

    def _get_cell_text(self, row: int, col: int) -> str:
        """Get text from a table cell."""
        item = self.items_table.item(row, col)
        return item.text().strip() if item else ""

    def _get_username(self) -> str:
        """Get current username."""
        try:
            if self.parent and hasattr(self.parent, 'current_user'):
                return self.parent.current_user
        except Exception:
            pass
        return "unknown"

    # ==================================================================
    # Import/Export
    # ==================================================================

    def _import_from_excel(self):
        """Import items from Excel file."""
        if not OPENPYXL_AVAILABLE:
            QMessageBox.warning(
                self, "Library Required",
                "openpyxl library is required for Excel import.\n\n"
                "Install it with: pip install openpyxl"
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Excel", "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if not file_path:
            return

        try:
            wb = openpyxl.load_workbook(file_path)
            ws = wb.active
            
            # Read headers
            headers = []
            first_row = next(ws.iter_rows(min_row=1, max_row=1))
            for cell in first_row:
                headers.append(str(cell.value).strip().lower() if cell.value else "")

            if 'item_code' not in headers:
                QMessageBox.warning(self, "Missing Column", 
                                  "Column 'item_code' is required.")
                return

            col_idx = {h: i for i, h in enumerate(headers) if h}
            imported = 0

            for row_data in ws.iter_rows(min_row=2, values_only=True):
                if not row_data or all(c is None for c in row_data):
                    continue

                item_code = str(row_data[col_idx.get('item_code', 0)] or "").strip()
                if not item_code:
                    continue

                self._add_item_row()
                row = self.items_table.rowCount() - 1

                # Set item code
                code_combo = self.items_table.cellWidget(row, COL_ITEM_CODE)
                if code_combo:
                    code_combo.setCurrentText(item_code)

                # Set other fields
                field_map = {
                    'request_qty': (COL_REQ_QTY, 'float', 1.0),
                    'qty': (COL_REQ_QTY, 'float', 1.0),
                    'est_unit_price': (COL_UNIT_PRICE, 'float', 0.0),
                    'unit_price': (COL_UNIT_PRICE, 'float', 0.0),
                    'currency': (COL_CURRENCY, 'str', 'USD'),
                    'subject': (COL_SUBJECT, 'str', ''),
                    'remarks': (COL_REMARKS, 'str', ''),
                    'unit': (COL_UNIT, 'str', 'EA'),
                }

                for field_name, (col, field_type, default) in field_map.items():
                    idx = col_idx.get(field_name)
                    if idx is not None and idx < len(row_data) and row_data[idx] is not None:
                        val = str(row_data[idx]).strip()
                        if field_type == 'float':
                            try:
                                val_float = float(val)
                                widget = self.items_table.cellWidget(row, col)
                                if widget and isinstance(widget, QDoubleSpinBox):
                                    widget.setValue(val_float)
                            except ValueError:
                                pass
                        elif field_type == 'str' and col == COL_CURRENCY:
                            widget = self.items_table.cellWidget(row, col)
                            if widget and isinstance(widget, QComboBox):
                                idx = widget.findText(val.upper())
                                if idx >= 0:
                                    widget.setCurrentIndex(idx)
                                else:
                                    widget.setCurrentText(val.upper())
                        else:
                            item = self.items_table.item(row, col)
                            if item:
                                item.setText(val)

                imported += 1

            self._renumber_rows()
            self._update_total_cost()
            QMessageBox.information(
                self, "Import Complete",
                f"{imported} items imported successfully."
            )
            self.status_bar.showMessage(f"{imported} items imported", 3000)

        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _export_to_excel(self):
        """Export items to Excel."""
        if not OPENPYXL_AVAILABLE:
            QMessageBox.warning(self, "Library Required", 
                              "openpyxl library is required.")
            return

        if self.items_table.rowCount() == 0:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Material Request", "material_request.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Material Request"

            # Header styling
            header_font = XlFont(bold=True, color="FFFFFF", size=11)
            header_fill = PatternFill(start_color="004D40", end_color="004D40", fill_type="solid")

            # Write headers
            headers = [
                self.items_table.horizontalHeaderItem(c).text()
                for c in range(self.items_table.columnCount())
            ]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")

            # Write data
            for row in range(self.items_table.rowCount()):
                for col in range(self.items_table.columnCount()):
                    if col == COL_ITEM_CODE:
                        widget = self.items_table.cellWidget(row, col)
                        val = widget.currentText() if widget else ""
                    elif col in (COL_REQ_QTY, COL_UNIT_PRICE):
                        widget = self.items_table.cellWidget(row, col)
                        val = widget.value() if widget else 0
                    elif col == COL_CURRENCY:
                        widget = self.items_table.cellWidget(row, col)
                        val = widget.currentText() if widget else ""
                    else:
                        item = self.items_table.item(row, col)
                        val = item.text() if item else ""
                    
                    ws.cell(row=row + 2, column=col + 1, value=val)

            # Auto-fit columns
            for col in range(1, len(headers) + 1):
                max_length = 0
                for row in range(1, self.items_table.rowCount() + 2):
                    cell = ws.cell(row=row, column=col)
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                ws.column_dimensions[get_column_letter(col)].width = min(max_length + 2, 40)

            wb.save(file_path)
            QMessageBox.information(self, "Export Complete", f"Exported to:\n{file_path}")
            self.status_bar.showMessage("Export complete", 3000)

        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _download_template(self):
        """Download Excel template."""
        if not OPENPYXL_AVAILABLE:
            QMessageBox.warning(self, "Library Required", 
                              "openpyxl library is required.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Template", "material_request_template.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Template"

            headers = [
                "item_code", "description", "size1", "size2",
                "material", "material_class", "discipline", "category",
                "unit", "subject", "request_qty", "est_unit_price",
                "currency", "remarks"
            ]
            
            header_font = XlFont(bold=True, color="FFFFFF", size=11)
            header_fill = PatternFill(start_color="004D40", end_color="004D40", fill_type="solid")

            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill

            # Example row
            example_data = [
                "PIPE-6-CS", "Carbon Steel Pipe 6\"", "6\"", "SCH 40",
                "ASTM A106", "Carbon Steel", "Piping", "Pipe",
                "MTR", "Site Area A", 10, 25.5, "USD", "Urgent requirement"
            ]
            for col, val in enumerate(example_data, 1):
                ws.cell(row=2, column=col, value=val)

            # Auto-fit
            for col in range(1, len(headers) + 1):
                ws.column_dimensions[get_column_letter(col)].width = 20

            wb.save(file_path)
            QMessageBox.information(self, "Template Created", 
                                  f"Template saved to:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ==================================================================
    # Print & Share
    # ==================================================================

    def _print_request(self):
        """Print the request as HTML."""
        if self.items_table.rowCount() == 0:
            QMessageBox.information(self, "No Data", "Nothing to print.")
            return

        html = self._generate_print_html()
        
        with tempfile.NamedTemporaryFile(
            suffix='.html', delete=False, mode='w', encoding='utf-8'
        ) as f:
            f.write(html)
            tmp_path = f.name

        QDesktopServices.openUrl(QUrl.fromLocalFile(tmp_path))
        self.status_bar.showMessage("Report opened for printing", 4000)

    def _generate_print_html(self) -> str:
        """Generate HTML for printing."""
        mr_no = self.mr_no_edit.text() or "Draft"
        company = self.company_edit.text()
        project = self.project_edit.text()
        discipline = self.discipline_combo.currentText()
        req_date = self.required_date.date().toString("yyyy-MM-dd")

        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Material Request - {mr_no}</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial; margin: 20px; color: #333; }}
                .header {{ border-bottom: 3px solid #004D40; padding-bottom: 15px; margin-bottom: 20px; }}
                .header h1 {{ color: #004D40; margin: 0; }}
                .info {{ margin: 15px 0; line-height: 1.8; }}
                .info td {{ padding: 2px 10px; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 15px; }}
                th {{ background: #004D40; color: white; padding: 8px; text-align: left; font-size: 10px; }}
                td {{ padding: 6px; border-bottom: 1px solid #ddd; font-size: 10px; }}
                .total {{ font-weight: bold; text-align: right; margin-top: 10px; font-size: 14px; }}
                .footer {{ margin-top: 30px; font-size: 10px; color: #888; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📋 Material Request</h1>
                <p>{mr_no} | {company} | {project}</p>
            </div>
            <table class="info">
                <tr><td><b>Discipline:</b></td><td>{discipline}</td>
                    <td><b>Required Date:</b></td><td>{req_date}</td></tr>
                <tr><td><b>WBS Code:</b></td><td>{self.wbs_edit.text()}</td>
                    <td><b>Type:</b></td><td>{self.request_type_combo.currentText()}</td></tr>
            </table>
            <table>
                <tr>
                    <th>#</th><th>Item Code</th><th>Description</th>
                    <th>Unit</th><th>Qty</th><th>Unit Price</th>
                    <th>Currency</th><th>Total</th>
                </tr>
        """

        for row in range(self.items_table.rowCount()):
            code_combo = self.items_table.cellWidget(row, COL_ITEM_CODE)
            code = code_combo.currentText() if code_combo else ""
            
            desc = self._get_cell_text(row, COL_DESCRIPTION)
            unit = self._get_cell_text(row, COL_UNIT)
            
            qty_widget = self.items_table.cellWidget(row, COL_REQ_QTY)
            qty = qty_widget.value() if qty_widget else 0
            
            price_widget = self.items_table.cellWidget(row, COL_UNIT_PRICE)
            price = price_widget.value() if price_widget else 0
            
            currency_widget = self.items_table.cellWidget(row, COL_CURRENCY)
            currency = currency_widget.currentText() if currency_widget else "USD"
            
            total = qty * price
            symbol = ALL_CURRENCIES.get(currency, "")

            html += f"""
                <tr>
                    <td>{row + 1}</td>
                    <td>{code}</td>
                    <td>{desc}</td>
                    <td>{unit}</td>
                    <td>{qty:.2f}</td>
                    <td>{symbol}{price:,.2f}</td>
                    <td>{currency}</td>
                    <td>{symbol}{total:,.2f}</td>
                </tr>
            """

        html += f"""
            </table>
            <div class="total">{self.total_cost_label.text()}</div>
            <div class="footer">
                Generated by iMat Material Control System | {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </div>
        </body>
        </html>
        """

        return html

    def _share_whatsapp(self):
        """Share request summary via WhatsApp."""
        mr_no = self.mr_no_edit.text() or "Draft"
        company = self.company_edit.text()
        project = self.project_edit.text()
        discipline = self.discipline_combo.currentText()
        
        # Build message
        lines = []
        lines.append(f"*Material Request:* {mr_no}")
        lines.append(f"*Company:* {company}")
        lines.append(f"*Project:* {project}")
        lines.append(f"*Discipline:* {discipline}")
        lines.append(f"*Required Date:* {self.required_date.date().toString('yyyy-MM-dd')}")
        lines.append("")
        lines.append("*Items:*")

        for row in range(min(self.items_table.rowCount(), 10)):
            code_combo = self.items_table.cellWidget(row, COL_ITEM_CODE)
            code = code_combo.currentText() if code_combo else ""
            desc = self._get_cell_text(row, COL_DESCRIPTION)
            
            qty_widget = self.items_table.cellWidget(row, COL_REQ_QTY)
            qty = qty_widget.value() if qty_widget else 0
            
            lines.append(f"  {row + 1}. {code} – {desc} (Qty: {qty:.0f})")

        if self.items_table.rowCount() > 10:
            lines.append(f"  ... and {self.items_table.rowCount() - 10} more items")

        lines.append("")
        lines.append(f"*Total:* {self.total_cost_label.text().replace('<b>', '').replace('</b>', '')}")

        message = "%0A".join(lines)
        wa_url = f"https://wa.me/989160684552?text={message}"
        webbrowser.open(wa_url)
        
        self.status_bar.showMessage("WhatsApp message prepared", 3000)

    def _open_history(self):
        """Open material request history."""
        from ui.material_request_history_dialog import MaterialRequestHistoryDialog
        dlg = MaterialRequestHistoryDialog(self.parent, user_role=self.user_role)
        dlg.exec()