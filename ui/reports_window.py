# ui/reports_window.py
"""Reports Window – iMat Material Control (includes shortage, PO receipts, in-transit)."""

import os
import sys
from typing import List, Dict

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
    QDateEdit, QLabel, QMessageBox, QLineEdit, QTableWidget,
    QTableWidgetItem, QFrame, QStatusBar, QToolBar, QFileDialog,
    QApplication, QAbstractItemView
)
from PyQt6.QtCore import QDate, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db.database import SessionLocal
from logic.reports import (
    generate_inventory_summary, generate_transaction_report,
    get_low_stock_items, get_stock_value_report,
)
from logic.reports_logic import (
    get_current_inventory, get_preservation_alerts,
    get_traceability_report, get_qc_summary, get_expiry_report,
    get_document_summary, get_material_shortage_report,
    get_po_receipt_summary, get_in_transit_report,
)
from ui.logo_widget import LogoWidget
from utils.excel_export import export_to_excel
from utils.logger import setup_logger

logger = setup_logger(__name__)

REPORT_TYPES = {
    "inventory_summary": {"name": "Inventory Summary", "icon": "📊", "description": "Current inventory levels"},
    "transaction_history": {"name": "Transaction History", "icon": "📋", "description": "Transaction log"},
    "live_stock": {"name": "Live Stock Report", "icon": "📦", "description": "Real-time stock"},
    "traceability": {"name": "Material Traceability", "icon": "🔗", "description": "History by heat number"},
    "material_shortage": {"name": "Material Shortage (MR vs Stock)", "icon": "⚠️", "description": "MR vs available stock"},
    "po_receipts": {"name": "PO / Delivery Receipts", "icon": "🧾", "description": "MRR linked to PO/vendor/DN"},
    "in_transit": {"name": "In-Transit Transfers", "icon": "🚚", "description": "Open MTR transfers"},
    "document_history": {"name": "Document History", "icon": "📄", "description": "Warehouse documents"},
    "low_stock": {"name": "Low Stock Report", "icon": "⚠️", "description": "Below minimum"},
    "stock_value": {"name": "Stock Value Report", "icon": "💰", "description": "Inventory value"},
    "expiry": {"name": "Expiry Date Report", "icon": "⌛", "description": "Expiring items"},
    "preservation": {"name": "Preservation Report", "icon": "🛡️", "description": "Preservation alerts"},
    "qc_summary": {"name": "QC Summary", "icon": "✅", "description": "QC overview"},
}


class ReportsWindow(QDialog):
    report_generated = pyqtSignal(str, list)

    def __init__(self, parent=None, report_type: str = "inventory_summary", user_role: str = "viewer"):
        super().__init__(parent)
        self.user_role = user_role
        self.parent = parent
        self.report_type = report_type
        self.db = SessionLocal()
        self.current_data: List[Dict] = []
        self.current_headers: List[str] = []
        self.setWindowTitle("iMat – Reports")
        self.setMinimumSize(1000, 700)
        self._init_ui()
        self._set_report_type(report_type)
        QTimer.singleShot(200, self._generate_report)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self._build_header(main_layout)
        self._build_toolbar(main_layout)
        self._build_filter_panel(main_layout)
        self._build_content(main_layout)
        self._build_status_bar(main_layout)

    def _build_header(self, parent_layout):
        header = QFrame()
        header.setStyleSheet("QFrame { background-color: #004D40; } QLabel { color: white; }")
        header.setFixedHeight(70)
        layout = QHBoxLayout(header)
        layout.addWidget(LogoWidget())
        title = QLabel("📊 Reports")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addStretch()
        self.subtitle = QLabel("Generate and view reports")
        self.subtitle.setStyleSheet("color: #B2DFDB;")
        layout.addWidget(self.subtitle)
        parent_layout.addWidget(header)

    def _build_toolbar(self, parent_layout):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        act = toolbar.addAction("🔄 Generate")
        act.triggered.connect(self._generate_report)
        toolbar.addSeparator()
        for label, fmt in [("📥 Excel", "excel"), ("📄 CSV", "csv")]:
            a = toolbar.addAction(label)
            a.triggered.connect(lambda checked=False, f=fmt: self._export_data(f))
        parent_layout.addWidget(toolbar)

    def _build_filter_panel(self, parent_layout):
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.addWidget(QLabel("Report:"))
        self.report_type_combo = QComboBox()
        for key, config in REPORT_TYPES.items():
            self.report_type_combo.addItem(f"{config['icon']} {config['name']}", key)
        self.report_type_combo.currentIndexChanged.connect(self._on_report_type_changed)
        layout.addWidget(self.report_type_combo)
        layout.addWidget(QLabel("From:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        layout.addWidget(self.start_date)
        layout.addWidget(QLabel("To:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        layout.addWidget(self.end_date)
        layout.addWidget(QLabel("Heat No:"))
        self.heat_no_input = QLineEdit()
        self.heat_no_input.setMaximumWidth(120)
        self.heat_no_input.setVisible(False)
        layout.addWidget(self.heat_no_input)
        layout.addStretch()
        parent_layout.addWidget(frame)

    def _build_content(self, parent_layout):
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        parent_layout.addWidget(self.table)
        self.record_count_label = QLabel("Records: 0")
        parent_layout.addWidget(self.record_count_label)

    def _build_status_bar(self, parent_layout):
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")
        parent_layout.addWidget(self.status_bar)

    def _set_report_type(self, report_type: str):
        for i in range(self.report_type_combo.count()):
            if self.report_type_combo.itemData(i) == report_type:
                self.report_type_combo.setCurrentIndex(i)
                return

    def _on_report_type_changed(self, index: int):
        self.report_type = self.report_type_combo.currentData()
        self.heat_no_input.setVisible(self.report_type == "traceability")
        config = REPORT_TYPES.get(self.report_type or "", {})
        self.subtitle.setText(config.get("description", ""))

    def _generate_report(self):
        self.report_type = self.report_type_combo.currentData()
        start = self.start_date.date().toPyDate()
        end = self.end_date.date().toPyDate()
        heat_no = self.heat_no_input.text().strip() or None
        self.status_bar.showMessage("Generating report...")
        QApplication.processEvents()
        try:
            if self.report_type == "inventory_summary":
                self.current_data = generate_inventory_summary()
            elif self.report_type == "transaction_history":
                self.current_data = generate_transaction_report(start, end, None)
            elif self.report_type == "live_stock":
                stocks = get_current_inventory(self.db)
                self.current_data = [{
                    "Item Code": s[0],
                    "Description": s[1] if len(s) > 1 else "",
                    "Quantity": s[6] if len(s) > 6 else 0,
                } for s in stocks]
            elif self.report_type == "traceability":
                if not heat_no:
                    QMessageBox.warning(self, "Missing Heat No", "Please enter a Heat Number.")
                    return
                rows = get_traceability_report(self.db, heat_no)
                self.current_data = [{
                    "Doc No": r[0], "Doc Type": r[1], "Date": str(r[2]),
                    "Item": r[3], "Qty": r[4], "Location": r[7] if len(r) > 7 else "",
                } for r in rows]
            elif self.report_type == "material_shortage":
                self.current_data = get_material_shortage_report(self.db)
            elif self.report_type == "po_receipts":
                self.current_data = get_po_receipt_summary(self.db)
            elif self.report_type == "in_transit":
                self.current_data = get_in_transit_report(self.db)
            elif self.report_type == "document_history":
                self.current_data = get_document_summary(self.db, start, end)
            elif self.report_type == "low_stock":
                self.current_data = get_low_stock_items(threshold=10)
            elif self.report_type == "stock_value":
                self.current_data = get_stock_value_report()
            elif self.report_type == "expiry":
                rows = get_expiry_report(self.db)
                self.current_data = [{
                    "Item": r[0], "Description": r[1], "Heat": r[2],
                    "Expiry": str(r[3]), "Qty": r[5],
                } for r in rows]
            elif self.report_type == "preservation":
                rows = get_preservation_alerts(self.db)
                self.current_data = [{
                    "Item": r[0], "Description": r[1], "Due": str(r[5]), "Qty": r[7],
                } for r in rows]
            elif self.report_type == "qc_summary":
                summary = get_qc_summary(self.db)
                self.current_data = [
                    {"QC Status": k, "Items": v["item_count"], "Qty": v["total_quantity"]}
                    for k, v in summary.items()
                ]
            else:
                self.current_data = []
            self._populate_table()
            self.status_bar.showMessage(f"Report ready – {len(self.current_data)} rows")
            self.report_generated.emit(self.report_type, self.current_data)
        except Exception as e:
            logger.error(f"Report failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Report Error", str(e))

    def _populate_table(self):
        self.table.clear()
        if not self.current_data:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.record_count_label.setText("Records: 0")
            return
        headers = list(self.current_data[0].keys())
        self.current_headers = headers
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self.current_data))
        for r, row in enumerate(self.current_data):
            for c, key in enumerate(headers):
                val = row.get(key, "")
                self.table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))
        self.table.resizeColumnsToContents()
        self.record_count_label.setText(f"Records: {len(self.current_data)}")

    def _export_data(self, format_type: str):
        if not self.current_data:
            QMessageBox.information(self, "Export", "No data to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export", f"report_{self.report_type}", "All (*.*)")
        if not path:
            return
        try:
            if format_type == "excel":
                export_to_excel(self.current_data, path)
            else:
                import csv
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=self.current_headers)
                    w.writeheader()
                    w.writerows(self.current_data)
            self.status_bar.showMessage(f"Exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def closeEvent(self, event):
        try:
            self.db.close()
        except Exception:
            pass
        super().closeEvent(event)
