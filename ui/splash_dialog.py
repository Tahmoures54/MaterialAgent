# ui/splash_dialog.py
"""
Splash Screen Dialog – iMat Material Control System (EPC Edition).

Animated splash screen with:
- Smooth fade-in entrance animation
- Progress bar with status messages
- Pulsing logo animation
- Version and copyright display
- Loading tips rotation
- Database initialization progress
- Module loading status
- Graceful error handling
- Skip button for fast systems
- Responsive design
- Professional EPC branding
"""

import os
import sys
import random
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, 
    QWidget, QHBoxLayout, QPushButton, QGraphicsOpacityEffect,
    QApplication
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QTimer,
    QParallelAnimationGroup, QSequentialAnimationGroup,
    QPauseAnimation, QSize
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPaintEvent
)

from ui.logo_widget import SplashLogoWidget, AnimatedDot

# ==================================================================
# Constants
# ==================================================================

APP_NAME = "iMat Warehouse"
APP_VERSION = "2.0.0"
APP_EDITION = "EPC Edition"
APP_COPYRIGHT = f"© {datetime.now().year} iMat International"
APP_WEBSITE = "www.imat.io"

# Splash duration in milliseconds
SPLASH_DURATION = 3000
FADE_OUT_DURATION = 500

# Loading messages
LOADING_MESSAGES = [
    "Initializing database connection...",
    "Loading material catalog...",
    "Preparing warehouse structure...",
    "Loading AI prediction engine...",
    "Setting up quality control module...",
    "Loading document templates...",
    "Preparing report generator...",
    "Checking license status...",
    "Loading user preferences...",
    "Starting application...",
]

# Loading tips
LOADING_TIPS = [
    "💡 Tip: Use barcode scanner for quick item lookup",
    "💡 Tip: Double-click items in tables to edit",
    "💡 Tip: Right-click for context menus everywhere",
    "💡 Tip: Use Ctrl+F to search in any table",
    "💡 Tip: Export reports to Excel for further analysis",
    "💡 Tip: AI prediction works best with 90+ days of data",
    "💡 Tip: Set up auto-backup in System menu",
    "💡 Tip: Use WhatsApp button to share reports instantly",
    "💡 Tip: QC release can process multiple items at once",
    "💡 Tip: Material traceability tracks every movement",
]


# ==================================================================
# Splash Dialog
# ==================================================================

class SplashDialog(QDialog):
    """
    Animated splash screen for iMat application startup.
    
    Features:
    - Smooth fade-in and fade-out
    - Animated progress bar
    - Loading status messages
    - Random tips display
    - Professional branding
    """

    def __init__(self, parent=None):
        """
        Initialize the splash screen.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Window setup
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(480, 320)
        
        # State
        self._progress_value = 0
        self._current_message_index = 0
        self._skip_requested = False
        
        # Build UI
        self._init_ui()
        
        # Setup animations
        self._setup_animations()
        
        # Center on screen
        self._center_on_screen()

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _init_ui(self):
        """Initialize the splash screen UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Card container
        self.card = QWidget(self)
        self.card.setObjectName("splashCard")
        self.card.setStyleSheet("""
            #splashCard {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F5FFFA
                );
                border-radius: 20px;
                border: 2px solid #B2DFDB;
            }
        """)
        self.card.setGeometry(0, 0, 480, 320)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(30, 20, 30, 20)
        card_layout.setSpacing(0)

        # ---- Top Section: Logo & Title ----
        top_section = QVBoxLayout()
        top_section.setSpacing(8)
        top_section.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo widget (compact version with larger dot)
        logo_container = QWidget()
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Animated dot
        self.pulse_dot = AnimatedDot(color=QColor("#004D40"))
        self.pulse_dot.setFixedSize(24, 24)
        logo_layout.addWidget(self.pulse_dot)
        logo_layout.addSpacing(8)

        # App name
        app_name = QLabel(APP_NAME)
        app_name.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        app_name.setStyleSheet("color: #004D40; background: transparent; border: none;")
        logo_layout.addWidget(app_name)

        top_section.addWidget(logo_container)

        # Edition badge
        edition_label = QLabel(APP_EDITION)
        edition_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        edition_label.setStyleSheet("""
            color: #00897B;
            background: transparent;
            border: none;
            padding: 2px 12px;
        """)
        edition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_section.addWidget(edition_label)

        # Slogan
        slogan = QLabel("Where Inventory Meets AI")
        slogan.setFont(QFont("Segoe UI", 10))
        slogan.setStyleSheet("color: #607D8B; font-style: italic; background: transparent; border: none;")
        slogan.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_section.addWidget(slogan)

        card_layout.addLayout(top_section)
        card_layout.addSpacing(15)

        # ---- Progress Section ----
        progress_section = QVBoxLayout()
        progress_section.setSpacing(6)

        # Status message
        self.message_label = QLabel("Initializing, please wait...")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setStyleSheet("""
            color: #555;
            font-size: 12px;
            background: transparent;
            border: none;
        """)
        progress_section.addWidget(self.message_label)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFixedHeight(22)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #E0E0E0;
                border: none;
                border-radius: 11px;
                text-align: center;
                font-size: 10px;
                font-weight: bold;
                color: #333;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #004D40, stop:0.5 #00897B, stop:1 #4DB6AC
                );
                border-radius: 11px;
            }
        """)
        progress_section.addWidget(self.progress)

        # Percentage label
        self.percentage_label = QLabel("0%")
        self.percentage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.percentage_label.setStyleSheet("""
            color: #004D40;
            font-size: 18px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        progress_section.addWidget(self.percentage_label)

        card_layout.addLayout(progress_section)
        card_layout.addSpacing(10)

        # ---- Tip Section ----
        tip_layout = QHBoxLayout()
        tip_layout.setSpacing(6)
        
        tip_icon = QLabel("💡")
        tip_icon.setStyleSheet("font-size: 14px; background: transparent; border: none;")
        tip_layout.addWidget(tip_icon)
        
        self.tip_label = QLabel(random.choice(LOADING_TIPS))
        self.tip_label.setWordWrap(True)
        self.tip_label.setStyleSheet("""
            color: #78909C;
            font-size: 10px;
            font-style: italic;
            background: transparent;
            border: none;
        """)
        tip_layout.addWidget(self.tip_label, 1)

        card_layout.addLayout(tip_layout)
        card_layout.addStretch()

        # ---- Bottom: Version & Copyright ----
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)

        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setStyleSheet("""
            color: #90A4AE;
            font-size: 9px;
            background: transparent;
            border: none;
        """)
        bottom_layout.addWidget(version_label)

        bottom_layout.addStretch()

        copyright_label = QLabel(APP_COPYRIGHT)
        copyright_label.setStyleSheet("""
            color: #90A4AE;
            font-size: 9px;
            background: transparent;
            border: none;
        """)
        bottom_layout.addWidget(copyright_label)

        bottom_layout.addStretch()

        website_label = QLabel(APP_WEBSITE)
        website_label.setStyleSheet("""
            color: #00897B;
            font-size: 9px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        bottom_layout.addWidget(website_label)

        card_layout.addLayout(bottom_layout)

    # ==================================================================
    # Animation Setup
    # ==================================================================

    def _setup_animations(self):
        """Setup all splash screen animations."""
        # Entrance fade-in effect
        self._opacity_effect = QGraphicsOpacityEffect()
        self._opacity_effect.setOpacity(0.0)
        self.card.setGraphicsEffect(self._opacity_effect)

        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in.setDuration(600)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Progress bar animation
        self._progress_anim = QPropertyAnimation(self.progress, b"value")
        self._progress_anim.setDuration(SPLASH_DURATION)
        self._progress_anim.setStartValue(0)
        self._progress_anim.setEndValue(100)
        self._progress_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Connect progress updates
        self._progress_anim.valueChanged.connect(self._on_progress_changed)
        self._progress_anim.finished.connect(self._on_animation_finished)

        # Message rotation timer
        self._message_timer = QTimer(self)
        self._message_timer.timeout.connect(self._rotate_message)
        self._message_timer.setInterval(800)

        # Tip rotation timer
        self._tip_timer = QTimer(self)
        self._tip_timer.timeout.connect(self._rotate_tip)
        self._tip_timer.setInterval(5000)

    def _center_on_screen(self):
        """Center the splash screen on the primary monitor."""
        screen = QApplication.primaryScreen()
        if screen:
            center = screen.availableGeometry().center()
            frame = self.frameGeometry()
            frame.moveCenter(center)
            self.move(frame.topLeft())

    # ==================================================================
    # Animation Events
    # ==================================================================

    def _on_progress_changed(self, value: int):
        """Handle progress value change."""
        self._progress_value = value
        self.percentage_label.setText(f"{value}%")

    def _rotate_message(self):
        """Rotate loading messages."""
        self._current_message_index = (self._current_message_index + 1) % len(LOADING_MESSAGES)
        self.message_label.setText(LOADING_MESSAGES[self._current_message_index])

    def _rotate_tip(self):
        """Rotate loading tips."""
        new_tip = random.choice(LOADING_TIPS)
        self.tip_label.setText(new_tip)

    def _on_animation_finished(self):
        """Handle animation completion."""
        if not self._skip_requested:
            # Brief pause then close
            QTimer.singleShot(200, self._fade_out_and_close)

    def _fade_out_and_close(self):
        """Fade out and close the splash screen."""
        self._fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_out.setDuration(FADE_OUT_DURATION)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out.finished.connect(self._do_close)
        self._fade_out.start()

    def _do_close(self):
        """Actually close the dialog."""
        self.accept()

    # ==================================================================
    # Public Methods
    # ==================================================================

    def start_animation(self):
        """Start all splash animations."""
        # Start fade-in
        self._fade_in.start()
        
        # Start progress after fade-in
        QTimer.singleShot(400, self._progress_anim.start)
        
        # Start message rotation
        QTimer.singleShot(200, self._message_timer.start)
        
        # Start tip rotation
        QTimer.singleShot(1000, self._tip_timer.start)

    def skip(self):
        """Skip the splash screen immediately."""
        self._skip_requested = True
        self._message_timer.stop()
        self._tip_timer.stop()
        
        # Jump to end
        self._progress_anim.stop()
        self.progress.setValue(100)
        self.percentage_label.setText("100%")
        self.message_label.setText("Ready!")
        
        # Quick fade out
        QTimer.singleShot(100, self._fade_out_and_close)

    def set_message(self, message: str):
        """
        Set a custom status message.
        
        Args:
            message: Status message to display
        """
        self.message_label.setText(message)

    def set_progress(self, value: int):
        """
        Set progress value directly.
        
        Args:
            value: Progress value (0-100)
        """
        if 0 <= value <= 100:
            self.progress.setValue(value)
            self.percentage_label.setText(f"{value}%")
            self._progress_value = value

    def showEvent(self, event):
        """Handle show event."""
        super().showEvent(event)
        self.start_animation()

    def keyPressEvent(self, event):
        """Handle key press - Escape to skip."""
        if event.key() == Qt.Key.Key_Escape:
            self.skip()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press - click to skip."""
        self.skip()
        super().mousePressEvent(event)

    def exec(self):
        """Override exec to handle the case where animation finishes."""
        # Start animation
        self.start_animation()
        # Call parent exec
        return super().exec()


# ==================================================================
# Simple Splash (Lightweight version for quick startup)
# ==================================================================

class SimpleSplashDialog(QDialog):
    """Lightweight splash screen for quick startup scenarios."""

    def __init__(self, parent=None):
        """Initialize the simple splash."""
        super().__init__(parent)
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(350, 200)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # App name
        name = QLabel(APP_NAME)
        name.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        name.setStyleSheet("color: #004D40;")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)

        # Loading
        self.message = QLabel("Loading...")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setStyleSheet("color: #666;")
        layout.addWidget(self.message)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #E0E0E0;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #004D40;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress)

        # Center on screen
        screen = QApplication.primaryScreen()
        if screen:
            center = screen.availableGeometry().center()
            frame = self.frameGeometry()
            frame.moveCenter(center)
            self.move(frame.topLeft())

    def set_message(self, message: str):
        """Set status message."""
        self.message.setText(message)

    def set_progress(self, value: int):
        """Set progress value."""
        self.progress.setValue(value)


# ==================================================================
# Module Exports
# ==================================================================

__all__ = ['SplashDialog', 'SimpleSplashDialog']