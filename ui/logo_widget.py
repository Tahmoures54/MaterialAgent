# ui/logo_widget.py
"""
Animated Logo Widget – iMat Material Control System (EPC Edition).

Custom animated logo widget with:
- Pulsing dot animation
- Gradient text effects
- Smooth fade-in entrance (on text labels)
- Hover interaction effects
- Customizable colors and text
- Support for dark/light themes
- Optional logo image display
- Shadow and glow effects
- Resize responsive design
- Accessibility support (tooltips)
"""

import os
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect,
    QSizePolicy, QApplication
)
from PyQt6.QtGui import (
    QPixmap, QColor, QFont, QPainter, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPaintEvent,
    QMouseEvent, QEnterEvent
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QSequentialAnimationGroup,
    QPauseAnimation, QSize, QRect, QPoint, QPointF, QTimer,
    pyqtProperty
)


# ==================================================================
# Animated Dot Widget
# ==================================================================

class AnimatedDot(QWidget):
    """Animated pulsing dot with glow effect."""

    def __init__(self, color: QColor = QColor("#008B8B"), parent=None):
        """
        Initialize the animated dot.

        Args:
            color: Color of the dot
            parent: Parent widget
        """
        super().__init__(parent)
        self._color = color
        self._pulse_scale = 1.0
        self._glow_opacity = 0.6

        self.setFixedSize(24, 24)

        # Setup animations
        self._setup_animations()

    def _setup_animations(self):
        """Setup pulse animations."""
        # Pulse scale animation
        self._pulse_anim = QPropertyAnimation(self, b"pulse_scale")
        self._pulse_anim.setDuration(1500)
        self._pulse_anim.setStartValue(1.0)
        self._pulse_anim.setEndValue(0.7)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.setLoopCount(-1)

        # Glow opacity animation
        self._glow_anim = QPropertyAnimation(self, b"glow_opacity")
        self._glow_anim.setDuration(1500)
        self._glow_anim.setStartValue(0.6)
        self._glow_anim.setEndValue(0.2)
        self._glow_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._glow_anim.setLoopCount(-1)

        # Start animations
        self._pulse_anim.start()
        self._glow_anim.start()

    def get_pulse_scale(self) -> float:
        """Get pulse scale value."""
        return self._pulse_scale

    def set_pulse_scale(self, scale: float):
        """Set pulse scale value."""
        self._pulse_scale = scale
        self.update()

    def get_glow_opacity(self) -> float:
        """Get glow opacity value."""
        return self._glow_opacity

    def set_glow_opacity(self, opacity: float):
        """Set glow opacity value."""
        self._glow_opacity = opacity
        self.update()

    # Properties for animation
    pulse_scale = pyqtProperty(float, get_pulse_scale, set_pulse_scale)
    glow_opacity = pyqtProperty(float, get_glow_opacity, set_glow_opacity)

    def paintEvent(self, event: QPaintEvent):
        """Paint the animated dot."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Use QPointF for PyQt6 compatibility
        center = QPointF(12.0, 12.0)
        base_radius = 5.0

        # Draw glow
        glow_radius = base_radius * 2.5 * self._pulse_scale
        glow_color = QColor(
            self._color.red(),
            self._color.green(),
            self._color.blue(),
            int(80 * self._glow_opacity)
        )
        glow_gradient = QRadialGradient(center, glow_radius)
        glow_gradient.setColorAt(0.0, glow_color)
        glow_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow_gradient))
        painter.drawEllipse(center, glow_radius, glow_radius)

        # Draw dot
        dot_radius = base_radius * self._pulse_scale
        painter.setBrush(QBrush(self._color))
        painter.drawEllipse(center, dot_radius, dot_radius)

        painter.end()

    def set_color(self, color: QColor):
        """Change dot color."""
        self._color = color
        self.update()


# ==================================================================
# Logo Widget
# ==================================================================

class LogoWidget(QWidget):
    """
    Animated iMat logo widget with pulsing dot and text.

    Features:
    - Animated pulsing indicator dot
    - Gradient or solid color title
    - Optional slogan text
    - Optional logo image
    - Smooth entrance animation (text fade-in)
    - Hover interaction effects
    - Theme-aware colors
    - Customizable text and colors
    """

    def __init__(
        self,
        title: str = "iMat Warehouse",
        slogan: str = "Where Inventory Meets AI",
        pulse_color: QColor = QColor("#008B8B"),
        title_color: QColor = QColor("#004D40"),
        logo_filename: str = "logo_small.png",
        show_slogan: bool = True,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the logo widget.

        Args:
            title: Main title text
            slogan: Slogan/subtitle text
            pulse_color: Color for the animated dot
            title_color: Color for the title text
            logo_filename: Logo image filename (in resources/images/)
            show_slogan: Whether to show the slogan
            parent: Parent widget
        """
        super().__init__(parent)

        # Store settings
        self._pulse_color = pulse_color
        self._title_color = title_color
        self._logo_filename = logo_filename
        self._title_text = title
        self._slogan_text = slogan
        self._show_slogan = show_slogan
        self._is_hovered = False

        # Setup UI
        self._init_ui()

        # Start entrance animation on labels only
        self._start_entrance_animation()

    def _init_ui(self):
        """Initialize the UI layout."""
        # Main layout
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(6, 4, 6, 4)
        outer_layout.setSpacing(8)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # ---- Animated Dot ----
        dot_container = QWidget()
        dot_container.setFixedSize(28, 28)
        dot_layout = QHBoxLayout(dot_container)
        dot_layout.setContentsMargins(0, 0, 0, 0)
        dot_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.pulse_dot = AnimatedDot(color=self._pulse_color)
        dot_layout.addWidget(self.pulse_dot)
        outer_layout.addWidget(dot_container)

        # ---- Text Block ----
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        # Title label
        self.title_label = QLabel(self._title_text)
        self.title_label.setStyleSheet(f"""
            font-size: 18px;
            font-weight: bold;
            color: {self._title_color.name()};
            background: transparent;
            border: none;
        """)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed
        )
        text_layout.addWidget(self.title_label)

        # Slogan label
        if self._show_slogan:
            self.slogan_label = QLabel(self._slogan_text)
            self.slogan_label.setStyleSheet("""
                font-size: 11px;
                color: #78909C;
                background: transparent;
                border: none;
                font-style: italic;
            """)
            text_layout.addWidget(self.slogan_label)
        else:
            self.slogan_label = None

        outer_layout.addWidget(text_widget)
        outer_layout.addStretch()

        # ---- Logo Image (optional) ----
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(40, 40)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Try to load logo image
        logo_path = os.path.join(
            os.path.dirname(__file__), "..", "resources", "images", self._logo_filename
        )

        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(
                40, 40,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.logo_label.setPixmap(pixmap)
            outer_layout.addWidget(self.logo_label)
        else:
            self.logo_label.setVisible(False)

        # ---- Tooltip ----
        self.setToolTip(
            f"{self._title_text}\n"
            f"{self._slogan_text}\n\n"
            "AI-Powered Material Control System"
        )

        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        self.title_label.setMouseTracking(True)

    def _start_entrance_animation(self):
        """Start fade-in on title and slogan labels (avoids painter conflicts)."""
        # Effect for title
        self._title_effect = QGraphicsOpacityEffect()
        self._title_effect.setOpacity(0.0)
        self.title_label.setGraphicsEffect(self._title_effect)

        self._title_anim = QPropertyAnimation(self._title_effect, b"opacity")
        self._title_anim.setDuration(800)
        self._title_anim.setStartValue(0.0)
        self._title_anim.setEndValue(1.0)
        self._title_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Effect for slogan (if exists)
        if self.slogan_label:
            self._slogan_effect = QGraphicsOpacityEffect()
            self._slogan_effect.setOpacity(0.0)
            self.slogan_label.setGraphicsEffect(self._slogan_effect)

            self._slogan_anim = QPropertyAnimation(self._slogan_effect, b"opacity")
            self._slogan_anim.setDuration(800)
            self._slogan_anim.setStartValue(0.0)
            self._slogan_anim.setEndValue(1.0)
            self._slogan_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._slogan_anim.finished.connect(self._clear_slogan_effect)
            self._slogan_anim.start()
        else:
            self._slogan_anim = None

        self._title_anim.finished.connect(self._clear_title_effect)
        self._title_anim.start()

    def _clear_title_effect(self):
        """Remove the opacity effect from title label."""
        if self._title_effect:
            self.title_label.setGraphicsEffect(None)
            self._title_effect = None

    def _clear_slogan_effect(self):
        """Remove the opacity effect from slogan label."""
        if self._slogan_effect:
            self.slogan_label.setGraphicsEffect(None)
            self._slogan_effect = None

    # ==================================================================
    # Hover Effects
    # ==================================================================

    def enterEvent(self, event: QEnterEvent):
        """Handle mouse enter - enlarge dot and brighten title."""
        self._is_hovered = True
        self.pulse_dot.setFixedSize(18, 18)

        # Brighten title
        lighter_color = self._title_color.lighter(120)
        self.title_label.setStyleSheet(f"""
            font-size: 18px;
            font-weight: bold;
            color: {lighter_color.name()};
            background: transparent;
            border: none;
        """)

        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave - restore original appearance."""
        self._is_hovered = False
        self.pulse_dot.setFixedSize(14, 14)

        # Restore title color
        self.title_label.setStyleSheet(f"""
            font-size: 18px;
            font-weight: bold;
            color: {self._title_color.name()};
            background: transparent;
            border: none;
        """)

        super().leaveEvent(event)

    # ==================================================================
    # Public Methods
    # ==================================================================

    def set_title(self, title: str):
        """
        Set the title text.

        Args:
            title: New title text
        """
        self._title_text = title
        self.title_label.setText(title)
        self.setToolTip(
            f"{title}\n{self._slogan_text}\n\n"
            "AI-Powered Material Control System"
        )

    def set_slogan(self, slogan: str):
        """
        Set the slogan text.

        Args:
            slogan: New slogan text
        """
        self._slogan_text = slogan
        if self.slogan_label:
            self.slogan_label.setText(slogan)
        self.setToolTip(
            f"{self._title_text}\n{slogan}\n\n"
            "AI-Powered Material Control System"
        )

    def set_pulse_color(self, color: QColor):
        """
        Set the pulse dot color.

        Args:
            color: New color for the dot
        """
        self._pulse_color = color
        self.pulse_dot.set_color(color)

    def set_title_color(self, color: QColor):
        """
        Set the title text color.

        Args:
            color: New color for the title
        """
        self._title_color = color
        self.title_label.setStyleSheet(f"""
            font-size: 18px;
            font-weight: bold;
            color: {color.name()};
            background: transparent;
            border: none;
        """)

    def set_logo_image(self, filename: str):
        """
        Set a custom logo image.

        Args:
            filename: Image filename in resources/images/
        """
        logo_path = os.path.join(
            os.path.dirname(__file__), "..", "resources", "images", filename
        )

        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(
                40, 40,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.logo_label.setPixmap(pixmap)
            self.logo_label.setVisible(True)
        else:
            self.logo_label.setVisible(False)

    def show_slogan(self, show: bool):
        """
        Show or hide the slogan.

        Args:
            show: True to show slogan
        """
        self._show_slogan = show
        if self.slogan_label:
            self.slogan_label.setVisible(show)

    def apply_theme(self, is_dark: bool):
        """
        Apply dark or light theme colors.

        Args:
            is_dark: True for dark theme
        """
        if is_dark:
            self.set_title_color(QColor("#E0E0E0"))
            self.set_pulse_color(QColor("#4DB6AC"))
            if self.slogan_label:
                self.slogan_label.setStyleSheet("""
                    font-size: 11px;
                    color: #B0BEC5;
                    background: transparent;
                    border: none;
                    font-style: italic;
                """)
        else:
            self.set_title_color(QColor("#004D40"))
            self.set_pulse_color(QColor("#008B8B"))
            if self.slogan_label:
                self.slogan_label.setStyleSheet("""
                    font-size: 11px;
                    color: #78909C;
                    background: transparent;
                    border: none;
                    font-style: italic;
                """)

    def get_title(self) -> str:
        """Get the current title text."""
        return self._title_text

    def get_slogan(self) -> str:
        """Get the current slogan text."""
        return self._slogan_text

    def sizeHint(self) -> QSize:
        """Get the preferred size."""
        return QSize(250, 50)

    def minimumSizeHint(self) -> QSize:
        """Get the minimum size."""
        return QSize(150, 40)


# ==================================================================
# Compact Logo Widget (for toolbars)
# ==================================================================

class CompactLogoWidget(QWidget):
    """Compact version of the logo widget for toolbars and small spaces."""

    def __init__(
        self,
        title: str = "iMat",
        pulse_color: QColor = QColor("#008B8B"),
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the compact logo widget.

        Args:
            title: Short title text
            pulse_color: Color for the animated dot
            parent: Parent widget
        """
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # Animated dot
        dot = AnimatedDot(color=pulse_color)
        dot.setFixedSize(20, 20)
        layout.addWidget(dot)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: bold;
            color: {pulse_color.name()};
            background: transparent;
            border: none;
        """)
        layout.addWidget(title_label)

        self.setToolTip(f"{title} – AI-Powered Inventory Management")


# ==================================================================
# Large Logo Widget (for splash screen)
# ==================================================================

class SplashLogoWidget(QWidget):
    """Large logo widget for splash screen."""

    def __init__(
        self,
        title: str = "iMat Warehouse",
        slogan: str = "Where Inventory Meets AI",
        pulse_color: QColor = QColor("#004D40"),
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the splash logo widget.

        Args:
            title: Main title text
            slogan: Slogan text
            pulse_color: Color for the dot and title
            parent: Parent widget
        """
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Animated dot (larger)
        dot_container = QWidget()
        dot_layout = QHBoxLayout(dot_container)
        dot_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        dot = AnimatedDot(color=pulse_color)
        dot.setFixedSize(40, 40)
        dot_layout.addWidget(dot)
        layout.addWidget(dot_container)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: 28px;
            font-weight: bold;
            color: {pulse_color.name()};
            background: transparent;
            border: none;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Slogan
        slogan_label = QLabel(slogan)
        slogan_label.setStyleSheet("""
            font-size: 14px;
            color: #607D8B;
            background: transparent;
            border: none;
            font-style: italic;
        """)
        slogan_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(slogan_label)

        # Version
        version_label = QLabel("v2.0.0 EPC Edition")
        version_label.setStyleSheet("""
            font-size: 10px;
            color: #90A4AE;
            background: transparent;
            border: none;
        """)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)


# ==================================================================
# Module Exports
# ==================================================================

__all__ = [
    'LogoWidget',
    'CompactLogoWidget',
    'SplashLogoWidget',
    'AnimatedDot',
]