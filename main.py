# iMat/main.py
"""
iMat Material Control System – Main Entry Point (EPC Edition).

Application startup and initialization with:
- Splash screen with loading animation
- Database initialization and migration
- License validation and trial management
- User authentication
- Main window launch with role-based access
- Error handling and logging
- Single instance check
- High DPI support
- Crash reporting
"""

import sys
import os
import traceback
from datetime import datetime
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QTimer, QSharedMemory
from PyQt6.QtGui import QIcon, QFont

# ==================================================================
# Imports from project modules
# ==================================================================

from db.database import init_db, SessionLocal, get_database_info, backup_database
from db.models import User, ProjectInfo
from ui.splash_dialog import SplashDialog, SimpleSplashDialog
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow
from utils.logger import setup_logger, log_error, log_info, log_warning
from utils.license import is_license_valid, load_license, get_machine_id
from utils.trial import get_trial_status, is_trial_activated, activate_trial

# ==================================================================
# Constants
# ==================================================================

APP_NAME = "iMat Warehouse"
APP_VERSION = "2.0.0"
APP_EDITION = "EPC Edition"
ORGANIZATION_NAME = "iMat International"
ORGANIZATION_DOMAIN = "imat.io"

# Database path
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "aimat.db"))

# Single instance key
SINGLE_INSTANCE_KEY = "iMatWarehouseEPC_SingleInstance"

# Setup logger
logger = setup_logger("iMat")


# ==================================================================
# Exception Handler
# ==================================================================

def setup_exception_handler():
    """Setup global exception handler for unhandled exceptions."""
    def exception_hook(exc_type, exc_value, exc_traceback):
        """Global exception handler."""
        # Log the error
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.critical(f"Unhandled exception:\n{error_msg}")
        
        # Write to crash log
        crash_log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(crash_log_dir, exist_ok=True)
        crash_log_path = os.path.join(
            crash_log_dir,
            f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        
        try:
            with open(crash_log_path, 'w', encoding='utf-8') as f:
                f.write(f"iMat Crash Report\n")
                f.write(f"Version: {APP_VERSION}\n")
                f.write(f"Time: {datetime.now()}\n")
                f.write(f"Machine ID: {get_machine_id()}\n")
                f.write(f"{'='*60}\n\n")
                f.write(error_msg)
        except Exception:
            pass
        
        # Show error dialog
        QMessageBox.critical(
            None,
            "Application Error",
            f"An unexpected error occurred:\n\n{str(exc_value)}\n\n"
            f"A crash report has been saved to:\n{crash_log_path}\n\n"
            f"Please contact support@imat.io for assistance."
        )
        
        sys.exit(1)
    
    sys.excepthook = exception_hook


# ==================================================================
# Single Instance Check
# ==================================================================

def check_single_instance() -> bool:
    """
    Check if another instance is already running.
    
    Returns:
        True if this is the only instance
    """
    shared_memory = QSharedMemory(SINGLE_INSTANCE_KEY)
    
    if shared_memory.attach():
        # Another instance is running
        QMessageBox.warning(
            None,
            "Already Running",
            f"{APP_NAME} is already running.\n\n"
            "Please check your taskbar or system tray for the running instance."
        )
        return False
    
    # Create shared memory
    if not shared_memory.create(1):
        logger.warning("Failed to create shared memory for single instance check")
    
    return True


# ==================================================================
# Application Setup
# ==================================================================

def setup_application() -> QApplication:
    """
    Setup the Qt application with proper settings.
    
    Returns:
        Configured QApplication instance
    """
    # Enable High DPI support
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setOrganizationDomain(ORGANIZATION_DOMAIN)
    app.setApplicationVersion(APP_VERSION)
    
    # Set application icon
    icon_path = os.path.join(os.path.dirname(__file__), "resources", "images", "logo.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Apply stylesheet
    app.setStyleSheet("""
        QToolTip {
            background-color: #004D40;
            color: white;
            border: 1px solid #00695C;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
        }
    """)
    
    return app


# ==================================================================
# Database Initialization
# ==================================================================

def initialize_database(splash: SplashDialog) -> bool:
    """
    Initialize database with progress updates.
    
    Args:
        splash: Splash screen for progress updates
    
    Returns:
        True if initialization successful
    """
    try:
        splash.set_message("Initializing database...")
        splash.set_progress(20)
        
        # Initialize database
        init_db()
        
        splash.set_message("Database initialized")
        splash.set_progress(40)
        
        # Create default project info if needed
        session = SessionLocal()
        try:
            if session.query(ProjectInfo).count() == 0:
                default_project = ProjectInfo(
                    company_name="FARASAKOU",
                    project_name="Storage Development",
                    project_code="001"
                )
                session.add(default_project)
                session.commit()
                logger.info("Default project info created")
        finally:
            session.close()
        
        logger.info("Database initialized successfully")
        
        # Get database info
        db_info = get_database_info()
        logger.info(f"Database: {db_info.get('url', 'Unknown')} | "
                   f"Tables: {len(db_info.get('tables', []))} | "
                   f"Size: {db_info.get('size_mb', 0)} MB")
        
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        splash.close()
        QMessageBox.critical(
            None,
            "Database Error",
            f"Failed to initialize database:\n\n{str(e)}\n\n"
            "Please check:\n"
            "• Database file permissions\n"
            "• Disk space availability\n"
            "• Database file integrity"
        )
        return False


# ==================================================================
# License Check
# ==================================================================

def check_license(splash: SplashDialog) -> dict:
    """
    Check license status.
    
    Args:
        splash: Splash screen for progress updates
    
    Returns:
        License status dictionary
    """
    splash.set_message("Checking license...")
    splash.set_progress(50)
    
    license_info = {
        "has_license": False,
        "has_trial": False,
        "trial_active": False,
        "message": "",
    }
    
    # Check full license
    if is_license_valid():
        license_info["has_license"] = True
        license_info["message"] = "Full license active"
        logger.info("Full license validated")
        return license_info
    
    # Check trial
    try:
        session = SessionLocal()
        trial_status = get_trial_status(session)
        session.close()
        
        if trial_status['active']:
            license_info["has_trial"] = True
            license_info["trial_active"] = True
            license_info["message"] = (
                f"Trial active - {trial_status['days_left']} days remaining"
            )
            
            # Activate trial if not already
            if not is_trial_activated():
                activate_trial()
                
            logger.info(f"Trial active: {trial_status['days_left']} days remaining")
        elif trial_status.get('in_grace_period'):
            license_info["has_trial"] = True
            license_info["trial_active"] = True
            license_info["message"] = "Trial in grace period"
            logger.warning("Trial in grace period")
        else:
            license_info["message"] = "Trial expired - running in demo mode"
            logger.warning("Trial expired")
    except Exception as e:
        logger.error(f"Trial check failed: {e}")
        license_info["message"] = "Demo mode (limited)"
    
    return license_info


# ==================================================================
# Authentication
# ==================================================================

def authenticate_user(splash: SplashDialog) -> tuple:
    """
    Show login dialog and authenticate user.
    
    Args:
        splash: Splash screen
    
    Returns:
        Tuple of (username, role) or (None, None) if cancelled
    """
    splash.set_message("Waiting for login...")
    splash.set_progress(80)
    
    # Close splash before showing login
    splash.close()
    
    # Show login dialog
    login = LoginDialog()
    
    if login.exec() != LoginDialog.DialogCode.Accepted:
        logger.info("User cancelled login")
        return None, None
    
    username = login.current_user
    role = login.user_role
    
    logger.info(f"User logged in: {username} (Role: {role})")
    
    return username, role


# ==================================================================
# Main Entry Point
# ==================================================================

def main():
    """Main application entry point."""
    
    # Check single instance
    if not check_single_instance():
        return 1
    
    # Setup exception handler
    setup_exception_handler()
    
    # Setup application
    app = setup_application()
    
    # Show splash screen
    splash = SplashDialog()
    splash.set_message("Starting iMat Warehouse...")
    splash.set_progress(5)
    splash.show()
    app.processEvents()
    
    # Initialize database
    if not initialize_database(splash):
        return 1
    
    # Check license
    license_info = check_license(splash)
    splash.set_progress(60)
    
    # Wait for splash animation
    splash.set_message("Ready to start...")
    splash.set_progress(100)
    
    # Use exec() to wait for animation
    if splash.exec() != SplashDialog.DialogCode.Accepted:
        # Splash was skipped or closed
        pass
    
    # Authenticate user
    username, role = authenticate_user(splash)
    
    if not username:
        logger.info("Application closed - no user logged in")
        return 0
    
    # Create and show main window
    try:
        window = MainWindow(user_role=role, username=username)
        window.show()
        
        logger.info(f"Main window opened for user: {username}")
        
        # Run application event loop
        exit_code = app.exec()
        
        logger.info(f"Application closed with exit code: {exit_code}")
        return exit_code
        
    except Exception as e:
        logger.critical(f"Failed to create main window: {e}", exc_info=True)
        QMessageBox.critical(
            None,
            "Fatal Error",
            f"Failed to start the application:\n\n{str(e)}\n\n"
            "Please contact support@imat.io for assistance."
        )
        return 1


# ==================================================================
# Script Entry Point
# ==================================================================

if __name__ == "__main__":
    # Print startup banner
    print(f"\n{'='*60}")
    print(f"  {APP_NAME} v{APP_VERSION} - {APP_EDITION}")
    print(f"  {ORGANIZATION_NAME}")
    print(f"  www.imat.io")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Start application
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nApplication interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)