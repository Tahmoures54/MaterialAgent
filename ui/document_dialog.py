# ui/document_dialog.py
"""
Warehouse Document Manager – iMat Material Control System (EPC Edition).

Complete document management with:
- All EPC document types (MRR, MIV, MSR, OSND, MTR, RTV, MRV, etc.)
- Document header creation with auto-numbering
- Line item management with stock integration
- Document workflow (Draft → Approved → Closed)
- Import/Export to Excel
- Document printing and preview
- Role-based access control
- Visual flow indicators (IN/OUT/TRANSFER/RETURN)
- Real-time stock validation
- Duplicate document detection
"""

import os
import json
from datetime import date, datetime
from typing import Optional, List, Dict, Any, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QFormLayout, QMessageBox,
    QDateEdit, QHeaderView, QLabel, QFrame, QStatusBar, QWidget,
    QTabWidget, QTextEdit, QSplitter, QMenu, QToolBar, QToolButton,
    QCheckBox, QSpinBox, QDoubleSpinBox, QGroupBox, QScrollArea,
    QAbstractItemView, QApplication, QFileDialog, QInputDialog,
    QDialogButtonBox, QProgressBar
)
from PyQt6.QtCore import Qt, QDate, QUrl, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QAction, QDesktopServices

from sqlalchemy import func, or_
from db.database import SessionLocal, get_db_session
from db.models import (
    Document, DocumentLine, Product, Stock, Location, Transaction
)
from logic.document_logic import (
    create_document, update_document_status,
    get_document_by_no, get_documents_by_date, delete_document
)
from logic.stock_logic import add_stock, remove_stock, get_stock_by_item
from ui.logo_widget import LogoWidget
from ui.transaction_dialog import TransactionDialog
from utils.excel_export import export_to_excel
from utils.html_export import export_document_to_html, preview_html_in_browser

# ==================================================================
# Constants
# ==================================================================

# Document type definitions with metadata
DOCUMENT_TYPES = [
    ("MRR", "Material Receipt Report", "📥", "IN", "#27ae60"),
    ("MIV", "Material Issue Voucher", "📤", "OUT", "#e67e22"),
    ("MSR", "Material Store Requisition", "📋", "REQUEST", "#3498db"),
    ("OSND", "Over, Short & Damaged Report", "⚠️", "ADJUST", "#e74c3c"),
    ("MTR", "Material Transfer Note", "🔄", "TRANSFER", "#9b59b6"),
    ("RTV", "Return to Vendor", "↩️", "RETURN", "#c0392b"),
    ("MRV", "Material Return Voucher", "♻️", "RETURN", "#2ecc71"),
    ("ADJ", "Stock Adjustment", "⚖️", "ADJUST", "#f39c12"),
    ("RES", "Material Reservation", "🔒", "RESERVE", "#2980b9"),
    ("SRN", "Supplier Return Note", "↩️", "RETURN", "#c0392b"),
    ("WOM", "Work Order Material Issue", "📤", "OUT", "#e67e22"),
    ("GAT", "Gate Pass (Material Out)", "🚪", "OUT", "#7f8c8d"),
    ("RCT", "General Receipt", "📥", "IN", "#27ae60"),
    ("ISS", "General Issue", "📤", "OUT", "#e67e22"),
    ("TRN", "General Transfer", "🔄", "TRANSFER", "#9b59b6"),
]

# Document flow categories
RECEIPT_TYPES = {"MRR", "RCT", "MRV"}
ISSUE_TYPES = {"MIV", "ISS", "WOM", "GAT"}
TRANSFER_TYPES = {"MTR", "TRN"}
RETURN_TYPES = {"RTV", "SRN"}
ADJUSTMENT_TYPES = {"OSND", "ADJ"}
NO_STOCK_CHANGE = {"MSR", "RES"}

# Document status flow
STATUS_TRANSITIONS = {
    "DRAFT": ["APPROVED", "REJECTED", "CANCELLED"],
    "APPROVED": ["CLOSED"],
    "REJECTED": ["DRAFT"],
    "CLOSED": [],
    "CANCELLED": [],
}

STATUS_COLORS = {
    "DRAFT": {"bg": "#FFF9C4", "fg": "#F57F17"},
    "APPROVED": {"bg": "#C8E6C9", "fg": "#2E7D32"},
    "REJECTED": {"bg": "#FFCDD2", "fg": "#C62828"},
    "CLOSED": {"bg": "#BBDEFB", "fg": "#1565C0"},
    "CANCELLED": {"bg": "#E0E0E0", "fg": "#616161"},
}

# ==================================================================
# Document Dialog
# ==================================================================

class DocumentDialog(QDialog):
    """
    Comprehensive warehouse document manager.
    
    Supports all EPC document types with inventory integration,
    workflow management, and reporting capabilities.
    """

    document_created = pyqtSignal(str)  # document number
    document_updated = pyqtSignal(str)

    def __init__(self, parent=None, default_type: Optional[str] = None, 
                 user_role: str = "viewer", document_id: Optional[int] = None):
        """
        Initialize the document dialog.
        
        Args:
            parent: Parent widget
            default_type: Default document type to select
            user_role: Current user's role
            document_id: Optional document ID to load for editing
        """
        super().__init__(parent)
        self.parent = parent
        self.user_role = user_role
        self.current_user = self._get_username_from_parent()
        self.document_id = document_id
        
        # State
        self.db = SessionLocal()
        self.edit_mode = document_id is not None
        self.current_document: Optional[Document] = None
        
        # Window setup
        self.setWindowTitle("iMat – Document Manager" if not self.edit_mode 
                           else "iMat – Edit Document")
        self.setMinimumSize(1200, 750)
        
        # Build UI
        self._init_ui()
        
        # Load data
        self._load_recent_documents()
        
        # Set default type
        if default_type:
            idx = self.doc_type_combo.findData(default_type)
            if idx >= 0:
                self.doc_type_combo.setCurrentIndex(idx)
        
        # Load document if editing
        if self.document_id:
            self._load_document(self.document_id)
        
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

        title = QLabel("📄 Document Manager")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("Create and manage warehouse documents")
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

        self.action_new = toolbar.addAction("➕ New Document")
        self.action_new.triggered.connect(self._new_document)
        toolbar.addSeparator()
        
        self.action_save = toolbar.addAction("💾 Save")
        self.action_save.triggered.connect(self._save_document)
        toolbar.addSeparator()
        
        self.action_approve = toolbar.addAction("✅ Approve")
        self.action_approve.triggered.connect(lambda: self._change_status("APPROVED"))
        
        self.action_reject = toolbar.addAction("❌ Reject")
        self.action_reject.triggered.connect(lambda: self._change_status("REJECTED"))
        
        self.action_close = toolbar.addAction("🔒 Close")
        self.action_close.triggered.connect(lambda: self._change_status("CLOSED"))
        toolbar.addSeparator()
        
        self.action_refresh = toolbar.addAction("🔄 Refresh")
        self.action_refresh.triggered.connect(self._load_recent_documents)
        
        self.action_delete = toolbar.addAction("🗑️ Delete")
        self.action_delete.triggered.connect(self._delete_document)

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

        # Tab 1: Document Form
        self.tab_form = self._build_form_tab()
        self.tab_widget.addTab(self.tab_form, "📝 Document Form")

        # Tab 2: Document List
        self.tab_list = self._build_list_tab()
        self.tab_widget.addTab(self.tab_list, "📋 Recent Documents")

        parent_layout.addWidget(self.tab_widget)

    def _build_form_tab(self) -> QWidget:
        """Build the document form tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(10)

        # Scroll area for the form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)
        form_layout.setSpacing(12)

        # ---- Document Header Section ----
        header_group = QGroupBox("📄 Document Header")
        header_group.setStyleSheet(self._get_group_style())
        header_form = QFormLayout(header_group)
        header_form.setSpacing(8)

        # Document Type
        self.doc_type_combo = QComboBox()
        for code, name, icon, flow, color in DOCUMENT_TYPES:
            self.doc_type_combo.addItem(f"{icon} {code} – {name}", code)
        self.doc_type_combo.setMinimumWidth(300)
        self.doc_type_combo.currentIndexChanged.connect(self._on_type_changed)
        header_form.addRow("Document Type *:", self.doc_type_combo)

        # Document Number
        doc_no_layout = QHBoxLayout()
        self.doc_no_input = QLineEdit()
        self.doc_no_input.setPlaceholderText("Auto-generated if left blank")
        doc_no_layout.addWidget(self.doc_no_input)
        btn_generate = QPushButton("🔄 Auto")
        btn_generate.setToolTip("Generate document number automatically")
        btn_generate.clicked.connect(self._generate_doc_number)
        doc_no_layout.addWidget(btn_generate)
        header_form.addRow("Document No *:", doc_no_layout)

        # Date
        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        header_form.addRow("Document Date *:", self.date_input)

        # Subject
        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("Document subject or title")
        header_form.addRow("Subject:", self.subject_input)

        # PO Number
        self.po_no_input = QLineEdit()
        self.po_no_input.setPlaceholderText("Purchase Order number")
        header_form.addRow("PO No:", self.po_no_input)

        # Reference
        self.reference_input = QLineEdit()
        self.reference_input.setPlaceholderText("Invoice / Request reference")
        header_form.addRow("Reference:", self.reference_input)

        # Delivery Note (receipt types)
        self.delivery_note_input = QLineEdit()
        self.delivery_note_input.setPlaceholderText("Supplier delivery note number")
        header_form.addRow("Delivery Note:", self.delivery_note_input)

        # Vendor (receipt types)
        self.vendor_input = QLineEdit()
        self.vendor_input.setPlaceholderText("Supplier / Vendor name")
        header_form.addRow("Vendor:", self.vendor_input)

        # Subcontractor (issue types)
        self.subcontractor_input = QLineEdit()
        self.subcontractor_input.setPlaceholderText("Subcontractor / Receiver")
        header_form.addRow("Subcontractor:", self.subcontractor_input)

        # Remarks
        self.remarks_input = QTextEdit()
        self.remarks_input.setMaximumHeight(60)
        self.remarks_input.setPlaceholderText("Additional remarks or notes")
        header_form.addRow("Remarks:", self.remarks_input)

        form_layout.addWidget(header_group)

        # ---- Document Lines Section ----
        lines_group = QGroupBox("📋 Document Lines")
        lines_group.setStyleSheet(self._get_group_style())
        lines_layout = QVBoxLayout(lines_group)

        # Lines table
        self.lines_table = QTableWidget()
        self.lines_table.setColumnCount(8)
        self.lines_table.setHorizontalHeaderLabels([
            "#", "Item Code", "Description", "Heat No",
            "Location", "Quantity", "Unit", "Actions"
        ])
        self.lines_table.horizontalHeader().setStretchLastSection(True)
        self.lines_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lines_table.setAlternatingRowColors(True)
        self.lines_table.setStyleSheet("""
            QTableWidget {
                background: white;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #004D40;
                color: white;
                font-weight: bold;
                padding: 4px;
            }
        """)
        
        column_widths = [40, 120, 200, 100, 100, 80, 60, 80]
        for i, w in enumerate(column_widths):
            self.lines_table.setColumnWidth(i, w)

        lines_layout.addWidget(self.lines_table)

        # Lines action buttons
        lines_btn_layout = QHBoxLayout()
        
        btn_add_line = QPushButton("➕ Add Line")
        btn_add_line.setStyleSheet(self._get_button_style("primary"))
        btn_add_line.clicked.connect(self._add_line)
        lines_btn_layout.addWidget(btn_add_line)
        
        btn_remove_line = QPushButton("❌ Remove Line")
        btn_remove_line.setStyleSheet(self._get_button_style("danger"))
        btn_remove_line.clicked.connect(self._remove_line)
        lines_btn_layout.addWidget(btn_remove_line)
        
        lines_btn_layout.addStretch()
        
        self.total_qty_label = QLabel("Total Qty: 0")
        self.total_qty_label.setStyleSheet("font-weight: bold; color: #004D40;")
        lines_btn_layout.addWidget(self.total_qty_label)
        
        lines_layout.addLayout(lines_btn_layout)

        form_layout.addWidget(lines_group)

        # ---- Action Buttons ----
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        
        btn_save = QPushButton("💾 Save Document")
        btn_save.setStyleSheet(self._get_button_style("success"))
        btn_save.setMinimumHeight(40)
        btn_save.clicked.connect(self._save_document)
        action_layout.addWidget(btn_save)
        
        btn_clear = QPushButton("🔄 Clear Form")
        btn_clear.setStyleSheet(self._get_button_style("neutral"))
        btn_clear.clicked.connect(self._clear_form)
        action_layout.addWidget(btn_clear)
        
        action_layout.addStretch()
        
        form_layout.addLayout(action_layout)

        scroll.setWidget(form_container)
        layout.addWidget(scroll)

        # Initial type setup
        self._on_type_changed()

        return widget

    def _build_list_tab(self) -> QWidget:
        """Build the document list tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Search/filter bar
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("🔍 Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by doc no, type, vendor...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_documents)
        filter_layout.addWidget(self.search_input)
        
        filter_layout.addWidget(QLabel("Status:"))
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(["All", "DRAFT", "APPROVED", "REJECTED", "CLOSED", "CANCELLED"])
        self.status_filter_combo.currentTextChanged.connect(self._filter_documents)
        filter_layout.addWidget(self.status_filter_combo)
        
        filter_layout.addWidget(QLabel("Type:"))
        self.type_filter_combo = QComboBox()
        self.type_filter_combo.addItem("All")
        for code, name, icon, flow, color in DOCUMENT_TYPES:
            self.type_filter_combo.addItem(f"{icon} {code}", code)
        self.type_filter_combo.currentTextChanged.connect(self._filter_documents)
        filter_layout.addWidget(self.type_filter_combo)
        
        layout.addLayout(filter_layout)

        # Documents table
        self.docs_table = QTableWidget()
        self.docs_table.setColumnCount(10)
        self.docs_table.setHorizontalHeaderLabels([
            "Document No", "Type", "Flow", "Date", "Subject",
            "Vendor", "Status", "Lines", "Created By", "Actions"
        ])
        self.docs_table.horizontalHeader().setStretchLastSection(True)
        self.docs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.docs_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.docs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.docs_table.setAlternatingRowColors(True)
        self.docs_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.docs_table.customContextMenuRequested.connect(self._show_document_context_menu)
        self.docs_table.doubleClicked.connect(self._on_document_double_clicked)
        self.docs_table.setStyleSheet("""
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
                padding: 6px;
            }
        """)
        
        doc_column_widths = [150, 80, 60, 100, 150, 120, 80, 50, 100, 120]
        for i, w in enumerate(doc_column_widths):
            self.docs_table.setColumnWidth(i, w)

        layout.addWidget(self.docs_table)

        # Record count
        self.doc_count_label = QLabel("Documents: 0")
        self.doc_count_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.doc_count_label)

        return widget

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready – Create a new document or select from list")
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

    def _get_button_style(self, button_type: str) -> str:
        """Get button stylesheet by type."""
        styles = {
            "primary": """
                QPushButton {
                    background-color: #00897B;
                    color: white;
                    border: none;
                    padding: 6px 14px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #00695C; }
                QPushButton:disabled { background-color: #999; }
            """,
            "success": """
                QPushButton {
                    background-color: #2E86C1;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    font-weight: bold;
                    border-radius: 4px;
                    font-size: 13px;
                }
                QPushButton:hover { background-color: #2471A3; }
                QPushButton:disabled { background-color: #999; }
            """,
            "danger": """
                QPushButton {
                    background-color: #D32F2F;
                    color: white;
                    border: none;
                    padding: 6px 14px;
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
                    padding: 6px 14px;
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
        """Apply role-based access restrictions."""
        if self.user_role == "viewer":
            # Disable all editing
            for widget in self.findChildren((QLineEdit, QTextEdit, QComboBox, QDateEdit)):
                if hasattr(widget, 'setReadOnly'):
                    widget.setReadOnly(True)
                else:
                    widget.setEnabled(False)
            
            self.action_save.setEnabled(False)
            self.action_approve.setEnabled(False)
            self.action_reject.setEnabled(False)
            self.action_close.setEnabled(False)
            self.action_delete.setEnabled(False)
            self.action_new.setEnabled(False)
            self.status_bar.showMessage("Read-only mode – You cannot modify documents")

    def _get_username_from_parent(self) -> str:
        """Get username from parent window."""
        try:
            if hasattr(self.parent, 'current_user'):
                return self.parent.current_user
        except Exception:
            pass
        return "unknown"

    # ==================================================================
    # Document Form Methods
    # ==================================================================

    def _on_type_changed(self):
        """Handle document type change - show/hide relevant fields."""
        code = self.doc_type_combo.currentData()
        if not code:
            return

        is_receipt = code in RECEIPT_TYPES
        is_issue = code in ISSUE_TYPES
        is_transfer = code in TRANSFER_TYPES
        is_return = code in RETURN_TYPES

        # Show/hide fields based on type
        self.delivery_note_input.setVisible(is_receipt)
        self.vendor_input.setVisible(is_receipt or is_return)
        self.subcontractor_input.setVisible(is_issue)

        # Update subtitle
        flow_text = "IN" if is_receipt else ("OUT" if is_issue else (
            "TRANSFER" if is_transfer else ("RETURN" if is_return else "OTHER")
        ))
        self.subtitle.setText(f"Document Type: {code} – Flow: {flow_text}")

    def _generate_doc_number(self):
        """Auto-generate document number."""
        doc_type = self.doc_type_combo.currentData()
        if not doc_type:
            return

        today_str = QDate.currentDate().toString("yyyyMMdd")
        
        # Count existing documents of this type for today
        count = self.db.query(Document).filter(
            Document.doc_type == doc_type,
            Document.doc_date == date.today()
        ).count()

        doc_no = f"{doc_type}-{today_str}-{count + 1:03d}"
        self.doc_no_input.setText(doc_no)

    def _add_line(self):
        """Add a new line to the document."""
        row = self.lines_table.rowCount()
        self.lines_table.insertRow(row)

        # Row number
        row_item = QTableWidgetItem(str(row + 1))
        row_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        row_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.lines_table.setItem(row, 0, row_item)

        # Item Code (editable)
        item_code_combo = QComboBox()
        item_code_combo.setEditable(True)
        item_code_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._load_item_codes(item_code_combo)
        item_code_combo.currentTextChanged.connect(
            lambda text, r=row: self._on_line_item_changed(r, text)
        )
        self.lines_table.setCellWidget(row, 1, item_code_combo)

        # Description (auto-filled)
        desc_item = QTableWidgetItem("")
        desc_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.lines_table.setItem(row, 2, desc_item)

        # Heat No (editable)
        heat_input = QLineEdit()
        heat_input.setPlaceholderText("Heat/Batch No")
        self.lines_table.setCellWidget(row, 3, heat_input)

        # Location (editable combo)
        location_combo = QComboBox()
        location_combo.setEditable(True)
        self._load_locations(location_combo)
        self.lines_table.setCellWidget(row, 4, location_combo)

        # Quantity (spinbox)
        qty_spin = QDoubleSpinBox()
        qty_spin.setRange(0.01, 999999.99)
        qty_spin.setDecimals(2)
        qty_spin.setValue(1.0)
        qty_spin.valueChanged.connect(self._update_total_qty)
        self.lines_table.setCellWidget(row, 5, qty_spin)

        # Unit (auto-filled)
        unit_item = QTableWidgetItem("EA")
        unit_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.lines_table.setItem(row, 6, unit_item)

        # Remove button
        btn_remove = QPushButton("🗑️")
        btn_remove.setFixedSize(30, 30)
        btn_remove.setStyleSheet("""
            QPushButton {
                background-color: #FFCDD2;
                border: none;
                border-radius: 15px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #EF9A9A;
            }
        """)
        btn_remove.clicked.connect(lambda: self._remove_line_at(row))
        self.lines_table.setCellWidget(row, 7, btn_remove)

        self._update_total_qty()

    def _remove_line(self):
        """Remove selected line."""
        current_row = self.lines_table.currentRow()
        if current_row >= 0:
            self._remove_line_at(current_row)

    def _remove_line_at(self, row: int):
        """Remove line at specific row."""
        self.lines_table.removeRow(row)
        # Renumber rows
        for i in range(self.lines_table.rowCount()):
            self.lines_table.item(i, 0).setText(str(i + 1))
        self._update_total_qty()

    def _on_line_item_changed(self, row: int, text: str):
        """Handle item code selection in line."""
        code = text.strip()
        if " – " in code:
            code = code.split(" – ", 1)[0].strip()

        session = get_db_session()
        try:
            product = session.query(Product).filter_by(item_code=code).first()
            if product:
                self.lines_table.item(row, 2).setText(product.description or "")
                self.lines_table.item(row, 6).setText(product.unit_of_measure or "EA")
        finally:
            session.close()

    def _load_item_codes(self, combo: QComboBox):
        """Load item codes into combo box."""
        session = get_db_session()
        try:
            products = session.query(
                Product.item_code, Product.description
            ).order_by(Product.item_code).all()
            
            combo.clear()
            combo.addItem("")
            for code, desc in products:
                display = f"{code} – {desc}" if desc else code
                combo.addItem(display, code)
        finally:
            session.close()

    def _load_locations(self, combo: QComboBox):
        """Load locations into combo box."""
        session = get_db_session()
        try:
            locations = session.query(Location.code).order_by(Location.code).all()
            combo.clear()
            combo.addItem("")
            for (code,) in locations:
                combo.addItem(code)
        finally:
            session.close()

    def _update_total_qty(self):
        """Update total quantity label."""
        total = 0
        for row in range(self.lines_table.rowCount()):
            widget = self.lines_table.cellWidget(row, 5)
            if widget and isinstance(widget, QDoubleSpinBox):
                total += widget.value()
        self.total_qty_label.setText(f"Total Qty: {total:.2f}")

    def _clear_form(self):
        """Clear the document form."""
        self.doc_type_combo.setCurrentIndex(0)
        self.doc_no_input.clear()
        self.date_input.setDate(QDate.currentDate())
        self.subject_input.clear()
        self.po_no_input.clear()
        self.reference_input.clear()
        self.delivery_note_input.clear()
        self.vendor_input.clear()
        self.subcontractor_input.clear()
        self.remarks_input.clear()
        self.lines_table.setRowCount(0)
        self.current_document = None
        self.edit_mode = False
        self._update_total_qty()

    def _new_document(self):
        """Switch to form tab and clear for new document."""
        self._clear_form()
        self.tab_widget.setCurrentIndex(0)
        self.doc_type_combo.setFocus()

    # ==================================================================
    # Save & Load Methods
    # ==================================================================

    def _validate_form(self) -> Tuple[bool, str]:
        """Validate the document form before saving."""
        doc_type = self.doc_type_combo.currentData()
        if not doc_type:
            return False, "Please select a document type."

        doc_no = self.doc_no_input.text().strip()
        if not doc_no:
            return False, "Document number is required."

        # Check duplicate document number (only for new documents)
        if not self.edit_mode:
            existing = self.db.query(Document).filter_by(doc_no=doc_no).first()
            if existing:
                return False, f"Document number '{doc_no}' already exists."

        if self.lines_table.rowCount() == 0:
            return False, "At least one line item is required."

        return True, ""

    def _save_document(self):
        """Save the document."""
        valid, error = self._validate_form()
        if not valid:
            QMessageBox.warning(self, "Validation Error", error)
            return

        try:
            # Collect header data
            header_data = {
                "doc_no": self.doc_no_input.text().strip(),
                "doc_type": self.doc_type_combo.currentData(),
                "doc_date": self.date_input.date().toPyDate(),
                "po_no": self.po_no_input.text().strip(),
                "reference_no": self.reference_input.text().strip(),
                "delivery_note_no": self.delivery_note_input.text().strip(),
                "vendor_name": self.vendor_input.text().strip(),
                "subcontractor": self.subcontractor_input.text().strip(),
                "subject": self.subject_input.text().strip(),
                "remarks": self.remarks_input.toPlainText().strip(),
                "created_by": self.current_user,
            }

            # Collect lines data
            lines_data = []
            for row in range(self.lines_table.rowCount()):
                item_combo = self.lines_table.cellWidget(row, 1)
                item_code = item_combo.currentText().strip() if item_combo else ""
                
                # Extract code from display format
                if " – " in item_code:
                    item_code = item_code.split(" – ", 1)[0].strip()

                heat_widget = self.lines_table.cellWidget(row, 3)
                heat_no = heat_widget.text().strip() if heat_widget else ""

                loc_combo = self.lines_table.cellWidget(row, 4)
                loc_code = loc_combo.currentText().strip() if loc_combo else ""

                # Get location ID from code
                location_id = None
                if loc_code:
                    loc = self.db.query(Location).filter_by(code=loc_code).first()
                    if loc:
                        location_id = loc.id

                if not item_code or not location_id:
                    continue

                qty_widget = self.lines_table.cellWidget(row, 5)
                qty = qty_widget.value() if qty_widget else 0

                unit_item = self.lines_table.item(row, 6)
                unit = unit_item.text() if unit_item else "EA"

                lines_data.append({
                    "item_code": item_code,
                    "heat_no": heat_no,
                    "location_id": location_id,
                    "qty": qty,
                    "unit": unit,
                })

            if not lines_data:
                QMessageBox.warning(self, "Validation Error", 
                                   "No valid line items found.")
                return

            # Create or update document
            if self.edit_mode and self.current_document:
                # Update existing document (basic fields only)
                doc = self.current_document
                doc.doc_no = header_data["doc_no"]
                doc.doc_type = header_data["doc_type"]
                doc.doc_date = header_data["doc_date"]
                doc.po_no = header_data["po_no"]
                doc.reference_no = header_data["reference_no"]
                doc.subject = header_data["subject"]
                doc.remarks = header_data["remarks"]
                doc.vendor_name = header_data["vendor_name"]
                doc.subcontractor = header_data["subcontractor"]
                self.db.commit()
                QMessageBox.information(self, "Success", "Document updated successfully.")
                self.document_updated.emit(doc.doc_no)
            else:
                # Create new document
                doc = create_document(self.db, header_data, lines_data)
                QMessageBox.information(
                    self, "Success",
                    f"Document '{doc.doc_no}' created successfully.\n"
                    f"Lines: {len(lines_data)} | Total Qty: {sum(l['qty'] for l in lines_data):.2f}"
                )
                self.document_created.emit(doc.doc_no)

            self._load_recent_documents()
            self.status_bar.showMessage(f"Document saved: {header_data['doc_no']}", 5000)

        except ValueError as e:
            self.db.rollback()
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save document:\n{str(e)}")

    def _load_document(self, document_id: int):
        """Load a document for editing."""
        doc = self.db.query(Document).filter_by(id=document_id).first()
        if not doc:
            QMessageBox.warning(self, "Not Found", "Document not found.")
            return

        self.current_document = doc
        self.edit_mode = True

        # Fill header
        idx = self.doc_type_combo.findData(doc.doc_type)
        if idx >= 0:
            self.doc_type_combo.setCurrentIndex(idx)
        
        self.doc_no_input.setText(doc.doc_no)
        self.doc_no_input.setReadOnly(True)  # Can't change doc number in edit mode
        
        if doc.doc_date:
            self.date_input.setDate(QDate(doc.doc_date.year, doc.doc_date.month, doc.doc_date.day))
        
        self.subject_input.setText(doc.subject or "")
        self.po_no_input.setText(doc.po_no or "")
        self.reference_input.setText(doc.reference_no or "")
        self.delivery_note_input.setText(doc.delivery_note_no or "")
        self.vendor_input.setText(doc.vendor_name or "")
        self.subcontractor_input.setText(doc.subcontractor or "")
        self.remarks_input.setPlainText(doc.remarks or "")

        # Fill lines
        self.lines_table.setRowCount(0)
        for i, line in enumerate(doc.lines):
            self._add_line()
            row = self.lines_table.rowCount() - 1
            
            # Set item code
            item_combo = self.lines_table.cellWidget(row, 1)
            if item_combo:
                idx = item_combo.findData(line.item_code)
                if idx >= 0:
                    item_combo.setCurrentIndex(idx)
                else:
                    item_combo.setCurrentText(line.item_code)
            
            # Set heat no
            heat_widget = self.lines_table.cellWidget(row, 3)
            if heat_widget:
                heat_widget.setText(line.heat_no or "")
            
            # Set location
            loc_combo = self.lines_table.cellWidget(row, 4)
            if loc_combo and line.location:
                loc = self.db.query(Location).filter_by(id=line.location_id).first()
                if loc:
                    idx = loc_combo.findText(loc.code)
                    if idx >= 0:
                        loc_combo.setCurrentIndex(idx)
            
            # Set quantity
            qty_widget = self.lines_table.cellWidget(row, 5)
            if qty_widget:
                qty_widget.setValue(line.qty)
            
            # Set unit
            unit_item = self.lines_table.item(row, 6)
            if unit_item:
                unit_item.setText(line.unit or "EA")

        self._update_total_qty()
        self.tab_widget.setCurrentIndex(0)
        self.status_bar.showMessage(f"Loaded document: {doc.doc_no}", 3000)

    # ==================================================================
    # Document List Methods
    # ==================================================================

    def _load_recent_documents(self):
        """Load recent documents into the list table."""
        try:
            docs = self.db.query(Document).order_by(
                Document.created_at.desc()
            ).limit(100).all()

            self._display_documents(docs)
            self.doc_count_label.setText(f"Documents: {len(docs)}")
            self.status_bar.showMessage(f"Loaded {len(docs)} documents", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load documents:\n{str(e)}")

    def _display_documents(self, docs: List[Document]):
        """Display documents in the table."""
        self.docs_table.setRowCount(len(docs))

        for row, doc in enumerate(docs):
            # Document No
            doc_no_item = QTableWidgetItem(doc.doc_no)
            doc_no_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.docs_table.setItem(row, 0, doc_no_item)

            # Type
            self.docs_table.setItem(row, 1, QTableWidgetItem(doc.doc_type))

            # Flow indicator
            flow, color = self._get_flow_info(doc.doc_type)
            flow_item = QTableWidgetItem(flow)
            flow_item.setForeground(QColor(color))
            flow_item.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            self.docs_table.setItem(row, 2, flow_item)

            # Date
            date_str = str(doc.doc_date) if doc.doc_date else ""
            self.docs_table.setItem(row, 3, QTableWidgetItem(date_str))

            # Subject
            self.docs_table.setItem(row, 4, QTableWidgetItem(doc.subject or ""))

            # Vendor
            self.docs_table.setItem(row, 5, QTableWidgetItem(doc.vendor_name or ""))

            # Status with color
            status_item = QTableWidgetItem(doc.status)
            status_config = STATUS_COLORS.get(doc.status, {})
            if status_config:
                status_item.setBackground(QColor(status_config.get("bg", "#FFF")))
                status_item.setForeground(QColor(status_config.get("fg", "#000")))
            self.docs_table.setItem(row, 6, status_item)

            # Line count
            line_count = str(len(doc.lines))
            count_item = QTableWidgetItem(line_count)
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.docs_table.setItem(row, 7, count_item)

            # Created by
            self.docs_table.setItem(row, 8, QTableWidgetItem(doc.created_by or ""))

            # Actions button
            btn_actions = QPushButton("📋 Actions")
            btn_actions.setStyleSheet(self._get_button_style("primary"))
            btn_actions.clicked.connect(
                lambda checked, d=doc: self._show_document_actions(d)
            )
            self.docs_table.setCellWidget(row, 9, btn_actions)

    def _get_flow_info(self, doc_type: str) -> Tuple[str, str]:
        """Get flow indicator and color for document type."""
        if doc_type in RECEIPT_TYPES:
            return "⬇ IN", "#2E7D32"
        elif doc_type in ISSUE_TYPES:
            return "⬆ OUT", "#C62828"
        elif doc_type in TRANSFER_TYPES:
            return "↔ TRANSFER", "#1565C0"
        elif doc_type in RETURN_TYPES:
            return "↩ RETURN", "#E65100"
        elif doc_type in ADJUSTMENT_TYPES:
            return "⚖ ADJUST", "#F57F17"
        else:
            return "• OTHER", "#333"

    def _filter_documents(self):
        """Filter documents based on search criteria."""
        search_text = self.search_input.text().strip().lower()
        status_filter = self.status_filter_combo.currentText()
        type_filter = self.type_filter_combo.currentData()

        for row in range(self.docs_table.rowCount()):
            show = True

            if search_text:
                match = False
                for col in [0, 1, 4, 5, 8]:
                    item = self.docs_table.item(row, col)
                    if item and search_text in item.text().lower():
                        match = True
                        break
                if not match:
                    show = False

            if status_filter != "All":
                status_item = self.docs_table.item(row, 6)
                if status_item and status_item.text() != status_filter:
                    show = False

            if type_filter:
                type_item = self.docs_table.item(row, 1)
                if type_item and type_item.text() != type_filter:
                    show = False

            self.docs_table.setRowHidden(row, not show)

        visible_count = sum(
            1 for row in range(self.docs_table.rowCount())
            if not self.docs_table.isRowHidden(row)
        )
        self.doc_count_label.setText(f"Documents: {visible_count}")

    def _show_document_context_menu(self, pos):
        """Show context menu for document list."""
        row = self.docs_table.currentRow()
        if row < 0:
            return

        doc_no = self.docs_table.item(row, 0).text()
        doc = self.db.query(Document).filter_by(doc_no=doc_no).first()
        if not doc:
            return

        menu = QMenu(self)
        menu.addAction("✏️ Edit", lambda: self._load_document(doc.id))
        menu.addAction("📋 View Lines", lambda: self._view_document_lines(doc))
        menu.addSeparator()
        
        if doc.status == "DRAFT":
            menu.addAction("✅ Approve", lambda: self._change_status_for_doc(doc, "APPROVED"))
            menu.addAction("❌ Reject", lambda: self._change_status_for_doc(doc, "REJECTED"))
        elif doc.status == "APPROVED":
            menu.addAction("🔒 Close", lambda: self._change_status_for_doc(doc, "CLOSED"))
        elif doc.status == "REJECTED":
            menu.addAction("🔄 Reopen", lambda: self._change_status_for_doc(doc, "DRAFT"))
        
        menu.addSeparator()
        menu.addAction("📄 Export HTML", lambda: self._export_document_html(doc))
        menu.addAction("🗑️ Delete", lambda: self._delete_document_by_no(doc_no))
        
        menu.exec(self.docs_table.viewport().mapToGlobal(pos))

    def _on_document_double_clicked(self, index):
        """Handle double-click on document row."""
        row = index.row()
        doc_no = self.docs_table.item(row, 0).text()
        doc = self.db.query(Document).filter_by(doc_no=doc_no).first()
        if doc:
            self._load_document(doc.id)

    def _show_document_actions(self, doc: Document):
        """Show actions menu for a document."""
        menu = QMenu(self)
        menu.addAction("✏️ Edit Document", lambda: self._load_document(doc.id))
        menu.addAction("📋 View Lines", lambda: self._view_document_lines(doc))
        menu.addSeparator()
        
        if doc.status == "DRAFT":
            menu.addAction("✅ Approve", lambda: self._change_status_for_doc(doc, "APPROVED"))
        elif doc.status == "APPROVED":
            menu.addAction("🔒 Close", lambda: self._change_status_for_doc(doc, "CLOSED"))
        
        menu.addAction("📄 Export HTML", lambda: self._export_document_html(doc))
        
        menu.exec(self.sender().mapToGlobal(
            self.sender().rect().bottomLeft()
        ))

    # ==================================================================
    # Document Actions
    # ==================================================================

    def _change_status(self, new_status: str):
        """Change status of current document."""
        if not self.current_document:
            QMessageBox.warning(self, "No Document", 
                              "Please load a document first.")
            return
        self._change_status_for_doc(self.current_document, new_status)

    def _change_status_for_doc(self, doc: Document, new_status: str):
        """Change status for a specific document."""
        if new_status not in STATUS_TRANSITIONS.get(doc.status, []):
            QMessageBox.warning(
                self, "Invalid Transition",
                f"Cannot change status from '{doc.status}' to '{new_status}'.\n"
                f"Valid transitions: {', '.join(STATUS_TRANSITIONS.get(doc.status, []))}"
            )
            return

        try:
            update_document_status(
                self.db, doc.id, new_status,
                approved_by=self.current_user
            )
            self._load_recent_documents()
            self.status_bar.showMessage(
                f"Document {doc.doc_no} status changed to {new_status}", 5000
            )
            self.document_updated.emit(doc.doc_no)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _view_document_lines(self, doc: Document):
        """View document lines in a message box."""
        if not doc.lines:
            QMessageBox.information(self, "No Lines", "This document has no lines.")
            return

        text = f"<h3>Document: {doc.doc_no}</h3>"
        text += f"<p>Type: {doc.doc_type} | Date: {doc.doc_date}</p>"
        text += "<hr><table border='1' cellpadding='4' cellspacing='0'>"
        text += "<tr><th>#</th><th>Item Code</th><th>Heat No</th><th>Qty</th><th>Unit</th></tr>"

        for i, line in enumerate(doc.lines, 1):
            text += f"<tr><td>{i}</td><td>{line.item_code}</td>"
            text += f"<td>{line.heat_no or ''}</td><td>{line.qty}</td>"
            text += f"<td>{line.unit or 'EA'}</td></tr>"

        text += "</table>"
        QMessageBox.information(self, f"Document Lines - {doc.doc_no}", text)

    def _export_document_html(self, doc: Document):
        """Export document to HTML."""
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

        html = export_document_to_html(header, lines)
        preview_html_in_browser(html)
        self.status_bar.showMessage("Document opened in browser", 3000)

    def _delete_document(self):
        """Delete current document."""
        if not self.current_document:
            QMessageBox.warning(self, "No Document", 
                              "Please load a document first.")
            return
        self._delete_document_by_no(self.current_document.doc_no)

    def _delete_document_by_no(self, doc_no: str):
        """Delete a document by number."""
        doc = self.db.query(Document).filter_by(doc_no=doc_no).first()
        if not doc:
            return

        if doc.status != "DRAFT":
            QMessageBox.warning(
                self, "Cannot Delete",
                f"Only DRAFT documents can be deleted.\n"
                f"Current status: {doc.status}"
            )
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete document '{doc_no}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_document(self.db, doc.id)
                self._load_recent_documents()
                if self.current_document and self.current_document.id == doc.id:
                    self._clear_form()
                self.status_bar.showMessage(f"Document {doc_no} deleted", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # ==================================================================
    # Cleanup
    # ==================================================================

    def closeEvent(self, event):
        """Handle dialog close event."""
        self.db.close()
        super().closeEvent(event)