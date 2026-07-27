# utils/license.py
"""
License Management Utilities – iMat Material Control System (EPC Edition).

Comprehensive license management with:
- Machine ID generation (hardware-based)
- License key generation and validation
- Secure license storage
- Offline license support
- Trial period management
- License expiry checking
- Multi-license type support
- License activation/deactivation
- Grace period handling
- License backup and restore
"""

import os
import json
import hashlib
import uuid
import platform
import socket
import base64
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
from pathlib import Path


# ==================================================================
# Constants
# ==================================================================

# License file path
LICENSE_FILE = os.path.join(os.path.expanduser("~"), ".aimat_license")
LICENSE_BACKUP_FILE = os.path.join(os.path.expanduser("~"), ".aimat_license_backup")

# Trial file path
TRIAL_FILE = os.path.join(os.path.expanduser("~"), ".aimat_trial")

# Secret key – stored in obfuscated parts (Base64) to prevent trivial extraction
_SECRET_PARTS_B64 = [
    "QWlNYXQyMDI1",          # "AiMat2025"
    "IUAjJCVeJiooKQ==",      # "!@#$%^&*()"
    "RVBDX0VkaXRpb24="       # "EPC_Edition"
]
SECRET_KEY = "".join(base64.b64decode(p).decode() for p in _SECRET_PARTS_B64)

# License types – updated for global market plans
#   trial:       14-day full-feature trial, 200 records, 1 user
#   standard:    yearly subscription, up to 5k records, 2 users
#   professional: yearly, 50k records, 5 users, AI & advanced analytics
#   enterprise:  lifetime, unlimited everything, API & priority support
LICENSE_TYPES = {
    "trial":       {"duration_days": 14,     "max_records": 200,   "max_users": 1},
    "standard":    {"duration_days": 365,    "max_records": 5000,  "max_users": 2},
    "professional": {"duration_days": 365,   "max_records": 50000, "max_users": 5},
    "enterprise":  {"duration_days": 99999,  "max_records": -1,    "max_users": -1},
}

# Grace period after expiry (days)
GRACE_PERIOD_DAYS = 7


# ==================================================================
# Machine ID Generation
# ==================================================================

def get_machine_id() -> str:
    """
    Generate a unique machine identifier based on hardware.
    """
    components = []
    try:
        components.append(platform.node())
    except Exception:
        components.append("unknown-host")
    try:
        components.append(platform.processor())
    except Exception:
        components.append("unknown-processor")
    try:
        mac = uuid.getnode()
        components.append(str(mac))
    except Exception:
        components.append("unknown-mac")
    combined = "|".join(components)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def get_system_info() -> Dict[str, str]:
    """Get detailed system information for license verification."""
    info = {
        "machine_id": get_machine_id(),
        "hostname": platform.node(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.architecture()[0],
    }
    try:
        info["mac_address"] = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff)
                                        for i in range(0, 48, 8)][::-1])
    except Exception:
        info["mac_address"] = "unknown"
    return info


# ==================================================================
# License Key Generation
# ==================================================================

def generate_license_key(
    machine_id: str,
    license_type: str = "standard",
    expiry_days: int = 365,
    secret_key: str = SECRET_KEY,
) -> str:
    """
    Generate a license key for a specific machine.
    Format: MACHINE_ID-EXPIRY_DATE-SIGNATURE
    expiry_days is used directly – no automatic override.
    """
    expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y%m%d")
    data = f"{machine_id}|{expiry_date}|{license_type}|{secret_key}"
    signature = hashlib.sha256(data.encode()).hexdigest()[:10]
    return f"{machine_id}-{expiry_date}-{signature}"


def generate_trial_key(machine_id: str, trial_days: int = None) -> str:
    """Generate a trial license key (default 14 days)."""
    if trial_days is None:
        return generate_license_key(machine_id, "trial")
    return generate_license_key(machine_id, "trial", trial_days)


# ==================================================================
# License Validation
# ==================================================================

def validate_license(license_key: str, machine_id: str) -> bool:
    """Quick validation."""
    return validate_license_detailed(license_key, machine_id)["valid"]


def validate_license_detailed(license_key: str, machine_id: str) -> Dict[str, Any]:
    """
    Validate license and return detailed information.
    Tries all license types for signature matching.
    """
    result = {
        "valid": False,
        "machine_match": False,
        "expired": False,
        "signature_valid": False,
        "expiry_date": None,
        "days_remaining": 0,
        "in_grace_period": False,
        "message": "",
        "license_type": "unknown",
    }
    try:
        parts = license_key.split('-')
        if len(parts) != 3:
            result["message"] = "Invalid license key format"
            return result

        stored_machine, expiry_str, signature = parts
        result["machine_match"] = (stored_machine == machine_id)

        expiry_date = datetime.strptime(expiry_str, "%Y%m%d")
        result["expiry_date"] = expiry_date
        result["days_remaining"] = (expiry_date - datetime.now()).days

        grace_end = expiry_date + timedelta(days=GRACE_PERIOD_DAYS)
        result["expired"] = datetime.now() > grace_end
        result["in_grace_period"] = (
            datetime.now() > expiry_date and datetime.now() <= grace_end
        )

        # Try to match signature against all license types
        for lic_type, config in LICENSE_TYPES.items():
            data = f"{stored_machine}|{expiry_str}|{lic_type}|{SECRET_KEY}"
            expected_sig = hashlib.sha256(data.encode()).hexdigest()[:10]
            if signature == expected_sig:
                result["signature_valid"] = True
                result["license_type"] = lic_type
                break

        result["valid"] = (
            result["machine_match"] and
            not result["expired"] and
            result["signature_valid"]
        )

        if result["valid"]:
            if result["in_grace_period"]:
                result["message"] = f"License in grace period ({result['days_remaining']} days expired)"
            else:
                result["message"] = f"License valid ({result['days_remaining']} days remaining)"
        elif result["expired"]:
            result["message"] = "License has expired"
        elif not result["machine_match"]:
            result["message"] = "License does not match this machine"
        elif not result["signature_valid"]:
            result["message"] = "License signature is invalid"

    except Exception as e:
        result["message"] = f"Validation error: {str(e)}"

    return result


# ==================================================================
# License Storage
# ==================================================================

def save_license(license_key: str) -> bool:
    """Save license key to file."""
    try:
        data = {
            "license": license_key,
            "activated": datetime.now().isoformat(),
            "machine_id": get_machine_id(),
            "version": "2.0.0",
        }
        with open(LICENSE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        _backup_license(data)
        return True
    except IOError:
        return False


def load_license() -> str:
    """Load license key from file."""
    try:
        if os.path.exists(LICENSE_FILE):
            with open(LICENSE_FILE, 'r') as f:
                data = json.load(f)
                return data.get("license", "")
    except (json.JSONDecodeError, IOError):
        pass
    return ""


def load_license_info() -> Dict[str, Any]:
    """Load full license information."""
    try:
        if os.path.exists(LICENSE_FILE):
            with open(LICENSE_FILE, 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def is_license_valid() -> bool:
    """Quick check if current license is valid."""
    license_key = load_license()
    if not license_key:
        return False
    return validate_license(license_key, get_machine_id())


def get_license_status() -> Dict[str, Any]:
    """Get detailed license status."""
    license_key = load_license()
    machine_id = get_machine_id()
    if not license_key:
        return {
            "valid": False,
            "activated": False,
            "message": "No license found",
            "days_remaining": 0,
        }
    info = load_license_info()
    validation = validate_license_detailed(license_key, machine_id)
    return {
        **validation,
        "activated": True,
        "activated_date": info.get("activated", "Unknown"),
        "license_key": license_key,
    }


def _backup_license(data: Dict) -> bool:
    """Create a backup of license data."""
    try:
        with open(LICENSE_BACKUP_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except IOError:
        return False


def restore_license_from_backup() -> bool:
    """Restore license from backup file."""
    try:
        if os.path.exists(LICENSE_BACKUP_FILE):
            with open(LICENSE_BACKUP_FILE, 'r') as f:
                data = json.load(f)
            with open(LICENSE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            return True
    except (json.JSONDecodeError, IOError):
        pass
    return False


def delete_license() -> bool:
    """Delete the current license."""
    try:
        if os.path.exists(LICENSE_FILE):
            os.remove(LICENSE_FILE)
        if os.path.exists(LICENSE_BACKUP_FILE):
            os.remove(LICENSE_BACKUP_FILE)
        return True
    except OSError:
        return False


# ==================================================================
# Offline Activation
# ==================================================================

def generate_offline_request() -> str:
    """Generate an offline activation request string."""
    machine_id = get_machine_id()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    request_data = f"{machine_id}|{timestamp}"
    request_hash = hashlib.sha256(request_data.encode()).hexdigest()[:8]
    return f"{machine_id}-{timestamp}-{request_hash}"


def validate_offline_response(request_str: str, response_key: str) -> bool:
    """Validate an offline activation response."""
    try:
        machine_id = get_machine_id()
        parts = request_str.split('-')
        if len(parts) != 3:
            return False
        if parts[0] != machine_id:
            return False
        return validate_license(response_key, machine_id)
    except Exception:
        return False


# ==================================================================
# License Type Information
# ==================================================================

def get_license_type(license_key: str) -> str:
    """Determine license type from key (uses detailed validation)."""
    if not license_key:
        return "none"
    result = validate_license_detailed(license_key, get_machine_id())
    return result.get("license_type", "unknown")


def get_license_features(license_type: str) -> Dict[str, Any]:
    """Get features available for a license type."""
    features = {
        "basic_inventory": True,
        "document_management": True,
        "reports": True,
        "excel_export": True,
        "pdf_export": True,
        "qc_release": True,
        "preservation": True,
        "expiry_monitor": True,
        "barcode_scanner": True,
        "multi_user": False,
        "ai_prediction": False,
        "abc_analysis": False,
        "eoq_calculator": False,
        "advanced_reports": False,
        "api_access": False,
        "custom_branding": False,
        "priority_support": False,
    }
    if license_type in ["professional", "enterprise"]:
        features["ai_prediction"] = True
        features["abc_analysis"] = True
        features["eoq_calculator"] = True
        features["advanced_reports"] = True
        features["multi_user"] = True
    if license_type == "enterprise":
        features["api_access"] = True
        features["custom_branding"] = True
        features["priority_support"] = True
    return features


# ==================================================================
# Utility Functions
# ==================================================================

def get_remaining_days() -> int:
    """Get remaining days on current license."""
    license_key = load_license()
    if not license_key:
        return 0
    try:
        parts = license_key.split('-')
        if len(parts) >= 2:
            expiry_date = datetime.strptime(parts[1], "%Y%m%d")
            return (expiry_date - datetime.now()).days
    except (ValueError, IndexError):
        pass
    return 0


def is_in_grace_period() -> bool:
    """Check if license is in grace period."""
    remaining = get_remaining_days()
    return -GRACE_PERIOD_DAYS <= remaining < 0


def get_expiry_date() -> Optional[datetime]:
    """Get license expiry date."""
    license_key = load_license()
    if not license_key:
        return None
    try:
        parts = license_key.split('-')
        if len(parts) >= 2:
            return datetime.strptime(parts[1], "%Y%m%d")
    except (ValueError, IndexError):
        pass
    return None


def format_license_info() -> str:
    """Format license information for display."""
    status = get_license_status()
    lines = [
        "=" * 50,
        "iMat License Information",
        "=" * 50,
    ]
    if status.get("activated"):
        lines.append(f"Status: {'✅ Valid' if status['valid'] else '❌ Invalid'}")
        lines.append(f"Machine ID: {get_machine_id()}")
        lines.append(f"Activated: {status.get('activated_date', 'Unknown')}")
        lines.append(f"Expiry: {status.get('expiry_date', 'Unknown')}")
        lines.append(f"Days Remaining: {status.get('days_remaining', 0)}")
        if status.get("in_grace_period"):
            lines.append("⚠️ License is in grace period!")
        if status.get("expired"):
            lines.append("❌ License has expired!")
    else:
        lines.append("Status: ❌ No license activated")
        lines.append(f"Machine ID: {get_machine_id()}")
    lines.append("=" * 50)
    return "\n".join(lines)


__all__ = [
    'get_machine_id',
    'get_system_info',
    'generate_license_key',
    'generate_trial_key',
    'validate_license',
    'validate_license_detailed',
    'save_license',
    'load_license',
    'load_license_info',
    'is_license_valid',
    'get_license_status',
    'delete_license',
    'restore_license_from_backup',
    'generate_offline_request',
    'validate_offline_response',
    'get_license_type',
    'get_license_features',
    'get_remaining_days',
    'is_in_grace_period',
    'get_expiry_date',
    'format_license_info',
    'LICENSE_FILE',
    'SECRET_KEY',
    'GRACE_PERIOD_DAYS',
    'LICENSE_TYPES',
]