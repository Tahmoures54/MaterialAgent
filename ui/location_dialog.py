# ui/location_dialog.py
"""
Warehouse & Location Manager – iMat Material Control System (EPC Edition).

Comprehensive location management with:
- Hierarchical tree structure (Warehouse → Rack → Bin)
- Auto-code generation based on location type
- Drag-and-drop location reorganization (planned)
- Location capacity management
- Stock level visualization per location
- Location filtering and search
- Export location structure
- Print location labels/barcodes
- Location audit trail
- Multi-level hierarchy support
- Visual indicators for stock levels
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLineEdit, QComboBox, QFormLayout, QMessageBox,
    QLabel, QFrame, QWidget, QMenu, QToolBar, QStatusBar,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QTextEdit, QInputDialog, QFileDialog,
    QAbstractItemView, QApplication, QStyle, QProgressBar,
    QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import (
    QFont, QColor, QAction, QIcon, QDesktopServices,
    QBrush, QPainter, QPen
)

from sqlalchemy import func
from db.database import SessionLocal, get_db_session
from db.models import Location, Stock, Product
from logic.location_logic import (
    create_location, get_all_locations, update_location,
    delete_location, get_location_tree, get_location_path,
    get_location_by_code, get_location_by_id
)
from ui.logo_widget import LogoWidget
from utils.excel_export import export_to_excel

# ==================================================================
# Constants
# ==================================================================

# Location type definitions
LOCATION_TYPES = {
    "WAREHOUSE": {
        "icon": "🏭",
        "prefix": "WH",
        "color": QColor("#4CAF50"),
        "label": "Warehouse",
        "description": "Main warehouse building",
        "can_have_children": True,
    },
    "OPEN_YARD": {
        "icon": "🌳",
        "prefix": "YD",
        "color": QColor("#8BC34A"),
        "label": "Open Yard",
        "description": "Outdoor storage area",
        "can_have_children": True,
    },
    "RACK": {
        "icon": "🗄️",
        "prefix": "RK",
        "color": QColor("#FFC107"),
        "label": "Rack",
        "description": "Storage rack/shelf",
        "can_have_children": True,
    },
    "BIN": {
        "icon": "📦",
        "prefix": "BN",
        "color": QColor("#FF9800"),
        "label": "Bin",
        "description": "Individual storage bin",
        "can_have_children": False,
    },
    "QUARANTINE": {
        "icon": "⚠️",
        "prefix": "QA",
        "color": QColor("#F44336"),
        "label": "Quarantine Area",
        "description": "Inspection/quarantine zone",
        "can_have_children": False,
    },
}

# Stock level thresholds for color indicators
STOCK_LEVELS = {
    "empty": {"threshold": 0, "color": QColor("#9E9E9E"), "icon": "⚪"},
    "low": {"threshold": 10, "color": QColor("#FFC107"), "icon": "🟡"},
    "medium": {"threshold": 50, "color": QColor("#2196F3"), "icon": "🔵"},
    "high": {"threshold": 100, "color": QColor("#4CAF50"), "icon": "🟢"},
    "full": {"threshold": 500, "color": QColor("#004D40"), "icon": "🟣"},
}

# ==================================================================
# Location Dialog
# ==================================================================

class LocationDialog(QDialog):
    """
    Warehouse structure and location management dialog.

    Features:
    - Hierarchical tree view
    - Auto-code generation
    - Stock level visualization
    - Location CRUD operations
    - Search and filter
    - Export capabilities
    """

    location_changed = pyqtSignal()

    def __init__(self, parent=None, user_role: str = "viewer"):
        """
        Initialize the Location dialog.

        Args:
            parent: Parent widget
            user_role: Current user's role for access control
        """
        super().__init__(parent)
        self.parent = parent
        self.user_role = user_role
        self.db = SessionLocal()

        # State
        self.all_locations: List[Location] = []
        self.filtered_locations: List[Location] = []

        # Window setup
        self.setWindowTitle("iMat – Warehouse & Location Manager")
        self.setMinimumSize(1100, 700)
        self.setModal(True)

        # Build UI
        self._init_ui()

        # Load data
        self._load_tree()

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

        # Build components — content (tree) must come before toolbar
        # because toolbar actions connect to self.tree
        self._build_header(main_layout)
        self._build_search_bar(main_layout)
        self._build_content(main_layout)          # <-- moved up
        self._build_toolbar(main_layout)          # now self.tree exists
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

        title = QLabel("🏢 Warehouse Structure Manager")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.subtitle = QLabel("Organize storage locations for accurate inventory tracking")
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

        # Add actions
        self.action_add_warehouse = toolbar.addAction("🏭 Add Warehouse")
        self.action_add_warehouse.setToolTip("Add a new main warehouse")
        self.action_add_warehouse.triggered.connect(lambda: self._add_location("WAREHOUSE"))

        self.action_add_yard = toolbar.addAction("🌳 Add Yard")
        self.action_add_yard.setToolTip("Add a new open yard")
        self.action_add_yard.triggered.connect(lambda: self._add_location("OPEN_YARD"))

        self.action_add_rack = toolbar.addAction("🗄️ Add Rack")
        self.action_add_rack.setToolTip("Add a rack to selected location")
        self.action_add_rack.triggered.connect(lambda: self._add_location("RACK"))

        self.action_add_bin = toolbar.addAction("📦 Add Bin")
        self.action_add_bin.setToolTip("Add a bin to selected location")
        self.action_add_bin.triggered.connect(lambda: self._add_location("BIN"))

        self.action_add_quarantine = toolbar.addAction("⚠️ Add Quarantine")
        self.action_add_quarantine.setToolTip("Add a quarantine area")
        self.action_add_quarantine.triggered.connect(lambda: self._add_location("QUARANTINE"))
        toolbar.addSeparator()

        self.action_edit = toolbar.addAction("✏️ Edit")
        self.action_edit.setToolTip("Edit selected location")
        self.action_edit.triggered.connect(self._edit_location)

        self.action_delete = toolbar.addAction("🗑️ Delete")
        self.action_delete.setToolTip("Delete selected location")
        self.action_delete.triggered.connect(self._delete_location)
        toolbar.addSeparator()

        self.action_refresh = toolbar.addAction("🔄 Refresh")
        self.action_refresh.setToolTip("Refresh location tree")
        self.action_refresh.triggered.connect(self._load_tree)
        toolbar.addSeparator()

        self.action_expand = toolbar.addAction("📂 Expand All")
        self.action_expand.setToolTip("Expand all tree nodes")
        self.action_expand.triggered.connect(self.tree.expandAll)   # self.tree now exists

        self.action_collapse = toolbar.addAction("📁 Collapse All")
        self.action_collapse.setToolTip("Collapse all tree nodes")
        self.action_collapse.triggered.connect(self.tree.collapseAll)
        toolbar.addSeparator()

        self.action_export = toolbar.addAction("📥 Export")
        self.action_export.setToolTip("Export location structure to Excel")
        self.action_export.triggered.connect(self._export_locations)

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
        search_layout.setSpacing(10)

        # Search input
        search_layout.addWidget(QLabel("🔍 Filter:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by code, name, or description...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(300)
        self.search_input.textChanged.connect(self._filter_tree)
        search_layout.addWidget(self.search_input)

        # Type filter
        search_layout.addWidget(QLabel("Type:"))
        self.type_filter_combo = QComboBox()
        self.type_filter_combo.addItem("All Types")
        for type_key, type_data in LOCATION_TYPES.items():
            self.type_filter_combo.addItem(
                f"{type_data['icon']} {type_data['label']}", type_key
            )
        self.type_filter_combo.currentIndexChanged.connect(self._filter_tree)
        search_layout.addWidget(self.type_filter_combo)

        # Show empty locations
        self.show_empty_check = QCheckBox("Show Empty Locations")
        self.show_empty_check.setChecked(True)
        self.show_empty_check.toggled.connect(self._filter_tree)
        search_layout.addWidget(self.show_empty_check)

        search_layout.addStretch()

        # Location count
        self.location_count_label = QLabel("Locations: 0")
        self.location_count_label.setStyleSheet("color: #666; font-weight: bold;")
        search_layout.addWidget(self.location_count_label)

        parent_layout.addWidget(search_frame)

    def _build_content(self, parent_layout: QVBoxLayout):
        """Build the main content area with splitter."""
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Tree view
        left_panel = self._build_tree_panel()
        splitter.addWidget(left_panel)

        # Right panel: Details
        right_panel = self._build_details_panel()
        splitter.addWidget(right_panel)

        # Set initial sizes (60% tree, 40% details)
        splitter.setSizes([650, 400])

        parent_layout.addWidget(splitter)

    def _build_tree_panel(self) -> QWidget:
        """Build the tree view panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            "Code", "Name", "Type", "Stock Items", "Total Qty", "Description"
        ])
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.currentItemChanged.connect(self._on_selection_changed)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                font-size: 11px;
            }
            QTreeWidget::item:selected {
                background: #B2DFDB;
                color: #004D40;
            }
            QTreeWidget::item:hover {
                background: #E0F2F1;
            }
            QHeaderView::section {
                background-color: #004D40;
                color: white;
                font-weight: bold;
                padding: 4px;
                border: none;
            }
        """)

        # Column widths
        column_widths = [120, 150, 100, 80, 80, 150]
        for i, w in enumerate(column_widths):
            self.tree.setColumnWidth(i, w)

        layout.addWidget(self.tree)

        # Legend
        legend_frame = QFrame()
        legend_frame.setStyleSheet("""
            QFrame {
                background: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        legend_layout = QHBoxLayout(legend_frame)
        legend_layout.setSpacing(10)

        legend_layout.addWidget(QLabel("Stock Level:"))
        for level_name, level_data in STOCK_LEVELS.items():
            dot = QLabel(level_data["icon"])
            dot.setStyleSheet("font-size: 14px;")
            legend_layout.addWidget(dot)
            label = QLabel(level_name.capitalize())
            label.setStyleSheet(f"color: {level_data['color'].name()}; font-size: 9px;")
            legend_layout.addWidget(label)

        legend_layout.addStretch()
        layout.addWidget(legend_frame)

        return widget

    def _build_details_panel(self) -> QWidget:
        """Build the details panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Location details group
        details_group = QGroupBox("📍 Location Details")
        details_group.setStyleSheet(self._get_group_style())
        details_layout = QVBoxLayout(details_group)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(200)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 10px;
                font-size: 11px;
            }
        """)
        details_layout.addWidget(self.details_text)

        layout.addWidget(details_group)

        # Stock at location group
        stock_group = QGroupBox("📦 Stock at This Location")
        stock_group.setStyleSheet(self._get_group_style())
        stock_layout = QVBoxLayout(stock_group)

        self.stock_table = QTableWidget()
        self.stock_table.setColumnCount(6)
        self.stock_table.setHorizontalHeaderLabels([
            "Item Code", "Description", "Heat No",
            "QC Status", "Quantity", "Available"
        ])
        self.stock_table.horizontalHeader().setStretchLastSection(True)
        self.stock_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.stock_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stock_table.setAlternatingRowColors(True)
        self.stock_table.setMaximumHeight(250)
        self.stock_table.setStyleSheet("""
            QTableWidget {
                background: white;
                font-size: 10px;
            }
            QHeaderView::section {
                background-color: #004D40;
                color: white;
                font-weight: bold;
                padding: 3px;
                font-size: 10px;
            }
        """)

        stock_column_widths = [100, 150, 80, 80, 70, 70]
        for i, w in enumerate(stock_column_widths):
            self.stock_table.setColumnWidth(i, w)

        stock_layout.addWidget(self.stock_table)

        # Stock summary
        self.stock_summary_label = QLabel("")
        self.stock_summary_label.setStyleSheet("color: #666; font-size: 10px; padding: 4px;")
        stock_layout.addWidget(self.stock_summary_label)

        layout.addWidget(stock_group)

        return widget

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage(
            "Ready – Right-click on tree for context menu | Select location to view details"
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
        return styles.get(button_type, styles["primary"])

    # ==================================================================
    # Role Permissions
    # ==================================================================

    def _apply_role_permissions(self):
        """Apply role-based access restrictions."""
        if self.user_role == "viewer":
            self.action_add_warehouse.setEnabled(False)
            self.action_add_yard.setEnabled(False)
            self.action_add_rack.setEnabled(False)
            self.action_add_bin.setEnabled(False)
            self.action_add_quarantine.setEnabled(False)
            self.action_edit.setEnabled(False)
            self.action_delete.setEnabled(False)
            self.action_export.setEnabled(False)
            self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            self.status_bar.showMessage("Read-only mode – You cannot modify locations")

    # ==================================================================
    # Tree Methods
    # ==================================================================

    def _load_tree(self):
        """Load location tree from database."""
        self.tree.clear()
        self.all_locations = get_all_locations(self.db)

        # Build lookup dictionary
        items = {}
        root_items = []

        for loc in self.all_locations:
            type_config = LOCATION_TYPES.get(
                loc.location_type,
                {"icon": "📍", "color": QColor("#9E9E9E")}
            )

            # Get stock count for this location
            stock_count = len(loc.stocks) if loc.stocks else 0
            total_qty = sum(s.quantity for s in loc.stocks) if loc.stocks else 0

            # Create tree item
            item = QTreeWidgetItem([
                loc.code,
                loc.name or "",
                f"{type_config['icon']} {loc.location_type}",
                str(stock_count),
                f"{total_qty:.1f}",
                loc.description or ""
            ])

            # Store location data
            item.setData(0, Qt.ItemDataRole.UserRole, loc.id)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, loc)

            # Color based on type
            item.setForeground(0, type_config["color"])
            item.setForeground(1, type_config["color"])
            item.setForeground(2, type_config["color"])

            # Color based on stock level
            if stock_count == 0:
                item.setForeground(3, QColor("#9E9E9E"))
            elif total_qty > 100:
                item.setForeground(4, QColor("#4CAF50"))
            elif total_qty > 10:
                item.setForeground(4, QColor("#2196F3"))
            else:
                item.setForeground(4, QColor("#FFC107"))

            # Tooltip
            tooltip = (
                f"<b>Code:</b> {loc.code}<br>"
                f"<b>Name:</b> {loc.name}<br>"
                f"<b>Type:</b> {loc.location_type}<br>"
                f"<b>Stock Items:</b> {stock_count}<br>"
                f"<b>Total Qty:</b> {total_qty:.1f}<br>"
            )
            if loc.description:
                tooltip += f"<b>Description:</b> {loc.description}<br>"
            if loc.capacity:
                tooltip += f"<b>Capacity:</b> {loc.capacity}<br>"
            item.setToolTip(0, tooltip)

            items[loc.id] = item

            if loc.parent_id is None:
                root_items.append(item)
            else:
                parent_item = items.get(loc.parent_id)
                if parent_item:
                    parent_item.addChild(item)
                else:
                    root_items.append(item)

        # Add root items to tree
        for item in root_items:
            self.tree.addTopLevelItem(item)

        self.tree.expandAll()
        self.location_count_label.setText(f"Locations: {len(self.all_locations)}")
        self.status_bar.showMessage(f"Loaded {len(self.all_locations)} locations", 3000)

    def _filter_tree(self):
        """Filter tree based on search and type."""
        search_text = self.search_input.text().strip().lower()
        type_filter = self.type_filter_combo.currentData()
        show_empty = self.show_empty_check.isChecked()

        self._filter_items(self.tree.invisibleRootItem(), search_text, type_filter, show_empty)

    def _filter_items(self, parent_item, search_text: str, type_filter: Optional[str],
                      show_empty: bool):
        """Recursively filter tree items."""
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            loc = item.data(0, Qt.ItemDataRole.UserRole + 1)

            if not loc:
                continue

            # Check if matches search
            match_search = True
            if search_text:
                match_search = (
                    search_text in loc.code.lower() or
                    search_text in (loc.name or "").lower() or
                    search_text in (loc.description or "").lower()
                )

            # Check if matches type
            match_type = True
            if type_filter:
                match_type = loc.location_type == type_filter

            # Check if has stock
            has_stock = any(s.quantity > 0 for s in loc.stocks) if loc.stocks else False
            match_stock = show_empty or has_stock

            # Show/hide
            visible = match_search and match_type and match_stock

            # Also check children
            has_visible_children = False
            self._filter_items(item, search_text, type_filter, show_empty)

            for j in range(item.childCount()):
                if not item.child(j).isHidden():
                    has_visible_children = True
                    break

            item.setHidden(not visible and not has_visible_children)

            # Expand if visible and has children
            if visible and item.childCount() > 0:
                item.setExpanded(True)

    def _on_selection_changed(self, current, previous):
        """Handle tree selection change."""
        if not current:
            self._clear_details()
            return

        loc = current.data(0, Qt.ItemDataRole.UserRole + 1)
        if loc:
            self._show_location_details(loc)

    def _show_context_menu(self, pos):
        """Show context menu on right-click."""
        if self.user_role == "viewer":
            return

        item = self.tree.currentItem()
        if not item:
            return

        loc = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not loc:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #CCC;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
            }
            QMenu::item:selected {
                background-color: #E0F2F1;
                color: #004D40;
            }
        """)

        # Edit action
        menu.addAction("✏️ Edit Location", self._edit_location)

        # Add child actions
        add_menu = menu.addMenu("➕ Add Child Location")
        for type_key, type_data in LOCATION_TYPES.items():
            if type_data["can_have_children"] or item.parent() is None:
                add_menu.addAction(
                    f"{type_data['icon']} Add {type_data['label']}",
                    lambda t=type_key: self._add_location(t)
                )

        menu.addSeparator()

        # Delete action
        menu.addAction("🗑️ Delete Location", self._delete_location)

        menu.addSeparator()

        # View stock
        menu.addAction("📦 View Stock Details", lambda: self._show_location_details(loc))

        # Copy code
        menu.addAction("📋 Copy Location Code",
                      lambda: QApplication.clipboard().setText(loc.code))

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ==================================================================
    # Location Details
    # ==================================================================

    def _show_location_details(self, loc: Location):
        """Show details for a location."""
        # Get stock at this location
        stocks = self.db.query(Stock).filter(
            Stock.location_id == loc.id,
            Stock.quantity > 0
        ).all()

        # Build details HTML
        type_config = LOCATION_TYPES.get(
            loc.location_type,
            {"icon": "📍", "label": loc.location_type}
        )

        total_qty = sum(s.quantity for s in stocks)
        total_available = sum(s.available_qty for s in stocks)
        stock_count = len(stocks)

        details_html = f"""
        <div style="font-family: 'Segoe UI', Arial; line-height: 1.6;">
            <h3 style="color: #004D40; margin-bottom: 8px;">
                {type_config['icon']} {loc.code}
            </h3>
            <table style="width: 100%;">
                <tr><td style="color: #666; width: 100px;"><b>Name:</b></td>
                    <td>{loc.name or 'N/A'}</td></tr>
                <tr><td style="color: #666;"><b>Type:</b></td>
                    <td>{loc.location_type}</td></tr>
                <tr><td style="color: #666;"><b>Path:</b></td>
                    <td>{loc.full_path}</td></tr>
                <tr><td style="color: #666;"><b>Description:</b></td>
                    <td>{loc.description or 'N/A'}</td></tr>
                <tr><td style="color: #666;"><b>Capacity:</b></td>
                    <td>{loc.capacity or 'Not specified'}</td></tr>
                <tr><td style="color: #666;"><b>Stock Items:</b></td>
                    <td>{stock_count}</td></tr>
                <tr><td style="color: #666;"><b>Total Qty:</b></td>
                    <td>{total_qty:.1f}</td></tr>
                <tr><td style="color: #666;"><b>Available:</b></td>
                    <td>{total_available:.1f}</td></tr>
            </table>
        </div>
        """
        self.details_text.setHtml(details_html)

        # Display stock table
        self.stock_table.setRowCount(len(stocks))
        for row, stock in enumerate(stocks):
            product = self.db.query(Product).filter_by(item_code=stock.item_code).first()

            self.stock_table.setItem(row, 0, QTableWidgetItem(stock.item_code))
            self.stock_table.setItem(row, 1, QTableWidgetItem(
                product.description if product else ""
            ))
            self.stock_table.setItem(row, 2, QTableWidgetItem(stock.heat_no))

            # QC Status with color
            qc_item = QTableWidgetItem(stock.qc_status)
            qc_colors = {
                "QUARANTINE": ("#FFE0B2", "#E65100"),
                "ACCEPTED": ("#C8E6C9", "#2E7D32"),
                "REJECTED": ("#FFCDD2", "#B71C1C"),
            }
            if stock.qc_status in qc_colors:
                bg, fg = qc_colors[stock.qc_status]
                qc_item.setBackground(QColor(bg))
                qc_item.setForeground(QColor(fg))
            self.stock_table.setItem(row, 3, qc_item)

            qty_item = QTableWidgetItem(f"{stock.quantity:.1f}")
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.stock_table.setItem(row, 4, qty_item)

            avail_item = QTableWidgetItem(f"{stock.available_qty:.1f}")
            avail_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.stock_table.setItem(row, 5, avail_item)

        self.stock_summary_label.setText(
            f"Total Items: {stock_count} | "
            f"Total Qty: {total_qty:.1f} | "
            f"Available: {total_available:.1f}"
        )

    def _clear_details(self):
        """Clear the details panel."""
        self.details_text.clear()
        self.stock_table.setRowCount(0)
        self.stock_summary_label.setText("")

    # ==================================================================
    # CRUD Operations
    # ==================================================================

    def _add_location(self, default_type: Optional[str] = None):
        """Add a new location."""
        if self.user_role == "viewer":
            QMessageBox.warning(self, "Access Denied",
                              "You do not have permission to add locations.")
            return

        # Get parent from selection
        parent_item = self.tree.currentItem()
        parent_loc = None
        if parent_item:
            parent_loc = parent_item.data(0, Qt.ItemDataRole.UserRole + 1)

        dlg = LocationEditDialog(
            self, self.db, is_new=True,
            parent_location=parent_loc,
            default_type=default_type,
            user_role=self.user_role
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load_tree()
            self.location_changed.emit()
            self.status_bar.showMessage("New location added successfully", 3000)

    def _edit_location(self):
        """Edit selected location."""
        if self.user_role == "viewer":
            QMessageBox.warning(self, "Access Denied",
                              "You cannot edit locations.")
            return

        item = self.tree.currentItem()
        if not item:
            QMessageBox.warning(self, "No Selection",
                              "Please select a location to edit.")
            return

        loc = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not loc:
            return

        dlg = LocationEditDialog(
            self, self.db, is_new=False,
            location=loc, user_role=self.user_role
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load_tree()
            self.location_changed.emit()
            self.status_bar.showMessage("Location updated successfully", 3000)

    def _delete_location(self):
        """Delete selected location."""
        if self.user_role == "viewer":
            QMessageBox.warning(self, "Access Denied",
                              "You cannot delete locations.")
            return

        item = self.tree.currentItem()
        if not item:
            QMessageBox.warning(self, "No Selection",
                              "Please select a location to delete.")
            return

        loc = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not loc:
            return

        # Check for children
        children = self.db.query(Location).filter(
            Location.parent_id == loc.id,
            Location.is_active == True
        ).all()
        if children:
            child_codes = ", ".join(c.code for c in children)
            QMessageBox.warning(
                self, "Cannot Delete",
                f"This location has active sub-locations:\n{child_codes}\n\n"
                "Please remove or reassign them first."
            )
            return

        # Check for stock
        active_stock = self.db.query(Stock).filter(
            Stock.location_id == loc.id,
            Stock.quantity > 0
        ).count()
        if active_stock > 0:
            QMessageBox.warning(
                self, "Cannot Delete",
                f"This location contains {active_stock} stock item(s) with quantity > 0.\n\n"
                "Please move or dispose of the stock first."
            )
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete location '{loc.code}'?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_location(self.db, loc.id)
                self._load_tree()
                self._clear_details()
                self.location_changed.emit()
                self.status_bar.showMessage(f"Location '{loc.code}' deleted", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _generate_auto_code(self, loc_type: str, parent_loc: Optional[Location] = None) -> str:
        """Generate auto code for a new location."""
        type_config = LOCATION_TYPES.get(loc_type)
        if not type_config:
            return ""

        prefix = type_config["prefix"]

        if parent_loc and loc_type in ("RACK", "BIN"):
            # Child of parent - use parent code as base
            base = f"{parent_loc.code}-{prefix[0]}"
            last = self.db.query(Location.code).filter(
                Location.code.like(f"{base}%")
            ).order_by(Location.code.desc()).first()

            if last:
                try:
                    num = int(last.code.split(base)[-1]) + 1
                except (ValueError, IndexError):
                    num = 1
            else:
                num = 1
            return f"{base}{num:02d}"
        else:
            # Root level
            base = f"{prefix}-"
            last = self.db.query(Location.code).filter(
                Location.code.like(f"{base}%")
            ).order_by(Location.code.desc()).first()

            if last:
                try:
                    num = int(last.code.split(base)[-1]) + 1
                except (ValueError, IndexError):
                    num = 1
            else:
                num = 1
            return f"{base}{num:03d}"

    def _export_locations(self):
        """Export location structure to Excel."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Locations", "locations_export.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            headers = ["Code", "Name", "Type", "Parent", "Description",
                      "Capacity", "Stock Items", "Total Qty", "Path"]
            data = []

            for loc in self.all_locations:
                parent_code = loc.parent.code if loc.parent else ""
                stock_count = len(loc.stocks)
                total_qty = sum(s.quantity for s in loc.stocks) if loc.stocks else 0

                data.append({
                    "Code": loc.code,
                    "Name": loc.name or "",
                    "Type": loc.location_type,
                    "Parent": parent_code,
                    "Description": loc.description or "",
                    "Capacity": loc.capacity or "",
                    "Stock Items": stock_count,
                    "Total Qty": total_qty,
                    "Path": loc.full_path,
                })

            export_to_excel(data, headers, file_path, sheet_name="Locations")
            self.status_bar.showMessage(f"Exported to {file_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def closeEvent(self, event):
        """Handle dialog close event."""
        self.db.close()
        super().closeEvent(event)


# ==================================================================
# Location Edit Dialog
# ==================================================================

class LocationEditDialog(QDialog):
    """Dialog for adding or editing a location."""

    def __init__(self, parent=None, db=None, is_new: bool = True,
                 location: Optional[Location] = None,
                 parent_location: Optional[Location] = None,
                 default_type: Optional[str] = None,
                 user_role: str = "viewer"):
        """
        Initialize the edit dialog.

        Args:
            parent: Parent widget
            db: Database session
            is_new: True for new location, False for editing
            location: Location to edit (if not new)
            parent_location: Parent location (for new child locations)
            default_type: Default location type
            user_role: User role for permissions
        """
        super().__init__(parent)
        self.parent_dialog = parent
        self.db = db
        self.is_new = is_new
        self.location = location
        self.parent_location = parent_location
        self.user_role = user_role

        # Window setup
        if is_new:
            self.setWindowTitle("Add New Location")
        else:
            self.setWindowTitle(f"Edit Location: {location.code if location else ''}")
        self.setMinimumWidth(500)
        self.setModal(True)

        self._init_ui()

        # Fill form
        if not is_new and location:
            self._load_location_data()
        elif is_new:
            self._generate_initial_code(default_type)

        # Apply permissions
        if user_role == "viewer":
            self._set_readonly()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Form
        form_group = QGroupBox("Location Information")
        form_group.setStyleSheet("""
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
        """)
        form = QFormLayout(form_group)
        form.setSpacing(8)

        # Code
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("Auto-generated (editable)")
        self.code_edit.setStyleSheet("""
            QLineEdit {
                font-family: 'Consolas', monospace;
                font-size: 13px;
                font-weight: bold;
                padding: 8px;
                border: 1px solid #B0BEC5;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border: 2px solid #004D40;
            }
        """)
        form.addRow("Code *:", self.code_edit)

        # Name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Location name")
        form.addRow("Name *:", self.name_edit)

        # Type
        self.type_combo = QComboBox()
        for type_key, type_data in LOCATION_TYPES.items():
            self.type_combo.addItem(
                f"{type_data['icon']} {type_data['label']} - {type_data['description']}",
                type_key
            )
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Type *:", self.type_combo)

        # Description
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Optional description")
        form.addRow("Description:", self.desc_edit)

        # Capacity
        self.capacity_combo = QComboBox()
        self.capacity_combo.setEditable(True)
        self.capacity_combo.addItems(["", "Small", "Medium", "Large", "Extra Large"])
        self.capacity_combo.setCurrentIndex(0)
        form.addRow("Capacity:", self.capacity_combo)

        # Notes
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Additional notes")
        form.addRow("Notes:", self.notes_edit)

        # Auto-code hint
        self.hint_label = QLabel("")
        self.hint_label.setStyleSheet("color: #00796B; font-style: italic; font-size: 11px;")
        form.addRow(self.hint_label)

        layout.addWidget(form_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_save = QPushButton("💾 Save")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2E86C1;
                color: white;
                border: none;
                padding: 10px 24px;
                font-weight: bold;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #2471A3; }
        """)
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)

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

    def _load_location_data(self):
        """Load location data into form."""
        loc = self.location
        self.code_edit.setText(loc.code)
        self.name_edit.setText(loc.name or "")

        idx = self.type_combo.findData(loc.location_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        self.desc_edit.setText(loc.description or "")

        if loc.capacity:
            idx = self.capacity_combo.findText(loc.capacity)
            if idx >= 0:
                self.capacity_combo.setCurrentIndex(idx)
            else:
                self.capacity_combo.setCurrentText(loc.capacity)

        self.notes_edit.setText(loc.notes or "")

    def _generate_initial_code(self, default_type: Optional[str] = None):
        """Generate initial code for new location."""
        loc_type = default_type or self.type_combo.currentData()
        if loc_type and self.parent_dialog:
            auto_code = self.parent_dialog._generate_auto_code(loc_type, self.parent_location)
            self.code_edit.setText(auto_code)
            self.hint_label.setText(f"Auto-generated: {auto_code} (you can edit)")

    def _on_type_changed(self):
        """Handle type change - regenerate code."""
        if self.is_new and self.parent_dialog:
            self._generate_initial_code()

    def _set_readonly(self):
        """Set all fields to read-only."""
        for widget in self.findChildren((QLineEdit, QComboBox)):
            if hasattr(widget, 'setReadOnly'):
                widget.setReadOnly(True)
            else:
                widget.setEnabled(False)

    def _save(self):
        """Save the location."""
        code = self.code_edit.text().strip()
        name = self.name_edit.text().strip()
        loc_type = self.type_combo.currentData()

        if not code:
            QMessageBox.warning(self, "Validation", "Location code is required.")
            return

        if not name:
            QMessageBox.warning(self, "Validation", "Location name is required.")
            return

        try:
            if self.is_new:
                # Check duplicate code
                existing = self.db.query(Location).filter_by(code=code).first()
                if existing:
                    QMessageBox.warning(
                        self, "Duplicate Code",
                        f"A location with code '{code}' already exists."
                    )
                    return

                parent_id = self.parent_location.id if self.parent_location else None
                create_location(
                    self.db,
                    code=code,
                    name=name,
                    loc_type=loc_type,
                    parent_id=parent_id,
                    description=self.desc_edit.text().strip(),
                    capacity=self.capacity_combo.currentText().strip(),
                    notes=self.notes_edit.text().strip()
                )
            else:
                update_location(
                    self.db,
                    self.location.id,
                    code=code,
                    name=name,
                    location_type=loc_type,
                    description=self.desc_edit.text().strip(),
                    capacity=self.capacity_combo.currentText().strip(),
                    notes=self.notes_edit.text().strip()
                )

            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save location:\n{str(e)}")