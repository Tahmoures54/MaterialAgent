# ui/material_request_history_dialog.py
"""
Material Request History Dialog – iMat Material Control System (EPC Edition).

Comprehensive history viewer with:
- Full request listing with advanced filters
- Line item details in split view
- Status-based color coding
- Export to Excel, PDF, HTML
- Print and preview
- Edit existing requests
- Delete requests (with restrictions)
- WhatsApp sharing
- Email sharing
- Advanced search and filter
- Date range filtering
- Status workflow management
- Approval/rejection tracking
- Copy to clipboard
"""

import os
import tempfile
import webbrowser
from datetime import datetime, date
from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMessageBox, QLineEdit, QLabel,
    QFrame, QToolBar, QStatusBar, QWidget, QApplication, QFileDialog,
    QSplitter, QComboBox, QDateEdit, QCheckBox, QMenu,
    QAbstractItemView, QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt, QDate, QUrl, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QDesktopServices, QAction

from sqlalchemy import func, or_
from db.database import SessionLocal, get_db_session
from db.models import (
    MaterialRequest, MaterialRequestLine, Product, Location
)
from ui.logo_widget import LogoWidget
from utils.excel_export import export_to_excel
from utils.pdf_export import export_to_pdf

# ==================================================================
# Constants
# ==================================================================

# Status definitions
STATUS_CONFIG = {
    "PENDING": {
        "label": "Pending",
        "icon": "⏳",
        "bg": QColor("#FFE0B2"),
        "fg": QColor("#E65100"),
        "description": "Awaiting review and approval"
    },
    "APPROVED": {
        "label": "Approved",
        "icon": "✅",
        "bg": QColor("#C8E6C9"),
        "fg": QColor("#1B5E20"),
        "description": "Approved for processing"
    },
    "REJECTED": {
        "label": "Rejected",
        "icon": "❌",
        "bg": QColor("#FFCDD2"),
        "fg": QColor("#B71C1C"),
        "description": "Request has been rejected"
    },
    "CONVERTED": {
        "label": "Converted",
        "icon": "🔄",
        "bg": QColor("#BBDEFB"),
        "fg": QColor("#0D47A1"),
        "description": "Converted to purchase order"
    },
    "CANCELLED": {
        "label": "Cancelled",
        "icon": "🚫",
        "bg": QColor("#E0E0E0"),
        "fg": QColor("#616161"),
        "description": "Request has been cancelled"
    },
}

# Request type icons
REQUEST_TYPE_ICONS = {
    "Normal": "📋",
    "Urgent": "🔴",
    "Replacement": "🔄",
    "Additional": "➕",
    "Contingency": "⚠️",
}

# ==================================================================
# Material Request History Dialog
# ==================================================================

class MaterialRequestHistoryDialog(QDialog):
    """
    Material Request history viewer with full management capabilities.
    
    Features:
    - View all material requests with filters
    - Split view for lines
    - Status management
    - Export and share
    """

    request_updated = pyqtSignal(str)  # request number

    def __init__(self, parent=None, user_role: str = "viewer"):
        """
        Initialize the Material Request History dialog.
        
        Args:
            parent: Parent widget
            user_role: Current user's role
        """
        super().__init__(parent)
        self.user_role = user_role
        self.parent = parent
        self.db = SessionLocal()
        
        # State
        self.all_requests: List[MaterialRequest] = []
        self.filtered_requests: List[MaterialRequest] = []
        
        # Window setup
        self.setWindowTitle("iMat – Material Request History")
        self.setMinimumSize(1300, 750)
        
        # Build UI
        self._init_ui()
        
        # Load data
        self._load_requests()
        
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

        title = QLabel("📋 Material Request History")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("View, manage and export material requests")
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
        self.action_refresh.triggered.connect(self._load_requests)
        toolbar.addSeparator()

        self.action_edit = toolbar.addAction("✏️ Edit")
        self.action_edit.setToolTip("Edit selected request")
        self.action_edit.triggered.connect(self._edit_request)

        self.action_approve = toolbar.addAction("✅ Approve")
        self.action_approve.setToolTip("Approve selected request")
        self.action_approve.triggered.connect(lambda: self._change_status("APPROVED"))

        self.action_reject = toolbar.addAction("❌ Reject")
        self.action_reject.setToolTip("Reject selected request")
        self.action_reject.triggered.connect(lambda: self._change_status("REJECTED"))

        self.action_cancel = toolbar.addAction("🚫 Cancel")
        self.action_cancel.setToolTip("Cancel selected request")
        self.action_cancel.triggered.connect(lambda: self._change_status("CANCELLED"))

        self.action_delete = toolbar.addAction("🗑️ Delete")
        self.action_delete.setToolTip("Delete selected request")
        self.action_delete.triggered.connect(self._delete_request)
        toolbar.addSeparator()

        self.action_export_excel = toolbar.addAction("📥 Excel")
        self.action_export_excel.setToolTip("Export to Excel")
        self.action_export_excel.triggered.connect(self._export_excel)

        self.action_export_pdf = toolbar.addAction("📑 PDF")
        self.action_export_pdf.setToolTip("Export to PDF")
        self.action_export_pdf.triggered.connect(self._export_pdf)

        self.action_print = toolbar.addAction("🖨️ Print")
        self.action_print.setToolTip("Print report")
        self.action_print.triggered.connect(self._print_report)

        self.action_whatsapp = toolbar.addAction("💬 WhatsApp")
        self.action_whatsapp.setToolTip("Share via WhatsApp")
        self.action_whatsapp.triggered.connect(self._share_whatsapp)

        self.action_email = toolbar.addAction("📧 Email")
        self.action_email.setToolTip("Share via Email")
        self.action_email.triggered.connect(self._share_email)

        self.action_copy = toolbar.addAction("📋 Copy")
        self.action_copy.setToolTip("Copy to clipboard")
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

        # Search
        filter_layout.addWidget(QLabel("🔍:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by MR No, Project, Discipline...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(200)
        self.search_input.textChanged.connect(self._filter_requests)
        filter_layout.addWidget(self.search_input)

        # Status filter
        filter_layout.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItem("All Statuses")
        for status_key, status_config in STATUS_CONFIG.items():
            self.status_combo.addItem(
                f"{status_config['icon']} {status_config['label']}", 
                status_key
            )
        self.status_combo.currentIndexChanged.connect(self._filter_requests)
        filter_layout.addWidget(self.status_combo)

        # Date range
        filter_layout.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.dateChanged.connect(self._filter_requests)
        filter_layout.addWidget(self.date_from)

        filter_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.dateChanged.connect(self._filter_requests)
        filter_layout.addWidget(self.date_to)

        # Show all checkbox
        self.show_all_check = QCheckBox("Show All")
        self.show_all_check.setChecked(False)
        self.show_all_check.toggled.connect(self._filter_requests)
        filter_layout.addWidget(self.show_all_check)

        filter_layout.addStretch()

        # Request count
        self.count_label = QLabel("Requests: 0")
        self.count_label.setStyleSheet("color: #666; font-weight: bold;")
        filter_layout.addWidget(self.count_label)

        parent_layout.addWidget(filter_frame)

    def _build_content(self, parent_layout: QVBoxLayout):
        """Build the main content area with splitter."""
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Top: Requests table
        top_widget = self._build_requests_table()
        splitter.addWidget(top_widget)

        # Bottom: Lines table
        bottom_widget = self._build_lines_table()
        splitter.addWidget(bottom_widget)

        # Set initial sizes (60% top, 40% bottom)
        splitter.setSizes([400, 250])

        parent_layout.addWidget(splitter)

    def _build_requests_table(self) -> QWidget:
        """Build the requests table."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)

        self.requests_table = QTableWidget()
        self.requests_table.setColumnCount(13)
        self.requests_table.setHorizontalHeaderLabels([
            "MR Number", "Company", "Project", "WBS", "Type",
            "Discipline", "ISO Drawing", "Location",
            "Required Date", "Status", "Items", "Total Cost", "Remarks"
        ])
        self.requests_table.horizontalHeader().setStretchLastSection(True)
        self.requests_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.requests_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.requests_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.requests_table.setAlternatingRowColors(True)
        self.requests_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.requests_table.customContextMenuRequested.connect(self._show_context_menu)
        self.requests_table.doubleClicked.connect(self._edit_request)
        self.requests_table.currentItemChanged.connect(self._on_request_selected)
        self.requests_table.setStyleSheet("""
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
        req_col_widths = [130, 100, 120, 80, 70, 80, 100, 100, 90, 70, 50, 100, 120]
        for i, w in enumerate(req_col_widths):
            self.requests_table.setColumnWidth(i, w)

        layout.addWidget(self.requests_table)
        return widget

    def _build_lines_table(self) -> QWidget:
        """Build the lines table."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)

        # Label
        lbl = QLabel("📋 Request Line Items")
        lbl.setStyleSheet("font-weight: bold; color: #004D40; padding: 4px 8px;")
        layout.addWidget(lbl)

        self.lines_table = QTableWidget()
        self.lines_table.setColumnCount(10)
        self.lines_table.setHorizontalHeaderLabels([
            "#", "Item Code", "Description", "Subject",
            "Qty", "Unit Price", "Currency", "Total Cost",
            "Fulfilled", "Remarks"
        ])
        self.lines_table.horizontalHeader().setStretchLastSection(True)
        self.lines_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lines_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lines_table.setAlternatingRowColors(True)
        self.lines_table.setStyleSheet("""
            QTableWidget {
                background: #FAFAFA;
                font-size: 10px;
            }
            QHeaderView::section {
                background-color: #00695C;
                color: white;
                font-weight: bold;
                padding: 3px;
                font-size: 10px;
            }
        """)

        # Column widths
        line_col_widths = [30, 100, 180, 120, 70, 80, 60, 90, 70, 100]
        for i, w in enumerate(line_col_widths):
            self.lines_table.setColumnWidth(i, w)

        layout.addWidget(self.lines_table)
        return widget

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready – Select a request to view details")
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
            self.action_edit.setEnabled(False)
            self.action_approve.setEnabled(False)
            self.action_reject.setEnabled(False)
            self.action_cancel.setEnabled(False)
            self.action_delete.setEnabled(False)
            self.status_bar.showMessage("Read-only mode – You cannot modify requests")

    # ==================================================================
    # Data Loading & Filtering
    # ==================================================================

    def _load_requests(self):
        """Load all material requests."""
        try:
            self.all_requests = self.db.query(MaterialRequest).order_by(
                MaterialRequest.created_at.desc()
            ).all()
            self._filter_requests()
            self.status_bar.showMessage(f"Loaded {len(self.all_requests)} requests", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load requests:\n{str(e)}")

    def _filter_requests(self):
        """Apply filters to the requests."""
        search_text = self.search_input.text().strip().lower()
        status_filter = self.status_combo.currentData()
        show_all = self.show_all_check.isChecked()
        date_from = self.date_from.date().toPyDate()
        date_to = self.date_to.date().toPyDate()

        self.filtered_requests = []
        for req in self.all_requests:
            # Search filter
            if search_text:
                searchable = f"{req.request_no} {req.company} {req.project} {req.discipline} {req.remarks}"
                if search_text not in searchable.lower():
                    continue

            # Status filter
            if status_filter and req.status != status_filter:
                continue

            # Date filter
            if not show_all and req.required_date:
                if req.required_date < date_from or req.required_date > date_to:
                    continue

            self.filtered_requests.append(req)

        self._display_requests()
        self.count_label.setText(f"Requests: {len(self.filtered_requests)}")

    def _display_requests(self):
        """Display filtered requests in the table."""
        self.requests_table.setRowCount(len(self.filtered_requests))

        for row, req in enumerate(self.filtered_requests):
            # MR Number
            mr_item = QTableWidgetItem(req.request_no)
            mr_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            self.requests_table.setItem(row, 0, mr_item)

            # Company
            self.requests_table.setItem(row, 1, QTableWidgetItem(req.company or ""))

            # Project
            self.requests_table.setItem(row, 2, QTableWidgetItem(req.project or ""))

            # WBS
            self.requests_table.setItem(row, 3, QTableWidgetItem(req.wbs_code or ""))

            # Request Type with icon
            type_icon = REQUEST_TYPE_ICONS.get(req.request_type or "Normal", "📋")
            self.requests_table.setItem(row, 4, QTableWidgetItem(
                f"{type_icon} {req.request_type or 'Normal'}"
            ))

            # Discipline
            self.requests_table.setItem(row, 5, QTableWidgetItem(req.discipline or ""))

            # ISO Drawing
            self.requests_table.setItem(row, 6, QTableWidgetItem(req.iso_drawing_no or ""))

            # Location
            loc_name = req.target_location.code if req.target_location else ""
            self.requests_table.setItem(row, 7, QTableWidgetItem(loc_name))

            # Required Date
            date_str = str(req.required_date) if req.required_date else ""
            self.requests_table.setItem(row, 8, QTableWidgetItem(date_str))

            # Status with color
            status_config = STATUS_CONFIG.get(req.status, STATUS_CONFIG["PENDING"])
            status_item = QTableWidgetItem(
                f"{status_config['icon']} {status_config['label']}"
            )
            status_item.setBackground(status_config["bg"])
            status_item.setForeground(status_config["fg"])
            status_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.requests_table.setItem(row, 9, status_item)

            # Item count
            count_item = QTableWidgetItem(str(len(req.lines)))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.requests_table.setItem(row, 10, count_item)

            # Total cost
            total_cost = self._compute_total_cost(req)
            self.requests_table.setItem(row, 11, QTableWidgetItem(total_cost))

            # Remarks
            self.requests_table.setItem(row, 12, QTableWidgetItem(req.remarks or ""))

        self.lines_table.setRowCount(0)

    def _on_request_selected(self, current, previous):
        """Handle request selection - show lines."""
        self.lines_table.setRowCount(0)
        
        if not current:
            return

        row = current.row()
        if row < 0 or row >= len(self.filtered_requests):
            return

        req = self.filtered_requests[row]
        self._display_lines(req)

    def _display_lines(self, req: MaterialRequest):
        """Display line items for a request."""
        self.lines_table.setRowCount(len(req.lines))

        for i, line in enumerate(req.lines):
            # Line number
            num_item = QTableWidgetItem(str(i + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lines_table.setItem(i, 0, num_item)

            # Item Code
            self.lines_table.setItem(i, 1, QTableWidgetItem(line.item_code))

            # Description
            self.lines_table.setItem(i, 2, QTableWidgetItem(line.description or ""))

            # Subject
            self.lines_table.setItem(i, 3, QTableWidgetItem(line.subject or ""))

            # Quantity
            qty_item = QTableWidgetItem(f"{line.qty:.2f}")
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.lines_table.setItem(i, 4, qty_item)

            # Unit Price
            price_item = QTableWidgetItem(f"{line.unit_price or 0:.2f}")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.lines_table.setItem(i, 5, price_item)

            # Currency
            self.lines_table.setItem(i, 6, QTableWidgetItem(line.currency or "USD"))

            # Total Cost
            cost_item = QTableWidgetItem(f"{line.total_cost or 0:,.2f}")
            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.lines_table.setItem(i, 7, cost_item)

            # Fulfilled
            fulfilled = line.fulfilled_qty or 0
            fulfilled_str = f"{fulfilled:.2f}"
            if fulfilled >= line.qty:
                fulfilled_str = f"✅ {fulfilled_str}"
            self.lines_table.setItem(i, 8, QTableWidgetItem(fulfilled_str))

            # Remarks
            self.lines_table.setItem(i, 9, QTableWidgetItem(line.remarks or ""))

    def _compute_total_cost(self, req: MaterialRequest) -> str:
        """Compute total cost string for a request."""
        totals = {}
        for line in req.lines:
            curr = line.currency or "USD"
            totals[curr] = totals.get(curr, 0) + (line.total_cost or 0)

        if not totals:
            return "0.00"

        parts = []
        for curr, val in totals.items():
            parts.append(f"{val:,.2f} {curr}")
        
        return " + ".join(parts) if len(parts) > 1 else parts[0]

    # ==================================================================
    # Context Menu
    # ==================================================================

    def _show_context_menu(self, pos):
        """Show context menu on requests table."""
        row = self.requests_table.currentRow()
        if row < 0:
            return

        req = self.filtered_requests[row]
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: white;
                border: 1px solid #CCC;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
            }
            QMenu::item:selected {
                background: #E0F2F1;
                color: #004D40;
            }
        """)

        menu.addAction("✏️ Edit Request", self._edit_request)
        menu.addSeparator()

        if req.status == "PENDING":
            menu.addAction("✅ Approve", lambda: self._change_status_for_req(req, "APPROVED"))
            menu.addAction("❌ Reject", lambda: self._change_status_for_req(req, "REJECTED"))
            menu.addAction("🚫 Cancel", lambda: self._change_status_for_req(req, "CANCELLED"))
        
        menu.addSeparator()
        menu.addAction("📄 View Details", lambda: self._view_request_details(req))
        menu.addAction("📋 Copy MR Number", 
                      lambda: QApplication.clipboard().setText(req.request_no))
        menu.addSeparator()
        menu.addAction("💬 Share via WhatsApp", lambda: self._share_request_whatsapp(req))
        menu.addAction("📧 Share via Email", lambda: self._share_request_email(req))

        if req.status in ["PENDING", "REJECTED"]:
            menu.addSeparator()
            menu.addAction("🗑️ Delete", lambda: self._delete_specific_request(req))

        menu.exec(self.requests_table.viewport().mapToGlobal(pos))

    # ==================================================================
    # Request Actions
    # ==================================================================

    def _edit_request(self):
        """Edit selected request."""
        row = self.requests_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a request to edit.")
            return

        req = self.filtered_requests[row]
        
        from ui.material_request_dialog import MaterialRequestDialog
        dlg = MaterialRequestDialog(self, request_id=req.id, user_role=self.user_role)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load_requests()
            self.request_updated.emit(req.request_no)

    def _change_status(self, new_status: str):
        """Change status of selected request."""
        row = self.requests_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a request.")
            return

        req = self.filtered_requests[row]
        self._change_status_for_req(req, new_status)

    def _change_status_for_req(self, req: MaterialRequest, new_status: str):
        """Change status for a specific request."""
        valid_transitions = {
            "PENDING": ["APPROVED", "REJECTED", "CANCELLED"],
            "APPROVED": ["CONVERTED", "CANCELLED"],
            "REJECTED": ["PENDING"],
            "CANCELLED": [],
        }

        if new_status not in valid_transitions.get(req.status, []):
            QMessageBox.warning(
                self, "Invalid Transition",
                f"Cannot change status from '{req.status}' to '{new_status}'."
            )
            return

        confirm = QMessageBox.question(
            self, "Confirm Status Change",
            f"Change status of '{req.request_no}' from "
            f"'{req.status}' to '{new_status}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            req.status = new_status
            req.updated_at = datetime.utcnow()
            
            if new_status == "APPROVED":
                req.approved_by = self._get_username()
                req.approved_at = datetime.utcnow()
            
            self.db.commit()
            self._load_requests()
            self.request_updated.emit(req.request_no)
            self.status_bar.showMessage(
                f"Request {req.request_no} status changed to {new_status}", 5000
            )
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", str(e))

    def _delete_request(self):
        """Delete selected request."""
        row = self.requests_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a request.")
            return

        req = self.filtered_requests[row]
        self._delete_specific_request(req)

    def _delete_specific_request(self, req: MaterialRequest):
        """Delete a specific request."""
        if req.status in ["APPROVED", "CONVERTED"]:
            QMessageBox.warning(
                self, "Cannot Delete",
                f"Cannot delete request with status '{req.status}'."
            )
            return

        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete request '{req.request_no}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.db.delete(req)
                self.db.commit()
                self._load_requests()
                self.lines_table.setRowCount(0)
                self.status_bar.showMessage(f"Request {req.request_no} deleted", 3000)
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Error", str(e))

    def _view_request_details(self, req: MaterialRequest):
        """View detailed information about a request."""
        status_config = STATUS_CONFIG.get(req.status, STATUS_CONFIG["PENDING"])
        
        details = f"""
        <h3>Material Request Details</h3>
        <table style="width: 100%; line-height: 1.8;">
            <tr><td><b>MR Number:</b></td><td>{req.request_no}</td></tr>
            <tr><td><b>Company:</b></td><td>{req.company or 'N/A'}</td></tr>
            <tr><td><b>Project:</b></td><td>{req.project or 'N/A'}</td></tr>
            <tr><td><b>WBS Code:</b></td><td>{req.wbs_code or 'N/A'}</td></tr>
            <tr><td><b>Discipline:</b></td><td>{req.discipline or 'N/A'}</td></tr>
            <tr><td><b>Request Type:</b></td><td>{req.request_type or 'Normal'}</td></tr>
            <tr><td><b>Status:</b></td>
                <td style="color: {status_config['fg'].name()}; font-weight: bold;">
                    {status_config['icon']} {status_config['label']}
                </td></tr>
            <tr><td><b>Required Date:</b></td><td>{req.required_date or 'N/A'}</td></tr>
            <tr><td><b>Target Location:</b></td>
                <td>{req.target_location.code if req.target_location else 'N/A'}</td></tr>
            <tr><td><b>Items:</b></td><td>{len(req.lines)}</td></tr>
            <tr><td><b>Total Cost:</b></td><td>{self._compute_total_cost(req)}</td></tr>
            <tr><td><b>Created:</b></td><td>{req.created_at}</td></tr>
        </table>
        """

        QMessageBox.information(self, f"Request Details - {req.request_no}", details)

    # ==================================================================
    # Export Methods
    # ==================================================================

    def _collect_requests_data(self) -> tuple:
        """Collect requests table data for export."""
        headers = [
            self.requests_table.horizontalHeaderItem(c).text()
            for c in range(self.requests_table.columnCount())
        ]
        data = []
        for row in range(self.requests_table.rowCount()):
            if not self.requests_table.isRowHidden(row):
                row_dict = {}
                for col in range(self.requests_table.columnCount()):
                    item = self.requests_table.item(row, col)
                    row_dict[headers[col]] = item.text() if item else ""
                data.append(row_dict)
        return headers, data

    def _export_excel(self):
        """Export to Excel."""
        if not self.filtered_requests:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Material Requests", "material_requests.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            headers, data = self._collect_requests_data()
            export_to_excel(data, headers, file_path, sheet_name="Material Requests")
            self.status_bar.showMessage(f"Exported to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _export_pdf(self):
        """Export to PDF."""
        if not self.filtered_requests:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Material Requests", "material_requests.pdf",
            "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        try:
            headers, data = self._collect_requests_data()
            export_to_pdf(data, headers, file_path, title="Material Request History")
            self.status_bar.showMessage(f"PDF saved to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _print_report(self):
        """Print report as HTML."""
        if not self.filtered_requests:
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
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Material Request History</title>
            <style>
                body { font-family: 'Segoe UI', Arial; margin: 20px; }
                h1 { color: #004D40; }
                table { border-collapse: collapse; width: 100%; margin-top: 10px; }
                th { background: #004D40; color: white; padding: 8px; text-align: left; }
                td { padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px; }
                tr:nth-child(even) { background: #f9f9f9; }
                .status-pending { background: #FFE0B2; }
                .status-approved { background: #C8E6C9; }
                .status-rejected { background: #FFCDD2; }
            </style>
        </head>
        <body>
            <h1>📋 Material Request History</h1>
            <p>Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M") + """</p>
            <p>Total Requests: """ + str(len(self.filtered_requests)) + """</p>
            <table>
                <tr>
                    <th>MR Number</th><th>Company</th><th>Project</th>
                    <th>Discipline</th><th>Status</th><th>Items</th><th>Total Cost</th>
                </tr>
        """

        for req in self.filtered_requests:
            status_class = f"status-{req.status.lower()}" if req.status else ""
            html += f"""
                <tr class="{status_class}">
                    <td>{req.request_no}</td>
                    <td>{req.company or ''}</td>
                    <td>{req.project or ''}</td>
                    <td>{req.discipline or ''}</td>
                    <td>{req.status}</td>
                    <td>{len(req.lines)}</td>
                    <td>{self._compute_total_cost(req)}</td>
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
        if not self.filtered_requests:
            return

        headers, data = self._collect_requests_data()
        lines = ["\t".join(headers)]
        for row in data:
            lines.append("\t".join(row[h] for h in headers))
        
        QApplication.clipboard().setText("\n".join(lines))
        self.status_bar.showMessage("Copied to clipboard", 3000)

    # ==================================================================
    # Share Methods
    # ==================================================================

    def _share_whatsapp(self):
        """Share via WhatsApp."""
        row = self.requests_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a request.")
            return

        req = self.filtered_requests[row]
        self._share_request_whatsapp(req)

    def _share_request_whatsapp(self, req: MaterialRequest):
        """Share a specific request via WhatsApp."""
        lines = []
        lines.append(f"*Material Request:* {req.request_no}")
        lines.append(f"*Company:* {req.company or 'N/A'}")
        lines.append(f"*Project:* {req.project or 'N/A'}")
        lines.append(f"*Discipline:* {req.discipline or 'N/A'}")
        lines.append(f"*Status:* {req.status}")
        lines.append(f"*Items:* {len(req.lines)}")
        lines.append(f"*Total:* {self._compute_total_cost(req)}")
        
        message = "%0A".join(lines)
        wa_url = f"https://wa.me/989160684552?text={message}"
        webbrowser.open(wa_url)

    def _share_email(self):
        """Share via Email."""
        row = self.requests_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a request.")
            return

        req = self.filtered_requests[row]
        self._share_request_email(req)

    def _share_request_email(self, req: MaterialRequest):
        """Share a specific request via Email."""
        subject = f"Material Request: {req.request_no}"
        
        body = f"Material Request Details:%0D%0A%0D%0A"
        body += f"MR Number: {req.request_no}%0D%0A"
        body += f"Company: {req.company or 'N/A'}%0D%0A"
        body += f"Project: {req.project or 'N/A'}%0D%0A"
        body += f"Status: {req.status}%0D%0A"
        body += f"Items: {len(req.lines)}%0D%0A"
        body += f"Total Cost: {self._compute_total_cost(req)}%0D%0A"

        mailto = f"mailto:?subject={subject}&body={body}"
        QDesktopServices.openUrl(QUrl(mailto))
        self.status_bar.showMessage("Email client opened", 3000)

    def _get_username(self) -> str:
        """Get current username."""
        try:
            if self.parent and hasattr(self.parent, 'current_user'):
                return self.parent.current_user
        except Exception:
            pass
        return "unknown"

    def closeEvent(self, event):
        """Handle dialog close."""
        self.db.close()
        super().closeEvent(event)