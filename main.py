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

from db.database import init_db, SessionLocal, get_database_info, backup_database
from db.models import User, ProjectInfo
from ui.splash_dialog import SplashDialog, SimpleSplashDialog
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow


def _install_settings_dialog():
    """Wire System → Settings to the database engine dialog (admin only)."""
    from utils.logger import setup_logger
    _log = setup_logger("iMat.settings")

    def on_settings(self, checked: bool = False):
        if getattr(self, "user_role", "") != "admin":
            QMessageBox.warning(
                self, "Access Denied",
                "Only administrators can modify settings."
            )
            return
        try:
            from ui.database_settings_dialog import DatabaseSettingsDialog
            DatabaseSettingsDialog(self).exec()
        except Exception as e:
            _log.error(f"Settings dialog failed: {e}")
            QMessageBox.critical(
                self, "Settings Error",
                f"Could not open settings:\n{e}"
            )

    MainWindow.on_settings = on_settings


_install_settings_dialog()

from utils.logger import setup_logger, log_error, log_info, log_warning
from utils.license import is_license_valid, load_license, get_machine_id
from utils.trial import get_trial_status, is_trial_activated, activate_trial

APP_NAME = "iMat Warehouse"
APP_VERSION = "2.3.0"
# Keep main window title version in sync
try:
    import ui.main_window as _mw
    _mw.APP_VERSION = APP_VERSION
except Exception:
    pass
APP_EDITION = "EPC Edition"
ORGANIZATION_NAME = "iMat International"
ORGANIZATION_DOMAIN = "imat.io"

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "aimat.db"))
SINGLE_INSTANCE_KEY = "iMatWarehouseEPC_SingleInstance"
_single_instance_memory = None
logger = setup_logger("iMat")


def setup_exception_handler():
    def exception_hook(exc_type, exc_value, exc_traceback):
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.critical(f"Unhandled exception:\n{error_msg}")
        crash_log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(crash_log_dir, exist_ok=True)
        crash_log_path = os.path.join(
            crash_log_dir,
            f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        try:
            with open(crash_log_path, 'w', encoding='utf-8') as f:
                f.write(f"iMat Crash Report\nVersion: {APP_VERSION}\nTime: {datetime.now()}\n")
                f.write(f"Machine ID: {get_machine_id()}\n{'='*60}\n\n{error_msg}")
        except Exception:
            pass
        QMessageBox.critical(
            None, "Application Error",
            f"An unexpected error occurred:\n\n{str(exc_value)}\n\n"
            f"A crash report has been saved to:\n{crash_log_path}\n\n"
            f"Please contact support@imat.io for assistance."
        )
        sys.exit(1)
    sys.excepthook = exception_hook


def check_single_instance() -> bool:
    global _single_instance_memory
    _single_instance_memory = QSharedMemory(SINGLE_INSTANCE_KEY)
    if _single_instance_memory.attach():
        QMessageBox.warning(
            None, "Already Running",
            f"{APP_NAME} is already running.\n\n"
            "Please check your taskbar or system tray for the running instance."
        )
        return False
    if not _single_instance_memory.create(1):
        logger.warning("Failed to create shared memory for single instance check")
    return True


def setup_application() -> QApplication:
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setOrganizationDomain(ORGANIZATION_DOMAIN)
    app.setApplicationVersion(APP_VERSION)
    icon_path = os.path.join(os.path.dirname(__file__), "resources", "images", "logo.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet("""
        QToolTip {
            background-color: #004D40; color: white;
            border: 1px solid #00695C; padding: 4px 8px;
            border-radius: 4px; font-size: 11px;
        }
    """)
    return app


def initialize_database(splash: SplashDialog) -> bool:
    try:
        splash.set_message("Initializing database...")
        splash.set_progress(20)
        init_db()
        splash.set_message("Database initialized")
        splash.set_progress(40)
        session = SessionLocal()
        try:
            if session.query(ProjectInfo).count() == 0:
                session.add(ProjectInfo(
                    company_name="FARASAKOU",
                    project_name="Storage Development",
                    project_code="001"
                ))
                session.commit()
                logger.info("Default project info created")
        finally:
            session.close()
        logger.info("Database initialized successfully")
        db_info = get_database_info()
        logger.info(
            f"Database: {db_info.get('url', 'Unknown')} | "
            f"Tables: {len(db_info.get('tables', []))} | "
            f"Size: {db_info.get('size_mb', 0)} MB"
        )
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        splash.close()
        QMessageBox.critical(
            None, "Database Error",
            f"Failed to initialize database:\n\n{str(e)}\n\n"
            "Please check:\n"
            "• Database file permissions\n"
            "• Disk space availability\n"
            "• Database file integrity / SQL Server connectivity"
        )
        return False


def check_license(splash: SplashDialog) -> dict:
    splash.set_message("Checking license...")
    splash.set_progress(50)
    license_info = {
        "has_license": False,
        "has_trial": False,
        "trial_active": False,
        "message": "",
    }
    if is_license_valid():
        license_info["has_license"] = True
        license_info["message"] = "Full license active"
        logger.info("Full license validated")
        return license_info
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


def authenticate_user(splash: SplashDialog) -> tuple:
    splash.set_message("Waiting for login...")
    splash.set_progress(80)
    splash.close()
    login = LoginDialog()
    if login.exec() != LoginDialog.DialogCode.Accepted:
        logger.info("User cancelled login")
        return None, None
    username = login.current_user
    role = login.user_role
    logger.info(f"User logged in: {username} (Role: {role})")
    return username, role


def main():
    if not check_single_instance():
        return 1
    setup_exception_handler()
    app = setup_application()
    splash = SplashDialog()
    splash.set_message("Starting iMat Warehouse...")
    splash.set_progress(5)
    splash.show()
    app.processEvents()
    if not initialize_database(splash):
        return 1
    check_license(splash)
    splash.set_progress(60)
    splash.set_message("Ready to start...")
    splash.set_progress(100)
    if splash.exec() != SplashDialog.DialogCode.Accepted:
        pass
    username, role = authenticate_user(splash)
    if not username:
        logger.info("Application closed - no user logged in")
        return 0
    try:
        window = MainWindow(user_role=role, username=username)
        window.show()
        logger.info(f"Main window opened for user: {username}")
        exit_code = app.exec()
        logger.info(f"Application closed with exit code: {exit_code}")
        return exit_code
    except Exception as e:
        logger.critical(f"Failed to create main window: {e}", exc_info=True)
        QMessageBox.critical(
            None, "Fatal Error",
            f"Failed to start the application:\n\n{str(e)}\n\n"
            "Please contact support@imat.io for assistance."
        )
        return 1


if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  {APP_NAME} v{APP_VERSION} - {APP_EDITION}")
    print(f"  {ORGANIZATION_NAME}")
    print(f"  www.imat.io")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nApplication interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
