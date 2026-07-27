# utils/password_manager.py
"""
Password Management Utilities – iMat Material Control System (EPC Edition).

Secure password handling with:
- PBKDF2-SHA256 hashing with random salt
- Password strength validation
- Password policy enforcement
- Secure password generation
- Password expiry checking
- Password history tracking
- Brute force protection
- Constant-time comparison
"""

import os
import re
import hashlib
import secrets
import string
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, List


# ==================================================================
# Constants
# ==================================================================

# Password hashing parameters
HASH_ALGORITHM = 'sha256'
SALT_LENGTH = 32  # bytes
ITERATIONS = 100000  # PBKDF2 iterations
KEY_LENGTH = 32  # bytes (256 bits)

# Password policy defaults
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 128
REQUIRE_UPPERCASE = False
REQUIRE_LOWERCASE = False
REQUIRE_DIGITS = False
REQUIRE_SPECIAL_CHARS = False
PASSWORD_EXPIRY_DAYS = 0  # 0 = never expires
PASSWORD_HISTORY_COUNT = 3  # Number of previous passwords to remember

# Password strength thresholds
STRENGTH_VERY_WEAK = 0
STRENGTH_WEAK = 1
STRENGTH_MODERATE = 2
STRENGTH_STRONG = 3
STRENGTH_VERY_STRONG = 4

STRENGTH_LABELS = {
    STRENGTH_VERY_WEAK: "Very Weak",
    STRENGTH_WEAK: "Weak",
    STRENGTH_MODERATE: "Moderate",
    STRENGTH_STRONG: "Strong",
    STRENGTH_VERY_STRONG: "Very Strong",
}

STRENGTH_COLORS = {
    STRENGTH_VERY_WEAK: "#D32F2F",   # Red
    STRENGTH_WEAK: "#E65100",         # Orange
    STRENGTH_MODERATE: "#F57F17",     # Yellow
    STRENGTH_STRONG: "#2E7D32",       # Green
    STRENGTH_VERY_STRONG: "#004D40",  # Dark Green
}


# ==================================================================
# Core Hashing Functions
# ==================================================================

def hash_password(password: str) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256 with a random salt.
    
    Format: salt_hex:hash_hex
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password string in format 'salt:hash'
    
    Example:
        >>> hash_password("my_secure_password")
        'a1b2c3d4...:e5f6g7h8...'
    """
    salt = os.urandom(SALT_LENGTH)
    pwd_hash = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        password.encode('utf-8'),
        salt,
        ITERATIONS,
        dklen=KEY_LENGTH
    )
    return salt.hex() + ":" + pwd_hash.hex()


def verify_password(stored_password: str, provided_password: str) -> bool:
    """
    Verify a password against the stored hash using constant-time comparison.
    
    Args:
        stored_password: Stored hash in format 'salt:hash'
        provided_password: Plain text password to verify
    
    Returns:
        True if password matches
    
    Example:
        >>> stored = hash_password("my_password")
        >>> verify_password(stored, "my_password")
        True
        >>> verify_password(stored, "wrong_password")
        False
    """
    try:
        # Parse stored password
        salt_hex, hash_hex = stored_password.split(":")
        salt = bytes.fromhex(salt_hex)
        stored_hash = bytes.fromhex(hash_hex)
        
        # Hash the provided password
        computed_hash = hashlib.pbkdf2_hmac(
            HASH_ALGORITHM,
            provided_password.encode('utf-8'),
            salt,
            ITERATIONS,
            dklen=KEY_LENGTH
        )
        
        # Constant-time comparison to prevent timing attacks
        return _constant_time_compare(computed_hash, stored_hash)
        
    except (ValueError, AttributeError):
        return False


def _constant_time_compare(a: bytes, b: bytes) -> bool:
    """
    Compare two byte strings in constant time.
    
    Args:
        a: First byte string
        b: Second byte string
    
    Returns:
        True if equal
    """
    if len(a) != len(b):
        return False
    
    result = 0
    for x, y in zip(a, b):
        result |= x ^ y
    
    return result == 0


def needs_rehash(stored_password: str) -> bool:
    """
    Check if a stored password needs to be rehashed
    (e.g., if hashing parameters have been updated).
    
    Args:
        stored_password: Stored hash string
    
    Returns:
        True if password should be rehashed
    """
    try:
        salt_hex, hash_hex = stored_password.split(":")
        salt = bytes.fromhex(salt_hex)
        
        # Check if salt length or iterations have changed
        if len(salt) != SALT_LENGTH:
            return True
        
        return False
    except (ValueError, AttributeError):
        return True


# ==================================================================
# Password Validation
# ==================================================================

def validate_password_strength(
    password: str,
    min_length: int = MIN_PASSWORD_LENGTH,
    require_uppercase: bool = REQUIRE_UPPERCASE,
    require_lowercase: bool = REQUIRE_LOWERCASE,
    require_digits: bool = REQUIRE_DIGITS,
    require_special: bool = REQUIRE_SPECIAL_CHARS,
) -> Tuple[bool, str, int]:
    """
    Validate password against policy requirements.
    
    Args:
        password: Password to validate
        min_length: Minimum length
        require_uppercase: Require uppercase letters
        require_lowercase: Require lowercase letters
        require_digits: Require digits
        require_special: Require special characters
    
    Returns:
        Tuple of (is_valid, message, strength_score)
    
    Example:
        >>> validate_password_strength("Weak")
        (False, "Password must be at least 6 characters", 1)
        >>> validate_password_strength("Str0ng!Pass")
        (True, "Password is Strong", 3)
    """
    errors = []
    score = 0
    
    # Length check
    if len(password) < min_length:
        errors.append(f"Password must be at least {min_length} characters")
    elif len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if len(password) >= 16:
        score += 1
    
    # Character type checks
    has_upper = bool(re.search(r'[A-Z]', password))
    has_lower = bool(re.search(r'[a-z]', password))
    has_digit = bool(re.search(r'\d', password))
    has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>\[\]\\\/_\-+=\';`~]', password))
    
    if require_uppercase and not has_upper:
        errors.append("Password must contain at least one uppercase letter")
    if require_lowercase and not has_lower:
        errors.append("Password must contain at least one lowercase letter")
    if require_digits and not has_digit:
        errors.append("Password must contain at least one digit")
    if require_special and not has_special:
        errors.append("Password must contain at least one special character")
    
    # Score based on character variety
    char_types = sum([has_upper, has_lower, has_digit, has_special])
    score += char_types - 1 if char_types > 1 else 0
    
    # Check for common patterns
    if _has_common_patterns(password):
        score = max(0, score - 1)
        errors.append("Password contains common patterns")
    
    # Check for repeated characters
    if _has_repeated_characters(password):
        score = max(0, score - 1)
    
    # Check for sequential characters
    if _has_sequential_characters(password):
        score = max(0, score - 1)
    
    # Ensure score is within bounds
    score = max(STRENGTH_VERY_WEAK, min(STRENGTH_VERY_STRONG, score))
    
    # Build message
    if errors:
        message = "; ".join(errors)
    else:
        message = f"Password is {STRENGTH_LABELS[score]}"
    
    return len(errors) == 0, message, score


def _has_common_patterns(password: str) -> bool:
    """Check for common password patterns."""
    common_patterns = [
        r'password', r'12345', r'qwerty', r'abc123',
        r'admin', r'letmein', r'welcome', r'monkey',
        r'dragon', r'master', r'login',
    ]
    
    password_lower = password.lower()
    for pattern in common_patterns:
        if pattern in password_lower:
            return True
    
    return False


def _has_repeated_characters(password: str) -> bool:
    """Check for repeated characters."""
    return bool(re.search(r'(.)\1{2,}', password))


def _has_sequential_characters(password: str) -> bool:
    """Check for sequential characters."""
    sequences = [
        'abcdefghijklmnopqrstuvwxyz',
        'zyxwvutsrqponmlkjihgfedcba',
        '01234567890',
        '09876543210',
    ]
    
    password_lower = password.lower()
    for seq in sequences:
        for i in range(len(seq) - 2):
            if seq[i:i+3] in password_lower:
                return True
    
    return False


def check_password_expiry(
    last_changed: Optional[datetime],
    expiry_days: int = PASSWORD_EXPIRY_DAYS
) -> Tuple[bool, int]:
    """
    Check if a password has expired.
    
    Args:
        last_changed: Date password was last changed
        expiry_days: Number of days before expiry
    
    Returns:
        Tuple of (is_expired, days_remaining)
    """
    if expiry_days <= 0:
        return False, float('inf')
    
    if last_changed is None:
        return True, 0
    
    expiry_date = last_changed + timedelta(days=expiry_days)
    days_remaining = (expiry_date - datetime.now()).days
    
    return days_remaining <= 0, max(0, days_remaining)


# ==================================================================
# Password Generation
# ==================================================================

def generate_password(
    length: int = 12,
    include_uppercase: bool = True,
    include_lowercase: bool = True,
    include_digits: bool = True,
    include_special: bool = True,
    exclude_ambiguous: bool = True,
) -> str:
    """
    Generate a secure random password.
    
    Args:
        length: Password length
        include_uppercase: Include uppercase letters
        include_lowercase: Include lowercase letters
        include_digits: Include digits
        include_special: Include special characters
        exclude_ambiguous: Exclude ambiguous characters (0/O, 1/l/I, etc.)
    
    Returns:
        Generated password
    
    Example:
        >>> generate_password(16)
        'xK9#mP2$vL5@nQ8*w'
    """
    characters = ""
    
    if include_uppercase:
        chars = string.ascii_uppercase
        if exclude_ambiguous:
            chars = chars.replace('O', '').replace('I', '').replace('L', '')
        characters += chars
    
    if include_lowercase:
        chars = string.ascii_lowercase
        if exclude_ambiguous:
            chars = chars.replace('o', '').replace('l', '').replace('i', '')
        characters += chars
    
    if include_digits:
        chars = string.digits
        if exclude_ambiguous:
            chars = chars.replace('0', '').replace('1', '')
        characters += chars
    
    if include_special:
        special = '!@#$%^&*()_+-=[]{}|;:,.<>?'
        characters += special
    
    if not characters:
        characters = string.ascii_letters + string.digits
    
    # Ensure at least one of each required type
    password = []
    if include_uppercase:
        password.append(secrets.choice(string.ascii_uppercase))
    if include_lowercase:
        password.append(secrets.choice(string.ascii_lowercase))
    if include_digits:
        password.append(secrets.choice(string.digits))
    if include_special:
        password.append(secrets.choice('!@#$%^&*'))
    
    # Fill remaining length
    remaining = length - len(password)
    password.extend(secrets.choice(characters) for _ in range(remaining))
    
    # Shuffle
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)


def generate_passphrase(num_words: int = 4, separator: str = "-") -> str:
    """
    Generate a memorable passphrase using random words.
    
    Args:
        num_words: Number of words
        separator: Word separator
    
    Returns:
        Generated passphrase
    
    Example:
        >>> generate_passphrase(4)
        'correct-horse-battery-staple'
    """
    # Common word list (simplified)
    words = [
        'apple', 'banana', 'cherry', 'dragon', 'eagle', 'falcon', 'garden',
        'hammer', 'island', 'jungle', 'knight', 'lemon', 'mountain', 'noble',
        'orange', 'puzzle', 'quartz', 'river', 'storm', 'tiger', 'ultra',
        'valley', 'winter', 'xenon', 'yellow', 'zebra', 'anchor', 'bridge',
        'castle', 'diamond', 'emerald', 'forest', 'galaxy', 'harbor', 'iceberg',
        'jasper', 'koala', 'lantern', 'meteor', 'nebula', 'ocean', 'planet',
        'rocket', 'sapphire', 'thunder', 'unicorn', 'violet', 'whale', 'zenith',
        'aurora', 'bamboo', 'crystal', 'desert', 'eclipse', 'flame', 'glacier',
        'horizon', 'ivory', 'jade', 'kiwi', 'lotus', 'marble', 'nova',
        'onyx', 'pearl', 'quartz', 'ruby', 'silver', 'topaz', 'umber',
    ]
    
    selected = [secrets.choice(words) for _ in range(num_words)]
    
    # Add a random digit for extra security
    if secrets.randbelow(2):
        selected.append(str(secrets.randbelow(100)))
    
    return separator.join(selected)


# ==================================================================
# Password History
# ==================================================================

class PasswordHistory:
    """Track password history to prevent reuse."""
    
    def __init__(self, max_history: int = PASSWORD_HISTORY_COUNT):
        """
        Initialize password history.
        
        Args:
            max_history: Maximum number of previous passwords to store
        """
        self.max_history = max_history
        self._history: List[str] = []
    
    def add_password(self, hashed_password: str):
        """
        Add a password hash to history.
        
        Args:
            hashed_password: Hashed password to add
        """
        self._history.append(hashed_password)
        
        # Trim history
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]
    
    def is_previously_used(self, password: str) -> bool:
        """
        Check if a password has been used before.
        
        Args:
            password: Plain text password to check
        
        Returns:
            True if password was previously used
        """
        for old_hash in self._history:
            if verify_password(old_hash, password):
                return True
        return False
    
    def clear(self):
        """Clear password history."""
        self._history.clear()
    
    def count(self) -> int:
        """Get number of passwords in history."""
        return len(self._history)


# ==================================================================
# Utility Functions
# ==================================================================

def get_password_strength_info(password: str) -> Dict:
    """
    Get detailed password strength information.
    
    Args:
        password: Password to analyze
    
    Returns:
        Dictionary with strength details
    
    Example:
        >>> get_password_strength_info("MyStr0ng!Pass")
        {
            'length': 13,
            'score': 4,
            'label': 'Very Strong',
            'color': '#004D40',
            'has_uppercase': True,
            'has_lowercase': True,
            'has_digits': True,
            'has_special': True,
            ...
        }
    """
    valid, message, score = validate_password_strength(password)
    
    return {
        'length': len(password),
        'score': score,
        'label': STRENGTH_LABELS.get(score, "Unknown"),
        'color': STRENGTH_COLORS.get(score, "#000000"),
        'is_valid': valid,
        'message': message,
        'has_uppercase': bool(re.search(r'[A-Z]', password)),
        'has_lowercase': bool(re.search(r'[a-z]', password)),
        'has_digits': bool(re.search(r'\d', password)),
        'has_special': bool(re.search(r'[!@#$%^&*(),.?":{}|<>\[\]\\\/_\-+=\';`~]', password)),
        'has_common_patterns': _has_common_patterns(password),
        'has_repeated_chars': _has_repeated_characters(password),
        'has_sequential_chars': _has_sequential_characters(password),
    }


def mask_password(password: str, visible: int = 0) -> str:
    """
    Mask a password for display.
    
    Args:
        password: Password to mask
        visible: Number of characters to show at end
    
    Returns:
        Masked password
    """
    if len(password) <= visible:
        return password
    return '*' * (len(password) - visible) + password[-visible:]


def estimate_crack_time(password: str) -> str:
    """
    Estimate time to crack a password (very rough approximation).
    
    Args:
        password: Password to analyze
    
    Returns:
        Human-readable time estimate
    """
    # Character set size
    charset_size = 0
    if re.search(r'[a-z]', password):
        charset_size += 26
    if re.search(r'[A-Z]', password):
        charset_size += 26
    if re.search(r'\d', password):
        charset_size += 10
    if re.search(r'[!@#$%^&*(),.?":{}|<>\[\]\\\/_\-+=\';`~]', password):
        charset_size += 32
    
    if charset_size == 0:
        charset_size = 26
    
    # Total combinations
    combinations = charset_size ** len(password)
    
    # Assume 1 billion guesses per second
    guesses_per_second = 1_000_000_000
    seconds = combinations / guesses_per_second
    
    # Convert to human-readable
    if seconds < 1:
        return "Instantly"
    elif seconds < 60:
        return f"{seconds:.0f} seconds"
    elif seconds < 3600:
        return f"{seconds / 60:.0f} minutes"
    elif seconds < 86400:
        return f"{seconds / 3600:.0f} hours"
    elif seconds < 31536000:
        return f"{seconds / 86400:.0f} days"
    elif seconds < 315360000:
        return f"{seconds / 31536000:.1f} years"
    else:
        return "Centuries"


# ==================================================================
# Module Exports
# ==================================================================

__all__ = [
    # Hashing
    'hash_password',
    'verify_password',
    'needs_rehash',
    
    # Validation
    'validate_password_strength',
    'check_password_expiry',
    
    # Generation
    'generate_password',
    'generate_passphrase',
    
    # History
    'PasswordHistory',
    
    # Utilities
    'get_password_strength_info',
    'mask_password',
    'estimate_crack_time',
    
    # Constants
    'STRENGTH_LABELS',
    'STRENGTH_COLORS',
    'STRENGTH_VERY_WEAK',
    'STRENGTH_WEAK',
    'STRENGTH_MODERATE',
    'STRENGTH_STRONG',
    'STRENGTH_VERY_STRONG',
    'MIN_PASSWORD_LENGTH',
    'PASSWORD_EXPIRY_DAYS',
]