# utils/__init__.py
"""
iMat Utility Package - Material Control System (EPC Edition).
"""

__version__ = "2.0.0"
__author__ = "iMat Development Team"
__email__ = "support@imat.io"

# ==================================================================
# Core Utility Imports
# ==================================================================

from .calculations import (
    calculate_eoq,
    calculate_eoq_with_shortages,
    calculate_reorder_point,
    calculate_inventory_turnover,
    calculate_days_of_inventory,
    abc_classification,
    calculate_safety_stock,                    # This is the backward-compatible alias
    calculate_safety_stock_simple,
    calculate_safety_stock_service_level,
    calculate_safety_stock_fixed,
    calculate_safety_stock_percentage,
    get_z_score,
    calculate_mae,
    calculate_mse,
    calculate_rmse,
    calculate_mean,
    calculate_std_dev,
)

from .excel_export import (
    export_to_excel,
    export_inventory_summary,
    export_transaction_report,
    export_stock_report,
)

from .pdf_export import (
    export_to_pdf,
    export_transaction_report as pdf_export_transaction_report,
    export_inventory_report,
    export_stock_report as pdf_export_stock_report,
)

from .html_export import (
    export_document_to_html,
    save_html_to_file,
    preview_html_in_browser,
)

from .license import (
    get_machine_id,
    generate_license_key,
    validate_license,
    save_license,
    load_license,
    is_license_valid,
)

from .logger import (
    setup_logger,
    log_error,
    log_info,
    log_warning,
    log_debug,
    log_critical,
)

from .password_manager import (
    hash_password,
    verify_password,
)

from .trial import (
    get_trial_status,
)

# ==================================================================
# Additional Utilities
# ==================================================================

import os
import re
import json
import hashlib
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path


# ==================================================================
# File & Path Utilities
# ==================================================================

def ensure_directory(path: str) -> bool:
    """Ensure a directory exists, creating it if necessary."""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError:
        return False


def safe_filename(filename: str) -> str:
    """Convert a string to a safe filename."""
    safe = re.sub(r'[<>:"/\\|?*]', '_', filename)
    safe = safe.strip('. ')
    if len(safe) > 200:
        name, ext = os.path.splitext(safe)
        safe = name[:195] + ext
    return safe if safe else 'untitled'


# ==================================================================
# Date & Time Utilities
# ==================================================================

def format_date(date_obj: Optional[date], fmt: str = "%Y-%m-%d") -> str:
    """Format a date object to string."""
    if date_obj:
        return date_obj.strftime(fmt)
    return ""


def format_datetime(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a datetime object to string."""
    if dt:
        return dt.strftime(fmt)
    return ""


# ==================================================================
# String & Number Utilities
# ==================================================================

def format_currency(amount: float, currency: str = "USD", decimals: int = 2) -> str:
    """Format a currency amount."""
    symbols = {
        "USD": "$", "EUR": "€", "IRR": "﷼", "AED": "د.إ",
        "GBP": "£", "SAR": "﷼",
    }
    symbol = symbols.get(currency, currency)
    return f"{symbol}{amount:,.{decimals}f}"


def truncate_string(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """Truncate a string to a maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ==================================================================
# Validation Utilities
# ==================================================================

def is_valid_email(email: str) -> bool:
    """Validate email address format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_required(value: Any, field_name: str) -> Tuple[bool, str]:
    """Validate a required field."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return False, f"{field_name} is required."
    return True, ""


# ==================================================================
# WhatsApp Sharing
# ==================================================================

WHATSAPP_NUMBER = "+989160684552"

def share_via_whatsapp(message: str, number: str = WHATSAPP_NUMBER) -> str:
    """Generate a WhatsApp share URL."""
    import urllib.parse
    encoded = urllib.parse.quote(message)
    clean_number = number.replace("+", "").replace(" ", "")
    return f"https://wa.me/{clean_number}?text={encoded}"


# ==================================================================
# Package Exports
# ==================================================================

__all__ = [
    # Calculations
    'calculate_eoq',
    'calculate_eoq_with_shortages',
    'calculate_reorder_point',
    'calculate_inventory_turnover',
    'calculate_days_of_inventory',
    'abc_classification',
    'calculate_safety_stock',                    # Backward compatible
    'calculate_safety_stock_simple',
    'calculate_safety_stock_service_level',
    'calculate_safety_stock_fixed',
    'calculate_safety_stock_percentage',
    'get_z_score',
    'calculate_mae',
    'calculate_mse',
    'calculate_rmse',
    'calculate_mean',
    'calculate_std_dev',
    
    # Export
    'export_to_excel',
    'export_inventory_summary',
    'export_transaction_report',
    'export_stock_report',
    'export_to_pdf',
    'export_inventory_report',
    'export_document_to_html',
    'save_html_to_file',
    'preview_html_in_browser',
    
    # License
    'get_machine_id',
    'generate_license_key',
    'validate_license',
    'save_license',
    'load_license',
    'is_license_valid',
    
    # Logger
    'setup_logger',
    'log_error',
    'log_info',
    'log_warning',
    'log_debug',
    'log_critical',
    
    # Password
    'hash_password',
    'verify_password',
    
    # Trial
    'get_trial_status',
    
    # File utilities
    'ensure_directory',
    'safe_filename',
    
    # Date utilities
    'format_date',
    'format_datetime',
    
    # String utilities
    'format_currency',
    'truncate_string',
    'clean_text',
    
    # Validation
    'is_valid_email',
    'validate_required',
    
    # Sharing
    'share_via_whatsapp',
    'WHATSAPP_NUMBER',
]