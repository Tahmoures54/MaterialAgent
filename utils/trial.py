# utils/trial.py
"""
Trial Period Management – iMat Material Control System (EPC Edition).

Trial license management with:
- Trial period tracking
- Usage limits (records, features)
- Trial expiry notifications
- Grace period support
- Trial extension capability
- Usage statistics
- Feature restrictions
- Upgrade prompts
- Data preservation after expiry
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

from sqlalchemy.orm import Session

# Import license constants to keep trial duration in sync
from utils.license import LICENSE_TYPES


# ==================================================================
# Constants
# ==================================================================

# Trial file path
TRIAL_FILE = os.path.join(os.path.expanduser("~"), ".aimat_trial")

# Default trial duration – read from the same source as license.py
DEFAULT_TRIAL_DAYS = LICENSE_TYPES.get("trial", {}).get("duration_days", 14)
DEFAULT_MAX_RECORDS = LICENSE_TYPES.get("trial", {}).get("max_records", 200)
DEFAULT_MAX_DOCUMENTS = 50
DEFAULT_MAX_USERS = LICENSE_TYPES.get("trial", {}).get("max_users", 1)

# Grace period after trial expiry (days)
GRACE_PERIOD_DAYS = 3

# Trial features – now fully enabled to give the user the complete Professional experience
TRIAL_FEATURES = {
    "basic_inventory": True,
    "document_management": True,
    "reports": True,
    "excel_export": True,
    "pdf_export": True,
    "qc_release": True,
    "preservation": True,
    "expiry_monitor": True,
    "barcode_scanner": True,
    "multi_user": True,            # Enabled during trial
    "ai_prediction": True,         # Enabled during trial
    "abc_analysis": True,          # Enabled during trial
    "eoq_calculator": True,        # Enabled during trial
    "advanced_reports": True,      # Enabled during trial
    "api_access": False,           # Still off – Enterprise only
    "custom_branding": False,      # Still off – Enterprise only
    "priority_support": False,     # Still off – Enterprise only
    "auto_backup": True,
    "whatsapp_sharing": True,
}

# Notification thresholds
NOTIFY_DAYS_REMAINING = [7, 3, 1]  # Days before expiry to notify
NOTIFY_RECORDS_REMAINING = [20, 10, 5]  # Records remaining to notify


# ==================================================================
# Trial Data Management
# ==================================================================

def _load_trial_data() -> Dict[str, Any]:
    """
    Load trial data from file.
    
    Returns:
        Trial data dictionary
    """
    if os.path.exists(TRIAL_FILE):
        try:
            with open(TRIAL_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    return {}


def _save_trial_data(data: Dict[str, Any]) -> bool:
    """
    Save trial data to file.
    
    Args:
        data: Trial data dictionary
    
    Returns:
        True if saved successfully
    """
    try:
        os.makedirs(os.path.dirname(TRIAL_FILE), exist_ok=True)
        with open(TRIAL_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except IOError:
        return False


def _get_first_run_date() -> datetime:
    """
    Get or create the first run date.
    
    Returns:
        First run datetime
    """
    data = _load_trial_data()
    
    if 'first_run' in data:
        return datetime.fromisoformat(data['first_run'])
    else:
        now = datetime.now()
        data = {
            'first_run': now.isoformat(),
            'trial_days': DEFAULT_TRIAL_DAYS,
            'max_records': DEFAULT_MAX_RECORDS,
            'max_documents': DEFAULT_MAX_DOCUMENTS,
            'max_users': DEFAULT_MAX_USERS,
            'extensions': 0,
            'features': TRIAL_FEATURES,
            'notifications_sent': [],
            'activated': False,
        }
        _save_trial_data(data)
        return now


# ==================================================================
# Trial Status
# ==================================================================

def get_trial_status(db_session: Optional[Session] = None) -> Dict[str, Any]:
    """
    Get current trial status.
    
    Args:
        db_session: Optional database session for record counting
    
    Returns:
        Dictionary with trial status information
    """
    first_run = _get_first_run_date()
    data = _load_trial_data()
    
    now = datetime.now()
    trial_days = data.get('trial_days', DEFAULT_TRIAL_DAYS)
    expiry_date = first_run + timedelta(days=trial_days)
    grace_end = expiry_date + timedelta(days=GRACE_PERIOD_DAYS)
    
    days_passed = (now - first_run).days
    days_left = trial_days - days_passed
    
    # Count records if session provided
    records_used = 0
    documents_used = 0
    users_count = 0
    
    if db_session:
        try:
            from db.models import Product, Document, User
            
            records_used = db_session.query(Product).count()
            documents_used = db_session.query(Document).count()
            users_count = db_session.query(User).count()
        except Exception:
            pass
    
    max_records = data.get('max_records', DEFAULT_MAX_RECORDS)
    max_documents = data.get('max_documents', DEFAULT_MAX_DOCUMENTS)
    max_users = data.get('max_users', DEFAULT_MAX_USERS)
    
    records_left = max(0, max_records - records_used)
    documents_left = max(0, max_documents - documents_used)
    users_left = max(0, max_users - users_count)
    
    # Check if still active
    time_active = days_left > 0
    grace_active = days_left <= 0 and now <= grace_end
    limits_ok = records_used < max_records and documents_used < max_documents
    
    active = (time_active or grace_active) and limits_ok
    
    # Check notifications
    notifications = _check_notifications(days_left, records_left, data)
    
    return {
        'active': active,
        'days_left': max(0, days_left),
        'days_total': trial_days,
        'days_used': min(days_passed, trial_days),
        'expiry_date': expiry_date.strftime('%Y-%m-%d'),
        'grace_end_date': grace_end.strftime('%Y-%m-%d'),
        'in_grace_period': grace_active and not time_active,
        'records_used': records_used,
        'records_max': max_records,
        'records_left': records_left,
        'documents_used': documents_used,
        'documents_max': max_documents,
        'documents_left': documents_left,
        'users_count': users_count,
        'users_max': max_users,
        'users_left': users_left,
        'extensions': data.get('extensions', 0),
        'notifications': notifications,
        'features': data.get('features', TRIAL_FEATURES),
        'first_run': first_run.strftime('%Y-%m-%d'),
    }


def _check_notifications(
    days_left: int,
    records_left: int,
    data: Dict,
) -> list:
    """
    Check if notifications should be sent.
    """
    notifications = []
    sent = data.get('notifications_sent', [])
    
    for threshold in NOTIFY_DAYS_REMAINING:
        if days_left == threshold and f"days_{threshold}" not in sent:
            notifications.append({
                'type': 'days',
                'message': f"Trial expires in {threshold} day(s)",
                'days_left': days_left,
            })
    
    for threshold in NOTIFY_RECORDS_REMAINING:
        if records_left <= threshold and f"records_{threshold}" not in sent:
            notifications.append({
                'type': 'records',
                'message': f"Only {records_left} record(s) remaining",
                'records_left': records_left,
            })
    
    return notifications


def mark_notification_sent(notification_type: str, value: int) -> bool:
    """Mark a notification as sent to prevent duplicates."""
    data = _load_trial_data()
    sent = data.get('notifications_sent', [])
    
    key = f"{notification_type}_{value}"
    if key not in sent:
        sent.append(key)
        data['notifications_sent'] = sent
        return _save_trial_data(data)
    
    return True


# ==================================================================
# Feature Access
# ==================================================================

def is_feature_available(feature_name: str) -> bool:
    """Check if a feature is available in trial mode."""
    data = _load_trial_data()
    features = data.get('features', TRIAL_FEATURES)
    return features.get(feature_name, False)


def get_available_features() -> Dict[str, bool]:
    """Get all available features in trial mode."""
    data = _load_trial_data()
    return data.get('features', TRIAL_FEATURES).copy()


def get_unavailable_features() -> list:
    """Get list of features not available in trial."""
    features = get_available_features()
    return [name for name, available in features.items() if not available]


# ==================================================================
# Trial Management
# ==================================================================

def extend_trial(extra_days: int = 10) -> bool:
    """Extend the trial period."""
    data = _load_trial_data()
    max_extensions = 3
    current_extensions = data.get('extensions', 0)
    
    if current_extensions >= max_extensions:
        return False
    
    current_days = data.get('trial_days', DEFAULT_TRIAL_DAYS)
    data['trial_days'] = current_days + extra_days
    data['extensions'] = current_extensions + 1
    return _save_trial_data(data)


def extend_record_limit(extra_records: int = 50) -> bool:
    """Extend the record limit."""
    data = _load_trial_data()
    current_max = data.get('max_records', DEFAULT_MAX_RECORDS)
    data['max_records'] = current_max + extra_records
    return _save_trial_data(data)


def reset_trial() -> bool:
    """Reset the trial period (for testing/debugging)."""
    try:
        if os.path.exists(TRIAL_FILE):
            os.remove(TRIAL_FILE)
        return True
    except OSError:
        return False


def activate_trial() -> bool:
    """Activate the trial (mark as started)."""
    data = _load_trial_data()
    data['activated'] = True
    return _save_trial_data(data)


def is_trial_activated() -> bool:
    """Check if trial has been activated."""
    data = _load_trial_data()
    return data.get('activated', False)


# ==================================================================
# Usage Statistics
# ==================================================================

def get_usage_statistics(db_session: Optional[Session] = None) -> Dict[str, Any]:
    """Get detailed usage statistics for the trial period."""
    status = get_trial_status(db_session)
    
    stats = {
        'period': {
            'start': status.get('first_run', 'Unknown'),
            'end': status.get('expiry_date', 'Unknown'),
            'days_total': status['days_total'],
            'days_used': status['days_used'],
            'days_left': status['days_left'],
        },
        'records': {
            'used': status['records_used'],
            'max': status['records_max'],
            'left': status['records_left'],
            'usage_pct': round(status['records_used'] / status['records_max'] * 100, 1) 
                         if status['records_max'] > 0 else 0,
        },
        'documents': {
            'used': status['documents_used'],
            'max': status['documents_max'],
            'left': status['documents_left'],
            'usage_pct': round(status['documents_used'] / status['documents_max'] * 100, 1)
                         if status['documents_max'] > 0 else 0,
        },
        'users': {
            'used': status['users_count'],
            'max': status['users_max'],
            'left': status['users_left'],
        },
        'status': {
            'active': status['active'],
            'in_grace': status['in_grace_period'],
            'extensions': status['extensions'],
        },
    }
    
    return stats


def format_trial_summary(db_session: Optional[Session] = None) -> str:
    """Format trial status as a readable summary."""
    status = get_trial_status(db_session)
    
    lines = []
    lines.append("=" * 50)
    lines.append("iMat Trial License Summary")
    lines.append("=" * 50)
    
    if status['active']:
        if status['in_grace_period']:
            lines.append("⚠️ TRIAL IN GRACE PERIOD")
        else:
            lines.append("✅ Trial Active")
    else:
        lines.append("❌ Trial Expired")
    
    lines.append(f"Started: {status.get('first_run', 'Unknown')}")
    lines.append(f"Expires: {status.get('expiry_date', 'Unknown')}")
    lines.append(f"Days Remaining: {status['days_left']} of {status['days_total']}")
    
    if status['extensions'] > 0:
        lines.append(f"Extensions Used: {status['extensions']}")
    
    lines.append("")
    lines.append("Usage:")
    lines.append(f"  Records: {status['records_used']} / {status['records_max']} "
                f"({status['records_left']} remaining)")
    lines.append(f"  Documents: {status['documents_used']} / {status['documents_max']} "
                f"({status['documents_left']} remaining)")
    lines.append(f"  Users: {status['users_count']} / {status['users_max']}")
    
    lines.append("")
    lines.append("Available Features:")
    
    features = status.get('features', TRIAL_FEATURES)
    for feature, available in sorted(features.items()):
        icon = "✅" if available else "❌"
        lines.append(f"  {icon} {feature}")
    
    lines.append("")
    lines.append("To unlock all features, purchase a full license.")
    lines.append("Visit: www.imat.io")
    lines.append("WhatsApp: +98 916 068 4552")
    lines.append("=" * 50)
    
    return "\n".join(lines)


# ==================================================================
# Trial Check Decorator
# ==================================================================

def require_trial_active(func):
    """Decorator to check if trial is active before executing a function."""
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        status = get_trial_status()
        if not status['active']:
            raise TrialExpiredError(
                f"Trial has expired. Days remaining: {status['days_left']}. "
                "Please purchase a license to continue."
            )
        return func(*args, **kwargs)
    
    return wrapper


def require_feature(feature_name: str):
    """Decorator to check if a feature is available in trial."""
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not is_feature_available(feature_name):
                raise FeatureNotAvailableError(
                    f"Feature '{feature_name}' is not available in trial mode. "
                    "Please upgrade to a full license."
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ==================================================================
# Custom Exceptions
# ==================================================================

class TrialExpiredError(Exception):
    """Raised when trial period has expired."""
    pass


class FeatureNotAvailableError(Exception):
    """Raised when a feature is not available in trial mode."""
    pass


class RecordLimitExceededError(Exception):
    """Raised when record limit is exceeded."""
    pass


# ==================================================================
# Module Exports
# ==================================================================

__all__ = [
    # Status
    'get_trial_status',
    'is_feature_available',
    'get_available_features',
    'get_unavailable_features',
    
    # Management
    'extend_trial',
    'extend_record_limit',
    'reset_trial',
    'activate_trial',
    'is_trial_activated',
    
    # Statistics
    'get_usage_statistics',
    'format_trial_summary',
    
    # Decorators
    'require_trial_active',
    'require_feature',
    
    # Notifications
    'mark_notification_sent',
    
    # Exceptions
    'TrialExpiredError',
    'FeatureNotAvailableError',
    'RecordLimitExceededError',
    
    # Constants
    'TRIAL_FILE',
    'DEFAULT_TRIAL_DAYS',
    'DEFAULT_MAX_RECORDS',
    'GRACE_PERIOD_DAYS',
    'TRIAL_FEATURES',
]