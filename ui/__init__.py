# ui/__init__.py
"""
iMat UI Package - Material Control System (EPC Edition).

This package contains all dialog windows, widgets, and UI components
for the iMat Material Control System. Each module provides specific
functionality for warehouse management, quality control, reporting,
and user interaction.

Package Structure:
    - main_window: Main application window
    - main_window_ui: UI builder for main window
    - login_dialog: User authentication dialog
    - splash_dialog: Animated splash screen
    - start_dialog: Welcome/quick-start dialog
    - logo_widget: Animated logo with pulse effect
    - product_dialog: Material catalog CRUD
    - document_dialog: Warehouse document management
    - transaction_dialog: Transaction entry and history
    - location_dialog: Warehouse location hierarchy
    - qc_release_dialog: Quality control release
    - preservation_dialog: Preservation monitoring
    - stock_view_dialog: Live stock dashboard
    - reports_window: Report generation window
    - report_manager: Unified report center
    - abc_analysis_dialog: ABC inventory analysis
    - reorder_dialog: Reorder point calculator
    - expiry_monitor_dialog: Expiry date tracking
    - barcode_dialog: Barcode scanner interface
    - material_request_dialog: Material request creation
    - material_request_history_dialog: Request history
    - user_management_dialog: User and role management
    - license_dialog: License activation
    - auto_backup_dialog: Auto-backup configuration

Usage:
    from ui.main_window import MainWindow
    from ui.login_dialog import LoginDialog
    from ui.splash_dialog import SplashDialog
    
    # Create main window
    window = MainWindow(user_role="admin", username="admin")
    window.show()

Author: iMat Development Team
Version: 2.0.0
License: Proprietary
Website: https://www.imat.io
"""

# ==================================================================
# Version Information
# ==================================================================

__version__ = "2.0.0"
__author__ = "iMat Development Team"
__email__ = "support@imat.io"
__website__ = "https://www.imat.io"

# ==================================================================
# Core Window Imports
# ==================================================================

from .main_window import MainWindow, StockSearchThread
from .main_window_ui import MainWindowUIBuilder
from .login_dialog import LoginDialog
from .splash_dialog import SplashDialog
from .start_dialog import StartDialog
from .logo_widget import LogoWidget

# ==================================================================
# Material Control Imports
# ==================================================================

from .product_dialog import ProductDialog, NoScrollComboBox
from .document_dialog import DocumentDialog
from .transaction_dialog import (
    TransactionDialog,
    EditTransactionDialog,
    DEFAULT_DOC_NAMES
)
from .location_dialog import LocationDialog, LocationEditDialog
from .material_request_dialog import MaterialRequestDialog
from .material_request_history_dialog import MaterialRequestHistoryDialog

# ==================================================================
# Quality Control Imports
# ==================================================================

from .qc_release_dialog import QCReleaseDialog
from .preservation_dialog import PreservationDialog
from .expiry_monitor_dialog import ExpiryMonitorDialog

# ==================================================================
# Reports & Export Imports
# ==================================================================

from .reports_window import ReportsWindow
from .report_manager import ReportManagerDialog
from .stock_view_dialog import StockViewDialog

# ==================================================================
# Tools & Analysis Imports
# ==================================================================

from .abc_analysis_dialog import ABCAnalysisDialog
from .reorder_dialog import ReorderDialog
from .barcode_dialog import BarcodeDialog

# ==================================================================
# System & Administration Imports
# ==================================================================

from .user_management_dialog import UserManagementDialog
from .license_dialog import LicenseDialog, get_license_info
from .auto_backup_dialog import AutoBackupDialog

# ==================================================================
# Public API
# ==================================================================

__all__ = [
    # Core Windows
    'MainWindow',
    'MainWindowUIBuilder',
    'StockSearchThread',
    'LoginDialog',
    'SplashDialog',
    'StartDialog',
    'LogoWidget',
    
    # Material Control
    'ProductDialog',
    'NoScrollComboBox',
    'DocumentDialog',
    'TransactionDialog',
    'EditTransactionDialog',
    'DEFAULT_DOC_NAMES',
    'LocationDialog',
    'LocationEditDialog',
    'MaterialRequestDialog',
    'MaterialRequestHistoryDialog',
    
    # Quality Control
    'QCReleaseDialog',
    'PreservationDialog',
    'ExpiryMonitorDialog',
    
    # Reports & Export
    'ReportsWindow',
    'ReportManagerDialog',
    'StockViewDialog',
    
    # Tools & Analysis
    'ABCAnalysisDialog',
    'ReorderDialog',
    'BarcodeDialog',
    
    # System & Administration
    'UserManagementDialog',
    'LicenseDialog',
    'get_license_info',
    'AutoBackupDialog',
]

# ==================================================================
# Package Metadata
# ==================================================================

PACKAGE_METADATA = {
    "name": "iMat UI",
    "version": __version__,
    "description": "User Interface package for iMat Material Control System (EPC Edition)",
    "author": __author__,
    "email": __email__,
    "website": __website__,
    "license": "Proprietary",
    "python_requires": ">=3.9",
    "dependencies": [
        "PyQt6>=6.5.0",
        "sqlalchemy>=2.0.0",
        "openpyxl>=3.1.0",
        "reportlab>=4.0.0",
        "numpy>=1.24.0",
        "scikit-learn>=1.3.0",
    ],
}

# ==================================================================
# UI Constants
# ==================================================================

# Color scheme
COLORS = {
    "primary": "#004D40",           # Dark teal - main brand color
    "primary_light": "#00695C",     # Medium teal
    "primary_dark": "#00332E",      # Very dark teal
    "accent": "#00897B",            # Teal accent
    "accent_light": "#4DB6AC",      # Light teal
    "warning": "#FFA000",           # Amber warning
    "warning_light": "#FFE0B2",     # Light amber
    "danger": "#D32F2F",            # Red danger
    "danger_light": "#FFCDD2",      # Light red
    "success": "#388E3C",           # Green success
    "success_light": "#C8E6C9",     # Light green
    "info": "#1976D2",              # Blue info
    "info_light": "#BBDEFB",        # Light blue
    "background": "#F5F5F5",        # Light gray background
    "surface": "#FFFFFF",           # White surface
    "text_primary": "#212121",      # Dark text
    "text_secondary": "#757575",    # Gray text
    "border": "#E0E0E0",            # Light border
}

# QC Status colors
QC_STATUS_COLORS = {
    "QUARANTINE": {
        "background": "#FFE0B2",    # Light amber
        "foreground": "#E65100",    # Dark amber
        "icon": "⚠️",
    },
    "ACCEPTED": {
        "background": "#C8E6C9",    # Light green
        "foreground": "#1B5E20",    # Dark green
        "icon": "✅",
    },
    "REJECTED": {
        "background": "#FFCDD2",    # Light red
        "foreground": "#B71C1C",    # Dark red
        "icon": "❌",
    },
}

# Document type configurations
DOCUMENT_TYPES = {
    "MRR": {"icon": "📥", "color": "#27ae60", "flow": "IN", "label": "Material Receipt Report"},
    "MIV": {"icon": "📤", "color": "#e67e22", "flow": "OUT", "label": "Material Issue Voucher"},
    "MSR": {"icon": "📋", "color": "#3498db", "flow": "REQUEST", "label": "Material Store Requisition"},
    "OSND": {"icon": "⚠️", "color": "#e74c3c", "flow": "ADJUST", "label": "Over, Short & Damaged Report"},
    "MTR": {"icon": "🔄", "color": "#9b59b6", "flow": "TRANSFER", "label": "Material Transfer Note"},
    "RTV": {"icon": "↩️", "color": "#c0392b", "flow": "RETURN", "label": "Return to Vendor"},
    "MRV": {"icon": "♻️", "color": "#2ecc71", "flow": "RETURN", "label": "Material Return Voucher"},
    "ADJ": {"icon": "⚖️", "color": "#f39c12", "flow": "ADJUST", "label": "Stock Adjustment"},
    "RES": {"icon": "🔒", "color": "#2980b9", "flow": "RESERVE", "label": "Material Reservation"},
    "SRN": {"icon": "↩️", "color": "#c0392b", "flow": "RETURN", "label": "Supplier Return Note"},
    "WOM": {"icon": "📤", "color": "#e67e22", "flow": "OUT", "label": "Work Order Material Issue"},
    "GAT": {"icon": "🚪", "color": "#7f8c8d", "flow": "OUT", "label": "Gate Pass"},
    "RCT": {"icon": "📥", "color": "#27ae60", "flow": "IN", "label": "General Receipt"},
    "ISS": {"icon": "📤", "color": "#e67e22", "flow": "OUT", "label": "General Issue"},
    "TRN": {"icon": "🔄", "color": "#9b59b6", "flow": "TRANSFER", "label": "General Transfer"},
}

# Location type configurations
LOCATION_TYPES = {
    "WAREHOUSE": {"icon": "🏭", "prefix": "WH", "color": "#4CAF50"},
    "OPEN_YARD": {"icon": "🌳", "prefix": "YD", "color": "#8BC34A"},
    "RACK": {"icon": "🗄️", "prefix": "RK", "color": "#FFC107"},
    "BIN": {"icon": "📦", "prefix": "BN", "color": "#FF9800"},
    "QUARANTINE": {"icon": "⚠️", "prefix": "QA", "color": "#F44336"},
}

# User role configurations
USER_ROLES = {
    "admin": {
        "label": "Administrator",
        "icon": "👑",
        "color": "#0D47A1",
        "background": "#E3F2FD",
        "permissions": ["all"],
    },
    "operator": {
        "label": "Warehouse Operator",
        "icon": "📦",
        "color": "#1B5E20",
        "background": "#E8F5E9",
        "permissions": ["material_control", "reports", "qc_release"],
    },
    "technical": {
        "label": "Technical Office",
        "icon": "📐",
        "color": "#E65100",
        "background": "#FFF3E0",
        "permissions": ["material_request", "reports", "stock_view"],
    },
    "qc_inspector": {
        "label": "QC Inspector",
        "icon": "✅",
        "color": "#880E4F",
        "background": "#FCE4EC",
        "permissions": ["qc_release", "preservation", "expiry_monitor", "reports"],
    },
    "viewer": {
        "label": "Viewer",
        "icon": "👁️",
        "color": "#424242",
        "background": "#F5F5F5",
        "permissions": ["view_only"],
    },
}

# ==================================================================
# Font Configurations
# ==================================================================

FONTS = {
    "title": {
        "family": "Segoe UI, Arial, sans-serif",
        "size": 18,
        "weight": "bold",
    },
    "subtitle": {
        "family": "Segoe UI, Arial, sans-serif",
        "size": 14,
        "weight": "bold",
    },
    "body": {
        "family": "Segoe UI, Arial, sans-serif",
        "size": 12,
        "weight": "normal",
    },
    "small": {
        "family": "Segoe UI, Arial, sans-serif",
        "size": 10,
        "weight": "normal",
    },
    "monospace": {
        "family": "Consolas, Monaco, monospace",
        "size": 11,
        "weight": "normal",
    },
}

# ==================================================================
# Common Dialog Sizes
# ==================================================================

DIALOG_SIZES = {
    "small": (400, 300),
    "medium": (600, 450),
    "large": (900, 650),
    "xlarge": (1200, 800),
    "fullscreen": (1400, 900),
}

# ==================================================================
# Helper Functions
# ==================================================================

def get_role_info(role: str) -> dict:
    """
    Get role configuration information.
    
    Args:
        role: User role name
        
    Returns:
        Dict with role configuration or default viewer config
    """
    return USER_ROLES.get(role, USER_ROLES["viewer"])


def get_document_type_info(doc_type: str) -> dict:
    """
    Get document type configuration.
    
    Args:
        doc_type: Document type code
        
    Returns:
        Dict with document type configuration or default config
    """
    return DOCUMENT_TYPES.get(doc_type, {
        "icon": "📄",
        "color": "#2c3e50",
        "flow": "OTHER",
        "label": doc_type
    })


def get_qc_status_style(qc_status: str) -> dict:
    """
    Get QC status color configuration.
    
    Args:
        qc_status: QC status code
        
    Returns:
        Dict with background and foreground colors
    """
    return QC_STATUS_COLORS.get(qc_status, {
        "background": "#F5F5F5",
        "foreground": "#424242",
        "icon": "❓",
    })


def get_location_type_info(loc_type: str) -> dict:
    """
    Get location type configuration.
    
    Args:
        loc_type: Location type code
        
    Returns:
        Dict with location type configuration or default config
    """
    return LOCATION_TYPES.get(loc_type, {
        "icon": "📍",
        "prefix": "XX",
        "color": "#9E9E9E",
    })


def create_standard_button(text: str, button_type: str = "neutral") -> str:
    """
    Generate standard button stylesheet.
    
    Args:
        text: Button text (for determining icon)
        button_type: Type of button ('primary', 'success', 'danger', 'warning', 'neutral')
        
    Returns:
        CSS stylesheet string
    """
    styles = {
        "primary": """
            QPushButton {
                background-color: #004D40;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #00695C; }
            QPushButton:pressed { background-color: #00332E; }
            QPushButton:disabled { background-color: #999; }
        """,
        "success": """
            QPushButton {
                background-color: #388E3C;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #2E7D32; }
            QPushButton:pressed { background-color: #1B5E20; }
            QPushButton:disabled { background-color: #999; }
        """,
        "danger": """
            QPushButton {
                background-color: #D32F2F;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #C62828; }
            QPushButton:pressed { background-color: #B71C1C; }
            QPushButton:disabled { background-color: #999; }
        """,
        "warning": """
            QPushButton {
                background-color: #FFA000;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #FF8F00; }
            QPushButton:pressed { background-color: #FF6F00; }
            QPushButton:disabled { background-color: #999; }
        """,
        "neutral": """
            QPushButton {
                background-color: #E0E0E0;
                color: #333;
                border: 1px solid #CCC;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #D0D0D0; }
            QPushButton:pressed { background-color: #BDBDBD; }
            QPushButton:disabled { background-color: #F5F5F5; color: #999; }
        """,
    }
    return styles.get(button_type, styles["neutral"])


# ==================================================================
# Package Initialization
# ==================================================================

def initialize_ui():
    """
    Initialize UI package.
    Sets up application-wide settings and styles.
    """
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFont
    
    app = QApplication.instance()
    if app:
        # Set default font
        font = QFont("Segoe UI", 10)
        app.setFont(font)
        
        # Set application name
        app.setApplicationName("iMat Warehouse")
        app.setOrganizationName("iMat International")
        app.setApplicationVersion(__version__)


# Auto-initialize when package is imported
# initialize_ui()