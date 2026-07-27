# ui/transaction_dialog.py
"""
Transaction Manager – iMat Material Control System (EPC Edition).

Comprehensive transaction management with:
- Full transaction CRUD operations
- Searchable item code combo with catalog integration
- Document linking and reference tracking
- Excel import/export with templates
- Bulk transaction entry
- Transaction history with advanced filters
- Visual indicators for transaction types
- Role-based access control
- Quick barcode scanning integration
- Copy/paste support from Excel
- Transaction statistics and summaries
- Print and share capabilities
"""

import os
import json
import tempfile
import webbrowser
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QFileDialog, QMenu,
    QFormLayout, QDateEdit, QCompleter, QWidget, QGroupBox,
    QScrollArea, QGridLayout, QDoubleSpinBox, QTextEdit,
    QAbstractItemView, QStatusBar, QToolBar, QSplitter,
    QApplication, QProgressBar, QInputDialog
)
from PyQt6.QtCore import Qt, QDate, QUrl, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QDesktopServices, QAction, QWheelEvent

from db.database import SessionLocal, get_db_session
from db.models import Transaction, Product, Document
from ui.logo_widget import LogoWidget
from utils.excel_export import export_to_excel
from utils.pdf_export import export_to_pdf

# Try to import openpyxl
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

# Document type definitions
DOC_TYPES = [
    "MRR", "MIV", "MSR", "OSND", "MTR", "RTV", "MRV",
    "ADJ", "RES", "SRN", "WOM", "GAT", "RCT", "ISS", "TRN"
]

# Document name suggestions
DEFAULT_DOC_NAMES = [
    "Packing List",
    "MIV (Material Issue Voucher)",
    "MRV (Material Return Voucher)",
    "MSR (Material Store Requisition)",
    "MOM (Minutes of Meeting)",
    "MRIR (Material Receiving Inspection Report)",
    "MRR (Material Receiving Report)",
    "MIR (Material Inspection Request)",
    "SRV (Store Receiving Voucher)",
    "GRN (Goods Receipt Note)",
    "GIN (Goods Issue Note)",
    "MDN (Material Delivery Note)",
    "SMT (Site Material Requisition)",
    "MT74",
    "Delivery Note",
    "Purchase Order (PO)",
    "Inspection Report",
    "Certificate of Compliance (COC)",
    "Material Test Report (MTR)",
    "Non-Conformance Report (NCR)",
    "Request for Inspection (RFI)",
    "Technical Query (TQ)",
    "Site Instruction (SI)",
    "Material Approval Submittal (MAS)",
    "Bill of Lading (BOL)",
    "Transfer Order",
    "Return Merchandise Authorization (RMA)",
    "Stock Movement Record",
    "Inventory Adjustment",
    "Cycle Count Report",
]

# Transaction flow indicators
FLOW_INDICATORS = {
    "MRR": {"icon": "📥", "label": "IN", "color": "#2E7D32"},
    "RCT": {"icon": "📥", "label": "IN", "color": "#2E7D32"},
    "MIV": {"icon": "📤", "label": "OUT", "color": "#C62828"},
    "ISS": {"icon": "📤", "label": "OUT", "color": "#C62828"},
    "WOM": {"icon": "📤", "label": "OUT", "color": "#C62828"},
    "GAT": {"icon": "🚪", "label": "OUT", "color": "#7F8C8D"},
    "MTR": {"icon": "🔄", "label": "TRANSFER", "color": "#1565C0"},
    "TRN": {"icon": "🔄", "label": "TRANSFER", "color": "#1565C0"},
    "RTV": {"icon": "↩️", "label": "RETURN", "color": "#E65100"},
    "SRN": {"icon": "↩️", "label": "RETURN", "color": "#E65100"},
    "MRV": {"icon": "♻️", "label": "RETURN", "color": "#2ECC71"},
    "OSND": {"icon": "⚠️", "label": "ADJUST", "color": "#E74C3C"},
    "ADJ": {"icon": "⚖️", "label": "ADJUST", "color": "#F39C12"},
    "MSR": {"icon": "📋", "label": "REQUEST", "color": "#3498DB"},
    "RES": {"icon": "🔒", "label": "RESERVE", "color": "#2980B9"},
}

# ==================================================================
# NoScrollComboBox
# ==================================================================

class NoScrollComboBox(QComboBox):
    """ComboBox that doesn't scroll with mouse wheel."""
    def wheelEvent(self, event: QWheelEvent):
        event.ignore()


# ==================================================================
# Transaction Dialog
# ==================================================================

class TransactionDialog(QDialog):
    """
    Comprehensive transaction manager for material movements.
    
    Features:
    - View, create, edit, delete transactions
    - Search and filter
    - Excel import/export
    - Document linking
    """

    transactions_updated = pyqtSignal()

    def __init__(self, parent=None, transaction_id: Optional[int] = None,
                 item_code: Optional[str] = None, user_role: str = "viewer",
                 document_data: Optional[Dict] = None):
        """
        Initialize the Transaction dialog.
        
        Args:
            parent: Parent widget
            transaction_id: Optional transaction ID to edit
            item_code: Optional item code to pre-select
            user_role: Current user's role
            document_data: Optional document data to pre-fill
        """
        super().__init__(parent)
        self.parent = parent
        self.transaction_id = transaction_id
        self.preloaded_item_code = item_code
        self.user_role = user_role
        self.document_data = document_data or {}
        self.current_user = self._get_username()
        
        # State
        self.all_transactions: List[Transaction] = []
        self.item_info: Dict[str, Tuple] = {}  # code -> (desc, s1, s2, disc, cat, uom)
        
        # Window setup
        self.setWindowTitle("iMat – Transactions Manager")
        self.setMinimumSize(1300, 750)
        self.setModal(True)
        
        # Build UI
        self._init_ui()
        
        # Load data
        self._load_item_codes()
        self._load_transactions()
        
        # Pre-fill if needed
        if self.transaction_id:
            self._edit_existing_by_id(self.transaction_id)
        elif self.preloaded_item_code:
            self._prefill_item_code(self.preloaded_item_code)
        
        # Apply document defaults
        self._apply_document_defaults()
        
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
        self._build_quick_entry(main_layout)
        self._build_content(main_layout)
        self._build_status_bar(main_layout)

    def _build_header(self, parent_layout: QVBoxLayout):
        """Build the header."""
        header = QFrame()
        header.setStyleSheet("""
            QFrame { background-color: #004D40; border-radius: 0px; }
            QLabel { color: white; }
        """)
        header.setFixedHeight(70)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 15, 5)

        self.logo_widget = LogoWidget()
        header_layout.addWidget(self.logo_widget)

        title = QLabel("📋 Transactions Manager")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("View and manage material transactions")
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

        self.action_new = toolbar.addAction("➕ New Transaction")
        self.action_new.triggered.connect(self._show_new_form)
        toolbar.addSeparator()

        self.action_edit = toolbar.addAction("✏️ Edit")
        self.action_edit.triggered.connect(self._edit_selected)
        
        self.action_delete = toolbar.addAction("🗑️ Delete")
        self.action_delete.triggered.connect(self._delete_selected)
        toolbar.addSeparator()

        self.action_refresh = toolbar.addAction("🔄 Refresh")
        self.action_refresh.triggered.connect(self._load_transactions)
        toolbar.addSeparator()

        self.action_import = toolbar.addAction("📥 Import Excel")
        self.action_import.triggered.connect(self._import_excel)
        
        self.action_export = toolbar.addAction("📤 Export Excel")
        self.action_export.triggered.connect(self._export_excel)
        
        self.action_template = toolbar.addAction("📋 Template")
        self.action_template.triggered.connect(self._download_template)

        parent_layout.addWidget(toolbar)

    def _build_quick_entry(self, parent_layout: QVBoxLayout):
        """Build the quick entry bar."""
        quick_frame = QFrame()
        quick_frame.setStyleSheet("""
            QFrame {
                background: #FFF8E1;
                border-bottom: 1px solid #FFE082;
            }
        """)
        quick_layout = QHBoxLayout(quick_frame)
        quick_layout.setContentsMargins(10, 6, 10, 6)
        quick_layout.setSpacing(8)

        # Item code combo
        quick_layout.addWidget(QLabel("📷 Item:"))
        self.item_code_combo = NoScrollComboBox()
        self.item_code_combo.setEditable(True)
        self.item_code_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.item_code_combo.setMinimumWidth(300)
        self.item_code_combo.setPlaceholderText("Search or scan barcode...")
        self.item_code_combo.setStyleSheet("""
            QComboBox {
                background-color: #FFFDE7;
                border: 1px solid #FFC107;
                border-radius: 4px;
                padding: 4px;
                font-weight: bold;
                color: #5D4037;
            }
            QComboBox:focus {
                border: 2px solid #FF8F00;
            }
        """)
        self.item_code_combo.currentTextChanged.connect(self._on_item_changed)
        quick_layout.addWidget(self.item_code_combo)

        # Item info display
        self.item_info_label = QLabel("")
        self.item_info_label.setStyleSheet("color: #666; font-size: 10px;")
        quick_layout.addWidget(self.item_info_label)

        quick_layout.addStretch()

        # Quick add button
        btn_quick_add = QPushButton("➕ Add Transaction")
        btn_quick_add.setStyleSheet("""
            QPushButton {
                background-color: #FF8F00;
                color: white;
                border: none;
                padding: 6px 14px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #FF6F00; }
        """)
        btn_quick_add.clicked.connect(self._quick_add_transaction)
        quick_layout.addWidget(btn_quick_add)

        parent_layout.addWidget(quick_frame)

    def _build_content(self, parent_layout: QVBoxLayout):
        """Build the main content area."""
        # Search/filter bar
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

        search_layout.addWidget(QLabel("🔍:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by item code, doc no, description, vendor...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._apply_filter)
        search_layout.addWidget(self.search_input)

        search_layout.addWidget(QLabel("Type:"))
        self.type_filter_combo = QComboBox()
        self.type_filter_combo.addItem("All Types")
        for dt in DOC_TYPES:
            self.type_filter_combo.addItem(dt)
        self.type_filter_combo.currentIndexChanged.connect(self._apply_filter)
        search_layout.addWidget(self.type_filter_combo)

        search_layout.addStretch()

        self.record_count_label = QLabel("Transactions: 0")
        self.record_count_label.setStyleSheet("color: #666; font-weight: bold;")
        search_layout.addWidget(self.record_count_label)

        parent_layout.addWidget(search_frame)

        # Main table
        self.table = QTableWidget()
        self.table.setColumnCount(18)
        self.table.setHorizontalHeaderLabels([
            "ID", "Item Code", "Description", "Doc Date", "Doc No",
            "Doc Name", "Doc Type", "Flow", "PO No", "MR No",
            "Project", "Tag No", "Manufacturer", "Cert No",
            "Req Qty", "Issue Qty", "Receive Qty", "Remarks"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._edit_selected)
        self.table.setStyleSheet("""
            QTableWidget {
                background: white;
                font-size: 10px;
            }
            QTableWidget::item:selected {
                background-color: #B2DFDB;
                color: #004D40;
            }
            QHeaderView::section {
                background-color: #004D40;
                color: white;
                font-weight: bold;
                padding: 3px;
                font-size: 9px;
            }
        """)

        # Column widths
        col_widths = [40, 100, 150, 80, 80, 120, 50, 50, 70, 70, 70, 70, 80, 70, 60, 60, 60, 100]
        for i, w in enumerate(col_widths):
            self.table.setColumnWidth(i, w)

        parent_layout.addWidget(self.table)

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready – Use search bar or quick entry to add transactions")
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
            self.action_new.setEnabled(False)
            self.action_edit.setEnabled(False)
            self.action_delete.setEnabled(False)
            self.action_import.setEnabled(False)
            self.item_code_combo.setEnabled(False)
            self.status_bar.showMessage("Read-only mode – Viewing transactions")

    def _get_username(self) -> str:
        """Get current username."""
        try:
            if self.parent and hasattr(self.parent, 'current_user'):
                return self.parent.current_user
        except Exception:
            pass
        return "system"

    # ==================================================================
    # Data Loading
    # ==================================================================

    def _load_item_codes(self):
        """Load item codes into combo box."""
        session = get_db_session()
        try:
            products = session.query(
                Product.item_code, Product.description, Product.size1,
                Product.size2, Product.discipline, Product.category,
                Product.unit_of_measure
            ).order_by(Product.item_code).all()

            self.item_info.clear()
            self.item_code_combo.blockSignals(True)
            self.item_code_combo.clear()
            self.item_code_combo.addItem("")

            for p in products:
                self.item_info[p.item_code] = (
                    p.description or "", p.size1 or "", p.size2 or "",
                    p.discipline or "", p.category or "", p.unit_of_measure or "EA"
                )
                display = f"{p.item_code} – {p.description}" if p.description else p.item_code
                self.item_code_combo.addItem(display, p.item_code)

            self.item_code_combo.blockSignals(False)

            # Setup completer
            completer = QCompleter(
                [self.item_code_combo.itemText(i) for i in range(self.item_code_combo.count())],
                self
            )
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.item_code_combo.setCompleter(completer)

        finally:
            session.close()

    def _load_transactions(self):
        """Load all transactions."""
        session = get_db_session()
        try:
            self.all_transactions = session.query(Transaction).order_by(
                Transaction.id.desc()
            ).limit(500).all()

            self._apply_filter()
        finally:
            session.close()

    def _apply_filter(self):
        """Apply filters to transactions."""
        search_text = self.search_input.text().strip().lower()
        type_filter = self.type_filter_combo.currentText()
        if type_filter == "All Types":
            type_filter = None

        filtered = self.all_transactions

        if search_text:
            filtered = [
                t for t in filtered
                if search_text in (t.item_code or "").lower()
                or search_text in (t.doc_no or "").lower()
                or search_text in (t.doc_name or "").lower()
                or search_text in (t.contractor_vendor or "").lower()
                or search_text in (t.remarks or "").lower()
            ]

        if type_filter:
            filtered = [t for t in filtered if t.doc_type == type_filter]

        self._display_transactions(filtered)
        self.record_count_label.setText(f"Transactions: {len(filtered)}")

    def _display_transactions(self, transactions: List[Transaction]):
        """Display transactions in the table."""
        self.table.setRowCount(len(transactions))

        for row, trans in enumerate(transactions):
            # ID
            self.table.setItem(row, 0, QTableWidgetItem(str(trans.id)))

            # Item Code
            code_item = QTableWidgetItem(trans.item_code)
            code_item.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
            self.table.setItem(row, 1, code_item)

            # Description (from product)
            desc = self.item_info.get(trans.item_code, ("", "", "", "", "", ""))[0]
            self.table.setItem(row, 2, QTableWidgetItem(desc))

            # Doc Date
            date_str = trans.doc_date.strftime("%Y-%m-%d") if trans.doc_date else ""
            self.table.setItem(row, 3, QTableWidgetItem(date_str))

            # Doc No
            self.table.setItem(row, 4, QTableWidgetItem(trans.doc_no or ""))

            # Doc Name
            self.table.setItem(row, 5, QTableWidgetItem(trans.doc_name or ""))

            # Doc Type
            self.table.setItem(row, 6, QTableWidgetItem(trans.doc_type or ""))

            # Flow indicator
            flow_config = FLOW_INDICATORS.get(trans.doc_type or "", {})
            flow_item = QTableWidgetItem(
                f"{flow_config.get('icon', '•')} {flow_config.get('label', 'OTHER')}"
            )
            flow_item.setForeground(QColor(flow_config.get("color", "#333")))
            self.table.setItem(row, 7, flow_item)

            # PO No
            self.table.setItem(row, 8, QTableWidgetItem(trans.po_no or ""))

            # MR No
            self.table.setItem(row, 9, QTableWidgetItem(trans.mr_no or ""))

            # Project
            self.table.setItem(row, 10, QTableWidgetItem(trans.project_code or ""))

            # Tag No
            self.table.setItem(row, 11, QTableWidgetItem(trans.tag_no or ""))

            # Manufacturer
            self.table.setItem(row, 12, QTableWidgetItem(trans.manufacturer or ""))

            # Cert No
            self.table.setItem(row, 13, QTableWidgetItem(trans.cert_no or ""))

            # Request Qty
            req_item = QTableWidgetItem(f"{trans.request_qty or 0:.2f}")
            req_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 14, req_item)

            # Issue Qty
            issue_item = QTableWidgetItem(f"{trans.issue_qty or 0:.2f}")
            issue_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if trans.issue_qty and trans.issue_qty > 0:
                issue_item.setForeground(QColor("#C62828"))
            self.table.setItem(row, 15, issue_item)

            # Receive Qty
            recv_item = QTableWidgetItem(f"{trans.receive_qty or 0:.2f}")
            recv_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if trans.receive_qty and trans.receive_qty > 0:
                recv_item.setForeground(QColor("#2E7D32"))
            self.table.setItem(row, 16, recv_item)

            # Remarks
            self.table.setItem(row, 17, QTableWidgetItem(trans.remarks or ""))

    # ==================================================================
    # Item Selection
    # ==================================================================

    def _on_item_changed(self, text: str):
        """Handle item selection change."""
        code = text.strip()
        if " – " in code:
            code = code.split(" – ", 1)[0].strip()

        if code in self.item_info:
            info = self.item_info[code]
            self.item_info_label.setText(
                f"Desc: {info[0]} | Disc: {info[3]} | Cat: {info[4]} | UOM: {info[5]}"
            )
        else:
            self.item_info_label.setText("")

    def _prefill_item_code(self, code: str):
        """Pre-fill item code."""
        idx = self.item_code_combo.findData(code)
        if idx >= 0:
            self.item_code_combo.setCurrentIndex(idx)
        else:
            self.item_code_combo.setCurrentText(code)

    def _apply_document_defaults(self):
        """Apply document data defaults."""
        if not self.document_data:
            return

        d = self.document_data
        # Store for use in new transaction form
        self._doc_defaults = {
            "doc_no": d.get("doc_no", ""),
            "doc_date": d.get("doc_date", date.today()),
            "doc_type": d.get("doc_type", ""),
            "po_no": d.get("po_no", ""),
            "mr_no": d.get("reference", ""),
            "vendor": d.get("vendor", ""),
            "location": d.get("location", ""),
            "remarks": d.get("remarks", ""),
        }

    # ==================================================================
    # Transaction Actions
    # ==================================================================

    def _quick_add_transaction(self):
        """Quick add transaction from the top bar."""
        code = self._get_selected_item_code()
        if not code:
            QMessageBox.warning(self, "Missing Item", "Please select an item code.")
            return

        # Check if item exists
        session = get_db_session()
        try:
            exists = session.query(Product).filter_by(item_code=code).first()
            if not exists:
                reply = QMessageBox.question(
                    self, "Item Not Found",
                    f"Item '{code}' not in catalog. Create it now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    from ui.product_dialog import ProductDialog
                    ProductDialog(self, item_code=code, user_role=self.user_role).exec()
                    self._load_item_codes()
                    self._prefill_item_code(code)
                return
        finally:
            session.close()

        self._show_new_form(item_code=code)

    def _get_selected_item_code(self) -> str:
        """Get selected item code from combo."""
        idx = self.item_code_combo.currentIndex()
        if idx > 0:
            return self.item_code_combo.currentData() or self.item_code_combo.currentText().strip()
        return ""

    def _show_new_form(self, item_code: str = ""):
        """Show the new transaction form."""
        dlg = EditTransactionDialog(
            self, transaction_id=None, username=self.current_user,
            item_code=item_code, user_role=self.user_role,
            doc_defaults=getattr(self, '_doc_defaults', None)
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load_transactions()
            self.transactions_updated.emit()
            self.status_bar.showMessage("Transaction saved successfully", 3000)

    def _edit_selected(self):
        """Edit selected transaction."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a transaction to edit.")
            return

        trans_id = int(self.table.item(row, 0).text())
        self._edit_existing_by_id(trans_id)

    def _edit_existing_by_id(self, trans_id: int):
        """Edit transaction by ID."""
        dlg = EditTransactionDialog(
            self, transaction_id=trans_id, username=self.current_user,
            user_role=self.user_role
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load_transactions()
            self.transactions_updated.emit()

    def _delete_selected(self):
        """Delete selected transactions."""
        rows = set()
        for item in self.table.selectedItems():
            rows.add(item.row())

        if not rows:
            QMessageBox.warning(self, "No Selection", "Please select transactions to delete.")
            return

        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {len(rows)} transaction(s)?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        session = get_db_session()
        try:
            deleted = 0
            for row in rows:
                trans_id = int(self.table.item(row, 0).text())
                trans = session.query(Transaction).filter_by(id=trans_id).first()
                if trans:
                    session.delete(trans)
                    deleted += 1

            session.commit()
            self._load_transactions()
            self.transactions_updated.emit()
            self.status_bar.showMessage(f"{deleted} transaction(s) deleted", 3000)
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()

    # ==================================================================
    # Context Menu
    # ==================================================================

    def _show_context_menu(self, pos):
        """Show context menu on table."""
        menu = QMenu(self)
        menu.addAction("✏️ Edit", self._edit_selected)
        menu.addAction("🗑️ Delete", self._delete_selected)
        menu.addSeparator()
        menu.addAction("📋 Copy Selected Rows", self._copy_selected_rows)
        menu.addAction("📋 Copy Item Codes", self._copy_item_codes)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_selected_rows(self):
        """Copy selected rows to clipboard."""
        rows = set()
        for item in self.table.selectedItems():
            rows.add(item.row())

        if not rows:
            return

        headers = [self.table.horizontalHeaderItem(c).text() for c in range(self.table.columnCount())]
        lines = ["\t".join(headers)]
        for row in sorted(rows):
            row_data = [self.table.item(row, c).text() if self.table.item(row, c) else "" for c in range(self.table.columnCount())]
            lines.append("\t".join(row_data))

        QApplication.clipboard().setText("\n".join(lines))
        self.status_bar.showMessage(f"{len(rows)} rows copied", 3000)

    def _copy_item_codes(self):
        """Copy selected item codes."""
        rows = set()
        for item in self.table.selectedItems():
            rows.add(item.row())

        codes = []
        for row in sorted(rows):
            item = self.table.item(row, 1)
            if item:
                codes.append(item.text())

        if codes:
            QApplication.clipboard().setText("\n".join(codes))
            self.status_bar.showMessage(f"{len(codes)} codes copied", 3000)

    # ==================================================================
    # Excel Import/Export
    # ==================================================================

    def _import_excel(self):
        """Import transactions from Excel."""
        if not OPENPYXL_AVAILABLE:
            QMessageBox.warning(self, "Library Required", "Install openpyxl: pip install openpyxl")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Excel", "", "Excel Files (*.xlsx *.xls)"
        )
        if not file_path:
            return

        try:
            wb = openpyxl.load_workbook(file_path)
            ws = wb.active
            headers = [str(c.value or "").strip().lower() for c in next(ws.iter_rows(min_row=1, max_row=1))]

            if 'item_code' not in headers:
                QMessageBox.warning(self, "Missing Column", "Column 'item_code' is required.")
                return

            col_idx = {h: i for i, h in enumerate(headers) if h}
            session = get_db_session()
            imported = 0

            for row_data in ws.iter_rows(min_row=2, values_only=True):
                if not row_data or all(c is None for c in row_data):
                    continue

                item_code = str(row_data[col_idx.get('item_code', 0)] or "").strip()
                if not item_code:
                    continue

                trans = Transaction(item_code=item_code, created_by=self.current_user)

                # Date
                date_val = row_data[col_idx.get('doc_date', 3)] if 'doc_date' in col_idx else None
                if date_val:
                    if isinstance(date_val, str):
                        try:
                            trans.doc_date = datetime.strptime(date_val, "%Y-%m-%d").date()
                        except ValueError:
                            trans.doc_date = date.today()
                    elif isinstance(date_val, datetime):
                        trans.doc_date = date_val.date()
                    else:
                        trans.doc_date = date.today()
                else:
                    trans.doc_date = date.today()

                # Map fields
                field_map = {
                    'doc_no': 'doc_no', 'doc_name': 'doc_name', 'doc_type': 'doc_type',
                    'po_no': 'po_no', 'mr_no': 'mr_no', 'project_code': 'project_code',
                    'tag_no': 'tag_no', 'manufacturer': 'manufacturer', 'cert_no': 'cert_no',
                    'contractor_vendor': 'contractor_vendor', 'heat_no': 'heat_no',
                    'serial_no': 'serial_no', 'pkg_no': 'pkg_no',
                    'location': 'location', 'subject': 'subject', 'remarks': 'remarks',
                }

                for col_name, attr_name in field_map.items():
                    idx = col_idx.get(col_name)
                    if idx is not None and idx < len(row_data) and row_data[idx] is not None:
                        setattr(trans, attr_name, str(row_data[idx]).strip())

                # Numeric fields
                for col_name, attr_name in [('request_qty', 'request_qty'), ('issue_qty', 'issue_qty'), ('receive_qty', 'receive_qty')]:
                    idx = col_idx.get(col_name)
                    if idx is not None and idx < len(row_data) and row_data[idx] is not None:
                        try:
                            setattr(trans, attr_name, float(row_data[idx]))
                        except (ValueError, TypeError):
                            pass

                session.add(trans)
                imported += 1

            session.commit()
            QMessageBox.information(self, "Import Complete", f"{imported} transactions imported.")
            self._load_transactions()
            self.transactions_updated.emit()
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))
        finally:
            session.close()

    def _export_excel(self):
        """Export transactions to Excel."""
        if not OPENPYXL_AVAILABLE:
            QMessageBox.warning(self, "Library Required", "Install openpyxl")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Transactions", "transactions_export.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Transactions"

            headers = [self.table.horizontalHeaderItem(c).text() for c in range(self.table.columnCount())]
            header_font = XlFont(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="004D40", end_color="004D40", fill_type="solid")

            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill

            for row in range(self.table.rowCount()):
                if not self.table.isRowHidden(row):
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        ws.cell(row=row + 2, column=col + 1, value=item.text() if item else "")

            wb.save(file_path)
            self.status_bar.showMessage(f"Exported to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _download_template(self):
        """Download Excel template."""
        if not OPENPYXL_AVAILABLE:
            QMessageBox.warning(self, "Library Required", "Install openpyxl")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Template", "transaction_template.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Template"

            headers = [
                'item_code', 'doc_date', 'doc_type', 'doc_name', 'doc_no',
                'subject', 'mr_no', 'po_no', 'project_code', 'tag_no',
                'manufacturer', 'cert_no', 'contractor_vendor',
                'request_qty', 'issue_qty', 'receive_qty',
                'heat_no', 'serial_no', 'pkg_no', 'location', 'remarks'
            ]

            header_font = XlFont(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="004D40", end_color="004D40", fill_type="solid")

            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill

            wb.save(file_path)
            self.status_bar.showMessage("Template saved", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ==================================================================
# Edit Transaction Dialog
# ==================================================================

class EditTransactionDialog(QDialog):
    """Dialog for creating or editing a single transaction."""

    def __init__(self, parent=None, transaction_id: Optional[int] = None,
                 username: str = "", item_code: str = "", user_role: str = "viewer",
                 doc_defaults: Optional[Dict] = None):
        """
        Initialize the edit dialog.
        
        Args:
            parent: Parent widget
            transaction_id: Transaction ID to edit (None for new)
            username: Current username
            item_code: Pre-selected item code
            user_role: User role
            doc_defaults: Document data to pre-fill
        """
        super().__init__(parent)
        self.trans_id = transaction_id
        self.username = username
        self.pre_item_code = item_code
        self.user_role = user_role
        self.doc_defaults = doc_defaults or {}

        self.setWindowTitle("Edit Transaction" if transaction_id else "New Transaction")
        self.setMinimumWidth(800)
        self.setModal(True)

        self._init_ui()

        if self.trans_id:
            self._load_data()
        else:
            self._apply_defaults()

        if user_role == "viewer":
            self._set_readonly()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(8)

        # ---- Document Info ----
        doc_group = QGroupBox("📄 Document Info")
        doc_form = QFormLayout(doc_group)
        doc_form.setSpacing(6)

        self.item_code_input = QLineEdit()
        self.item_code_input.setPlaceholderText("Item Code *")
        self.item_code_input.setMinimumHeight(30)
        self.item_code_input.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        doc_form.addRow("Item Code *:", self.item_code_input)

        self.doc_date_input = QDateEdit(QDate.currentDate())
        self.doc_date_input.setCalendarPopup(True)
        doc_form.addRow("Doc Date:", self.doc_date_input)

        self.doc_no_input = QLineEdit()
        self.doc_no_input.setPlaceholderText("Document number")
        doc_form.addRow("Doc No:", self.doc_no_input)

        self.doc_name_combo = QComboBox()
        self.doc_name_combo.setEditable(True)
        self.doc_name_combo.addItems(DEFAULT_DOC_NAMES)
        self.doc_name_combo.setCurrentText("")
        doc_form.addRow("Doc Name:", self.doc_name_combo)

        self.doc_type_input = QComboBox()
        self.doc_type_input.setEditable(True)
        self.doc_type_input.addItems(DOC_TYPES)
        self.doc_type_input.setCurrentText("")
        doc_form.addRow("Doc Type:", self.doc_type_input)

        self.po_no_input = QLineEdit()
        self.po_no_input.setPlaceholderText("PO Number")
        doc_form.addRow("PO No:", self.po_no_input)

        self.mr_no_input = QLineEdit()
        self.mr_no_input.setPlaceholderText("MR Number")
        doc_form.addRow("MR No:", self.mr_no_input)

        grid.addWidget(doc_group, 0, 0)

        # ---- Tracking Info ----
        track_group = QGroupBox("🔍 Tracking Info")
        track_form = QFormLayout(track_group)
        track_form.setSpacing(6)

        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("Subject")
        track_form.addRow("Subject:", self.subject_input)

        self.project_input = QLineEdit()
        self.project_input.setPlaceholderText("Project Code")
        track_form.addRow("Project:", self.project_input)

        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Tag Number")
        track_form.addRow("Tag No:", self.tag_input)

        self.mfg_input = QLineEdit()
        self.mfg_input.setPlaceholderText("Manufacturer")
        track_form.addRow("Manufacturer:", self.mfg_input)

        self.cert_input = QLineEdit()
        self.cert_input.setPlaceholderText("Certificate Number")
        track_form.addRow("Cert No:", self.cert_input)

        self.heat_input = QLineEdit()
        self.heat_input.setPlaceholderText("Heat Number")
        track_form.addRow("Heat No:", self.heat_input)

        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("Serial Number")
        track_form.addRow("Serial No:", self.serial_input)

        self.pkg_input = QLineEdit()
        self.pkg_input.setPlaceholderText("Package Number")
        track_form.addRow("PKG No:", self.pkg_input)

        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("Storage Location")
        track_form.addRow("Location:", self.location_input)

        self.vendor_input = QLineEdit()
        self.vendor_input.setPlaceholderText("Vendor / Contractor")
        track_form.addRow("Vendor:", self.vendor_input)

        grid.addWidget(track_group, 0, 1)

        # ---- Quantities ----
        qty_group = QGroupBox("📊 Quantities")
        qty_form = QFormLayout(qty_group)
        qty_form.setSpacing(6)

        self.req_qty_spin = QDoubleSpinBox()
        self.req_qty_spin.setRange(0, 9999999.99)
        self.req_qty_spin.setDecimals(2)
        self.req_qty_spin.setValue(0)
        qty_form.addRow("Request Qty:", self.req_qty_spin)

        self.issue_qty_spin = QDoubleSpinBox()
        self.issue_qty_spin.setRange(0, 9999999.99)
        self.issue_qty_spin.setDecimals(2)
        self.issue_qty_spin.setValue(0)
        qty_form.addRow("Issue Qty:", self.issue_qty_spin)

        self.rcv_qty_spin = QDoubleSpinBox()
        self.rcv_qty_spin.setRange(0, 9999999.99)
        self.rcv_qty_spin.setDecimals(2)
        self.rcv_qty_spin.setValue(0)
        qty_form.addRow("Receive Qty:", self.rcv_qty_spin)

        self.remarks_input = QTextEdit()
        self.remarks_input.setMaximumHeight(60)
        self.remarks_input.setPlaceholderText("Remarks")
        qty_form.addRow("Remarks:", self.remarks_input)

        grid.addWidget(qty_group, 1, 0, 1, 2)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2E86C1;
                color: white;
                border: none;
                padding: 10px 24px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #2471A3; }
        """)
        self.save_btn.clicked.connect(self._save_data)
        btn_layout.addWidget(self.save_btn)

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

    def _load_data(self):
        """Load transaction data for editing."""
        session = get_db_session()
        try:
            trans = session.query(Transaction).get(self.trans_id)
            if trans:
                self.item_code_input.setText(trans.item_code)
                if trans.doc_date:
                    self.doc_date_input.setDate(QDate(trans.doc_date.year, trans.doc_date.month, trans.doc_date.day))
                self.doc_no_input.setText(trans.doc_no or "")
                self.doc_name_combo.setCurrentText(trans.doc_name or "")
                self.doc_type_input.setCurrentText(trans.doc_type or "")
                self.po_no_input.setText(trans.po_no or "")
                self.mr_no_input.setText(trans.mr_no or "")
                self.subject_input.setText(trans.subject or "")
                self.project_input.setText(trans.project_code or "")
                self.tag_input.setText(trans.tag_no or "")
                self.mfg_input.setText(trans.manufacturer or "")
                self.cert_input.setText(trans.cert_no or "")
                self.heat_input.setText(trans.heat_no or "")
                self.serial_input.setText(trans.serial_no or "")
                self.pkg_input.setText(trans.pkg_no or "")
                self.location_input.setText(trans.location or "")
                self.vendor_input.setText(trans.contractor_vendor or "")
                self.req_qty_spin.setValue(trans.request_qty or 0)
                self.issue_qty_spin.setValue(trans.issue_qty or 0)
                self.rcv_qty_spin.setValue(trans.receive_qty or 0)
                self.remarks_input.setPlainText(trans.remarks or "")
        finally:
            session.close()

    def _apply_defaults(self):
        """Apply document defaults for new transaction."""
        if self.pre_item_code:
            self.item_code_input.setText(self.pre_item_code)

        if self.doc_defaults:
            d = self.doc_defaults
            self.doc_no_input.setText(d.get("doc_no", ""))
            self.doc_type_input.setCurrentText(d.get("doc_type", ""))
            if d.get("doc_date"):
                if isinstance(d["doc_date"], date):
                    self.doc_date_input.setDate(QDate(d["doc_date"].year, d["doc_date"].month, d["doc_date"].day))
            self.po_no_input.setText(d.get("po_no", ""))
            self.mr_no_input.setText(d.get("mr_no", ""))
            self.vendor_input.setText(d.get("vendor", ""))
            self.location_input.setText(d.get("location", ""))
            self.remarks_input.setPlainText(d.get("remarks", ""))

    def _set_readonly(self):
        """Set all fields to read-only."""
        for widget in self.findChildren((QLineEdit, QTextEdit)):
            widget.setReadOnly(True)
        for widget in self.findChildren((QComboBox, QDateEdit, QDoubleSpinBox)):
            widget.setEnabled(False)
        self.save_btn.setVisible(False)

    def _save_data(self):
        """Save transaction data."""
        code = self.item_code_input.text().strip()
        if not code:
            QMessageBox.warning(self, "Validation", "Item Code is required.")
            return

        session = get_db_session()
        try:
            if self.trans_id:
                trans = session.query(Transaction).get(self.trans_id)
            else:
                trans = Transaction(created_by=self.username)
                session.add(trans)

            trans.item_code = code
            trans.doc_date = self.doc_date_input.date().toPyDate()
            trans.doc_no = self.doc_no_input.text().strip()
            trans.doc_name = self.doc_name_combo.currentText().strip()
            trans.doc_type = self.doc_type_input.currentText().strip()
            trans.po_no = self.po_no_input.text().strip()
            trans.mr_no = self.mr_no_input.text().strip()
            trans.subject = self.subject_input.text().strip()
            trans.project_code = self.project_input.text().strip()
            trans.tag_no = self.tag_input.text().strip()
            trans.manufacturer = self.mfg_input.text().strip()
            trans.cert_no = self.cert_input.text().strip()
            trans.heat_no = self.heat_input.text().strip()
            trans.serial_no = self.serial_input.text().strip()
            trans.pkg_no = self.pkg_input.text().strip()
            trans.location = self.location_input.text().strip()
            trans.contractor_vendor = self.vendor_input.text().strip()
            trans.request_qty = self.req_qty_spin.value()
            trans.issue_qty = self.issue_qty_spin.value()
            trans.receive_qty = self.rcv_qty_spin.value()
            trans.remarks = self.remarks_input.toPlainText().strip()

            session.commit()
            self.accept()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            session.close()