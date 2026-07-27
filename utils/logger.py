# utils/logger.py
"""
Logging Utilities – iMat Material Control System (EPC Edition).

Comprehensive logging system with:
- File and console logging
- Rotating file handlers
- Multiple log levels
- Module-specific loggers
- Exception traceback logging
- Performance timing logs
- User action audit logging
- Database operation logging
- Error notification hooks
- Log file management
- Colored console output
"""

import os
import sys
import logging
import traceback
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Any
from functools import wraps
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


# ==================================================================
# Constants
# ==================================================================

# Log directory
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")

# Log file settings
MAX_LOG_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 10  # Keep 10 backup files

# Log format
CONSOLE_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
FILE_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
DETAILED_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s'
AUDIT_FORMAT = '%(asctime)s - AUDIT - %(message)s'

# Date format
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# ANSI color codes for console output
COLORS = {
    'DEBUG': '\033[36m',      # Cyan
    'INFO': '\033[32m',       # Green
    'WARNING': '\033[33m',    # Yellow
    'ERROR': '\033[31m',      # Red
    'CRITICAL': '\033[35m',   # Magenta
    'RESET': '\033[0m',       # Reset
    'BOLD': '\033[1m',        # Bold
    'DIM': '\033[2m',         # Dim
}


# ==================================================================
# Custom Formatters
# ==================================================================

class ColoredFormatter(logging.Formatter):
    """Formatter with ANSI color codes for console output."""
    
    def format(self, record):
        """Format log record with colors."""
        # Add color based on level
        levelname = record.levelname
        if levelname in COLORS:
            record.levelname = f"{COLORS[levelname]}{levelname}{COLORS['RESET']}"
            record.msg = f"{COLORS[levelname]}{record.msg}{COLORS['RESET']}"
        
        # Dim the module name
        if hasattr(record, 'name'):
            record.name = f"{COLORS['DIM']}{record.name}{COLORS['RESET']}"
        
        return super().format(record)


class AuditFormatter(logging.Formatter):
    """Formatter for audit trail logs."""
    
    def format(self, record):
        """Format audit record."""
        timestamp = datetime.now().strftime(DATE_FORMAT)
        return f"{timestamp} - AUDIT - {record.msg}"


# ==================================================================
# Custom Handlers
# ==================================================================

class ErrorNotificationHandler(logging.Handler):
    """Handler that triggers notifications for ERROR and CRITICAL logs."""
    
    def __init__(self, callback: Optional[Callable] = None):
        """
        Initialize with optional callback.
        
        Args:
            callback: Function to call with error message
        """
        super().__init__()
        self.callback = callback
        self.setLevel(logging.ERROR)
    
    def emit(self, record):
        """Handle error log record."""
        msg = self.format(record)
        if self.callback:
            try:
                self.callback(msg)
            except Exception:
                pass


# ==================================================================
# Logger Setup
# ==================================================================

def setup_logger(
    name: str = __name__,
    level: int = logging.INFO,
    log_to_console: bool = True,
    log_to_file: bool = True,
    log_format: str = CONSOLE_FORMAT,
    file_format: str = FILE_FORMAT,
    colored_console: bool = True,
    rotating: bool = True,
    max_bytes: int = MAX_LOG_FILE_SIZE,
    backup_count: int = BACKUP_COUNT,
    error_callback: Optional[Callable] = None,
) -> logging.Logger:
    """
    Configure and return a logger instance.
    
    Args:
        name: Logger name (usually __name__)
        level: Logging level
        log_to_console: Enable console output
        log_to_file: Enable file output
        log_format: Format for console output
        file_format: Format for file output
        colored_console: Use colored output on console
        rotating: Use rotating file handler
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        error_callback: Callback for error notifications
    
    Returns:
        Configured logger instance
    
    Example:
        >>> logger = setup_logger(__name__)
        >>> logger.info("Application started")
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        
        if colored_console:
            console_formatter = ColoredFormatter(log_format, datefmt=DATE_FORMAT)
        else:
            console_formatter = logging.Formatter(log_format, datefmt=DATE_FORMAT)
        
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_to_file:
        # Ensure log directory exists
        os.makedirs(LOG_DIR, exist_ok=True)
        
        log_file = os.path.join(LOG_DIR, f"aimat_{datetime.now().strftime('%Y%m%d')}.log")
        
        if rotating:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
        else:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
        
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(file_format, datefmt=DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Error notification handler
    if error_callback:
        error_handler = ErrorNotificationHandler(error_callback)
        error_handler.setFormatter(logging.Formatter(DETAILED_FORMAT, datefmt=DATE_FORMAT))
        logger.addHandler(error_handler)
    
    return logger


def get_logger(name: str = __name__) -> logging.Logger:
    """
    Get an existing logger or create a new one.
    
    Args:
        name: Logger name
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        return setup_logger(name)
    
    return logger


# ==================================================================
# Specialized Loggers
# ==================================================================

def setup_audit_logger(log_file: Optional[str] = None) -> logging.Logger:
    """
    Setup a logger specifically for audit trail.
    
    Args:
        log_file: Path to audit log file
    
    Returns:
        Audit logger instance
    """
    if log_file is None:
        log_file = os.path.join(LOG_DIR, f"audit_{datetime.now().strftime('%Y%m%d')}.log")
    
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    logger = logging.getLogger("audit")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_FILE_SIZE,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        handler.setFormatter(AuditFormatter())
        logger.addHandler(handler)
    
    return logger


def setup_db_logger() -> logging.Logger:
    """
    Setup a logger specifically for database operations.
    
    Returns:
        Database logger instance
    """
    log_file = os.path.join(LOG_DIR, f"database_{datetime.now().strftime('%Y%m%d')}.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    logger = logging.getLogger("database")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_FILE_SIZE,
            backupCount=5,
            encoding='utf-8'
        )
        formatter = logging.Formatter(DETAILED_FORMAT, datefmt=DATE_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def setup_performance_logger() -> logging.Logger:
    """
    Setup a logger for performance timing.
    
    Returns:
        Performance logger instance
    """
    log_file = os.path.join(LOG_DIR, f"performance_{datetime.now().strftime('%Y%m%d')}.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    logger = logging.getLogger("performance")
    logger.setLevel(logging.DEBUG)
    
    if not logger.handlers:
        handler = RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_FILE_SIZE,
            backupCount=5,
            encoding='utf-8'
        )
        formatter = logging.Formatter(
            '%(asctime)s - %(message)s',
            datefmt=DATE_FORMAT
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


# ==================================================================
# Convenience Functions
# ==================================================================

def log_error(module: str, error_message: str, exception: Optional[Exception] = None):
    """
    Log an error with optional exception traceback.
    
    Args:
        module: Module name
        error_message: Error description
        exception: Optional exception object
    """
    logger = get_logger(module)
    
    if exception:
        logger.error(f"{error_message} - {str(exception)}", exc_info=True)
    else:
        logger.error(error_message)


def log_info(module: str, message: str):
    """
    Log an info message.
    
    Args:
        module: Module name
        message: Info message
    """
    logger = get_logger(module)
    logger.info(message)


def log_warning(module: str, message: str):
    """
    Log a warning message.
    
    Args:
        module: Module name
        message: Warning message
    """
    logger = get_logger(module)
    logger.warning(message)


def log_debug(module: str, message: str):
    """
    Log a debug message.
    
    Args:
        module: Module name
        message: Debug message
    """
    logger = get_logger(module)
    logger.debug(message)


def log_critical(module: str, message: str, exception: Optional[Exception] = None):
    """
    Log a critical error.
    
    Args:
        module: Module name
        message: Critical error message
        exception: Optional exception object
    """
    logger = get_logger(module)
    
    if exception:
        logger.critical(f"{message} - {str(exception)}", exc_info=True)
    else:
        logger.critical(message)


def log_audit(
    user: str,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    details: str = "",
    status: str = "SUCCESS"
):
    """
    Log an audit trail entry.
    
    Args:
        user: Username who performed the action
        action: Action performed (CREATE, UPDATE, DELETE, LOGIN, etc.)
        entity_type: Type of entity (Product, Document, etc.)
        entity_id: ID of the entity
        details: Additional details
        status: Result status (SUCCESS, FAILURE)
    """
    audit_logger = setup_audit_logger()
    
    audit_message = (
        f"User={user} | Action={action} | "
        f"Entity={entity_type} | ID={entity_id} | "
        f"Status={status}"
    )
    
    if details:
        audit_message += f" | Details={details}"
    
    audit_logger.info(audit_message)


def log_db_operation(operation: str, table: str, details: str = "", 
                     duration_ms: float = 0):
    """
    Log a database operation.
    
    Args:
        operation: Operation type (SELECT, INSERT, UPDATE, DELETE)
        table: Table name
        details: Additional details
        duration_ms: Operation duration in milliseconds
    """
    db_logger = setup_db_logger()
    
    message = f"{operation} | Table={table}"
    
    if duration_ms > 0:
        message += f" | Duration={duration_ms:.2f}ms"
    
    if details:
        message += f" | {details}"
    
    db_logger.info(message)


# ==================================================================
# Decorators
# ==================================================================

def log_function_call(logger_name: Optional[str] = None):
    """
    Decorator to log function calls.
    
    Args:
        logger_name: Logger name (uses module name if None)
    
    Example:
        @log_function_call()
        def my_function():
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            log = get_logger(logger_name or func.__module__)
            
            # Log function entry
            log.debug(f"Entering: {func.__name__}()")
            
            try:
                result = func(*args, **kwargs)
                log.debug(f"Exiting: {func.__name__}() - Success")
                return result
            except Exception as e:
                log.error(f"Error in {func.__name__}(): {str(e)}", exc_info=True)
                raise
        
        return wrapper
    return decorator


def log_performance(logger_name: Optional[str] = None):
    """
    Decorator to log function execution time.
    
    Args:
        logger_name: Logger name
    
    Example:
        @log_performance()
        def slow_function():
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            perf_logger = setup_performance_logger()
            
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = (time.perf_counter() - start_time) * 1000
                perf_logger.debug(
                    f"{func.__module__}.{func.__name__}() - {elapsed:.2f}ms"
                )
        
        return wrapper
    return decorator


def log_exceptions(logger_name: Optional[str] = None, reraise: bool = True):
    """
    Decorator to log exceptions and optionally reraise them.
    
    Args:
        logger_name: Logger name
        reraise: Whether to reraise the exception
    
    Example:
        @log_exceptions(reraise=False)
        def safe_function():
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            log = get_logger(logger_name or func.__module__)
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log.error(
                    f"Exception in {func.__name__}(): {str(e)}",
                    exc_info=True
                )
                if reraise:
                    raise
        
        return wrapper
    return decorator


# ==================================================================
# Log Management
# ==================================================================

def get_log_files(sort_by_date: bool = True) -> list:
    """
    Get list of log files.
    
    Args:
        sort_by_date: Sort by modification date
    
    Returns:
        List of log file paths
    """
    if not os.path.exists(LOG_DIR):
        return []
    
    log_files = []
    for f in os.listdir(LOG_DIR):
        if f.endswith('.log'):
            filepath = os.path.join(LOG_DIR, f)
            log_files.append(filepath)
    
    if sort_by_date:
        log_files.sort(key=os.path.getmtime, reverse=True)
    
    return log_files


def cleanup_old_logs(max_age_days: int = 30) -> int:
    """
    Delete log files older than specified days.
    
    Args:
        max_age_days: Maximum age of log files in days
    
    Returns:
        Number of files deleted
    """
    if not os.path.exists(LOG_DIR):
        return 0
    
    cutoff = datetime.now().timestamp() - (max_age_days * 24 * 3600)
    deleted = 0
    
    for f in os.listdir(LOG_DIR):
        if f.endswith('.log'):
            filepath = os.path.join(LOG_DIR, f)
            if os.path.getmtime(filepath) < cutoff:
                try:
                    os.remove(filepath)
                    deleted += 1
                except OSError:
                    pass
    
    return deleted


def get_log_size_info() -> dict:
    """
    Get information about log files.
    
    Returns:
        Dictionary with log size information
    """
    info = {
        "log_directory": LOG_DIR,
        "total_files": 0,
        "total_size_mb": 0,
        "oldest_file": None,
        "newest_file": None,
        "files": [],
    }
    
    if not os.path.exists(LOG_DIR):
        return info
    
    log_files = get_log_files(sort_by_date=True)
    info["total_files"] = len(log_files)
    
    if log_files:
        info["newest_file"] = os.path.basename(log_files[0])
        info["oldest_file"] = os.path.basename(log_files[-1])
    
    for filepath in log_files:
        try:
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            info["total_size_mb"] += size_mb
            info["files"].append({
                "name": os.path.basename(filepath),
                "size_mb": round(size_mb, 2),
                "modified": datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M:%S'),
            })
        except OSError:
            pass
    
    info["total_size_mb"] = round(info["total_size_mb"], 2)
    
    return info


def purge_all_logs() -> int:
    """
    Delete all log files.
    
    Returns:
        Number of files deleted
    """
    if not os.path.exists(LOG_DIR):
        return 0
    
    deleted = 0
    for f in os.listdir(LOG_DIR):
        if f.endswith('.log'):
            try:
                os.remove(os.path.join(LOG_DIR, f))
                deleted += 1
            except OSError:
                pass
    
    return deleted


# ==================================================================
# Global Logger Instance
# ==================================================================

# Create default application logger
app_logger = setup_logger("iMat")


# ==================================================================
# Module Exports
# ==================================================================

__all__ = [
    # Setup functions
    'setup_logger',
    'get_logger',
    'setup_audit_logger',
    'setup_db_logger',
    'setup_performance_logger',
    
    # Convenience functions
    'log_error',
    'log_info',
    'log_warning',
    'log_debug',
    'log_critical',
    'log_audit',
    'log_db_operation',
    
    # Decorators
    'log_function_call',
    'log_performance',
    'log_exceptions',
    
    # Log management
    'get_log_files',
    'cleanup_old_logs',
    'get_log_size_info',
    'purge_all_logs',
    
    # Constants
    'LOG_DIR',
    'app_logger',
    
    # Formatters
    'ColoredFormatter',
    'AuditFormatter',
    
    # Handlers
    'ErrorNotificationHandler',
]