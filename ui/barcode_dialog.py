# ui/barcode_dialog.py
"""
Barcode/QR Code Scanner Dialog – iMat Material Control System (EPC Edition).

Provides a floating barcode scanning interface with:
- Manual barcode entry via keyboard
- Barcode format auto-detection
- Quick item lookup and transaction creation
- New item registration for unknown codes
- Scan history with recent items
- Sound feedback on scan
- Support for multiple barcode formats
- Keyboard shortcut activation
- Always-on-top floating window
- Visual feedback animations
"""

import re
import time
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QFrame,
    QListWidget, QListWidgetItem, QWidget, QSplitter,
    QCheckBox, QComboBox, QStatusBar, QSizePolicy,
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QSize, QRect, QPoint
)
from PyQt6.QtGui import (
    QFont, QColor, QIcon, QKeySequence, QShortcut,
    QPainter, QPen, QBrush, QPalette
)

from db.database import get_db_session
from db.models import Product, Stock, Location
from ui.logo_widget import LogoWidget

# Try to import optional sound library
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# ==================================================================
# Constants
# ==================================================================

# Barcode format patterns
BARCODE_PATTERNS = {
    "EAN-13": r"^\d{13}$",
    "EAN-8": r"^\d{8}$",
    "UPC-A": r"^\d{12}$",
    "UPC-E": r"^\d{6}$",
    "CODE-39": r"^[A-Z0-9\-\.\ \$\/\+\%]{1,43}$",
    "CODE-128": r"^[\x00-\x7F]{1,80}$",
    "QR-CODE": r"^[A-Za-z0-9\-_]{1,100}$",
    "CUSTOM": r"^[A-Z]{2,4}-\d{3,6}$",
}

# Prefix/suffix for iMat item codes
IMAT_PREFIXES = ["PIP-", "FLG-", "CBL-", "VLV-", "FIT-", "ELC-", "INS-", "MEC-"]

# Scan history limit
MAX_HISTORY = 50

# Scan debounce time (ms)
SCAN_DEBOUNCE = 300


# ==================================================================
# Barcode Scanner Widget
# ==================================================================

class BarcodeScannerWidget(QWidget):
    """Visual barcode scanner animation widget."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 60)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_angle)
        self._active = False

    def start_animation(self):
        """Start scanning animation."""
        self._active = True
        self._timer.start(50)

    def stop_animation(self):
        """Stop scanning animation."""
        self._active = False
        self._timer.stop()
        self.update()

    def _update_angle(self):
        """Update scan line angle."""
        self._angle = (self._angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        """Paint the scanner widget."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background circle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#E0F2F1")))
        painter.drawEllipse(5, 5, 50, 50)

        # Border
        painter.setPen(QPen(QColor("#004D40"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(5, 5, 50, 50)

        # Barcode lines
        painter.setPen(QPen(QColor("#004D40"), 2))
        line_positions = [15, 20, 26, 30, 36, 40, 46]
        for x in line_positions:
            painter.drawLine(x, 18, x, 42)

        # Scanning line (animated)
        if self._active:
            painter.save()
            painter.translate(30, 30)
            painter.rotate(self._angle)
            painter.setPen(QPen(QColor("#FF0000"), 1.5))
            painter.drawLine(-20, 0, 20, 0)
            painter.restore()


# ==================================================================
# Barcode Dialog
# ==================================================================

class BarcodeDialog(QDialog):
    """
    Floating barcode scanner dialog for quick item lookup.
    
    Features:
    - Always-on-top floating window
    - Manual barcode entry
    - Auto-detection of barcode format
    - Quick transaction creation
    - New item registration
    - Scan history
    - Sound feedback
    """

    # Signals
    barcode_scanned = pyqtSignal(str)
    item_found = pyqtSignal(str, str)  # item_code, description
    transaction_requested = pyqtSignal(str)  # item_code

    def __init__(self, main_window, parent=None, user_role: str = "viewer"):
        """
        Initialize the barcode dialog.
        
        Args:
            main_window: Reference to main window for transaction creation
            parent: Parent widget
            user_role: Current user's role
        """
        super().__init__(parent)
        self.main_window = main_window
        self.user_role = user_role
        self.scan_history: List[Dict] = []
        self.last_scan_time = 0
        self.sound_enabled = True
        self.auto_open_transaction = True
        
        # Window setup
        self.setWindowTitle("iMat – Barcode Scanner")
        self.setFixedSize(450, 500)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Setup UI
        self._init_ui()
        
        # Setup shortcuts
        self._setup_shortcuts()
        
        # Focus on input
        QTimer.singleShot(100, self.barcode_input.setFocus)

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _init_ui(self):
        """Initialize the user interface."""
        # Main card with shadow
        self.card = QFrame(self)
        self.card.setObjectName("barcodeCard")
        self.card.setStyleSheet("""
            #barcodeCard {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F5FFFA
                );
                border-radius: 16px;
                border: 2px solid #008B8B;
            }
        """)
        self.card.setGeometry(0, 0, 450, 500)

        # Shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.card.setGraphicsEffect(shadow)

        # Main layout
        main_layout = QVBoxLayout(self.card)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(8)

        # ---- Title Bar ----
        title_bar = self._build_title_bar()
        main_layout.addLayout(title_bar)

        # ---- Scanner Animation ----
        scanner_layout = QHBoxLayout()
        scanner_layout.addStretch()
        self.scanner_widget = BarcodeScannerWidget()
        scanner_layout.addWidget(self.scanner_widget)
        scanner_layout.addStretch()
        main_layout.addLayout(scanner_layout)

        # ---- Status Label ----
        self.status_label = QLabel("📷 Ready to scan...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            color: #004D40;
            font-weight: bold;
            font-size: 13px;
            background: transparent;
            padding: 4px;
        """)
        main_layout.addWidget(self.status_label)

        # ---- Barcode Input ----
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px solid #B0C4DE;
                border-radius: 10px;
                padding: 2px;
            }
            QFrame:focus-within {
                border: 2px solid #008B8B;
            }
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 4, 4, 4)
        input_layout.setSpacing(4)

        # Barcode icon
        icon_label = QLabel("📷")
        icon_label.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        input_layout.addWidget(icon_label)

        # Input field
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Scan or type barcode here...")
        self.barcode_input.setMinimumHeight(40)
        self.barcode_input.setStyleSheet("""
            QLineEdit {
                border: none;
                padding: 6px 10px;
                font-size: 15px;
                font-family: 'Consolas', 'Courier New', monospace;
                background: transparent;
                color: #004D40;
            }
            QLineEdit:focus {
                border: none;
            }
        """)
        self.barcode_input.setClearButtonEnabled(True)
        input_layout.addWidget(self.barcode_input)

        # Submit button
        btn_submit = QPushButton("🔍")
        btn_submit.setFixedSize(40, 40)
        btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #00897B;
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00695C;
            }
            QPushButton:pressed {
                background-color: #004D40;
            }
        """)
        btn_submit.clicked.connect(self._process_barcode)
        input_layout.addWidget(btn_submit)

        main_layout.addWidget(input_frame)

        # ---- Format Detection ----
        self.format_label = QLabel("")
        self.format_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.format_label.setStyleSheet("""
            color: #666;
            font-size: 10px;
            background: transparent;
        """)
        main_layout.addWidget(self.format_label)

        # ---- Options ----
        options_layout = QHBoxLayout()
        options_layout.setSpacing(10)

        self.auto_open_check = QCheckBox("Auto-open transaction")
        self.auto_open_check.setChecked(self.auto_open_transaction)
        self.auto_open_check.setStyleSheet("font-size: 10px; color: #555;")
        options_layout.addWidget(self.auto_open_check)

        self.sound_check = QCheckBox("Sound")
        self.sound_check.setChecked(self.sound_enabled)
        self.sound_check.setStyleSheet("font-size: 10px; color: #555;")
        options_layout.addWidget(self.sound_check)

        options_layout.addStretch()
        main_layout.addLayout(options_layout)

        # ---- History List ----
        history_label = QLabel("📋 Recent Scans:")
        history_label.setStyleSheet("""
            font-weight: bold;
            color: #004D40;
            font-size: 11px;
            background: transparent;
            margin-top: 4px;
        """)
        main_layout.addWidget(history_label)

        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(150)
        self.history_list.setStyleSheet("""
            QListWidget {
                background: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 6px 10px;
                border-bottom: 1px solid #EEE;
            }
            QListWidget::item:hover {
                background: #E0F2F1;
            }
            QListWidget::item:selected {
                background: #B2DFDB;
                color: #004D40;
            }
        """)
        self.history_list.itemDoubleClicked.connect(self._on_history_double_clicked)
        main_layout.addWidget(self.history_list)

        # ---- Bottom Buttons ----
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)

        btn_clear_history = QPushButton("🗑️ Clear History")
        btn_clear_history.setStyleSheet(self._get_button_style("neutral"))
        btn_clear_history.clicked.connect(self._clear_history)
        bottom_layout.addWidget(btn_clear_history)

        bottom_layout.addStretch()

        btn_new_item = QPushButton("📦 New Item")
        btn_new_item.setStyleSheet(self._get_button_style("primary"))
        btn_new_item.clicked.connect(self._open_new_item_dialog)
        bottom_layout.addWidget(btn_new_item)

        btn_close = QPushButton("✕ Close")
        btn_close.setStyleSheet(self._get_button_style("danger"))
        btn_close.clicked.connect(self._close_dialog)
        bottom_layout.addWidget(btn_close)

        main_layout.addLayout(bottom_layout)

        # ---- Status Bar ----
        self.status_bar = QStatusBar()
        self.status_bar.setMaximumHeight(20)
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: transparent;
                color: #888;
                font-size: 9px;
                border: none;
            }
        """)
        self.status_bar.showMessage("Press ESC to close | Enter to scan")
        main_layout.addWidget(self.status_bar)

    def _build_title_bar(self) -> QHBoxLayout:
        """Build the title bar with drag handle."""
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(4, 0, 4, 0)

        # Logo
        logo = LogoWidget()
        title_bar.addWidget(logo)

        title_bar.addStretch()

        # Slogan
        slogan = QLabel("iMat Barcode")
        slogan.setStyleSheet("""
            color: #008B8B;
            font-weight: bold;
            font-size: 14px;
            background: transparent;
        """)
        title_bar.addWidget(slogan)

        title_bar.addStretch()

        # Always on top toggle
        btn_pin = QPushButton("📌")
        btn_pin.setFixedSize(28, 28)
        btn_pin.setCheckable(True)
        btn_pin.setChecked(True)
        btn_pin.setToolTip("Toggle always on top")
        btn_pin.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14px;
                border-radius: 14px;
            }
            QPushButton:hover {
                background: #E0E0E0;
            }
            QPushButton:checked {
                background: #B2DFDB;
            }
        """)
        btn_pin.clicked.connect(self._toggle_always_on_top)
        title_bar.addWidget(btn_pin)

        # Minimize button
        btn_min = QPushButton("−")
        btn_min.setFixedSize(28, 28)
        btn_min.setToolTip("Minimize")
        btn_min.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
                font-weight: bold;
                color: #888;
                border-radius: 14px;
            }
            QPushButton:hover {
                background: #E0E0E0;
                color: #333;
            }
        """)
        btn_min.clicked.connect(self.showMinimized)
        title_bar.addWidget(btn_min)

        # Close button
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setToolTip("Close scanner")
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14px;
                font-weight: bold;
                color: #888;
                border-radius: 14px;
            }
            QPushButton:hover {
                background: #FFCDD2;
                color: #D32F2F;
            }
        """)
        btn_close.clicked.connect(self._close_dialog)
        title_bar.addWidget(btn_close)

        return title_bar

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Enter key to scan
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self._process_barcode)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, self._process_barcode)
        
        # Escape to close
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._close_dialog)
        
        # Ctrl+L to clear input
        QShortcut(QKeySequence("Ctrl+L"), self, self.barcode_input.clear)

    # ==================================================================
    # Style Methods
    # ==================================================================

    def _get_button_style(self, button_type: str) -> str:
        """Get button stylesheet by type."""
        styles = {
            "primary": """
                QPushButton {
                    background-color: #00897B;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    font-weight: bold;
                    border-radius: 6px;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #00695C; }
            """,
            "danger": """
                QPushButton {
                    background-color: #EF5350;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    font-weight: bold;
                    border-radius: 6px;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #E53935; }
            """,
            "neutral": """
                QPushButton {
                    background-color: #E0E0E0;
                    color: #333;
                    border: none;
                    padding: 6px 12px;
                    font-weight: bold;
                    border-radius: 6px;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #D0D0D0; }
            """,
        }
        return styles.get(button_type, styles["neutral"])

    # ==================================================================
    # Barcode Processing
    # ==================================================================

    def _process_barcode(self):
        """Process the entered barcode."""
        # Debounce
        current_time = time.time()
        if current_time - self.last_scan_time < SCAN_DEBOUNCE / 1000:
            return
        self.last_scan_time = current_time

        code = self.barcode_input.text().strip()
        if not code:
            self._show_status("⚠️ Please enter a barcode", "warning")
            return

        # Detect format
        barcode_format = self._detect_format(code)
        self.format_label.setText(f"Format: {barcode_format}")

        # Clean code (remove prefix/suffix if needed)
        clean_code = self._clean_barcode(code)

        # Play sound
        if self.sound_check.isChecked():
            self._play_scan_sound()

        # Start scanner animation
        self.scanner_widget.start_animation()
        QTimer.singleShot(1000, self.scanner_widget.stop_animation)

        # Emit signal
        self.barcode_scanned.emit(clean_code)

        # Look up item
        self._lookup_item(clean_code)

        # Clear input for next scan
        self.barcode_input.clear()
        self.barcode_input.setFocus()

    def _detect_format(self, code: str) -> str:
        """
        Detect barcode format from pattern.
        
        Args:
            code: Barcode string
            
        Returns:
            Detected format name
        """
        for format_name, pattern in BARCODE_PATTERNS.items():
            if re.match(pattern, code):
                return format_name
        
        # Check iMat prefixes
        for prefix in IMAT_PREFIXES:
            if code.startswith(prefix):
                return f"iMat-{prefix.rstrip('-')}"
        
        return "Unknown"

    def _clean_barcode(self, code: str) -> str:
        """
        Clean barcode by removing common prefixes/suffixes.
        
        Args:
            code: Raw barcode string
            
        Returns:
            Cleaned item code
        """
        # Remove common barcode prefixes
        prefixes_to_remove = ["SCAN:", "BAR:", "QR:"]
        for prefix in prefixes_to_remove:
            if code.upper().startswith(prefix):
                code = code[len(prefix):]

        # Remove whitespace and special characters
        code = code.strip().upper()
        
        return code

    def _lookup_item(self, code: str):
        """
        Look up item in database by barcode.
        
        Args:
            code: Item code to look up
        """
        session = get_db_session()
        try:
            # Search by item_code
            product = session.query(Product).filter_by(item_code=code).first()

            if not product:
                # Try partial match
                product = session.query(Product).filter(
                    Product.item_code.like(f"%{code}%")
                ).first()

            if product:
                # Item found
                self._on_item_found(product)
            else:
                # Item not found
                self._on_item_not_found(code)

        except Exception as e:
            self._show_status(f"❌ Error: {str(e)}", "error")
        finally:
            session.close()

    def _on_item_found(self, product):
        """
        Handle found item.
        
        Args:
            product: Product object
        """
        # Get stock info
        session = get_db_session()
        try:
            total_stock = session.query(
                Stock.quantity, Stock.qc_status
            ).filter(
                Stock.item_code == product.item_code,
                Stock.quantity > 0
            ).all()

            available = sum(s[0] for s in total_stock if s[1] == "ACCEPTED")
            quarantine = sum(s[0] for s in total_stock if s[1] == "QUARANTINE")
        finally:
            session.close()

        # Update status
        status_text = f"✅ Found: {product.description or product.item_code}"
        if available > 0:
            status_text += f" | Available: {available:.0f}"
        if quarantine > 0:
            status_text += f" | Quarantine: {quarantine:.0f}"
        
        self._show_status(status_text, "success")

        # Update display
        self.status_label.setText(
            f"📦 {product.item_code} - {product.description or 'No description'}"
        )
        self.status_label.setStyleSheet("""
            color: #2E7D32;
            font-weight: bold;
            font-size: 12px;
            background: transparent;
        """)

        # Add to history
        self._add_to_history(product.item_code, product.description or "", True)

        # Emit signals
        self.item_found.emit(product.item_code, product.description or "")

        # Auto-open transaction if enabled
        if self.auto_open_check.isChecked() and self.user_role != "viewer":
            self._open_transaction_dialog(product.item_code)

    def _on_item_not_found(self, code: str):
        """
        Handle item not found.
        
        Args:
            code: Item code that wasn't found
        """
        self._show_status(f"❓ Not found: {code}", "warning")
        
        self.status_label.setText(f"🔍 Code '{code}' not in database")
        self.status_label.setStyleSheet("""
            color: #E65100;
            font-weight: bold;
            font-size: 12px;
            background: transparent;
        """)

        # Add to history
        self._add_to_history(code, "Not found", False)

        # Ask user what to do
        if self.user_role != "viewer":
            reply = QMessageBox.question(
                self,
                "Item Not Found",
                f"The code '{code}' was not found in your inventory.\n\n"
                "Would you like to create a new item with this code?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )

            if reply == QMessageBox.StandardButton.Yes:
                self._open_new_item_dialog(code)

    def _open_transaction_dialog(self, item_code: str):
        """
        Open transaction dialog for an item.
        
        Args:
            item_code: Item code to create transaction for
        """
        from ui.transaction_dialog import TransactionDialog
        
        dlg = TransactionDialog(
            self.main_window,
            item_code=item_code,
            user_role=self.user_role
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if self.main_window:
                self.main_window.refresh_data()
            self.transaction_requested.emit(item_code)

    def _open_new_item_dialog(self, item_code: str = ""):
        """
        Open new item dialog.
        
        Args:
            item_code: Optional item code to pre-fill
        """
        from ui.product_dialog import ProductDialog
        
        dlg = ProductDialog(
            self.main_window,
            item_code=item_code,
            user_role=self.user_role
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if self.main_window:
                self.main_window.refresh_data()
            if item_code:
                self._lookup_item(item_code)

    # ==================================================================
    # History Management
    # ==================================================================

    def _add_to_history(self, code: str, description: str, found: bool):
        """
        Add scan to history.
        
        Args:
            code: Scanned code
            description: Item description
            found: Whether item was found
        """
        # Remove duplicate if exists
        self.scan_history = [
            h for h in self.scan_history
            if h["code"] != code
        ]

        # Add new entry
        self.scan_history.insert(0, {
            "code": code,
            "description": description,
            "found": found,
            "timestamp": datetime.now()
        })

        # Limit history
        if len(self.scan_history) > MAX_HISTORY:
            self.scan_history = self.scan_history[:MAX_HISTORY]

        # Update list widget
        self._update_history_display()

    def _update_history_display(self):
        """Update the history list widget."""
        self.history_list.clear()

        for entry in self.scan_history:
            icon = "✅" if entry["found"] else "❓"
            time_str = entry["timestamp"].strftime("%H:%M:%S")
            text = f"{icon} {entry['code']} - {entry['description']} ({time_str})"
            
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry["code"])
            
            if not entry["found"]:
                item.setForeground(QColor("#E65100"))
            else:
                item.setForeground(QColor("#2E7D32"))
            
            self.history_list.addItem(item)

    def _on_history_double_clicked(self, item):
        """
        Handle double-click on history item.
        
        Args:
            item: Clicked QListWidgetItem
        """
        code = item.data(Qt.ItemDataRole.UserRole)
        if code:
            self.barcode_input.setText(code)
            self._process_barcode()

    def _clear_history(self):
        """Clear scan history."""
        reply = QMessageBox.question(
            self, "Clear History",
            "Clear all scan history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.scan_history.clear()
            self.history_list.clear()
            self._show_status("History cleared", "info")

    # ==================================================================
    # UI Helpers
    # ==================================================================

    def _show_status(self, message: str, status_type: str = "info"):
        """
        Show status message with color.
        
        Args:
            message: Status message
            status_type: Type of status ('info', 'success', 'warning', 'error')
        """
        colors = {
            "info": "#1976D2",
            "success": "#2E7D32",
            "warning": "#E65100",
            "error": "#D32F2F",
        }
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background: transparent;
                color: {colors.get(status_type, '#888')};
                font-size: 9px;
                font-weight: bold;
                border: none;
            }}
        """)
        self.status_bar.showMessage(message, 5000)

    def _play_scan_sound(self):
        """Play scan confirmation sound."""
        if PYGAME_AVAILABLE:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                
                # Generate simple beep
                import numpy as np
                sample_rate = 44100
                duration = 0.1
                frequency = 1000
                
                t = np.linspace(0, duration, int(sample_rate * duration), False)
                tone = np.sin(frequency * 2 * np.pi * t)
                
                # Fade out
                fade = np.linspace(1.0, 0.0, len(tone))
                tone = (tone * fade * 32767).astype(np.int16)
                
                sound = pygame.sndarray.make_sound(tone)
                sound.play()
            except Exception:
                pass  # Silently fail if sound not available

    def _toggle_always_on_top(self):
        """Toggle always-on-top window flag."""
        flags = self.windowFlags()
        if flags & Qt.WindowType.WindowStaysOnTopHint:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        self.show()

    def _close_dialog(self):
        """Close the barcode dialog."""
        if self.main_window:
            self.main_window.action_barcode.setChecked(False)
        self.close()

    # ==================================================================
    # Window Dragging
    # ==================================================================

    def mousePressEvent(self, event):
        """Handle mouse press for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for window dragging."""
        if hasattr(self, '_drag_pos') and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if hasattr(self, '_drag_pos'):
            del self._drag_pos
        super().mouseReleaseEvent(event)

    # ==================================================================
    # Public Methods
    # ==================================================================

    def focus_input(self):
        """Focus the barcode input field."""
        self.barcode_input.setFocus()
        self.barcode_input.selectAll()

    def set_code(self, code: str):
        """
        Set barcode code programmatically.
        
        Args:
            code: Barcode string
        """
        self.barcode_input.setText(code)
        self._process_barcode()

    def get_history(self) -> List[Dict]:
        """
        Get scan history.
        
        Returns:
            List of scan history entries
        """
        return self.scan_history.copy()

    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.main_window:
            self.main_window.action_barcode.setChecked(False)
        super().closeEvent(event)