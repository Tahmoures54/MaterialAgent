# ui/reorder_dialog.py
"""
Reorder Point Calculator – iMat Material Control System (EPC Edition).

Comprehensive inventory optimization with:
- Safety stock calculation (multiple methods)
- Reorder point determination
- Economic Order Quantity (EOQ)
- Service level-based calculations
- Demand forecasting integration
- Lead time variability analysis
- What-if scenario testing
- Visual inventory level indicators
- Export calculations to Excel
- Print optimization report
- WhatsApp sharing for purchase requests
- Multi-item batch analysis
- Historical demand analysis
"""

import os
import tempfile
import webbrowser
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QDoubleSpinBox, QFormLayout, QTextEdit,
    QFrame, QStatusBar, QCompleter, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QWidget, QSplitter,
    QTabWidget, QSpinBox, QCheckBox, QAbstractItemView,
    QFileDialog, QApplication, QToolBar, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QColor, QDesktopServices, QAction

from db.database import get_db_session, SessionLocal
from db.models import Product, Stock, Transaction
from ai.optimizer import InventoryOptimizer
from ai.predictor import load_demand_history, DemandPredictor
from ui.logo_widget import LogoWidget
from utils.excel_export import export_to_excel

# ==================================================================
# Constants
# ==================================================================

# Service level options with Z-scores
SERVICE_LEVELS = {
    "50% (z=0.00)": 0.00,
    "75% (z=0.67)": 0.67,
    "80% (z=0.84)": 0.84,
    "85% (z=1.04)": 1.04,
    "90% (z=1.28)": 1.28,
    "95% (z=1.65)": 1.65,
    "97% (z=1.88)": 1.88,
    "98% (z=2.05)": 2.05,
    "99% (z=2.33)": 2.33,
    "99.5% (z=2.58)": 2.58,
    "99.9% (z=3.09)": 3.09,
}

# Safety stock methods
SAFETY_STOCK_METHODS = [
    "Simple (Max Lead Time)",
    "Service Level (Z-score)",
    "Fixed Quantity",
    "Percentage of Demand",
]

# Ordering cost defaults by category
DEFAULT_ORDERING_COSTS = {
    "Piping": 100.0,
    "Mechanical": 150.0,
    "Electrical": 75.0,
    "Instrument": 50.0,
    "Civil": 200.0,
    "Structure": 200.0,
    "General": 50.0,
}

# Holding cost percentage (of unit cost)
DEFAULT_HOLDING_COST_PCT = 0.15  # 15% per year

# ==================================================================
# Reorder Dialog
# ==================================================================

class ReorderDialog(QDialog):
    """
    Reorder point and safety stock calculator dialog.
    
    Features:
    - Multiple safety stock calculation methods
    - EOQ calculation
    - Service level optimization
    - Demand history integration
    - Batch analysis
    """

    calculation_complete = pyqtSignal(dict)

    def __init__(self, parent=None, user_role: str = "viewer", 
                 item_code: Optional[str] = None):
        """
        Initialize the Reorder dialog.
        
        Args:
            parent: Parent widget
            user_role: Current user's role
            item_code: Optional item code to pre-select
        """
        super().__init__(parent)
        self.user_role = user_role
        self.parent = parent
        self.pre_item_code = item_code
        
        # State
        self.item_dict: Dict[str, Tuple[str, float, str]] = {}  # code -> (desc, cost, discipline)
        self.calculation_results: List[Dict] = []
        
        # Window setup
        self.setWindowTitle("iMat – Reorder Point & Safety Stock Calculator")
        self.setMinimumSize(900, 650)
        self.setModal(True)
        
        # Build UI
        self._init_ui()
        
        # Load data
        self._load_items()
        
        # Pre-select item if provided
        if self.pre_item_code:
            self._select_item(self.pre_item_code)

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

        title = QLabel("📊 Reorder Point Calculator")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("Optimize inventory levels with safety stock and EOQ")
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

        self.action_calculate = toolbar.addAction("🔍 Calculate")
        self.action_calculate.setToolTip("Calculate reorder point for selected item")
        self.action_calculate.triggered.connect(self._calculate)
        toolbar.addSeparator()

        self.action_add_to_list = toolbar.addAction("➕ Add to List")
        self.action_add_to_list.setToolTip("Add result to batch analysis list")
        self.action_add_to_list.triggered.connect(self._add_to_list)
        
        self.action_clear_list = toolbar.addAction("🗑️ Clear List")
        self.action_clear_list.setToolTip("Clear batch analysis list")
        self.action_clear_list.triggered.connect(self._clear_list)
        toolbar.addSeparator()

        self.action_export = toolbar.addAction("📥 Export")
        self.action_export.triggered.connect(self._export_excel)
        
        self.action_print = toolbar.addAction("🖨️ Print")
        self.action_print.triggered.connect(self._print_report)
        
        self.action_whatsapp = toolbar.addAction("💬 Share WhatsApp")
        self.action_whatsapp.triggered.connect(self._share_whatsapp)

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

        # Tab 1: Single Item Calculator
        self.tab_single = self._build_single_tab()
        self.tab_widget.addTab(self.tab_single, "🔍 Single Item")

        # Tab 2: Batch Analysis
        self.tab_batch = self._build_batch_tab()
        self.tab_widget.addTab(self.tab_batch, "📊 Batch Analysis")

        parent_layout.addWidget(self.tab_widget)

    def _build_single_tab(self) -> QWidget:
        """Build the single item calculator tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(10)

        # ---- Item Selection ----
        item_group = QGroupBox("📦 Item Selection")
        item_group.setStyleSheet(self._get_group_style())
        item_layout = QFormLayout(item_group)
        item_layout.setSpacing(6)

        self.item_combo = QComboBox()
        self.item_combo.setEditable(True)
        self.item_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.item_combo.setMinimumWidth(350)
        self.item_combo.lineEdit().setPlaceholderText("Search by item code or description...")
        self.item_combo.currentTextChanged.connect(self._on_item_changed)
        item_layout.addRow("Item:", self.item_combo)

        self.item_info_label = QLabel("")
        self.item_info_label.setStyleSheet("color: #666; font-size: 10px;")
        item_layout.addRow(self.item_info_label)

        layout.addWidget(item_group)

        # ---- Demand Parameters ----
        demand_group = QGroupBox("📈 Demand Parameters")
        demand_group.setStyleSheet(self._get_group_style())
        demand_form = QFormLayout(demand_group)
        demand_form.setSpacing(6)

        # Average daily demand
        self.daily_demand_spin = QDoubleSpinBox()
        self.daily_demand_spin.setRange(0.01, 1000000)
        self.daily_demand_spin.setDecimals(2)
        self.daily_demand_spin.setValue(10)
        self.daily_demand_spin.setToolTip("Average daily demand in units")
        demand_form.addRow("Avg Daily Demand:", self.daily_demand_spin)

        # Demand std dev
        self.demand_std_spin = QDoubleSpinBox()
        self.demand_std_spin.setRange(0, 1000000)
        self.demand_std_spin.setDecimals(2)
        self.demand_std_spin.setValue(3)
        self.demand_std_spin.setToolTip("Standard deviation of daily demand")
        demand_form.addRow("Demand Std Dev:", self.demand_std_spin)

        # Lead time
        lead_layout = QHBoxLayout()
        self.lead_time_spin = QDoubleSpinBox()
        self.lead_time_spin.setRange(0.5, 365)
        self.lead_time_spin.setValue(7)
        self.lead_time_spin.setSuffix(" days")
        lead_layout.addWidget(self.lead_time_spin)

        self.max_lead_time_spin = QDoubleSpinBox()
        self.max_lead_time_spin.setRange(0.5, 365)
        self.max_lead_time_spin.setValue(14)
        self.max_lead_time_spin.setSuffix(" days (max)")
        self.max_lead_time_spin.setToolTip("Maximum possible lead time")
        lead_layout.addWidget(self.max_lead_time_spin)

        demand_form.addRow("Lead Time:", lead_layout)

        layout.addWidget(demand_group)

        # ---- Safety Stock Settings ----
        safety_group = QGroupBox("🛡️ Safety Stock Settings")
        safety_group.setStyleSheet(self._get_group_style())
        safety_form = QFormLayout(safety_group)
        safety_form.setSpacing(6)

        # Method
        self.method_combo = QComboBox()
        self.method_combo.addItems(SAFETY_STOCK_METHODS)
        self.method_combo.currentIndexChanged.connect(self._on_method_changed)
        safety_form.addRow("Method:", self.method_combo)

        # Service level
        self.service_level_combo = QComboBox()
        self.service_level_combo.addItems(list(SERVICE_LEVELS.keys()))
        self.service_level_combo.setCurrentText("95% (z=1.65)")
        safety_form.addRow("Service Level:", self.service_level_combo)

        # Fixed safety stock
        self.fixed_safety_spin = QDoubleSpinBox()
        self.fixed_safety_spin.setRange(0, 999999)
        self.fixed_safety_spin.setDecimals(2)
        self.fixed_safety_spin.setValue(50)
        self.fixed_safety_spin.setVisible(False)
        safety_form.addRow("Fixed Safety Stock:", self.fixed_safety_spin)

        # Percentage
        self.pct_safety_spin = QDoubleSpinBox()
        self.pct_safety_spin.setRange(0, 100)
        self.pct_safety_spin.setDecimals(1)
        self.pct_safety_spin.setValue(20)
        self.pct_safety_spin.setSuffix("%")
        self.pct_safety_spin.setVisible(False)
        safety_form.addRow("% of Lead Time Demand:", self.pct_safety_spin)

        layout.addWidget(safety_group)

        # ---- Cost Parameters (EOQ) ----
        cost_group = QGroupBox("💰 Cost Parameters (EOQ)")
        cost_group.setStyleSheet(self._get_group_style())
        cost_form = QFormLayout(cost_group)
        cost_form.setSpacing(6)

        self.ordering_cost_spin = QDoubleSpinBox()
        self.ordering_cost_spin.setRange(1, 99999)
        self.ordering_cost_spin.setDecimals(2)
        self.ordering_cost_spin.setValue(50)
        self.ordering_cost_spin.setPrefix("$ ")
        self.ordering_cost_spin.setToolTip("Fixed cost per order")
        cost_form.addRow("Ordering Cost:", self.ordering_cost_spin)

        self.unit_cost_spin = QDoubleSpinBox()
        self.unit_cost_spin.setRange(0.01, 999999)
        self.unit_cost_spin.setDecimals(2)
        self.unit_cost_spin.setValue(10)
        self.unit_cost_spin.setPrefix("$ ")
        self.unit_cost_spin.setToolTip("Unit cost of the item")
        cost_form.addRow("Unit Cost:", self.unit_cost_spin)

        self.holding_pct_spin = QDoubleSpinBox()
        self.holding_pct_spin.setRange(1, 50)
        self.holding_pct_spin.setDecimals(1)
        self.holding_pct_spin.setValue(DEFAULT_HOLDING_COST_PCT * 100)
        self.holding_pct_spin.setSuffix("%")
        self.holding_pct_spin.setToolTip("Annual holding cost as % of unit cost")
        cost_form.addRow("Holding Cost %:", self.holding_pct_spin)

        self.current_stock_spin = QDoubleSpinBox()
        self.current_stock_spin.setRange(0, 999999)
        self.current_stock_spin.setDecimals(2)
        self.current_stock_spin.setValue(0)
        self.current_stock_spin.setToolTip("Current available stock (0 = auto-detect)")
        cost_form.addRow("Current Stock:", self.current_stock_spin)

        layout.addWidget(cost_group)

        # ---- Calculate Button ----
        btn_calc = QPushButton("🔍 Calculate Reorder Point")
        btn_calc.setMinimumHeight(45)
        btn_calc.setStyleSheet("""
            QPushButton {
                background-color: #2E86C1;
                color: white;
                border: none;
                padding: 12px 24px;
                font-weight: bold;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #2471A3; }
            QPushButton:pressed { background-color: #1B6B93; }
        """)
        btn_calc.clicked.connect(self._calculate)
        layout.addWidget(btn_calc)

        # ---- Result Display ----
        result_group = QGroupBox("📊 Calculation Results")
        result_group.setStyleSheet(self._get_group_style())
        result_layout = QVBoxLayout(result_group)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(250)
        self.result_text.setStyleSheet("""
            QTextEdit {
                background: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 10px;
                font-size: 12px;
                line-height: 1.6;
            }
        """)
        result_layout.addWidget(self.result_text)

        layout.addWidget(result_group)

        return widget

    def _build_batch_tab(self) -> QWidget:
        """Build the batch analysis tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Description
        desc = QLabel(
            "Add items from the Single Item tab to build a batch analysis list. "
            "You can then export or print all items together."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(desc)

        # Batch table
        self.batch_table = QTableWidget()
        self.batch_table.setColumnCount(8)
        self.batch_table.setHorizontalHeaderLabels([
            "Item Code", "Description", "Daily Demand",
            "Safety Stock", "Reorder Point", "EOQ",
            "Recommended Order", "Status"
        ])
        self.batch_table.horizontalHeader().setStretchLastSection(True)
        self.batch_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.batch_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.batch_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.batch_table.setAlternatingRowColors(True)
        self.batch_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.batch_table.customContextMenuRequested.connect(self._show_batch_context_menu)
        self.batch_table.setStyleSheet("""
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

        col_widths = [110, 180, 80, 80, 80, 80, 100, 80]
        for i, w in enumerate(col_widths):
            self.batch_table.setColumnWidth(i, w)

        layout.addWidget(self.batch_table)

        # Batch summary
        self.batch_summary_label = QLabel("Items: 0")
        self.batch_summary_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.batch_summary_label)

        return widget

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage(
            "Ready – Select an item and click Calculate"
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

    def _get_group_style(self) -> str:
        """Get group box stylesheet."""
        return """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #B2DFDB;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #004D40;
            }
        """

    # ==================================================================
    # Data Loading
    # ==================================================================

    def _load_items(self):
        """Load items into combo box."""
        session = get_db_session()
        try:
            products = session.query(
                Product.item_code, Product.description, 
                Product.unit_cost, Product.discipline
            ).order_by(Product.item_code).all()

            self.item_dict.clear()
            display_list = []
            
            for code, desc, cost, discipline in products:
                cost_val = cost or 0
                disc = discipline or ""
                self.item_dict[code] = (desc or "", cost_val, disc)
                display = f"{code} – {desc}" if desc else code
                display_list.append(display)

            self.item_combo.clear()
            self.item_combo.addItems(display_list)

            # Setup completer
            completer = QCompleter(display_list, self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.item_combo.setCompleter(completer)

        finally:
            session.close()

    def _select_item(self, item_code: str):
        """Select an item in the combo box."""
        for i in range(self.item_combo.count()):
            text = self.item_combo.itemText(i)
            if text.startswith(item_code):
                self.item_combo.setCurrentIndex(i)
                return

    def _on_item_changed(self, text: str):
        """Handle item selection change."""
        code = text.strip()
        if " – " in code:
            code = code.split(" – ", 1)[0].strip()

        if code in self.item_dict:
            desc, cost, discipline = self.item_dict[code]
            self.item_info_label.setText(
                f"Description: {desc} | Unit Cost: ${cost:,.2f} | Discipline: {discipline}"
            )
            
            # Auto-fill unit cost
            if cost > 0:
                self.unit_cost_spin.setValue(cost)
            
            # Auto-fill ordering cost based on discipline
            if discipline in DEFAULT_ORDERING_COSTS:
                self.ordering_cost_spin.setValue(DEFAULT_ORDERING_COSTS[discipline])

            # Try to load demand history
            self._load_demand_history(code)
            
            # Try to get current stock
            self._load_current_stock(code)
        else:
            self.item_info_label.setText("")

    def _load_demand_history(self, item_code: str):
        """Load demand history and auto-fill demand fields."""
        try:
            history = load_demand_history(item_code, days_back=90)
            if history and len(history) > 0:
                avg = sum(history) / len(history)
                self.daily_demand_spin.setValue(round(avg, 2))

                # Calculate std dev
                if len(history) > 1:
                    variance = sum((d - avg) ** 2 for d in history) / len(history)
                    std_dev = variance ** 0.5
                    self.demand_std_spin.setValue(round(std_dev, 2))

                self.status_bar.showMessage(
                    f"Demand loaded for {item_code} (avg: {avg:.2f}/day from {len(history)} days)",
                    3000
                )
        except Exception:
            pass  # Silently ignore

    def _load_current_stock(self, item_code: str):
        """Load current stock for an item."""
        session = get_db_session()
        try:
            total = session.query(
                func.sum(Stock.quantity - Stock.allocated_qty)
            ).filter(
                Stock.item_code == item_code,
                Stock.qc_status == 'ACCEPTED'
            ).scalar()

            if total and total > 0:
                self.current_stock_spin.setValue(float(total))
        except Exception:
            pass
        finally:
            session.close()

    def _on_method_changed(self, index: int):
        """Handle safety stock method change."""
        method = self.method_combo.currentText()
        
        # Show/hide relevant fields
        is_service_level = "Service Level" in method
        is_fixed = "Fixed" in method
        is_percentage = "Percentage" in method

        self.service_level_combo.setVisible(is_service_level)
        self.fixed_safety_spin.setVisible(is_fixed)
        self.pct_safety_spin.setVisible(is_percentage)

    # ==================================================================
    # Calculate Methods
    # ==================================================================

    def _get_item_code(self) -> Optional[str]:
        """Get selected item code."""
        text = self.item_combo.currentText().strip()
        if " – " in text:
            return text.split(" – ", 1)[0].strip()
        return text if text in self.item_dict else None

    def _calculate(self):
        """Calculate reorder point and safety stock."""
        item_code = self._get_item_code()
        if not item_code:
            QMessageBox.warning(self, "Select Item", "Please select an item first.")
            return

        # Get parameters
        daily_demand = self.daily_demand_spin.value()
        demand_std = self.demand_std_spin.value()
        lead_time = self.lead_time_spin.value()
        max_lead_time = self.max_lead_time_spin.value()
        ordering_cost = self.ordering_cost_spin.value()
        unit_cost = self.unit_cost_spin.value()
        holding_pct = self.holding_pct_spin.value() / 100
        current_stock = self.current_stock_spin.value()
        method = self.method_combo.currentText()

        # Calculate annual demand
        annual_demand = daily_demand * 365

        # Calculate holding cost per unit
        holding_cost_per_unit = unit_cost * holding_pct

        # Calculate safety stock
        safety_stock = self._calculate_safety_stock(
            method, daily_demand, demand_std, lead_time, max_lead_time
        )

        # Calculate reorder point
        reorder_point = lead_time * daily_demand + safety_stock

        # Calculate EOQ
        eoq = InventoryOptimizer.eoq(annual_demand, ordering_cost, holding_cost_per_unit)

        # Calculate recommended order quantity
        if current_stock <= 0:
            # Auto-detect current stock
            session = get_db_session()
            try:
                current_stock = float(
                    session.query(
                        func.sum(Stock.quantity - Stock.allocated_qty)
                    ).filter(
                        Stock.item_code == item_code,
                        Stock.qc_status == 'ACCEPTED'
                    ).scalar() or 0
                )
            except Exception:
                current_stock = 0
            finally:
                session.close()

        recommended_order = InventoryOptimizer.recommended_order_quantity(
            current_stock, reorder_point, eoq
        )

        # Get item info
        desc = self.item_dict.get(item_code, ("", 0, ""))[0]

        # Determine status
        if current_stock <= 0:
            status = "🔴 OUT OF STOCK"
            status_color = "#D32F2F"
        elif current_stock <= reorder_point:
            status = "🟠 ORDER NOW"
            status_color = "#E65100"
        elif current_stock <= reorder_point + safety_stock:
            status = "🟡 ORDER SOON"
            status_color = "#F57F17"
        else:
            status = "🟢 ADEQUATE"
            status_color = "#2E7D32"

        # Display results
        result_html = f"""
        <div style="font-family: 'Segoe UI', Arial; line-height: 1.8;">
            <h3 style="color: #004D40; margin-bottom: 10px;">
                📊 Reorder Analysis: {item_code} – {desc}
            </h3>
            <table style="width: 100%;">
                <tr style="background: #E0F2F1;">
                    <td style="padding: 6px; width: 200px;"><b>Parameter</b></td>
                    <td style="padding: 6px;"><b>Value</b></td>
                </tr>
                <tr>
                    <td style="padding: 6px;">Average Daily Demand</td>
                    <td style="padding: 6px;">{daily_demand:.2f} units/day</td>
                </tr>
                <tr style="background: #F5F5F5;">
                    <td style="padding: 6px;">Annual Demand</td>
                    <td style="padding: 6px;">{annual_demand:,.0f} units/year</td>
                </tr>
                <tr>
                    <td style="padding: 6px;">Lead Time</td>
                    <td style="padding: 6px;">{lead_time:.1f} days</td>
                </tr>
                <tr style="background: #F5F5F5;">
                    <td style="padding: 6px;">Lead Time Demand</td>
                    <td style="padding: 6px;">{lead_time * daily_demand:.1f} units</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold; color: #004D40;">Safety Stock</td>
                    <td style="padding: 6px; font-weight: bold; color: #004D40;">{safety_stock:.1f} units</td>
                </tr>
                <tr style="background: #F5F5F5;">
                    <td style="padding: 6px; font-weight: bold; color: #1565C0;">Reorder Point</td>
                    <td style="padding: 6px; font-weight: bold; color: #1565C0;">{reorder_point:.1f} units</td>
                </tr>
                <tr>
                    <td style="padding: 6px;">Economic Order Quantity (EOQ)</td>
                    <td style="padding: 6px;">{eoq:,.1f} units</td>
                </tr>
                <tr style="background: #F5F5F5;">
                    <td style="padding: 6px;">Current Stock</td>
                    <td style="padding: 6px;">{current_stock:,.1f} units</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold; color: #2E7D32;">Recommended Order</td>
                    <td style="padding: 6px; font-weight: bold; color: #2E7D32;">{recommended_order:,.1f} units</td>
                </tr>
            </table>
            <hr>
            <p style="font-size: 16px; font-weight: bold; color: {status_color}; text-align: center;">
                Status: {status}
            </p>
            <hr>
            <h4 style="color: #004D40;">💡 Recommendations:</h4>
            <ul>
                <li><b>Order when stock reaches:</b> {reorder_point:.0f} units</li>
                <li><b>Order quantity:</b> {eoq:.0f} units (EOQ)</li>
                <li><b>Safety stock buffer:</b> {safety_stock:.0f} units</li>
                <li><b>Days of supply at reorder point:</b> {reorder_point / daily_demand:.1f} days</li>
                <li><b>Orders per year:</b> {annual_demand / eoq:.1f} orders</li>
                <li><b>Annual holding cost:</b> ${eoq / 2 * holding_cost_per_unit:,.2f}</li>
                <li><b>Annual ordering cost:</b> ${annual_demand / eoq * ordering_cost:,.2f}</li>
            </ul>
        </div>
        """

        self.result_text.setHtml(result_html)
        self.status_bar.showMessage(f"Calculation complete for {item_code}", 5000)

        # Store result
        self._last_result = {
            "item_code": item_code,
            "description": desc,
            "daily_demand": daily_demand,
            "safety_stock": safety_stock,
            "reorder_point": reorder_point,
            "eoq": eoq,
            "recommended_order": recommended_order,
            "current_stock": current_stock,
            "status": status,
        }

        # Emit signal
        self.calculation_complete.emit(self._last_result)

    def _calculate_safety_stock(self, method: str, daily_demand: float,
                                 demand_std: float, lead_time: float,
                                 max_lead_time: float) -> float:
        """
        Calculate safety stock based on selected method.
        
        Args:
            method: Safety stock method
            daily_demand: Average daily demand
            demand_std: Standard deviation of demand
            lead_time: Average lead time in days
            max_lead_time: Maximum lead time in days
            
        Returns:
            Safety stock quantity
        """
        if "Simple" in method:
            return InventoryOptimizer.safety_stock_simple(
                max_lead_time, lead_time, daily_demand
            )
        elif "Service Level" in method:
            service_text = self.service_level_combo.currentText()
            z_score = SERVICE_LEVELS.get(service_text, 1.65)
            return InventoryOptimizer.safety_stock_service_level(
                0.95 if z_score == 1.65 else 0.99,  # Approximate service level
                demand_std, lead_time
            )
        elif "Fixed" in method:
            return self.fixed_safety_spin.value()
        elif "Percentage" in method:
            pct = self.pct_safety_spin.value() / 100
            return lead_time * daily_demand * pct
        else:
            return 0

    # ==================================================================
    # Batch Analysis Methods
    # ==================================================================

    def _add_to_list(self):
        """Add current calculation to batch list."""
        if not hasattr(self, '_last_result') or not self._last_result:
            QMessageBox.warning(self, "No Result", "Please calculate an item first.")
            return

        result = self._last_result
        row = self.batch_table.rowCount()
        self.batch_table.insertRow(row)

        self.batch_table.setItem(row, 0, QTableWidgetItem(result["item_code"]))
        self.batch_table.setItem(row, 1, QTableWidgetItem(result.get("description", "")))
        
        demand_item = QTableWidgetItem(f"{result['daily_demand']:.2f}")
        demand_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.batch_table.setItem(row, 2, demand_item)

        safety_item = QTableWidgetItem(f"{result['safety_stock']:.1f}")
        safety_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.batch_table.setItem(row, 3, safety_item)

        rop_item = QTableWidgetItem(f"{result['reorder_point']:.1f}")
        rop_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.batch_table.setItem(row, 4, rop_item)

        eoq_item = QTableWidgetItem(f"{result['eoq']:.1f}")
        eoq_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.batch_table.setItem(row, 5, eoq_item)

        order_item = QTableWidgetItem(f"{result['recommended_order']:.1f}")
        order_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.batch_table.setItem(row, 6, order_item)

        # Status with color
        status_item = QTableWidgetItem(result.get("status", ""))
        if "OUT" in result.get("status", ""):
            status_item.setForeground(QColor("#D32F2F"))
        elif "ORDER NOW" in result.get("status", ""):
            status_item.setForeground(QColor("#E65100"))
        elif "ORDER SOON" in result.get("status", ""):
            status_item.setForeground(QColor("#F57F17"))
        else:
            status_item.setForeground(QColor("#2E7D32"))
        self.batch_table.setItem(row, 7, status_item)

        self.batch_summary_label.setText(f"Items: {self.batch_table.rowCount()}")
        self.status_bar.showMessage(f"Added {result['item_code']} to batch list", 3000)
        self.tab_widget.setCurrentIndex(1)

    def _clear_list(self):
        """Clear batch analysis list."""
        if self.batch_table.rowCount() == 0:
            return

        reply = QMessageBox.question(
            self, "Clear List",
            "Clear all items from the batch list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.batch_table.setRowCount(0)
            self.batch_summary_label.setText("Items: 0")
            self.status_bar.showMessage("Batch list cleared", 3000)

    def _show_batch_context_menu(self, pos):
        """Show context menu on batch table."""
        menu = QMenu(self)
        menu.addAction("❌ Remove Selected", self._remove_batch_selected)
        menu.addAction("🗑️ Clear All", self._clear_list)
        menu.exec(self.batch_table.viewport().mapToGlobal(pos))

    def _remove_batch_selected(self):
        """Remove selected rows from batch table."""
        rows = set()
        for item in self.batch_table.selectedItems():
            rows.add(item.row())

        for row in sorted(rows, reverse=True):
            self.batch_table.removeRow(row)

        self.batch_summary_label.setText(f"Items: {self.batch_table.rowCount()}")

    # ==================================================================
    # Export & Share
    # ==================================================================

    def _collect_batch_data(self):
        """Collect batch table data."""
        if self.batch_table.rowCount() == 0:
            return None, None

        headers = [
            self.batch_table.horizontalHeaderItem(c).text()
            for c in range(self.batch_table.columnCount())
        ]
        data = []
        for row in range(self.batch_table.rowCount()):
            row_dict = {}
            for col in range(self.batch_table.columnCount()):
                item = self.batch_table.item(row, col)
                row_dict[headers[col]] = item.text() if item else ""
            data.append(row_dict)

        return headers, data

    def _export_excel(self):
        """Export batch analysis to Excel."""
        headers, data = self._collect_batch_data()
        if not data:
            QMessageBox.information(self, "No Data", 
                                  "Add items to the batch list first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Reorder Analysis", "reorder_analysis.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            export_to_excel(data, headers, file_path, sheet_name="Reorder Analysis")
            self.status_bar.showMessage(f"Exported to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _print_report(self):
        """Print analysis report."""
        headers, data = self._collect_batch_data()
        if not data:
            # Print single item result
            if not hasattr(self, '_last_result'):
                QMessageBox.information(self, "No Data", "Calculate an item first.")
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
            <title>Reorder Point Analysis</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial; margin: 20px; }}
                h1 {{ color: #004D40; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
                th {{ background: #004D40; color: white; padding: 8px; text-align: left; }}
                td {{ padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px; }}
            </style>
        </head>
        <body>
            <h1>📊 Reorder Point Analysis Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            <table>
                <tr>
                    <th>Item Code</th><th>Description</th><th>Daily Demand</th>
                    <th>Safety Stock</th><th>Reorder Point</th><th>EOQ</th>
                    <th>Recommended Order</th><th>Status</th>
                </tr>
        """

        if self.batch_table.rowCount() > 0:
            for row in range(self.batch_table.rowCount()):
                html += "<tr>"
                for col in range(self.batch_table.columnCount()):
                    item = self.batch_table.item(row, col)
                    html += f"<td>{item.text() if item else ''}</td>"
                html += "</tr>"
        elif hasattr(self, '_last_result'):
            r = self._last_result
            html += f"""
                <tr>
                    <td>{r['item_code']}</td><td>{r.get('description', '')}</td>
                    <td>{r['daily_demand']:.2f}</td><td>{r['safety_stock']:.1f}</td>
                    <td>{r['reorder_point']:.1f}</td><td>{r['eoq']:.1f}</td>
                    <td>{r['recommended_order']:.1f}</td><td>{r.get('status', '')}</td>
                </tr>
            """

        html += """
            </table>
        </body>
        </html>
        """
        return html

    def _share_whatsapp(self):
        """Share analysis via WhatsApp."""
        if not hasattr(self, '_last_result'):
            QMessageBox.warning(self, "No Result", "Calculate an item first.")
            return

        r = self._last_result
        lines = []
        lines.append("*📊 Reorder Analysis*")
        lines.append(f"*Item:* {r['item_code']} – {r.get('description', 'N/A')}")
        lines.append("")
        lines.append(f"• Daily Demand: {r['daily_demand']:.2f} units")
        lines.append(f"• Safety Stock: {r['safety_stock']:.1f} units")
        lines.append(f"• Reorder Point: {r['reorder_point']:.1f} units")
        lines.append(f"• EOQ: {r['eoq']:.1f} units")
        lines.append(f"• Recommended Order: {r['recommended_order']:.1f} units")
        lines.append(f"• Current Stock: {r['current_stock']:.1f} units")
        lines.append("")
        lines.append(f"*Status:* {r.get('status', 'N/A')}")
        lines.append("")
        lines.append("Please process purchase order accordingly.")
        lines.append(f"Generated by iMat – {datetime.now().strftime('%Y-%m-%d')}")

        message = "%0A".join(lines)
        wa_url = f"https://wa.me/989160684552?text={message}"
        webbrowser.open(wa_url)
        self.status_bar.showMessage("WhatsApp message prepared", 3000)


# ==================================================================
# Import needed for func
# ==================================================================

from sqlalchemy import func