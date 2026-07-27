# ui/product_dialog.py
"""
Material Coding (Product) Dialog – iMat Material Control System (EPC Edition).

Complete material master data management with:
- Full CRUD operations for product coding
- Searchable item code combo with autocomplete
- Discipline-based category filtering
- Excel import/export with template
- Bulk delete with confirmation
- Copy item codes to clipboard
- Quick-add form with validation
- Lifecycle status management
- Preservation settings
- Minimum stock level configuration
- Material class categorization
- Size and dimension tracking
- Unit of measure management
- Duplicate detection
- Last modified tracking
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFormLayout, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QSplitter, QFileDialog, QAbstractItemView, QMenu,
    QApplication, QGraphicsOpacityEffect, QGroupBox,
    QScrollArea, QWidget, QCheckBox, QSpinBox,
    QDoubleSpinBox, QTextEdit, QStatusBar, QToolBar
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QUrl, QEvent, pyqtSignal
)
from PyQt6.QtGui import QFont, QAction, QDesktopServices, QWheelEvent, QColor

from db.database import get_db_session, SessionLocal
from db.models import Product, Stock, Transaction
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

# Discipline to Category mapping
CATEGORY_MAP = {
    "Piping": ["Pipe", "Tube", "Flange", "Fitting", "Gasket", "Bolts & Nuts",
               "Valve", "Strainer", "Steam Trap", "Expansion Joint",
               "Pipe Support", "Hose", "Specialty Item"],
    "Civil": ["Concrete", "Rebar", "Formwork", "Anchor Bolt", "Embed Plate",
              "Grout", "Pile", "Slab", "Cement", "Aggregate"],
    "Structure": ["Steel Beam", "Steel Column", "Bracing", "Grating",
                  "Handrail", "Ladder", "Checkered Plate",
                  "Bolts & Nuts (Structural)", "Decking"],
    "Mechanical": ["Pump", "Compressor", "Turbine", "Fan", "Blower",
                   "Conveyor", "Tank", "Vessel", "Heat Exchanger",
                   "Filter", "Silencer"],
    "Electrical": ["Power Cable", "Control Cable", "Cable Tray", "Cable Ladder",
                   "Conduit", "Junction Box", "Lighting", "Switchgear",
                   "Transformer", "Bus Duct", "Panel", "Earthing"],
    "Instrument": ["Transmitter", "Gauge", "Switch", "Control Valve",
                   "Solenoid Valve", "Tubing", "Tube Fitting",
                   "Cable Gland", "Analyzer", "Orifice Plate"],
    "Painting": ["Primer", "Top Coat", "Thinner", "Epoxy", "Zinc Rich",
                 "Fireproofing", "Brush", "Roller"],
    "Insulation": ["Hot Insulation", "Cold Insulation", "Cladding",
                   "Jacketing", "Adhesive", "Tape", "Mastic"],
    "HVAC": ["Duct", "Diffuser", "Grille", "Damper", "Chiller",
             "AHU", "FCU", "Exhaust Fan"],
    "Fire Fighting": ["Fire Hose", "Sprinkler", "Deluge Valve",
                      "Fire Extinguisher", "Hydrant", "Monitor", "Detector"],
    "Telecom": ["Fiber Optic", "Coaxial Cable", "CCTV", "Telephone",
                "Speaker", "PAGA", "Antenna"],
    "Safety": ["Helmet", "Gloves", "Safety Shoes", "Goggles",
               "Harness", "Gas Detector", "First Aid Kit"],
    "Welding": ["Electrode", "Filler Wire", "Gas", "Welding Machine"],
    "NDT": ["Radiography Film", "Couplant", "Developer", "Penetrant"],
    "Chemicals": ["Acid", "Solvent", "Catalyst", "Inhibitor"],
    "Commissioning": ["Test Equipment", "Temporary Gasket", "Blind Flange"],
    "Scaffolding": ["Pipe", "Clamp", "Board", "Ladder"],
    "General": ["Tool", "Consumable", "Cleaning", "Office Supply"],
    "Spare Parts": ["Mechanical Seal", "Bearing", "Gasket", "O-Ring"],
}

# All disciplines list
ALL_DISCIPLINES = sorted(CATEGORY_MAP.keys())

# Material classes
MATERIAL_CLASSES = [
    "Carbon Steel", "Stainless Steel", "Alloy Steel",
    "Copper", "Aluminum", "Plastic", "Rubber",
    "Concrete", "Wood", "Glass", "Ceramic",
    "Composite", "Electrical", "Electronic", "Other"
]

# Lifecycle statuses
LIFECYCLE_STATUSES = ["ACTIVE", "OBSOLETE", "HOLD", "DISCONTINUED"]

# Preservation statuses
PRESERVATION_STATUSES = ["PRESERVED", "EXPIRED", "DAMAGED", "NOT_REQUIRED"]

# Units of measure
UOM_LIST = [
    "Pcs", "Box", "Kg", "MTR", "Liter", "Ton", "Set", 
    "Pair", "Roll", "Drum", "Bag", "Can", "Bundle",
    "Coil", "Ft", "Inch", "mm", "cm", "m2", "m3",
    "NOS", "Lot", "Kit", "Pack", "Sheet", "Spool"
]

# ==================================================================
# NoScrollComboBox
# ==================================================================

class NoScrollComboBox(QComboBox):
    """ComboBox that doesn't scroll when using mouse wheel."""
    
    def wheelEvent(self, event: QWheelEvent):
        """Ignore wheel events to prevent accidental value changes."""
        event.ignore()


# ==================================================================
# Product Dialog
# ==================================================================

class ProductDialog(QDialog):
    """
    Material coding management dialog for full CRUD operations.
    
    Features:
    - Searchable product list with filters
    - Quick-add/edit form with validation
    - Excel import/export
    - Bulk operations
    - Discipline-category hierarchy
    """

    coding_updated = pyqtSignal()

    def __init__(self, parent=None, product_id: Optional[int] = None,
                 item_code: Optional[str] = None, user_role: str = "viewer"):
        """
        Initialize the Product dialog.
        
        Args:
            parent: Parent widget
            product_id: Optional product ID to load for editing
            item_code: Optional item code to pre-fill for new item
            user_role: Current user's role
        """
        super().__init__(parent)
        self.product_id = product_id
        self.prefill_item_code = item_code
        self.user_role = user_role
        self.current_user = self._get_username()
        
        # State
        self.all_items: List[Product] = []
        self.editing_item: Optional[Product] = None
        self.form_visible = False
        
        # Window setup
        self.setWindowTitle("iMat – Material Coding (Code Library)")
        self.setMinimumSize(1200, 750)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowMinimizeButtonHint
        )
        
        # Build UI
        self._init_ui()
        
        # Load data
        self._load_items()
        
        # Pre-fill if needed
        if self.product_id:
            self._edit_existing_by_id(self.product_id)
        elif self.prefill_item_code:
            self._prefill_new_item(self.prefill_item_code)
        
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
        self._build_search_bar(main_layout)
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

        title = QLabel("📦 Material Coding")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("Manage item codes, descriptions and classifications")
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

        self.action_new = toolbar.addAction("➕ New Item")
        self.action_new.triggered.connect(self._show_new_form)
        toolbar.addSeparator()

        self.action_import = toolbar.addAction("📥 Import Excel")
        self.action_import.triggered.connect(self._import_excel)
        
        self.action_export = toolbar.addAction("📤 Export Excel")
        self.action_export.triggered.connect(self._export_excel)
        
        self.action_template = toolbar.addAction("📋 Template")
        self.action_template.triggered.connect(self._download_template)
        toolbar.addSeparator()

        self.action_delete = toolbar.addAction("🗑️ Delete Selected")
        self.action_delete.triggered.connect(self._delete_selected)
        
        self.action_copy = toolbar.addAction("📋 Copy Codes")
        self.action_copy.triggered.connect(self._copy_selected_codes)

        parent_layout.addWidget(toolbar)

    def _build_search_bar(self, parent_layout: QVBoxLayout):
        """Build the search and filter bar."""
        search_frame = QFrame()
        search_frame.setStyleSheet("""
            QFrame {
                background: #F5F5F5;
                border-bottom: 1px solid #CCC;
            }
        """)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(10, 6, 10, 6)
        search_layout.setSpacing(8)

        # Search input
        search_layout.addWidget(QLabel("🔍 Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by item code or description...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(250)
        self.search_input.textChanged.connect(self._apply_filter)
        search_layout.addWidget(self.search_input)

        # Discipline filter
        search_layout.addWidget(QLabel("Discipline:"))
        self.filter_discipline_combo = NoScrollComboBox()
        self.filter_discipline_combo.addItem("All")
        self.filter_discipline_combo.currentTextChanged.connect(self._apply_filter)
        search_layout.addWidget(self.filter_discipline_combo)

        # Status filter
        search_layout.addWidget(QLabel("Status:"))
        self.filter_status_combo = QComboBox()
        self.filter_status_combo.addItems(["All", "ACTIVE", "OBSOLETE", "HOLD"])
        self.filter_status_combo.currentTextChanged.connect(self._apply_filter)
        search_layout.addWidget(self.filter_status_combo)

        search_layout.addStretch()

        # Item count
        self.count_label = QLabel("Items: 0")
        self.count_label.setStyleSheet("color: #666; font-weight: bold;")
        search_layout.addWidget(self.count_label)

        parent_layout.addWidget(search_frame)

    def _build_content(self, parent_layout: QVBoxLayout):
        """Build the main content area with splitter."""
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Product table
        table_widget = self._build_table()
        splitter.addWidget(table_widget)

        # Edit form
        form_widget = self._build_form()
        splitter.addWidget(form_widget)

        # Set sizes
        splitter.setSizes([450, 300])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        parent_layout.addWidget(splitter)

    def _build_table(self) -> QWidget:
        """Build the product table."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)

        self.table = QTableWidget()
        self.table.setColumnCount(13)
        self.table.setHorizontalHeaderLabels([
            "#", "Item Code", "Description", "Material Class",
            "Discipline", "Category", "Unit", "Min Qty",
            "Size1", "Size2", "Lifecycle", "Preservation",
            "Last Modified"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._edit_selected_item)
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
        col_widths = [35, 110, 200, 100, 90, 100, 50, 60, 70, 70, 80, 80, 100]
        for i, w in enumerate(col_widths):
            self.table.setColumnWidth(i, w)

        layout.addWidget(self.table)
        return widget

    def _build_form(self) -> QWidget:
        """Build the edit form."""
        self.form_widget = QFrame()
        self.form_widget.setFrameShape(QFrame.Shape.StyledPanel)
        self.form_widget.setStyleSheet("""
            QFrame {
                background: #FFF9E6;
                border: 1px solid #E6C300;
                border-radius: 4px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #CCB300;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: #5C4B00;
            }
            QLineEdit, QComboBox {
                border: 1px solid #CCB300;
                border-radius: 3px;
                padding: 4px 6px;
                background: white;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 2px solid #B38F00;
            }
        """)
        self.form_widget.setVisible(False)

        form_outer = QVBoxLayout(self.form_widget)
        form_outer.setContentsMargins(10, 10, 10, 10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)
        form_layout.setSpacing(8)

        # ---- Group 1: Item Information ----
        item_grp = QGroupBox("📦 Item Information")
        item_layout = QFormLayout(item_grp)
        item_layout.setSpacing(4)

        self.item_code_edit = QLineEdit()
        self.item_code_edit.setPlaceholderText("Unique code (e.g., PIPE-6-CS)")
        self.item_code_edit.setMinimumHeight(30)
        self.item_code_edit.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        item_layout.addRow("Item Code *:", self.item_code_edit)

        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Description of the item")
        item_layout.addRow("Description:", self.desc_edit)

        self.part_number_edit = QLineEdit()
        self.part_number_edit.setPlaceholderText("Manufacturer part number (optional)")
        item_layout.addRow("Part Number:", self.part_number_edit)

        self.size1_edit = QLineEdit()
        self.size1_edit.setPlaceholderText("Size 1 (e.g., 6\")")
        item_layout.addRow("Size 1:", self.size1_edit)

        self.size2_edit = QLineEdit()
        self.size2_edit.setPlaceholderText("Size 2 (e.g., SCH 40)")
        item_layout.addRow("Size 2:", self.size2_edit)

        self.material_edit = QLineEdit()
        self.material_edit.setPlaceholderText("Material (e.g., ASTM A106)")
        item_layout.addRow("Material:", self.material_edit)

        form_layout.addWidget(item_grp)

        # ---- Group 2: Classification ----
        class_grp = QGroupBox("🏷️ Classification")
        class_layout = QFormLayout(class_grp)
        class_layout.setSpacing(4)

        self.material_class_combo = NoScrollComboBox()
        self.material_class_combo.addItems(MATERIAL_CLASSES)
        self.material_class_combo.setCurrentIndex(-1)
        class_layout.addRow("Material Class:", self.material_class_combo)

        self.discipline_combo = NoScrollComboBox()
        self.discipline_combo.addItems(ALL_DISCIPLINES)
        self.discipline_combo.setCurrentIndex(-1)
        self.discipline_combo.currentTextChanged.connect(self._update_category_combo)
        class_layout.addRow("Discipline:", self.discipline_combo)

        self.category_combo = NoScrollComboBox()
        self.category_combo.setEditable(True)
        all_categories = sorted(set(cat for cats in CATEGORY_MAP.values() for cat in cats))
        self.category_combo.addItems(all_categories)
        self.category_combo.setCurrentText("")
        class_layout.addRow("Category:", self.category_combo)

        form_layout.addWidget(class_grp)

        # ---- Group 3: Unit & Quantity ----
        uom_grp = QGroupBox("📏 Unit & Quantity")
        uom_layout = QFormLayout(uom_grp)
        uom_layout.setSpacing(4)

        self.uom_combo = NoScrollComboBox()
        self.uom_combo.setEditable(True)
        self.uom_combo.addItems(UOM_LIST)
        self.uom_combo.setCurrentText("")
        uom_layout.addRow("Unit of Measure:", self.uom_combo)

        self.min_qty_spin = QDoubleSpinBox()
        self.min_qty_spin.setRange(0, 999999)
        self.min_qty_spin.setDecimals(2)
        self.min_qty_spin.setValue(0)
        self.min_qty_spin.setToolTip("Minimum required stock level")
        uom_layout.addRow("Min Required Qty:", self.min_qty_spin)

        self.unit_cost_spin = QDoubleSpinBox()
        self.unit_cost_spin.setRange(0, 9999999)
        self.unit_cost_spin.setDecimals(2)
        self.unit_cost_spin.setValue(0)
        self.unit_cost_spin.setPrefix("$ ")
        uom_layout.addRow("Unit Cost:", self.unit_cost_spin)

        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0, 999999)
        self.weight_spin.setDecimals(2)
        self.weight_spin.setValue(0)
        self.weight_spin.setSuffix(" kg")
        uom_layout.addRow("Weight:", self.weight_spin)

        form_layout.addWidget(uom_grp)

        # ---- Group 4: Status ----
        status_grp = QGroupBox("🔄 Status & Preservation")
        status_layout = QFormLayout(status_grp)
        status_layout.setSpacing(4)

        self.lifecycle_combo = NoScrollComboBox()
        self.lifecycle_combo.addItems(LIFECYCLE_STATUSES)
        self.lifecycle_combo.setCurrentText("ACTIVE")
        status_layout.addRow("Lifecycle:", self.lifecycle_combo)

        self.preservation_combo = NoScrollComboBox()
        self.preservation_combo.addItems(PRESERVATION_STATUSES)
        self.preservation_combo.setCurrentText("PRESERVED")
        status_layout.addRow("Preservation:", self.preservation_combo)

        self.preservation_required_check = QCheckBox("Preservation Required")
        status_layout.addRow(self.preservation_required_check)

        self.preservation_interval_spin = QSpinBox()
        self.preservation_interval_spin.setRange(30, 3650)
        self.preservation_interval_spin.setValue(365)
        self.preservation_interval_spin.setSuffix(" days")
        self.preservation_interval_spin.setToolTip("Interval between preservation activities")
        status_layout.addRow("Interval:", self.preservation_interval_spin)

        self.storage_condition_edit = QLineEdit()
        self.storage_condition_edit.setPlaceholderText("e.g., Covered, Temperature Controlled")
        status_layout.addRow("Storage:", self.storage_condition_edit)

        form_layout.addWidget(status_grp)

        # ---- Group 5: Remarks ----
        remarks_grp = QGroupBox("📝 Remarks")
        remarks_layout = QFormLayout(remarks_grp)
        self.remarks_edit = QTextEdit()
        self.remarks_edit.setMaximumHeight(60)
        self.remarks_edit.setPlaceholderText("Additional remarks or notes")
        remarks_layout.addRow(self.remarks_edit)
        form_layout.addWidget(remarks_grp)

        form_layout.addStretch()

        scroll.setWidget(form_container)
        form_outer.addWidget(scroll)

        # Form buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.save_new_btn = QPushButton("💾 Save && New")
        self.save_new_btn.setStyleSheet(self._get_button_style("primary"))
        self.save_new_btn.clicked.connect(self._save_and_new)

        self.save_close_btn = QPushButton("✔ Save && Close")
        self.save_close_btn.setStyleSheet(self._get_button_style("success"))
        self.save_close_btn.clicked.connect(self._save_and_close)

        self.cancel_btn = QPushButton("✖ Cancel")
        self.cancel_btn.setStyleSheet(self._get_button_style("neutral"))
        self.cancel_btn.clicked.connect(self._hide_form)

        btn_layout.addWidget(self.save_new_btn)
        btn_layout.addWidget(self.save_close_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)

        form_outer.addLayout(btn_layout)

        return self.form_widget

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready – Double-click item to edit")
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
            "primary": """
                QPushButton {
                    background-color: #1976D2;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #1565C0; }
                QPushButton:disabled { background-color: #999; }
            """,
            "success": """
                QPushButton {
                    background-color: #388E3C;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #2E7D32; }
                QPushButton:disabled { background-color: #999; }
            """,
            "danger": """
                QPushButton {
                    background-color: #D32F2F;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #C62828; }
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
            self.action_new.setEnabled(False)
            self.action_import.setEnabled(False)
            self.action_delete.setEnabled(False)
            self.save_new_btn.setEnabled(False)
            self.save_close_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self._set_form_enabled(False)
            self.status_bar.showMessage("Read-only mode – Viewing coding")

    def _set_form_enabled(self, enabled: bool):
        """Enable or disable all form fields."""
        for widget in self.form_widget.findChildren((QLineEdit, QTextEdit, QComboBox, 
                                                       QDoubleSpinBox, QSpinBox, QCheckBox)):
            widget.setEnabled(enabled)
        
        if not enabled:
            self.save_new_btn.setVisible(False)
            self.save_close_btn.setVisible(False)
            self.cancel_btn.setVisible(False)
        else:
            self.save_new_btn.setVisible(True)
            self.save_close_btn.setVisible(True)
            self.cancel_btn.setVisible(True)

    def _get_username(self) -> str:
        """Get current username."""
        try:
            parent_win = self.parent()
            if parent_win and hasattr(parent_win, 'current_user'):
                return parent_win.current_user
        except Exception:
            pass
        return "system"

    # ==================================================================
    # Data Loading
    # ==================================================================

    def _load_items(self):
        """Load all products from database."""
        session = get_db_session()
        try:
            self.all_items = session.query(Product).order_by(Product.item_code).all()
            
            # Load filter disciplines
            disciplines = sorted(set(
                item.discipline for item in self.all_items if item.discipline
            ))
            self.filter_discipline_combo.blockSignals(True)
            self.filter_discipline_combo.clear()
            self.filter_discipline_combo.addItem("All")
            for d in disciplines:
                self.filter_discipline_combo.addItem(d)
            self.filter_discipline_combo.blockSignals(False)
            
            self._apply_filter()
        finally:
            session.close()

    def _apply_filter(self):
        """Apply filters to the product list."""
        search_text = self.search_input.text().strip().lower()
        discipline_filter = self.filter_discipline_combo.currentText()
        status_filter = self.filter_status_combo.currentText()

        if discipline_filter == "All":
            discipline_filter = None
        if status_filter == "All":
            status_filter = None

        filtered = self.all_items

        if search_text:
            filtered = [
                item for item in filtered
                if search_text in item.item_code.lower()
                or (item.description and search_text in item.description.lower())
                or (item.part_number and search_text in item.part_number.lower())
            ]

        if discipline_filter:
            filtered = [item for item in filtered if item.discipline == discipline_filter]

        if status_filter:
            filtered = [item for item in filtered if item.lifecycle_status == status_filter]

        self._display_items(filtered)
        self.count_label.setText(f"Items: {len(filtered)}")

    def _display_items(self, items: List[Product]):
        """Display products in the table."""
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            # Row number
            row_item = QTableWidgetItem(str(row + 1))
            row_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, row_item)

            # Item Code
            code_item = QTableWidgetItem(item.item_code)
            code_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            self.table.setItem(row, 1, code_item)

            # Description
            self.table.setItem(row, 2, QTableWidgetItem(item.description or ""))

            # Material Class
            self.table.setItem(row, 3, QTableWidgetItem(item.material_class or ""))

            # Discipline
            disc_item = QTableWidgetItem(item.discipline or "")
            if item.discipline:
                disc_item.setForeground(QColor("#004D40"))
            self.table.setItem(row, 4, disc_item)

            # Category
            self.table.setItem(row, 5, QTableWidgetItem(item.category or ""))

            # Unit
            uom_item = QTableWidgetItem(item.unit_of_measure or "")
            uom_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 6, uom_item)

            # Min Qty
            min_qty_item = QTableWidgetItem(str(item.min_required_qty or 0))
            min_qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 7, min_qty_item)

            # Size1
            self.table.setItem(row, 8, QTableWidgetItem(item.size1 or ""))

            # Size2
            self.table.setItem(row, 9, QTableWidgetItem(item.size2 or ""))

            # Lifecycle
            lifecycle_item = QTableWidgetItem(item.lifecycle_status or "ACTIVE")
            lifecycle_colors = {
                "ACTIVE": ("#C8E6C9", "#2E7D32"),
                "OBSOLETE": ("#FFCDD2", "#B71C1C"),
                "HOLD": ("#FFF9C4", "#F57F17"),
                "DISCONTINUED": ("#E0E0E0", "#616161"),
            }
            if item.lifecycle_status in lifecycle_colors:
                bg, fg = lifecycle_colors[item.lifecycle_status]
                lifecycle_item.setBackground(QColor(bg))
                lifecycle_item.setForeground(QColor(fg))
            self.table.setItem(row, 10, lifecycle_item)

            # Preservation
            self.table.setItem(row, 11, QTableWidgetItem(item.preservation_status or ""))

            # Last Modified
            last_user = item.updated_by or item.created_by or ""
            last_time = item.updated_at.strftime("%Y-%m-%d") if item.updated_at else ""
            self.table.setItem(row, 12, QTableWidgetItem(
                f"{last_user} ({last_time})" if last_time else last_user
            ))

    # ==================================================================
    # Form Methods
    # ==================================================================

    def _show_new_form(self):
        """Show form for new item."""
        if self.user_role == "viewer":
            QMessageBox.warning(self, "Access Denied", "You cannot add items.")
            return
        self._clear_form()
        self.form_widget.setVisible(True)
        self.form_visible = True
        self.item_code_edit.setFocus()

    def _hide_form(self):
        """Hide the edit form."""
        self.form_widget.setVisible(False)
        self.form_visible = False
        self.editing_item = None
        self._clear_form()

    def _clear_form(self):
        """Clear all form fields."""
        self.item_code_edit.clear()
        self.desc_edit.clear()
        self.part_number_edit.clear()
        self.size1_edit.clear()
        self.size2_edit.clear()
        self.material_edit.clear()
        self.material_class_combo.setCurrentIndex(-1)
        self.discipline_combo.setCurrentIndex(-1)
        self.category_combo.setCurrentText("")
        self.uom_combo.setCurrentText("")
        self.min_qty_spin.setValue(0)
        self.unit_cost_spin.setValue(0)
        self.weight_spin.setValue(0)
        self.lifecycle_combo.setCurrentText("ACTIVE")
        self.preservation_combo.setCurrentText("PRESERVED")
        self.preservation_required_check.setChecked(False)
        self.preservation_interval_spin.setValue(365)
        self.storage_condition_edit.clear()
        self.remarks_edit.clear()
        self.editing_item = None

    def _fill_form_from_item(self, item: Product):
        """Fill form with item data."""
        self.item_code_edit.setText(item.item_code)
        self.item_code_edit.setReadOnly(True)  # Can't change code when editing
        self.desc_edit.setText(item.description or "")
        self.part_number_edit.setText(item.part_number or "")
        self.size1_edit.setText(item.size1 or "")
        self.size2_edit.setText(item.size2 or "")
        self.material_edit.setText(item.material or "")

        idx = self.material_class_combo.findText(item.material_class or "")
        if idx >= 0:
            self.material_class_combo.setCurrentIndex(idx)
        else:
            self.material_class_combo.setCurrentIndex(-1)

        idx = self.discipline_combo.findText(item.discipline or "")
        if idx >= 0:
            self.discipline_combo.setCurrentIndex(idx)
        else:
            self.discipline_combo.setCurrentIndex(-1)

        self._update_category_combo(item.discipline or "")
        idx = self.category_combo.findText(item.category or "")
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        else:
            self.category_combo.setCurrentText(item.category or "")

        idx = self.uom_combo.findText(item.unit_of_measure or "")
        if idx >= 0:
            self.uom_combo.setCurrentIndex(idx)
        else:
            self.uom_combo.setCurrentText(item.unit_of_measure or "")

        self.min_qty_spin.setValue(item.min_required_qty or 0)
        self.unit_cost_spin.setValue(item.unit_cost or 0)
        self.weight_spin.setValue(item.weight or 0)

        idx = self.lifecycle_combo.findText(item.lifecycle_status or "ACTIVE")
        if idx >= 0:
            self.lifecycle_combo.setCurrentIndex(idx)

        idx = self.preservation_combo.findText(item.preservation_status or "PRESERVED")
        if idx >= 0:
            self.preservation_combo.setCurrentIndex(idx)

        self.preservation_required_check.setChecked(item.preservation_required or False)
        self.preservation_interval_spin.setValue(item.preservation_interval_days or 365)
        self.storage_condition_edit.setText(item.storage_condition or "")
        self.remarks_edit.setPlainText(item.remarks or "")

    def _update_category_combo(self, discipline: str):
        """Update category combo based on selected discipline."""
        self.category_combo.clear()
        if discipline and discipline in CATEGORY_MAP:
            self.category_combo.addItems(CATEGORY_MAP[discipline])
        else:
            all_categories = sorted(set(cat for cats in CATEGORY_MAP.values() for cat in cats))
            self.category_combo.addItems(all_categories)
        self.category_combo.setCurrentText("")

    def _prefill_new_item(self, item_code: str):
        """Prefill form for new item with given code."""
        if self.user_role == "viewer":
            return
        self._clear_form()
        self.item_code_edit.setText(item_code)
        self.item_code_edit.setReadOnly(False)
        self.form_widget.setVisible(True)
        self.form_visible = True

    def _edit_existing_by_id(self, product_id: int):
        """Edit product by ID."""
        session = get_db_session()
        try:
            item = session.query(Product).filter_by(id=product_id).first()
            if item:
                self._fill_form_from_item(item)
                self.editing_item = item
                self.form_widget.setVisible(True)
                self.form_visible = True
        finally:
            session.close()

    def _edit_selected_item(self):
        """Edit selected product from table."""
        if self.user_role == "viewer":
            QMessageBox.warning(self, "Access Denied", "You can only view products.")
            return

        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an item to edit.")
            return

        item_code = self.table.item(row, 1).text()
        session = get_db_session()
        try:
            item = session.query(Product).filter_by(item_code=item_code).first()
            if item:
                self._fill_form_from_item(item)
                self.editing_item = item
                self.form_widget.setVisible(True)
                self.form_visible = True
        finally:
            session.close()

    # ==================================================================
    # Save Methods
    # ==================================================================

    def _validate_form(self) -> Tuple[bool, str]:
        """Validate the form before saving."""
        item_code = self.item_code_edit.text().strip()
        if not item_code:
            return False, "Item Code is required."

        if not self.editing_item:
            # Check duplicate for new items
            session = get_db_session()
            try:
                existing = session.query(Product).filter_by(item_code=item_code).first()
                if existing:
                    return False, f"Item code '{item_code}' already exists."
            finally:
                session.close()

        return True, ""

    def _collect_form_data(self) -> Dict:
        """Collect form data into a dictionary."""
        return {
            "item_code": self.item_code_edit.text().strip(),
            "part_number": self.part_number_edit.text().strip() or None,
            "description": self.desc_edit.text().strip(),
            "size1": self.size1_edit.text().strip() or None,
            "size2": self.size2_edit.text().strip() or None,
            "material": self.material_edit.text().strip() or None,
            "material_class": self.material_class_combo.currentText().strip() or None,
            "discipline": self.discipline_combo.currentText().strip() or None,
            "category": self.category_combo.currentText().strip() or None,
            "unit_of_measure": self.uom_combo.currentText().strip() or None,
            "min_required_qty": self.min_qty_spin.value(),
            "unit_cost": self.unit_cost_spin.value(),
            "weight": self.weight_spin.value() or None,
            "lifecycle_status": self.lifecycle_combo.currentText(),
            "preservation_status": self.preservation_combo.currentText(),
            "preservation_required": self.preservation_required_check.isChecked(),
            "preservation_interval_days": self.preservation_interval_spin.value(),
            "storage_condition": self.storage_condition_edit.text().strip() or None,
            "remarks": self.remarks_edit.toPlainText().strip() or None,
        }

    def _save_product(self) -> bool:
        """Save product to database. Returns True if successful."""
        valid, error = self._validate_form()
        if not valid:
            QMessageBox.warning(self, "Validation Error", error)
            return False

        data = self._collect_form_data()
        session = get_db_session()

        try:
            if self.editing_item:
                # Update existing
                product = session.query(Product).filter_by(id=self.editing_item.id).first()
                if not product:
                    QMessageBox.critical(self, "Error", "Product not found.")
                    return False
                
                for key, value in data.items():
                    if key != "item_code":  # Don't update item_code
                        setattr(product, key, value)
                
                product.updated_by = self.current_user
            else:
                # Create new
                product = Product(**data)
                product.created_by = self.current_user
                product.updated_by = self.current_user
                session.add(product)

            session.commit()
            self._load_items()
            return True

        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Database Error", str(e))
            return False
        finally:
            session.close()

    def _save_and_new(self):
        """Save and prepare for new item."""
        if self._save_product():
            self._clear_form()
            self.item_code_edit.setReadOnly(False)
            self.item_code_edit.setFocus()
            self.status_bar.showMessage("Item saved successfully", 3000)
            self.coding_updated.emit()

    def _save_and_close(self):
        """Save and close the form."""
        if self._save_product():
            self._hide_form()
            self.status_bar.showMessage("Item saved successfully", 3000)
            self.coding_updated.emit()

    # ==================================================================
    # Delete Methods
    # ==================================================================

    def _delete_selected(self):
        """Delete selected products."""
        if self.user_role == "viewer":
            QMessageBox.warning(self, "Access Denied", "You cannot delete items.")
            return

        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select items to delete.")
            return

        item_codes = []
        for row in selected_rows:
            code = self.table.item(row, 1).text()
            if code:
                item_codes.append(code)

        codes_text = ", ".join(item_codes)
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete the following items and all their data?\n\n{codes_text}\n\n"
            "⚠️ This action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        session = get_db_session()
        try:
            deleted = 0
            for code in item_codes:
                product = session.query(Product).filter_by(item_code=code).first()
                if product:
                    # Check for existing stock
                    active_stock = session.query(Stock).filter(
                        Stock.item_code == code,
                        Stock.quantity > 0
                    ).count()
                    
                    if active_stock > 0:
                        QMessageBox.warning(
                            self, "Cannot Delete",
                            f"Cannot delete '{code}' - it has {active_stock} active stock record(s)."
                        )
                        continue

                    session.delete(product)
                    deleted += 1

            session.commit()
            self._load_items()
            self._clear_form()
            self._hide_form()
            QMessageBox.information(self, "Deleted", f"{deleted} item(s) deleted.")
            self.status_bar.showMessage(f"{deleted} items deleted", 3000)
            self.coding_updated.emit()

        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Database Error", str(e))
        finally:
            session.close()

    def _copy_selected_codes(self):
        """Copy selected item codes to clipboard."""
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.warning(self, "Nothing Selected", "Please select rows first.")
            return

        codes = []
        for row in sorted(selected_rows):
            item = self.table.item(row, 1)
            if item:
                codes.append(item.text())

        if codes:
            QApplication.clipboard().setText("\n".join(codes))
            self.status_bar.showMessage(f"{len(codes)} item codes copied to clipboard", 3000)

    # ==================================================================
    # Context Menu
    # ==================================================================

    def _show_context_menu(self, pos):
        """Show context menu on table."""
        menu = QMenu(self)
        menu.addAction("✏️ Edit Selected", self._edit_selected_item)
        menu.addAction("📋 Copy Item Codes", self._copy_selected_codes)
        menu.addSeparator()
        menu.addAction("🗑️ Delete Selected", self._delete_selected)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ==================================================================
    # Excel Import/Export
    # ==================================================================

    def _import_excel(self):
        """Import products from Excel file."""
        if not OPENPYXL_AVAILABLE:
            QMessageBox.warning(self, "Library Required", 
                              "openpyxl library is required.\nInstall: pip install openpyxl")
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
            
            headers = []
            first_row = next(ws.iter_rows(min_row=1, max_row=1))
            for cell in first_row:
                headers.append(str(cell.value).strip().lower() if cell.value else "")

            if 'item_code' not in headers:
                QMessageBox.warning(self, "Missing Column", "Column 'item_code' is required.")
                return

            col_idx = {h: i for i, h in enumerate(headers) if h}
            session = get_db_session()
            imported = 0
            skipped = 0

            for row_data in ws.iter_rows(min_row=2, values_only=True):
                if not row_data or all(c is None for c in row_data):
                    continue

                item_code = str(row_data[col_idx.get('item_code', 0)] or "").strip()
                if not item_code:
                    continue

                # Check duplicate
                if session.query(Product).filter_by(item_code=item_code).first():
                    skipped += 1
                    continue

                product = Product()
                product.item_code = item_code
                product.created_by = self.current_user
                product.updated_by = self.current_user

                field_map = {
                    'description': 'description',
                    'part_number': 'part_number',
                    'size1': 'size1',
                    'size2': 'size2',
                    'material': 'material',
                    'material_class': 'material_class',
                    'discipline': 'discipline',
                    'category': 'category',
                    'unit_of_measure': 'unit_of_measure',
                    'remarks': 'remarks',
                    'storage_condition': 'storage_condition',
                }

                for col_name, attr_name in field_map.items():
                    idx = col_idx.get(col_name)
                    if idx is not None and idx < len(row_data) and row_data[idx] is not None:
                        setattr(product, attr_name, str(row_data[idx]).strip())

                # Numeric fields
                for col_name, attr_name in [('min_required_qty', 'min_required_qty'),
                                            ('unit_cost', 'unit_cost'),
                                            ('weight', 'weight')]:
                    idx = col_idx.get(col_name)
                    if idx is not None and idx < len(row_data) and row_data[idx] is not None:
                        try:
                            setattr(product, attr_name, float(row_data[idx]))
                        except (ValueError, TypeError):
                            pass

                # Status fields
                for col_name, attr_name in [('lifecycle_status', 'lifecycle_status'),
                                            ('preservation_status', 'preservation_status')]:
                    idx = col_idx.get(col_name)
                    if idx is not None and idx < len(row_data) and row_data[idx] is not None:
                        val = str(row_data[idx]).strip().upper()
                        if val in ["ACTIVE", "OBSOLETE", "HOLD", "DISCONTINUED"]:
                            setattr(product, attr_name, val)

                session.add(product)
                imported += 1

            session.commit()
            session.close()
            self._load_items()
            
            msg = f"{imported} items imported successfully."
            if skipped > 0:
                msg += f"\n{skipped} duplicates skipped."
            QMessageBox.information(self, "Import Complete", msg)
            self.status_bar.showMessage(msg, 5000)
            self.coding_updated.emit()

        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _export_excel(self):
        """Export products to Excel."""
        if not OPENPYXL_AVAILABLE:
            QMessageBox.warning(self, "Library Required", "openpyxl is required.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Products", "product_coding.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Products"

            headers = [
                "Item Code", "Description", "Part Number", "Material Class",
                "Discipline", "Category", "Unit", "Min Qty", "Unit Cost",
                "Size1", "Size2", "Material", "Weight", "Lifecycle",
                "Preservation", "Storage", "Remarks"
            ]

            header_font = XlFont(bold=True, color="FFFFFF", size=11)
            header_fill = PatternFill(start_color="004D40", end_color="004D40", fill_type="solid")

            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")

            row_num = 2
            for item in self.all_items:
                ws.cell(row=row_num, column=1, value=item.item_code)
                ws.cell(row=row_num, column=2, value=item.description)
                ws.cell(row=row_num, column=3, value=item.part_number)
                ws.cell(row=row_num, column=4, value=item.material_class)
                ws.cell(row=row_num, column=5, value=item.discipline)
                ws.cell(row=row_num, column=6, value=item.category)
                ws.cell(row=row_num, column=7, value=item.unit_of_measure)
                ws.cell(row=row_num, column=8, value=item.min_required_qty)
                ws.cell(row=row_num, column=9, value=item.unit_cost)
                ws.cell(row=row_num, column=10, value=item.size1)
                ws.cell(row=row_num, column=11, value=item.size2)
                ws.cell(row=row_num, column=12, value=item.material)
                ws.cell(row=row_num, column=13, value=item.weight)
                ws.cell(row=row_num, column=14, value=item.lifecycle_status)
                ws.cell(row=row_num, column=15, value=item.preservation_status)
                ws.cell(row=row_num, column=16, value=item.storage_condition)
                ws.cell(row=row_num, column=17, value=item.remarks)
                row_num += 1

            for col in range(1, len(headers) + 1):
                ws.column_dimensions[get_column_letter(col)].width = 18

            wb.save(file_path)
            QMessageBox.information(self, "Export Complete", f"Exported to:\n{file_path}")
            self.status_bar.showMessage("Export complete", 3000)

        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _download_template(self):
        """Download Excel template."""
        if not OPENPYXL_AVAILABLE:
            QMessageBox.warning(self, "Library Required", "openpyxl is required.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Template", "product_template.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Template"

            headers = [
                "item_code", "description", "part_number", "material_class",
                "discipline", "category", "unit_of_measure", "min_required_qty",
                "unit_cost", "size1", "size2", "material", "weight",
                "lifecycle_status", "preservation_status", "storage_condition", "remarks"
            ]

            header_font = XlFont(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="004D40", end_color="004D40", fill_type="solid")

            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill

            # Example row
            example = [
                "PIPE-6-CS", "Carbon Steel Pipe 6\"", "ASTM-A106-GrB",
                "Carbon Steel", "Piping", "Pipe", "MTR", 10, 25.5,
                "6\"", "SCH 40", "ASTM A106 Gr.B", 42.5,
                "ACTIVE", "PRESERVED", "Covered", "Example item"
            ]
            for col, val in enumerate(example, 1):
                ws.cell(row=2, column=col, value=val)

            for col in range(1, len(headers) + 1):
                ws.column_dimensions[get_column_letter(col)].width = 20

            wb.save(file_path)
            QMessageBox.information(self, "Template Created", f"Template saved to:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))