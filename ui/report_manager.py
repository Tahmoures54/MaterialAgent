# ui/report_manager.py
"""
Unified Report Manager – iMat Material Control System (EPC Edition).

Centralized report hub with:
- All reports accessible from one place
- Quick-access report tiles
- Report categories with icons
- Favorite reports pinning
- Recent reports history
- Report scheduling (future)
- Email report delivery
- WhatsApp report sharing
- Custom report builder interface
- Export format selection
- Preview before export
- Batch report generation
"""

import os
import json
import tempfile
import webbrowser
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget, QMessageBox, QComboBox, QDateEdit,
    QLineEdit, QFormLayout, QGroupBox, QScrollArea,
    QGridLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QSpinBox, QFileDialog,
    QAbstractItemView, QSplitter, QStatusBar, QToolBar,
    QTextEdit, QApplication, QMenu
)
from PyQt6.QtCore import Qt, QDate, QUrl, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QDesktopServices, QAction, QIcon

from ui.logo_widget import LogoWidget
from utils.excel_export import export_to_excel
from utils.pdf_export import export_to_pdf

# ==================================================================
# Constants
# ==================================================================

# Report definitions
REPORTS = {
    "inventory_summary": {
        "name": "Inventory Summary",
        "icon": "📊",
        "category": "Inventory",
        "description": "Overview of all items with current stock levels, "
                      "allocated quantities, and available balance.",
        "color": "#4CAF50",
        "filters": ["discipline", "category", "location"],
    },
    "live_stock": {
        "name": "Live Stock Dashboard",
        "icon": "📦",
        "category": "Inventory",
        "description": "Real-time stock view with QC status, locations, "
                      "and heat number tracking.",
        "color": "#2196F3",
        "filters": ["qc_status", "location", "discipline"],
    },
    "transaction_history": {
        "name": "Transaction History",
        "icon": "📋",
        "category": "Transactions",
        "description": "Complete transaction log with document references, "
                      "quantities, and vendor details.",
        "color": "#FF9800",
        "filters": ["date_range", "doc_type", "item_code"],
    },
    "document_history": {
        "name": "Document History",
        "icon": "📄",
        "category": "Transactions",
        "description": "All warehouse documents (MRR, MIV, MSR, etc.) "
                      "with status and line items.",
        "color": "#9C27B0",
        "filters": ["date_range", "doc_type", "status"],
    },
    "traceability": {
        "name": "Material Traceability",
        "icon": "🔗",
        "category": "Quality",
        "description": "Full traceability by heat number showing all "
                      "receipts, issues, and current location.",
        "color": "#00BCD4",
        "filters": ["heat_no", "item_code"],
    },
    "expiry_report": {
        "name": "Expiry Date Report",
        "icon": "⌛",
        "category": "Quality",
        "description": "Items approaching or past expiry date with "
                      "color-coded status indicators.",
        "color": "#F44336",
        "filters": ["days_threshold", "qc_status", "location"],
    },
    "preservation_report": {
        "name": "Preservation Report",
        "icon": "🛡️",
        "category": "Quality",
        "description": "Preservation schedule with overdue alerts "
                      "and next due dates.",
        "color": "#607D8B",
        "filters": ["status", "discipline", "location"],
    },
    "qc_report": {
        "name": "QC Status Report",
        "icon": "✅",
        "category": "Quality",
        "description": "Quality control summary with quarantine, "
                      "accepted, and rejected quantities.",
        "color": "#8BC34A",
        "filters": ["date_range", "qc_status", "discipline"],
    },
    "abc_analysis": {
        "name": "ABC Analysis",
        "icon": "📈",
        "category": "Analysis",
        "description": "Pareto classification of inventory items "
                      "by value or quantity.",
        "color": "#E91E63",
        "filters": ["period", "method"],
    },
    "reorder_report": {
        "name": "Reorder Report",
        "icon": "🔔",
        "category": "Analysis",
        "description": "Items below reorder point with recommended "
                      "order quantities.",
        "color": "#FF5722",
        "filters": ["discipline", "location"],
    },
    "stock_value": {
        "name": "Stock Value Report",
        "icon": "💰",
        "category": "Analysis",
        "description": "Total inventory value by item, discipline, "
                      "and location.",
        "color": "#009688",
        "filters": ["discipline", "location"],
    },
    "material_request": {
        "name": "Material Request Report",
        "icon": "📋",
        "category": "Technical",
        "description": "Material requests from Technical Office "
                      "with status and line items.",
        "color": "#3F51B5",
        "filters": ["date_range", "status", "discipline"],
    },
}

# Report categories
REPORT_CATEGORIES = {
    "Inventory": {"icon": "📦", "color": "#4CAF50"},
    "Transactions": {"icon": "📋", "color": "#FF9800"},
    "Quality": {"icon": "✅", "color": "#00BCD4"},
    "Analysis": {"icon": "📈", "color": "#E91E63"},
    "Technical": {"icon": "📐", "color": "#3F51B5"},
}

# Export formats
EXPORT_FORMATS = {
    "excel": {"icon": "📥", "label": "Excel (.xlsx)", "ext": ".xlsx"},
    "pdf": {"icon": "📑", "label": "PDF (.pdf)", "ext": ".pdf"},
    "html": {"icon": "🌐", "label": "HTML (.html)", "ext": ".html"},
    "csv": {"icon": "📄", "label": "CSV (.csv)", "ext": ".csv"},
}

# ==================================================================
# Report Manager Dialog
# ==================================================================

class ReportManagerDialog(QDialog):
    """
    Unified report manager for all iMat reports.
    
    Features:
    - Centralized access to all reports
    - Category-based organization
    - Quick filters for each report
    - Multiple export formats
    - Favorite reports
    - Recent reports history
    """

    report_generated = pyqtSignal(str)  # report name

    def __init__(self, parent=None, user_role: str = "viewer"):
        """
        Initialize the Report Manager dialog.
        
        Args:
            parent: Parent widget
            user_role: Current user's role
        """
        super().__init__(parent)
        self.parent = parent
        self.user_role = user_role
        
        # State
        self.selected_report: Optional[str] = None
        self.favorite_reports: List[str] = []
        self.recent_reports: List[str] = []
        
        # Window setup
        self.setWindowTitle("iMat – Report Manager")
        self.setMinimumSize(1000, 700)
        self.setModal(True)
        
        # Build UI
        self._init_ui()
        
        # Load favorites
        self._load_favorites()

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

        title = QLabel("📊 Reports & Export Center")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("Generate, preview, and export reports")
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

        self.action_generate = toolbar.addAction("🔄 Generate Report")
        self.action_generate.setToolTip("Generate the selected report")
        self.action_generate.triggered.connect(self._generate_report)
        toolbar.addSeparator()

        self.action_export_excel = toolbar.addAction("📥 Excel")
        self.action_export_excel.setToolTip("Export current report to Excel")
        self.action_export_excel.triggered.connect(lambda: self._export_report("excel"))
        
        self.action_export_pdf = toolbar.addAction("📑 PDF")
        self.action_export_pdf.setToolTip("Export current report to PDF")
        self.action_export_pdf.triggered.connect(lambda: self._export_report("pdf"))
        
        self.action_export_html = toolbar.addAction("🌐 HTML")
        self.action_export_html.setToolTip("Export current report to HTML")
        self.action_export_html.triggered.connect(lambda: self._export_report("html"))
        toolbar.addSeparator()

        self.action_print = toolbar.addAction("🖨️ Print")
        self.action_print.triggered.connect(self._print_report)
        
        self.action_whatsapp = toolbar.addAction("💬 Share WhatsApp")
        self.action_whatsapp.triggered.connect(self._share_whatsapp)
        
        self.action_email = toolbar.addAction("📧 Email Report")
        self.action_email.triggered.connect(self._email_report)

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

        # Tab 1: All Reports
        self.tab_all = self._build_all_reports_tab()
        self.tab_widget.addTab(self.tab_all, "📊 All Reports")

        # Tab 2: Favorites
        self.tab_favorites = self._build_favorites_tab()
        self.tab_widget.addTab(self.tab_favorites, "⭐ Favorites")

        # Tab 3: Recent
        self.tab_recent = self._build_recent_tab()
        self.tab_widget.addTab(self.tab_recent, "🕐 Recent")

        parent_layout.addWidget(self.tab_widget)

    def _build_all_reports_tab(self) -> QWidget:
        """Build the all reports tab with category sections."""
        widget = QWidget()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(20)

        # Description
        desc = QLabel(
            "<h3>Select a Report</h3>"
            "Choose from the available reports below. Click on a report card "
            "to select it and configure filters."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Reports organized by category
        for category, cat_config in REPORT_CATEGORIES.items():
            cat_group = QGroupBox(f"{cat_config['icon']} {category}")
            cat_group.setStyleSheet(f"""
                QGroupBox {{
                    font-weight: bold;
                    border: 1px solid {cat_config['color']}40;
                    border-left: 4px solid {cat_config['color']};
                    border-radius: 6px;
                    margin-top: 8px;
                    padding: 15px;
                    padding-top: 25px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: {cat_config['color']};
                }}
            """)

            grid = QGridLayout(cat_group)
            grid.setSpacing(10)

            # Filter reports in this category
            cat_reports = {
                key: val for key, val in REPORTS.items()
                if val["category"] == category
            }

            col = 0
            row = 0
            for report_key, report in cat_reports.items():
                card = self._build_report_card(report_key, report)
                grid.addWidget(card, row, col)
                col += 1
                if col >= 3:
                    col = 0
                    row += 1

            layout.addWidget(cat_group)

        layout.addStretch()

        scroll.setWidget(container)
        
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        return widget

    def _build_favorites_tab(self) -> QWidget:
        """Build the favorites tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)

        self.favorites_label = QLabel(
            "⭐ <b>Favorite Reports</b><br>"
            "Click the star icon on any report to add it to favorites."
        )
        self.favorites_label.setWordWrap(True)
        layout.addWidget(self.favorites_label)

        self.favorites_grid = QGridLayout()
        self.favorites_grid.setSpacing(10)
        layout.addLayout(self.favorites_grid)

        layout.addStretch()

        self._update_favorites_grid()
        return widget

    def _build_recent_tab(self) -> QWidget:
        """Build the recent reports tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)

        self.recent_label = QLabel(
            "🕐 <b>Recently Generated Reports</b>"
        )
        self.recent_label.setWordWrap(True)
        layout.addWidget(self.recent_label)

        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(4)
        self.recent_table.setHorizontalHeaderLabels([
            "Report", "Category", "Generated", "Actions"
        ])
        self.recent_table.horizontalHeader().setStretchLastSection(True)
        self.recent_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setStyleSheet("""
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
        self.recent_table.setColumnWidth(0, 200)
        self.recent_table.setColumnWidth(1, 100)
        self.recent_table.setColumnWidth(2, 150)

        layout.addWidget(self.recent_table)

        self._update_recent_table()
        return widget

    def _build_report_card(self, report_key: str, report: Dict) -> QFrame:
        """Build a clickable report card."""
        card = QFrame()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setMinimumSize(250, 120)
        card.setMaximumWidth(320)
        card.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 2px solid {report['color']}30;
                border-radius: 10px;
                padding: 15px;
            }}
            QFrame:hover {{
                border-color: {report['color']};
                background: {report['color']}08;
            }}
            QFrame[selected="true"] {{
                border-color: {report['color']};
                background: {report['color']}15;
                border-width: 3px;
            }}
        """)
        card.setProperty("selected", "false")

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(6)

        # Header
        header_layout = QHBoxLayout()
        
        icon_label = QLabel(report["icon"])
        icon_label.setStyleSheet(f"font-size: 28px; border: none; background: transparent;")
        header_layout.addWidget(icon_label)

        name_label = QLabel(f"<b style='font-size: 13px;'>{report['name']}</b>")
        name_label.setStyleSheet("border: none; background: transparent;")
        name_label.setWordWrap(True)
        header_layout.addWidget(name_label, 1)

        # Favorite button
        is_fav = report_key in self.favorite_reports
        btn_fav = QPushButton("⭐" if is_fav else "☆")
        btn_fav.setFixedSize(28, 28)
        btn_fav.setToolTip("Add to favorites" if not is_fav else "Remove from favorites")
        btn_fav.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                font-size: 16px;
                border-radius: 14px;
            }}
            QPushButton:hover {{
                background: #FFF9C4;
            }}
        """)
        btn_fav.clicked.connect(lambda: self._toggle_favorite(report_key, btn_fav))
        header_layout.addWidget(btn_fav)

        card_layout.addLayout(header_layout)

        # Description
        desc_label = QLabel(report["description"])
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 10px; border: none; background: transparent;")
        card_layout.addWidget(desc_label)

        # Filter tags
        if report.get("filters"):
            tags_layout = QHBoxLayout()
            tags_layout.setSpacing(4)
            for filt in report["filters"][:3]:
                tag = QLabel(filt.replace("_", " ").title())
                tag.setStyleSheet(f"""
                    background: {report['color']}20;
                    color: {report['color']};
                    border-radius: 3px;
                    padding: 2px 6px;
                    font-size: 9px;
                    border: none;
                """)
                tags_layout.addWidget(tag)
            tags_layout.addStretch()
            card_layout.addLayout(tags_layout)

        # Click handler
        card.mousePressEvent = lambda event: self._select_report(report_key, card)

        return card

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready – Select a report to generate")
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
    # Report Selection & Management
    # ==================================================================

    def _select_report(self, report_key: str, card: QFrame = None):
        """Select a report."""
        # Deselect all cards
        for child in self.tab_all.findChildren(QFrame):
            if child.property("selected") == "true":
                child.setProperty("selected", "false")
                child.setStyleSheet(child.styleSheet())

        # Select the clicked card
        if card:
            card.setProperty("selected", "true")
            card.setStyleSheet(card.styleSheet())

        self.selected_report = report_key
        report = REPORTS.get(report_key, {})
        
        self.status_bar.showMessage(
            f"Selected: {report.get('name', 'Unknown')} – "
            f"Click 'Generate Report' or double-click to run"
        )

        # Add to recent
        self._add_to_recent(report_key)

    def _toggle_favorite(self, report_key: str, btn: QPushButton):
        """Toggle favorite status for a report."""
        if report_key in self.favorite_reports:
            self.favorite_reports.remove(report_key)
            btn.setText("☆")
        else:
            self.favorite_reports.append(report_key)
            btn.setText("⭐")

        self._save_favorites()
        self._update_favorites_grid()

    def _add_to_recent(self, report_key: str):
        """Add report to recent list."""
        if report_key in self.recent_reports:
            self.recent_reports.remove(report_key)
        
        self.recent_reports.insert(0, report_key)
        
        # Keep only last 10
        if len(self.recent_reports) > 10:
            self.recent_reports = self.recent_reports[:10]

        self._update_recent_table()

    def _update_favorites_grid(self):
        """Update the favorites grid."""
        # Clear grid
        while self.favorites_grid.count():
            item = self.favorites_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.favorite_reports:
            self.favorites_label.setText(
                "⭐ <b>No Favorite Reports</b><br>"
                "Click the star icon on any report to add it to favorites."
            )
            return

        col = 0
        row = 0
        for report_key in self.favorite_reports:
            report = REPORTS.get(report_key)
            if report:
                card = self._build_report_card(report_key, report)
                self.favorites_grid.addWidget(card, row, col)
                col += 1
                if col >= 3:
                    col = 0
                    row += 1

    def _update_recent_table(self):
        """Update the recent reports table."""
        self.recent_table.setRowCount(len(self.recent_reports))

        for row, report_key in enumerate(self.recent_reports):
            report = REPORTS.get(report_key, {})
            
            self.recent_table.setItem(row, 0, QTableWidgetItem(
                f"{report.get('icon', '📄')} {report.get('name', report_key)}"
            ))
            self.recent_table.setItem(row, 1, QTableWidgetItem(
                report.get('category', '')
            ))
            self.recent_table.setItem(row, 2, QTableWidgetItem(
                datetime.now().strftime("%Y-%m-%d %H:%M")
            ))

            # Run again button
            btn_run = QPushButton("🔄 Run Again")
            btn_run.setStyleSheet("""
                QPushButton {
                    background-color: #00897B;
                    color: white;
                    border: none;
                    padding: 4px 10px;
                    font-weight: bold;
                    border-radius: 3px;
                    font-size: 10px;
                }
                QPushButton:hover { background-color: #00695C; }
            """)
            btn_run.clicked.connect(lambda checked, rk=report_key: self._run_report(rk))
            self.recent_table.setCellWidget(row, 3, btn_run)

    # ==================================================================
    # Favorites Persistence
    # ==================================================================

    def _get_favorites_file(self) -> str:
        """Get favorites file path."""
        return os.path.join(
            os.path.dirname(__file__), '..', 'config', 'favorite_reports.json'
        )

    def _load_favorites(self):
        """Load favorite reports from file."""
        fav_file = self._get_favorites_file()
        if os.path.exists(fav_file):
            try:
                with open(fav_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.favorite_reports = data.get('favorites', [])
                    self.recent_reports = data.get('recent', [])
            except Exception:
                self.favorite_reports = []
                self.recent_reports = []

    def _save_favorites(self):
        """Save favorite reports to file."""
        fav_file = self._get_favorites_file()
        os.makedirs(os.path.dirname(fav_file), exist_ok=True)
        
        try:
            with open(fav_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'favorites': self.favorite_reports,
                    'recent': self.recent_reports
                }, f, indent=2)
        except Exception:
            pass

    # ==================================================================
    # Report Generation
    # ==================================================================

    def _generate_report(self):
        """Generate the selected report."""
        if not self.selected_report:
            QMessageBox.warning(self, "No Selection", 
                              "Please select a report first.")
            return

        self._run_report(self.selected_report)

    def _run_report(self, report_key: str):
        """Run a specific report by opening its dialog."""
        report = REPORTS.get(report_key, {})
        
        try:
            if report_key == "inventory_summary":
                from ui.reports_window import ReportsWindow
                dlg = ReportsWindow(self.parent, report_type="inventory", user_role=self.user_role)
                dlg.exec()

            elif report_key == "live_stock":
                from ui.stock_view_dialog import StockViewDialog
                dlg = StockViewDialog(self.parent, user_role=self.user_role)
                dlg.exec()

            elif report_key == "transaction_history":
                from ui.reports_window import ReportsWindow
                dlg = ReportsWindow(self.parent, report_type="transaction", user_role=self.user_role)
                dlg.exec()

            elif report_key == "document_history":
                if self.parent and hasattr(self.parent, 'on_document_history_report'):
                    self.parent.on_document_history_report()
                else:
                    from ui.reports_window import ReportsWindow
                    dlg = ReportsWindow(self.parent, report_type="document_history", user_role=self.user_role)
                    dlg.exec()

            elif report_key == "traceability":
                if self.parent and hasattr(self.parent, 'on_traceability_report'):
                    self.parent.on_traceability_report()
                else:
                    from ui.reports_window import ReportsWindow
                    dlg = ReportsWindow(self.parent, report_type="traceability", user_role=self.user_role)
                    dlg.exec()

            elif report_key == "expiry_report":
                if self.parent and hasattr(self.parent, 'on_expiry_monitor'):
                    self.parent.on_expiry_monitor()
                else:
                    from ui.expiry_monitor_dialog import ExpiryMonitorDialog
                    dlg = ExpiryMonitorDialog(self.parent, user_role=self.user_role)
                    dlg.exec()

            elif report_key == "preservation_report":
                if self.parent and hasattr(self.parent, 'on_preservation_dashboard'):
                    self.parent.on_preservation_dashboard()
                else:
                    from ui.preservation_dialog import PreservationDialog
                    dlg = PreservationDialog(self.parent, user_role=self.user_role)
                    dlg.exec()

            elif report_key == "qc_report":
                from ui.qc_release_dialog import QCReleaseDialog
                dlg = QCReleaseDialog(self.parent, user_role=self.user_role)
                dlg.exec()

            elif report_key == "abc_analysis":
                if self.parent and hasattr(self.parent, 'on_abc_analysis'):
                    self.parent.on_abc_analysis()
                else:
                    from ui.abc_analysis_dialog import ABCAnalysisDialog
                    dlg = ABCAnalysisDialog(self.parent, user_role=self.user_role)
                    dlg.exec()

            elif report_key == "reorder_report":
                if self.parent and hasattr(self.parent, 'on_reorder_calculator'):
                    self.parent.on_reorder_calculator()
                else:
                    from ui.reorder_dialog import ReorderDialog
                    dlg = ReorderDialog(self.parent, user_role=self.user_role)
                    dlg.exec()

            elif report_key == "stock_value":
                from logic.reports import get_stock_value_report
                data = get_stock_value_report()
                if data:
                    self._show_data_preview(data, "Stock Value Report")
                else:
                    QMessageBox.information(self, "No Data", "No stock value data available.")

            elif report_key == "material_request":
                if self.parent and hasattr(self.parent, 'on_material_request_history'):
                    self.parent.on_material_request_history()
                else:
                    from ui.material_request_history_dialog import MaterialRequestHistoryDialog
                    dlg = MaterialRequestHistoryDialog(self.parent, user_role=self.user_role)
                    dlg.exec()

            else:
                QMessageBox.information(
                    self, "Report",
                    f"Report '{report.get('name', report_key)}' is not yet available.\n"
                    "Coming in next version."
                )
                return

            self._add_to_recent(report_key)
            self.report_generated.emit(report_key)
            self.status_bar.showMessage(
                f"Generated: {report.get('name', report_key)}", 5000
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to generate report:\n{str(e)}"
            )

    def _show_data_preview(self, data: List[Dict], title: str):
        """Show a data preview dialog."""
        if not data:
            QMessageBox.information(self, "No Data", "No data to display.")
            return

        # Build HTML preview
        headers = list(data[0].keys())
        html = f"""
        <html>
        <head><style>
            body {{ font-family: 'Segoe UI', Arial; margin: 10px; }}
            h2 {{ color: #004D40; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th {{ background: #004D40; color: white; padding: 6px; text-align: left; font-size: 10px; }}
            td {{ padding: 4px; border-bottom: 1px solid #ddd; font-size: 10px; }}
            tr:nth-child(even) {{ background: #f9f9f9; }}
        </style></head>
        <body>
            <h2>{title}</h2>
            <table>
                <tr>
        """
        
        for h in headers:
            html += f"<th>{h}</th>"
        html += "</tr>"

        for row in data[:50]:  # Limit to 50 rows
            html += "<tr>"
            for h in headers:
                html += f"<td>{row.get(h, '')}</td>"
            html += "</tr>"

        html += """
            </table>
        </body>
        </html>
        """

        with tempfile.NamedTemporaryFile(
            suffix='.html', delete=False, mode='w', encoding='utf-8'
        ) as f:
            f.write(html)
            tmp_path = f.name

        QDesktopServices.openUrl(QUrl.fromLocalFile(tmp_path))

    # ==================================================================
    # Export & Share
    # ==================================================================

    def _export_report(self, format_type: str):
        """Export the main table data from parent."""
        if not self.parent or not hasattr(self.parent, 'table'):
            QMessageBox.warning(self, "Error", "Main table not accessible.")
            return

        table = self.parent.table
        if table.rowCount() == 0:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        format_config = EXPORT_FORMATS.get(format_type, EXPORT_FORMATS["excel"])
        file_path, _ = QFileDialog.getSaveFileName(
            self, f"Export as {format_config['label']}",
            f"report{format_config['ext']}",
            f"{format_config['label']} (*{format_config['ext']})"
        )
        if not file_path:
            return

        try:
            if format_type == "excel":
                if self.parent and hasattr(self.parent, 'on_export_excel'):
                    self.parent.on_export_excel()
            elif format_type == "pdf":
                if self.parent and hasattr(self.parent, 'on_export_pdf'):
                    self.parent.on_export_pdf()
            elif format_type == "html":
                if self.parent and hasattr(self.parent, 'on_export_document_html'):
                    self.parent.on_export_document_html()

            self.status_bar.showMessage(f"Exported as {format_config['label']}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _print_report(self):
        """Print the current report."""
        if self.parent and hasattr(self.parent, 'table'):
            # Open print dialog via parent
            self._export_report("html")

    def _share_whatsapp(self):
        """Share report via WhatsApp."""
        report = REPORTS.get(self.selected_report, {})
        report_name = report.get('name', 'Report') if self.selected_report else 'Report'

        lines = []
        lines.append(f"*📊 {report_name}*")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append("Report generated by iMat Material Control System.")
        lines.append("Please contact for detailed report.")

        message = "%0A".join(lines)
        wa_url = f"https://wa.me/989160684552?text={message}"
        webbrowser.open(wa_url)
        self.status_bar.showMessage("WhatsApp message prepared", 3000)

    def _email_report(self):
        """Send report via email."""
        report = REPORTS.get(self.selected_report, {})
        report_name = report.get('name', 'Report') if self.selected_report else 'Report'

        subject = f"iMat Report: {report_name}"
        body = (
            f"Report: {report_name}%0D%0A"
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}%0D%0A%0D%0A"
            f"Please find the attached report from iMat Material Control System."
        )

        mailto = f"mailto:?subject={subject}&body={body}"
        QDesktopServices.openUrl(QUrl(mailto))
        self.status_bar.showMessage("Email client opened", 3000)

    def closeEvent(self, event):
        """Handle dialog close."""
        self._save_favorites()
        super().closeEvent(event)