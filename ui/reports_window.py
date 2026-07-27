# ui/reports_window.py
"""
Reports Window – iMat Material Control System (EPC Edition).

Flexible report generation window with:
- Multiple report types in one interface
- Date range filtering
- Custom filters per report type
- Real-time preview
- Export to Excel, PDF, HTML, CSV
- Print functionality
- WhatsApp sharing
- Email delivery
- Copy to clipboard
- Column visibility control
- Sort by any column
- Search within results
- Report scheduling placeholder
"""

import os
import sys
import tempfile
import webbrowser
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, 
    QDateEdit, QLabel, QTextEdit, QMessageBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QStatusBar, QToolBar, QFileDialog, QApplication,
    QSplitter, QCheckBox, QGroupBox, QFormLayout,
    QAbstractItemView, QMenu, QWidget, QProgressBar
)
from PyQt6.QtCore import Qt, QDate, QUrl, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QDesktopServices, QAction

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db.database import SessionLocal, get_db_session
from db.models import (
    Product, Transaction, InventorySummary, Stock, Location,
    Document, DocumentLine, MaterialRequest
)
from logic.reports import (
    generate_inventory_summary, generate_transaction_report,
    get_low_stock_items, get_stock_value_report, get_movement_report
)
from logic.reports_logic import (
    get_current_inventory, get_preservation_alerts,
    get_traceability_report, get_stock_movements,
    get_qc_summary, get_expiry_report, get_document_summary
)
from ui.logo_widget import LogoWidget
from utils.excel_export import export_to_excel
from utils.pdf_export import export_to_pdf
from utils.logger import setup_logger

logger = setup_logger(__name__)

# ==================================================================
# Constants
# ==================================================================

# Report type definitions
REPORT_TYPES = {
    "inventory_summary": {
        "name": "Inventory Summary",
        "icon": "📊",
        "description": "Current inventory levels for all items",
        "filters": ["discipline", "category"],
    },
    "transaction_history": {
        "name": "Transaction History",
        "icon": "📋",
        "description": "Transaction log with document details",
        "filters": ["date_range", "doc_type", "item_code"],
    },
    "live_stock": {
        "name": "Live Stock Report",
        "icon": "📦",
        "description": "Real-time stock with QC status and locations",
        "filters": ["qc_status", "location", "discipline"],
    },
    "traceability": {
        "name": "Material Traceability",
        "icon": "🔗",
        "description": "Full history by heat number",
        "filters": ["heat_no"],
    },
    "document_history": {
        "name": "Document History",
        "icon": "📄",
        "description": "All warehouse documents with status",
        "filters": ["date_range", "doc_type", "status"],
    },
    "low_stock": {
        "name": "Low Stock Report",
        "icon": "⚠️",
        "description": "Items below minimum required quantity",
        "filters": ["threshold", "discipline"],
    },
    "stock_value": {
        "name": "Stock Value Report",
        "icon": "💰",
        "description": "Total inventory value analysis",
        "filters": ["discipline", "location"],
    },
    "expiry": {
        "name": "Expiry Date Report",
        "icon": "⌛",
        "description": "Items approaching or past expiry",
        "filters": ["days_threshold", "qc_status"],
    },
    "preservation": {
        "name": "Preservation Report",
        "icon": "🛡️",
        "description": "Preservation schedule and alerts",
        "filters": ["discipline", "location"],
    },
    "qc_summary": {
        "name": "QC Summary",
        "icon": "✅",
        "description": "Quality control status overview",
        "filters": [],
    },
    "msr_history": {
        "name": "MSR History",
        "icon": "📋",
        "description": "Material Store Requisition history",
        "filters": ["date_range", "status"],
    },
}

# Export formats
EXPORT_FORMATS = {
    "excel": {"label": "Excel (.xlsx)", "ext": ".xlsx"},
    "pdf": {"label": "PDF (.pdf)", "ext": ".pdf"},
    "html": {"label": "HTML (.html)", "ext": ".html"},
    "csv": {"label": "CSV (.csv)", "ext": ".csv"},
}

# ==================================================================
# Reports Window
# ==================================================================

class ReportsWindow(QDialog):
    """
    Flexible report generation and viewing window.
    
    Features:
    - Multiple report types
    - Custom filters
    - Table and text views
    - Export capabilities
    - Share options
    """

    report_generated = pyqtSignal(str, list)  # report_type, data

    def __init__(self, parent=None, report_type: str = "inventory_summary",
                 user_role: str = "viewer"):
        """
        Initialize the Reports window.
        
        Args:
            parent: Parent widget
            report_type: Default report type to show
            user_role: Current user's role
        """
        super().__init__(parent)
        self.user_role = user_role
        self.parent = parent
        self.report_type = report_type
        self.db = SessionLocal()
        
        # State
        self.current_data: List[Dict] = []
        self.current_headers: List[str] = []
        
        # Window setup
        self.setWindowTitle("iMat – Reports")
        self.setMinimumSize(1000, 700)
        
        # Build UI
        self._init_ui()
        
        # Set initial report type
        self._set_report_type(report_type)
        
        # Generate initial report
        QTimer.singleShot(200, self._generate_report)

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

        title = QLabel("📊 Reports")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("Generate and view reports")
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
        """)

        self.action_generate = toolbar.addAction("🔄 Generate")
        self.action_generate.setToolTip("Generate/re-run the current report")
        self.action_generate.triggered.connect(self._generate_report)
        toolbar.addSeparator()

        self.action_export_excel = toolbar.addAction("📥 Excel")
        self.action_export_excel.triggered.connect(lambda: self._export_data("excel"))
        
        self.action_export_pdf = toolbar.addAction("📑 PDF")
        self.action_export_pdf.triggered.connect(lambda: self._export_data("pdf"))
        
        self.action_export_html = toolbar.addAction("🌐 HTML")
        self.action_export_html.triggered.connect(lambda: self._export_data("html"))
        
        self.action_export_csv = toolbar.addAction("📄 CSV")
        self.action_export_csv.triggered.connect(lambda: self._export_data("csv"))
        toolbar.addSeparator()

        self.action_print = toolbar.addAction("🖨️ Print")
        self.action_print.triggered.connect(self._print_report)
        
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

        # Report type selector
        filter_layout.addWidget(QLabel("Report:"))
        self.report_type_combo = QComboBox()
        for key, config in REPORT_TYPES.items():
            self.report_type_combo.addItem(f"{config['icon']} {config['name']}", key)
        self.report_type_combo.currentIndexChanged.connect(self._on_report_type_changed)
        filter_layout.addWidget(self.report_type_combo)

        filter_layout.addWidget(QLabel("  |  "))

        # Date range
        filter_layout.addWidget(QLabel("From:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        filter_layout.addWidget(self.start_date)

        filter_layout.addWidget(QLabel("To:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        filter_layout.addWidget(self.end_date)

        filter_layout.addWidget(QLabel("  |  "))

        # Additional filters (dynamic)
        self.filter_widget = QWidget()
        self.filter_layout = QHBoxLayout(self.filter_widget)
        self.filter_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_layout.setSpacing(6)

        # Doc type filter
        filter_layout.addWidget(QLabel("Type:"))
        self.doc_type_combo = QComboBox()
        self.doc_type_combo.addItem("All Types")
        self.doc_type_combo.addItems([
            "MRR", "MIV", "MSR", "OSND", "MTR", "RTV", "MRV", "ADJ",
            "RES", "SRN", "WOM", "GAT", "RCT", "ISS", "TRN"
        ])
        filter_layout.addWidget(self.doc_type_combo)

        # Status filter
        filter_layout.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["All", "DRAFT", "APPROVED", "REJECTED", "CLOSED"])
        filter_layout.addWidget(self.status_combo)

        # Heat number filter (for traceability)
        filter_layout.addWidget(QLabel("Heat No:"))
        self.heat_no_input = QLineEdit()
        self.heat_no_input.setPlaceholderText("Enter heat number...")
        self.heat_no_input.setMaximumWidth(120)
        self.heat_no_input.setVisible(False)
        filter_layout.addWidget(self.heat_no_input)

        filter_layout.addWidget(self.filter_widget)
        filter_layout.addStretch()

        parent_layout.addWidget(filter_frame)

    def _build_content(self, parent_layout: QVBoxLayout):
        """Build the main content area."""
        # Table view
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
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

        parent_layout.addWidget(self.table)

        # Record count
        self.record_count_label = QLabel("Records: 0")
        self.record_count_label.setStyleSheet("color: #666; font-size: 10px; padding: 2px 8px;")
        parent_layout.addWidget(self.record_count_label)

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready – Select report type and click Generate")
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
    # Report Type Management
    # ==================================================================

    def _set_report_type(self, report_type: str):
        """Set the current report type."""
        for i in range(self.report_type_combo.count()):
            if self.report_type_combo.itemData(i) == report_type:
                self.report_type_combo.setCurrentIndex(i)
                return

    def _on_report_type_changed(self, index: int):
        """Handle report type change."""
        self.report_type = self.report_type_combo.currentData()
        
        # Show/hide filters based on report type
        is_traceability = self.report_type == "traceability"
        self.heat_no_input.setVisible(is_traceability)
        
        # Update subtitle
        config = REPORT_TYPES.get(self.report_type, {})
        self.subtitle.setText(config.get("description", ""))

    # ==================================================================
    # Report Generation
    # ==================================================================

    def _generate_report(self):
        """Generate the selected report."""
        self.report_type = self.report_type_combo.currentData()
        
        start = self.start_date.date().toPyDate()
        end = self.end_date.date().toPyDate()
        doc_type = self.doc_type_combo.currentText()
        if doc_type == "All Types":
            doc_type = None
        status = self.status_combo.currentText()
        if status == "All":
            status = None
        heat_no = self.heat_no_input.text().strip() or None

        self.status_bar.showMessage("Generating report...")
        QApplication.processEvents()

        try:
            if self.report_type == "inventory_summary":
                self.current_data = generate_inventory_summary()

            elif self.report_type == "transaction_history":
                self.current_data = generate_transaction_report(start, end, doc_type)

            elif self.report_type == "live_stock":
                stocks = get_current_inventory(self.db)
                self.current_data = []
                for s in stocks:
                    self.current_data.append({
                        "Item Code": s[0],
                        "Description": s[1] if len(s) > 1 else "",
                        "Heat No": s[2] if len(s) > 2 else "",
                        "Location": s[3] if len(s) > 3 else "",
                        "QC Status": s[4] if len(s) > 4 else "",
                        "Quantity": s[5] if len(s) > 5 else 0,
                        "Allocated": s[6] if len(s) > 6 else 0,
                        "Available": (s[5] - s[6]) if len(s) > 6 else 0,
                    })

            elif self.report_type == "traceability":
                if not heat_no:
                    QMessageBox.warning(self, "Missing Heat No", 
                                      "Please enter a Heat Number for traceability.")
                    return
                trace_data = get_traceability_report(self.db, heat_no)
                self.current_data = []
                for row in trace_data:
                    self.current_data.append({
                        "Doc No": row[0] if len(row) > 0 else "",
                        "Doc Type": row[1] if len(row) > 1 else "",
                        "Doc Date": str(row[2]) if len(row) > 2 else "",
                        "Item Code": row[3] if len(row) > 3 else "",
                        "Qty": row[4] if len(row) > 4 else 0,
                        "Drawing": row[5] if len(row) > 5 else "",
                        "Certificate": row[6] if len(row) > 6 else "",
                        "Location": row[7] if len(row) > 7 else "",
                        "Description": row[8] if len(row) > 8 else "",
                    })

            elif self.report_type == "document_history":
                docs = get_document_summary(self.db, start, end)
                self.current_data = docs

            elif self.report_type == "low_stock":
                self.current_data = get_low_stock_items(threshold=10)

            elif self.report_type == "stock_value":
                self.current_data = get_stock_value_report()

            elif self.report_type == "expiry":
                expiry_data = get_expiry_report(self.db, 90)
                self.current_data = []
                for row in expiry_data:
                    self.current_data.append({
                        "Item Code": row[0] if len(row) > 0 else "",
                        "Description": row[1] if len(row) > 1 else "",
                        "Heat No": row[2] if len(row) > 2 else "",
                        "Expiry Date": str(row[3]) if len(row) > 3 else "",
                        "Location": row[4] if len(row) > 4 else "",
                        "Quantity": row[5] if len(row) > 5 else 0,
                        "QC Status": row[6] if len(row) > 6 else "",
                    })

            elif self.report_type == "preservation":
                alerts = get_preservation_alerts(self.db)
                self.current_data = []
                for row in alerts:
                    self.current_data.append({
                        "Item Code": row[0] if len(row) > 0 else "",
                        "Description": row[1] if len(row) > 1 else "",
                        "Heat No": row[2] if len(row) > 2 else "",
                        "Location": row[3] if len(row) > 3 else "",
                        "Location Name": row[4] if len(row) > 4 else "",
                        "Next Due": str(row[5]) if len(row) > 5 else "",
                        "Status": row[6] if len(row) > 6 else "",
                        "Quantity": row[7] if len(row) > 7 else 0,
                    })

            elif self.report_type == "qc_summary":
                summary = get_qc_summary(self.db)
                self.current_data = []
                for status_key, stats in summary.items():
                    self.current_data.append({
                        "QC Status": status_key,
                        "Item Count": stats.get("item_count", 0),
                        "Total Quantity": stats.get("total_quantity", 0),
                    })

            elif self.report_type == "msr_history":
                # Get MSR documents
                msr_docs = self.db.query(Document).filter(
                    Document.doc_type == "MSR",
                    Document.doc_date.between(start, end)
                ).order_by(Document.doc_date.desc()).all()
                
                self.current_data = []
                for doc in msr_docs:
                    if status and doc.status != status:
                        continue
                    self.current_data.append({
                        "Doc No": doc.doc_no,
                        "Date": str(doc.doc_date),
                        "Subject": doc.subject or "",
                        "Vendor": doc.vendor_name or "",
                        "Status": doc.status,
                        "Lines": len(doc.lines),
                        "Created By": doc.created_by or "",
                    })

            else:
                self.current_data = []

            self._display_data()
            self.report_generated.emit(self.report_type, self.current_data)
            self.status_bar.showMessage(
                f"Report generated: {len(self.current_data)} records", 5000
            )

        except Exception as e:
            logger.exception("Report generation failed")
            QMessageBox.critical(self, "Error", f"Failed to generate report:\n{str(e)}")
            self.status_bar.showMessage("Report generation failed")

    def _display_data(self):
        """Display report data in the table."""
        if not self.current_data:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.record_count_label.setText("Records: 0")
            return

        # Get headers from first row
        self.current_headers = list(self.current_data[0].keys())
        
        self.table.setColumnCount(len(self.current_headers))
        self.table.setHorizontalHeaderLabels(self.current_headers)
        self.table.setRowCount(len(self.current_data))

        for row, record in enumerate(self.current_data):
            for col, header in enumerate(self.current_headers):
                value = record.get(header, "")
                
                if isinstance(value, (int, float)):
                    value_str = f"{value:,.2f}" if isinstance(value, float) else str(value)
                else:
                    value_str = str(value) if value is not None else ""
                
                item = QTableWidgetItem(value_str)
                
                # Right-align numbers
                if isinstance(value, (int, float)):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                # Color code certain fields
                if header in ["Status", "QC Status"]:
                    if value_str in ["APPROVED", "ACCEPTED", "CLOSED"]:
                        item.setBackground(QColor("#C8E6C9"))
                        item.setForeground(QColor("#2E7D32"))
                    elif value_str in ["REJECTED"]:
                        item.setBackground(QColor("#FFCDD2"))
                        item.setForeground(QColor("#C62828"))
                    elif value_str in ["QUARANTINE", "PENDING", "DRAFT"]:
                        item.setBackground(QColor("#FFE0B2"))
                        item.setForeground(QColor("#E65100"))
                
                self.table.setItem(row, col, item)

        self.table.resizeColumnsToContents()
        self.record_count_label.setText(f"Records: {len(self.current_data)}")

    # ==================================================================
    # Context Menu
    # ==================================================================

    def _show_context_menu(self, pos):
        """Show context menu on table."""
        menu = QMenu(self)
        menu.addAction("📋 Copy Selected Rows", self._copy_selected_rows)
        menu.addAction("📋 Copy All", self._copy_to_clipboard)
        menu.addSeparator()
        menu.addAction("📥 Export to Excel", lambda: self._export_data("excel"))
        menu.addAction("📑 Export to PDF", lambda: self._export_data("pdf"))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_selected_rows(self):
        """Copy selected rows to clipboard."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select rows to copy.")
            return

        rows = set()
        for item in selected:
            rows.add(item.row())

        lines = ["\t".join(self.current_headers)]
        for row in sorted(rows):
            row_data = []
            for col in range(len(self.current_headers)):
                item = self.table.item(row, col)
                row_data.append(item.text() if item else "")
            lines.append("\t".join(row_data))

        QApplication.clipboard().setText("\n".join(lines))
        self.status_bar.showMessage(f"{len(rows)} rows copied", 3000)

    # ==================================================================
    # Export Methods
    # ==================================================================

    def _collect_table_data(self) -> Tuple[List[str], List[Dict]]:
        """Collect current table data."""
        if not self.current_data:
            return [], []
        return self.current_headers, self.current_data

    def _export_data(self, format_type: str):
        """Export data to specified format."""
        if not self.current_data:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        format_config = EXPORT_FORMATS.get(format_type, EXPORT_FORMATS["excel"])
        
        config = REPORT_TYPES.get(self.report_type, {})
        default_name = f"{config.get('name', 'report').lower().replace(' ', '_')}{format_config['ext']}"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, f"Export as {format_config['label']}",
            default_name,
            f"{format_config['label']} (*{format_config['ext']})"
        )
        if not file_path:
            return

        try:
            headers, data = self._collect_table_data()

            if format_type == "excel":
                export_to_excel(data, headers, file_path)
            elif format_type == "pdf":
                export_to_pdf(data, headers, file_path, 
                            title=config.get('name', 'Report'))
            elif format_type == "html":
                self._export_html(file_path)
            elif format_type == "csv":
                self._export_csv(file_path)

            self.status_bar.showMessage(
                f"Exported as {format_config['label']} to {file_path}", 5000
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _export_html(self, file_path: str):
        """Export to HTML file."""
        html = self._generate_html_content()
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)

    def _export_csv(self, file_path: str):
        """Export to CSV file."""
        import csv
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.current_headers)
            writer.writeheader()
            writer.writerows(self.current_data)

    def _generate_html_content(self) -> str:
        """Generate HTML content for the report."""
        config = REPORT_TYPES.get(self.report_type, {})
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>{config.get('name', 'Report')}</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial; margin: 20px; }}
                h1 {{ color: #004D40; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
                th {{ background: #004D40; color: white; padding: 8px; text-align: left; font-size: 11px; }}
                td {{ padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px; }}
                tr:nth-child(even) {{ background: #f9f9f9; }}
                .footer {{ margin-top: 20px; font-size: 10px; color: #888; }}
            </style>
        </head>
        <body>
            <h1>{config.get('icon', '📊')} {config.get('name', 'Report')}</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            <p>Records: {len(self.current_data)}</p>
            <table>
                <tr>
        """
        
        for h in self.current_headers:
            html += f"<th>{h}</th>"
        html += "</tr>"

        for row in self.current_data:
            html += "<tr>"
            for h in self.current_headers:
                val = row.get(h, "")
                html += f"<td>{val}</td>"
            html += "</tr>"

        html += f"""
            </table>
            <div class="footer">
                Generated by iMat Material Control System
            </div>
        </body>
        </html>
        """
        return html

    def _print_report(self):
        """Print report via HTML."""
        if not self.current_data:
            QMessageBox.information(self, "No Data", "Nothing to print.")
            return

        html = self._generate_html_content()
        
        with tempfile.NamedTemporaryFile(
            suffix='.html', delete=False, mode='w', encoding='utf-8'
        ) as f:
            f.write(html)
            tmp_path = f.name

        QDesktopServices.openUrl(QUrl.fromLocalFile(tmp_path))
        self.status_bar.showMessage("Report opened for printing", 4000)

    def _copy_to_clipboard(self):
        """Copy all data to clipboard."""
        if not self.current_data:
            return

        lines = ["\t".join(self.current_headers)]
        for row in self.current_data:
            lines.append("\t".join(str(row.get(h, "")) for h in self.current_headers))

        QApplication.clipboard().setText("\n".join(lines))
        self.status_bar.showMessage("Report copied to clipboard", 3000)

    def _share_whatsapp(self):
        """Share report summary via WhatsApp."""
        config = REPORT_TYPES.get(self.report_type, {})
        
        lines = []
        lines.append(f"*📊 {config.get('name', 'Report')}*")
        lines.append(f"Records: {len(self.current_data)}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        
        # Add first 5 rows as preview
        if self.current_data:
            lines.append("*Sample Data:*")
            for i, row in enumerate(self.current_data[:5]):
                parts = []
                for h in self.current_headers[:4]:
                    parts.append(f"{h}: {row.get(h, '')}")
                lines.append(f"  {i+1}. {' | '.join(parts)}")
            
            if len(self.current_data) > 5:
                lines.append(f"  ... and {len(self.current_data) - 5} more rows")

        lines.append("")
        lines.append("Full report available in iMat.")
        lines.append(f"Generated by iMat Material Control System")

        message = "%0A".join(lines)
        wa_url = f"https://wa.me/989160684552?text={message}"
        webbrowser.open(wa_url)
        self.status_bar.showMessage("WhatsApp message prepared", 3000)

    def _share_email(self):
        """Share report via email."""
        config = REPORT_TYPES.get(self.report_type, {})
        
        subject = f"iMat Report: {config.get('name', 'Report')}"
        body = (
            f"Report Type: {config.get('name', 'Report')}%0D%0A"
            f"Records: {len(self.current_data)}%0D%0A"
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}%0D%0A%0D%0A"
            f"Please find the report from iMat Material Control System."
        )

        mailto = f"mailto:?subject={subject}&body={body}"
        QDesktopServices.openUrl(QUrl(mailto))
        self.status_bar.showMessage("Email client opened", 3000)

    def closeEvent(self, event):
        """Handle dialog close."""
        self.db.close()
        super().closeEvent(event)