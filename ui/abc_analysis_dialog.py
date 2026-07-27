# ui/abc_analysis_dialog.py
"""
ABC Analysis Dialog – iMat Material Control System (EPC Edition).

Performs ABC classification of inventory items based on:
- Total issue quantity (last 365 days)
- Total value (quantity × unit cost)
- User-selectable criteria

Features:
- Interactive Pareto chart (optional matplotlib integration)
- Export to Excel/PDF
- Color-coded classification table
- Multiple analysis methods
- Drill-down to item details
- Customizable A/B/C thresholds
- Print and copy functionality
"""

import os
import tempfile
import webbrowser
from datetime import date, timedelta
from typing import List, Dict, Tuple, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QStatusBar, QComboBox, QDoubleSpinBox, QFormLayout,
    QGroupBox, QRadioButton, QButtonGroup, QMessageBox,
    QFileDialog, QApplication, QWidget, QSplitter,
    QTextEdit, QAbstractItemView, QMenu, QToolBar
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QAction, QPainter, QBrush, QPen

from sqlalchemy import func
from db.database import get_db_session, SessionLocal
from db.models import Transaction, Product, Stock
from ai.optimizer import InventoryOptimizer
from ui.logo_widget import LogoWidget
from utils.excel_export import export_to_excel
from utils.pdf_export import export_to_pdf

# Optional matplotlib import for charting
try:
    import matplotlib
    matplotlib.use('QtAgg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


# ==================================================================
# Constants
# ==================================================================

DEFAULT_A_THRESHOLD = 70.0  # Percentage for Class A
DEFAULT_B_THRESHOLD = 90.0  # Percentage for Class B (rest is Class C)

CLASS_COLORS = {
    "A": {"bg": "#FFCDD2", "fg": "#B71C1C", "label": "A - High Value"},
    "B": {"bg": "#FFF9C4", "fg": "#F57F17", "label": "B - Medium Value"},
    "C": {"bg": "#C8E6C9", "fg": "#1B5E20", "label": "C - Low Value"},
}

CLASS_DESCRIPTIONS = {
    "A": "High-value items (~70% of total value, ~10% of items)\n"
         "• Tight control required\n"
         "• Frequent review\n"
         "• Accurate forecasting",
    "B": "Medium-value items (~20% of total value, ~20% of items)\n"
         "• Moderate control\n"
         "• Regular review\n"
         "• Normal forecasting",
    "C": "Low-value items (~10% of total value, ~70% of items)\n"
         "• Simple control\n"
         "• Periodic review\n"
         "• Basic forecasting",
}


# ==================================================================
# ABC Analysis Dialog
# ==================================================================

class ABCAnalysisDialog(QDialog):
    """
    ABC Analysis dialog for inventory classification.
    
    Classifies items into A, B, C categories based on cumulative
    value or quantity, following the Pareto principle (80/20 rule).
    """

    # Signal emitted when analysis is complete
    analysis_complete = pyqtSignal(dict)

    def __init__(self, parent=None, user_role: str = "viewer"):
        """
        Initialize the ABC Analysis dialog.
        
        Args:
            parent: Parent widget
            user_role: Current user's role for access control
        """
        super().__init__(parent)
        self.user_role = user_role
        self.parent = parent
        
        # Analysis data
        self.all_data: List[Dict] = []
        self.classified_data: List[Dict] = []
        self.total_value: float = 0.0
        self.a_threshold = DEFAULT_A_THRESHOLD
        self.b_threshold = DEFAULT_B_THRESHOLD
        
        # Window setup
        self.setWindowTitle("iMat – ABC Analysis (Pareto Classification)")
        self.setMinimumSize(1100, 700)
        self.setModal(True)
        
        # Build UI
        self._init_ui()
        
        # Load data and run analysis
        self._load_analysis_options()
        self._run_analysis()
        
        # Apply role restrictions
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
        self._build_control_panel(main_layout)
        self._build_content_area(main_layout)
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

        # Logo
        self.logo_widget = LogoWidget()
        header_layout.addWidget(self.logo_widget)

        # Title
        title = QLabel("📊 ABC Analysis")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Subtitle
        self.subtitle = QLabel("Pareto Classification of Inventory Items")
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

        # Refresh
        self.action_refresh = toolbar.addAction("🔄 Refresh")
        self.action_refresh.setToolTip("Re-run analysis with current settings")
        self.action_refresh.triggered.connect(self._run_analysis)
        toolbar.addSeparator()

        # Export actions
        self.action_export_excel = toolbar.addAction("📥 Export Excel")
        self.action_export_excel.setToolTip("Export analysis to Excel")
        self.action_export_excel.triggered.connect(self._export_excel)
        
        self.action_export_pdf = toolbar.addAction("📑 Export PDF")
        self.action_export_pdf.setToolTip("Export analysis to PDF")
        self.action_export_pdf.triggered.connect(self._export_pdf)
        toolbar.addSeparator()

        # Copy and Print
        self.action_copy = toolbar.addAction("📋 Copy to Clipboard")
        self.action_copy.setToolTip("Copy table to clipboard")
        self.action_copy.triggered.connect(self._copy_to_clipboard)
        
        self.action_print = toolbar.addAction("🖨️ Print Report")
        self.action_print.setToolTip("Print analysis report")
        self.action_print.triggered.connect(self._print_report)
        toolbar.addSeparator()

        # View details
        self.action_view_item = toolbar.addAction("🔍 View Selected Item")
        self.action_view_item.setToolTip("View details of selected item")
        self.action_view_item.triggered.connect(self._view_selected_item)

        parent_layout.addWidget(toolbar)

    def _build_control_panel(self, parent_layout: QVBoxLayout):
        """Build the analysis control panel."""
        control_frame = QFrame()
        control_frame.setStyleSheet("""
            QFrame {
                background: #F5F5F5;
                border-bottom: 1px solid #CCC;
            }
        """)
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(15, 10, 15, 10)
        control_layout.setSpacing(20)

        # Analysis method selection
        method_group = QGroupBox("Analysis Method")
        method_layout = QVBoxLayout(method_group)
        
        self.radio_quantity = QRadioButton("By Issue Quantity")
        self.radio_value = QRadioButton("By Total Value (Qty × Cost)")
        self.radio_quantity.setChecked(True)
        
        self.method_group = QButtonGroup(self)
        self.method_group.addButton(self.radio_quantity, 1)
        self.method_group.addButton(self.radio_value, 2)
        self.method_group.buttonClicked.connect(self._on_method_changed)
        
        method_layout.addWidget(self.radio_quantity)
        method_layout.addWidget(self.radio_value)
        control_layout.addWidget(method_group)

        # Time period selection
        period_group = QGroupBox("Analysis Period")
        period_layout = QVBoxLayout(period_group)
        
        self.period_combo = QComboBox()
        self.period_combo.addItems([
            "Last 30 Days",
            "Last 90 Days",
            "Last 180 Days",
            "Last 365 Days",
            "All Time"
        ])
        self.period_combo.setCurrentIndex(3)  # Default: Last 365 Days
        self.period_combo.currentIndexChanged.connect(self._on_period_changed)
        
        period_layout.addWidget(self.period_combo)
        control_layout.addWidget(period_group)

        # Threshold settings
        threshold_group = QGroupBox("Classification Thresholds")
        threshold_layout = QFormLayout(threshold_group)
        
        self.a_spin = QDoubleSpinBox()
        self.a_spin.setRange(30.0, 90.0)
        self.a_spin.setValue(DEFAULT_A_THRESHOLD)
        self.a_spin.setSuffix("%")
        self.a_spin.setToolTip("Cumulative percentage threshold for Class A")
        self.a_spin.valueChanged.connect(self._on_threshold_changed)
        
        self.b_spin = QDoubleSpinBox()
        self.b_spin.setRange(50.0, 99.0)
        self.b_spin.setValue(DEFAULT_B_THRESHOLD)
        self.b_spin.setSuffix("%")
        self.b_spin.setToolTip("Cumulative percentage threshold for Class B")
        self.b_spin.valueChanged.connect(self._on_threshold_changed)
        
        threshold_layout.addRow("Class A up to:", self.a_spin)
        threshold_layout.addRow("Class B up to:", self.b_spin)
        control_layout.addWidget(threshold_group)

        # Filter by discipline
        filter_group = QGroupBox("Filter")
        filter_layout = QVBoxLayout(filter_group)
        
        self.discipline_combo = QComboBox()
        self.discipline_combo.addItem("All Disciplines")
        self.discipline_combo.currentIndexChanged.connect(self._on_filter_changed)
        
        filter_layout.addWidget(self.discipline_combo)
        control_layout.addWidget(filter_group)

        control_layout.addStretch()
        parent_layout.addWidget(control_frame)

    def _build_content_area(self, parent_layout: QVBoxLayout):
        """Build the main content area with table and summary."""
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Summary panel
        summary_frame = QFrame()
        summary_frame.setStyleSheet("""
            QFrame {
                background: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        summary_layout = QVBoxLayout(summary_frame)
        
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("font-size: 12px; line-height: 1.6;")
        summary_layout.addWidget(self.summary_label)
        
        splitter.addWidget(summary_frame)

        # Main table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "#", "Item Code", "Description", "Discipline",
            "Total Value", "Cumulative %", "Class", "Category"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._view_selected_item)
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
                padding: 6px;
            }
        """)
        
        # Set column widths
        column_widths = [40, 120, 200, 100, 120, 100, 60, 120]
        for i, width in enumerate(column_widths):
            self.table.setColumnWidth(i, width)
        
        splitter.addWidget(self.table)
        
        # Set initial sizes (30% summary, 70% table)
        splitter.setSizes([150, 450])
        
        parent_layout.addWidget(splitter)

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready – Click Refresh to re-run analysis")
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
        """Apply role-based access restrictions."""
        if self.user_role == "viewer":
            # Viewers can only view, not export
            self.action_export_excel.setEnabled(False)
            self.action_export_pdf.setEnabled(False)
            self.action_copy.setEnabled(True)  # Can still copy
            self.action_print.setEnabled(False)
            self.radio_quantity.setEnabled(False)
            self.radio_value.setEnabled(False)
            self.period_combo.setEnabled(False)
            self.a_spin.setEnabled(False)
            self.b_spin.setEnabled(False)
            self.status_bar.showMessage("Read-only mode – Viewing ABC Analysis")

    # ==================================================================
    # Data Loading & Analysis
    # ==================================================================

    def _load_analysis_options(self):
        """Load filter options (disciplines) from database."""
        session = get_db_session()
        try:
            disciplines = session.query(Product.discipline).distinct().order_by(
                Product.discipline
            ).all()
            self.discipline_combo.blockSignals(True)
            self.discipline_combo.clear()
            self.discipline_combo.addItem("All Disciplines")
            for (d,) in disciplines:
                if d:
                    self.discipline_combo.addItem(d)
            self.discipline_combo.blockSignals(False)
        except Exception as e:
            self.status_bar.showMessage(f"Error loading options: {e}")
        finally:
            session.close()

    def _get_analysis_days(self) -> int:
        """Get the number of days for the analysis period."""
        period_map = {
            0: 30,
            1: 90,
            2: 180,
            3: 365,
            4: 9999,  # All time
        }
        return period_map.get(self.period_combo.currentIndex(), 365)

    def _run_analysis(self):
        """Execute the ABC analysis."""
        self.status_bar.showMessage("Running analysis...")
        QApplication.processEvents()

        session = get_db_session()
        try:
            days = self._get_analysis_days()
            use_value = self.radio_value.isChecked()
            discipline_filter = self.discipline_combo.currentText()
            
            if discipline_filter == "All Disciplines":
                discipline_filter = None

            # Get analysis data
            if use_value:
                self.all_data = self._get_value_analysis(session, days, discipline_filter)
            else:
                self.all_data = self._get_quantity_analysis(session, days, discipline_filter)

            if not self.all_data:
                self.table.setRowCount(0)
                self.summary_label.setText("No data available for the selected criteria.")
                self.status_bar.showMessage("No data found", 3000)
                return

            # Classify items
            self._classify_items()
            
            # Display results
            self._display_results()
            
            # Update summary
            self._update_summary()
            
            # Emit signal
            self.analysis_complete.emit(self._get_analysis_summary())
            
            self.status_bar.showMessage(
                f"Analysis complete – {len(self.classified_data)} items classified",
                5000
            )

        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", f"Failed to run analysis:\n{str(e)}")
            self.status_bar.showMessage("Analysis failed")
        finally:
            session.close()

    def _get_quantity_analysis(self, session, days: int, discipline: Optional[str]) -> List[Dict]:
        """Get analysis data based on issue quantity."""
        since = date.today() - timedelta(days=days) if days < 9999 else date(2000, 1, 1)
        
        query = session.query(
            Transaction.item_code,
            func.sum(Transaction.issue_qty).label('total_issue')
        ).filter(
            Transaction.doc_type.in_(["MIV", "ISS", "WOM", "GAT"]),
            Transaction.doc_date >= since
        )

        if discipline_filter:
            query = query.join(Product, Transaction.item_code == Product.item_code).filter(
                Product.discipline == discipline_filter
            )

        items = query.group_by(Transaction.item_code).all()

        data = []
        for item_code, total_issue in items:
            if total_issue and total_issue > 0:
                product = session.query(Product).filter_by(item_code=item_code).first()
                data.append({
                    "item_code": item_code,
                    "description": product.description if product else "",
                    "discipline": product.discipline if product else "",
                    "category": product.category if product else "",
                    "total_value": float(total_issue),
                    "unit_cost": product.unit_cost if product else 0,
                })
        return data

    def _get_value_analysis(self, session, days: int, discipline: Optional[str]) -> List[Dict]:
        """Get analysis data based on total value (quantity × unit cost)."""
        since = date.today() - timedelta(days=days) if days < 9999 else date(2000, 1, 1)

        query = session.query(
            Transaction.item_code,
            func.sum(Transaction.issue_qty).label('total_issue')
        ).filter(
            Transaction.doc_type.in_(["MIV", "ISS", "WOM", "GAT"]),
            Transaction.doc_date >= since
        )

        if discipline_filter:
            query = query.join(Product, Transaction.item_code == Product.item_code).filter(
                Product.discipline == discipline_filter
            )

        items = query.group_by(Transaction.item_code).all()

        data = []
        for item_code, total_issue in items:
            if total_issue and total_issue > 0:
                product = session.query(Product).filter_by(item_code=item_code).first()
                unit_cost = product.unit_cost if product and product.unit_cost else 1.0
                total_value = float(total_issue) * unit_cost
                data.append({
                    "item_code": item_code,
                    "description": product.description if product else "",
                    "discipline": product.discipline if product else "",
                    "category": product.category if product else "",
                    "total_value": total_value,
                    "unit_cost": unit_cost,
                })
        return data

    def _classify_items(self):
        """Classify items into A, B, C categories."""
        self.a_threshold = self.a_spin.value() / 100.0
        self.b_threshold = self.b_spin.value() / 100.0

        # Sort by value descending
        sorted_data = sorted(self.all_data, key=lambda x: x["total_value"], reverse=True)
        self.total_value = sum(item["total_value"] for item in sorted_data)

        cumulative = 0.0
        self.classified_data = []
        
        for item in sorted_data:
            cumulative += item["total_value"]
            cum_ratio = cumulative / self.total_value if self.total_value > 0 else 0
            
            if cum_ratio <= self.a_threshold:
                item["class"] = "A"
            elif cum_ratio <= self.b_threshold:
                item["class"] = "B"
            else:
                item["class"] = "C"
            
            item["cumulative_pct"] = round(cum_ratio * 100, 2)
            self.classified_data.append(item)

    def _display_results(self):
        """Display classified data in the table."""
        self.table.setRowCount(len(self.classified_data))
        
        for row, item in enumerate(self.classified_data):
            # Row number
            row_item = QTableWidgetItem(str(row + 1))
            row_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, row_item)
            
            # Item Code
            self.table.setItem(row, 1, QTableWidgetItem(item["item_code"]))
            
            # Description
            self.table.setItem(row, 2, QTableWidgetItem(item.get("description", "")))
            
            # Discipline
            self.table.setItem(row, 3, QTableWidgetItem(item.get("discipline", "")))
            
            # Total Value
            value_item = QTableWidgetItem(f"{item['total_value']:,.2f}")
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 4, value_item)
            
            # Cumulative %
            cum_item = QTableWidgetItem(f"{item['cumulative_pct']:.1f}%")
            cum_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 5, cum_item)
            
            # Class with color
            class_item = QTableWidgetItem(item["class"])
            class_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            class_item.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            
            class_config = CLASS_COLORS.get(item["class"], CLASS_COLORS["C"])
            class_item.setBackground(QColor(class_config["bg"]))
            class_item.setForeground(QColor(class_config["fg"]))
            self.table.setItem(row, 6, class_item)
            
            # Category
            self.table.setItem(row, 7, QTableWidgetItem(item.get("category", "")))

    def _update_summary(self):
        """Update the summary panel with analysis statistics."""
        if not self.classified_data:
            return

        # Count by class
        class_counts = {"A": 0, "B": 0, "C": 0}
        class_values = {"A": 0.0, "B": 0.0, "C": 0.0}
        
        for item in self.classified_data:
            cls = item["class"]
            class_counts[cls] += 1
            class_values[cls] += item["total_value"]

        total_items = len(self.classified_data)

        summary_html = f"""
        <div style="font-family: 'Segoe UI', Arial; line-height: 1.8;">
            <h3 style="color: #004D40; margin-bottom: 10px;">📊 ABC Analysis Summary</h3>
            <p><b>Analysis Period:</b> {self.period_combo.currentText()}</p>
            <p><b>Method:</b> {"Total Value (Qty × Cost)" if self.radio_value.isChecked() else "Issue Quantity"}</p>
            <p><b>Total Items:</b> {total_items} | <b>Total Value:</b> {self.total_value:,.2f}</p>
            <hr>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #004D40; color: white;">
                    <th style="padding: 8px;">Class</th>
                    <th style="padding: 8px;">Items</th>
                    <th style="padding: 8px;">% of Items</th>
                    <th style="padding: 8px;">Value</th>
                    <th style="padding: 8px;">% of Value</th>
                </tr>
        """
        
        for cls in ["A", "B", "C"]:
            config = CLASS_COLORS[cls]
            count = class_counts[cls]
            value = class_values[cls]
            pct_items = (count / total_items * 100) if total_items > 0 else 0
            pct_value = (value / self.total_value * 100) if self.total_value > 0 else 0
            
            summary_html += f"""
                <tr style="background: {config['bg']}; color: {config['fg']};">
                    <td style="padding: 6px; font-weight: bold;">Class {cls}</td>
                    <td style="padding: 6px; text-align: center;">{count}</td>
                    <td style="padding: 6px; text-align: center;">{pct_items:.1f}%</td>
                    <td style="padding: 6px; text-align: right;">{value:,.2f}</td>
                    <td style="padding: 6px; text-align: center;">{pct_value:.1f}%</td>
                </tr>
            """
        
        summary_html += """
            </table>
            <hr>
            <p style="font-size: 10px; color: #666;">
                💡 <b>Recommendation:</b> Focus inventory control efforts on Class A items.
                These represent the highest value and should have tight control and frequent review.
            </p>
        </div>
        """
        
        self.summary_label.setText(summary_html)

    def _get_analysis_summary(self) -> Dict:
        """Get summary dictionary of the analysis."""
        class_counts = {"A": 0, "B": 0, "C": 0}
        class_values = {"A": 0.0, "B": 0.0, "C": 0.0}
        
        for item in self.classified_data:
            cls = item["class"]
            class_counts[cls] += 1
            class_values[cls] += item["total_value"]

        return {
            "total_items": len(self.classified_data),
            "total_value": self.total_value,
            "class_counts": class_counts,
            "class_values": class_values,
            "a_threshold": self.a_threshold,
            "b_threshold": self.b_threshold,
            "method": "value" if self.radio_value.isChecked() else "quantity",
            "period": self.period_combo.currentText(),
        }

    # ==================================================================
    # Event Handlers
    # ==================================================================

    def _on_method_changed(self, button):
        """Handle analysis method change."""
        self._run_analysis()

    def _on_period_changed(self, index):
        """Handle period change."""
        self._run_analysis()

    def _on_threshold_changed(self, value):
        """Handle threshold change with debounce."""
        if hasattr(self, '_threshold_timer'):
            self._threshold_timer.stop()
        from PyQt6.QtCore import QTimer
        self._threshold_timer = QTimer(self)
        self._threshold_timer.setSingleShot(True)
        self._threshold_timer.setInterval(500)
        self._threshold_timer.timeout.connect(self._run_analysis)
        self._threshold_timer.start()

    def _on_filter_changed(self, index):
        """Handle discipline filter change."""
        self._run_analysis()

    def _show_context_menu(self, pos):
        """Show context menu on table right-click."""
        row = self.table.currentRow()
        if row < 0:
            return

        menu = QMenu(self)
        menu.addAction("🔍 View Item Details", self._view_selected_item)
        menu.addAction("📋 Copy Row", self._copy_selected_row)
        menu.addSeparator()
        menu.addAction("📊 Show Class A Items Only", lambda: self._filter_by_class("A"))
        menu.addAction("📊 Show Class B Items Only", lambda: self._filter_by_class("B"))
        menu.addAction("📊 Show Class C Items Only", lambda: self._filter_by_class("C"))
        menu.addAction("📊 Show All Items", lambda: self._filter_by_class(None))
        
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ==================================================================
    # Actions
    # ==================================================================

    def _view_selected_item(self):
        """View details of the selected item."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an item first.")
            return

        item_code = self.table.item(row, 1).text()
        item = next((i for i in self.classified_data if i["item_code"] == item_code), None)
        
        if item:
            cls = item["class"]
            config = CLASS_COLORS.get(cls, CLASS_COLORS["C"])
            
            details = f"""
            <div style="font-family: 'Segoe UI', Arial;">
                <h3 style="color: #004D40;">Item Details</h3>
                <p><b>Item Code:</b> {item['item_code']}</p>
                <p><b>Description:</b> {item.get('description', 'N/A')}</p>
                <p><b>Discipline:</b> {item.get('discipline', 'N/A')}</p>
                <p><b>Category:</b> {item.get('category', 'N/A')}</p>
                <p><b>Unit Cost:</b> {item.get('unit_cost', 0):,.2f}</p>
                <hr>
                <p><b>Total Value:</b> {item['total_value']:,.2f}</p>
                <p><b>Cumulative %:</b> {item['cumulative_pct']:.1f}%</p>
                <p style="color: {config['fg']}; font-weight: bold;">
                    Classification: Class {cls}
                </p>
                <hr>
                <p style="font-size: 10px; color: #666; white-space: pre-line;">
                    {CLASS_DESCRIPTIONS.get(cls, '')}
                </p>
            </div>
            """
            QMessageBox.information(self, f"Item Details - {item_code}", details)

    def _filter_by_class(self, class_filter: Optional[str]):
        """Filter table to show only items of a specific class."""
        for row in range(self.table.rowCount()):
            if class_filter is None:
                self.table.setRowHidden(row, False)
            else:
                class_item = self.table.item(row, 6)
                if class_item:
                    self.table.setRowHidden(row, class_item.text() != class_filter)

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

    def _copy_to_clipboard(self):
        """Copy entire table to clipboard."""
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "No Data", "Nothing to copy.")
            return

        headers = [
            self.table.horizontalHeaderItem(c).text()
            for c in range(self.table.columnCount())
        ]
        lines = ["\t".join(headers)]
        
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                row_data = []
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    row_data.append(item.text() if item else "")
                lines.append("\t".join(row_data))

        QApplication.clipboard().setText("\n".join(lines))
        self.status_bar.showMessage("Table copied to clipboard", 3000)

    def _export_excel(self):
        """Export analysis to Excel."""
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export ABC Analysis", "abc_analysis.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
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

            export_to_excel(data, headers, file_path, sheet_name="ABC Analysis")
            self.status_bar.showMessage(f"Exported to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _export_pdf(self):
        """Export analysis to PDF."""
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "No Data", "Nothing to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export ABC Analysis", "abc_analysis.pdf",
            "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        try:
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

            export_to_pdf(data, headers, file_path, title="ABC Analysis Report")
            self.status_bar.showMessage(f"PDF saved to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _print_report(self):
        """Print the analysis report as HTML."""
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "No Data", "Nothing to print.")
            return

        # Generate HTML report
        summary = self._get_analysis_summary()
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>ABC Analysis Report</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial; margin: 20px; }}
                h1 {{ color: #004D40; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
                th {{ background: #004D40; color: white; padding: 8px; text-align: left; }}
                td {{ padding: 6px; border-bottom: 1px solid #ddd; }}
                .class-A {{ background: #FFCDD2; }}
                .class-B {{ background: #FFF9C4; }}
                .class-C {{ background: #C8E6C9; }}
                .summary {{ margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>📊 ABC Analysis Report</h1>
            <div class="summary">
                <p><b>Period:</b> {self.period_combo.currentText()}</p>
                <p><b>Total Items:</b> {summary['total_items']}</p>
                <p><b>Total Value:</b> {summary['total_value']:,.2f}</p>
            </div>
            <table>
                <tr>
                    <th>#</th>
                    <th>Item Code</th>
                    <th>Description</th>
                    <th>Discipline</th>
                    <th>Total Value</th>
                    <th>Cumulative %</th>
                    <th>Class</th>
                </tr>
        """
        
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                item_code = self.table.item(row, 1).text()
                desc = self.table.item(row, 2).text()
                disc = self.table.item(row, 3).text()
                value = self.table.item(row, 4).text()
                cum = self.table.item(row, 5).text()
                cls = self.table.item(row, 6).text()
                
                html += f"""
                <tr class="class-{cls}">
                    <td>{row + 1}</td>
                    <td>{item_code}</td>
                    <td>{desc}</td>
                    <td>{disc}</td>
                    <td>{value}</td>
                    <td>{cum}</td>
                    <td><b>{cls}</b></td>
                </tr>
                """
        
        html += """
            </table>
        </body>
        </html>
        """
        
        # Open in browser for printing
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as f:
            f.write(html)
            tmp_path = f.name
        
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(tmp_path))
        self.status_bar.showMessage("Report opened in browser for printing", 4000)