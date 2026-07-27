# ui/auto_backup_dialog.py
"""
Auto-Backup Settings Dialog – iMat Material Control System (EPC Edition).

Provides comprehensive automatic backup configuration including:
- Enable/disable automatic backups
- Configurable backup interval (hours/days)
- Maximum number of backups to retain
- Destination folder selection
- Backup file naming patterns
- Manual backup trigger
- Backup history viewer
- Restore from backup functionality
- Compression options
- Email notification settings (optional)
"""

import os
import json
import shutil
import glob
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QCheckBox, QFileDialog, QGroupBox, QFormLayout,
    QLineEdit, QFrame, QWidget, QComboBox, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QStatusBar,
    QTabWidget, QTextEdit, QAbstractItemView, QDialogButtonBox,
    QSlider, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QIcon

from ui.logo_widget import LogoWidget
from config.config_manager import config

# ==================================================================
# Constants
# ==================================================================

DEFAULT_CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'app_config.json')
DEFAULT_BACKUP_DIR = os.path.join(os.path.expanduser("~"), "iMat_Backups")
DEFAULT_INTERVAL_HOURS = 24
DEFAULT_MAX_BACKUPS = 30
DEFAULT_COMPRESSION = True

INTERVAL_UNITS = {
    "hours": "Hours",
    "days": "Days",
    "weeks": "Weeks",
}

BACKUP_FILENAME_PATTERNS = [
    "aimat_backup_{timestamp}.db",
    "aimat_{date}_backup.db",
    "backup_{datetime}.db",
    "aimat_db_{date}_{time}.db",
]


# ==================================================================
# Backup Worker Thread
# ==================================================================

class BackupWorker(QThread):
    """Background thread for performing backup operations."""
    
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    error = pyqtSignal(str)

    def __init__(self, source_path: str, dest_path: str, compress: bool = False):
        super().__init__()
        self.source_path = source_path
        self.dest_path = dest_path
        self.compress = compress

    def run(self):
        """Execute the backup operation."""
        try:
            self.progress.emit(10)
            
            # Check source exists
            if not os.path.exists(self.source_path):
                self.error.emit(f"Source file not found: {self.source_path}")
                return

            self.progress.emit(30)
            
            # Create destination directory
            dest_dir = os.path.dirname(self.dest_path)
            os.makedirs(dest_dir, exist_ok=True)

            self.progress.emit(50)
            
            # Copy file
            if self.compress:
                import zipfile
                zip_path = self.dest_path.replace('.db', '.zip')
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.write(self.source_path, os.path.basename(self.source_path))
                self.dest_path = zip_path
            else:
                shutil.copy2(self.source_path, self.dest_path)

            self.progress.emit(90)
            
            # Verify backup
            if os.path.exists(self.dest_path):
                backup_size = os.path.getsize(self.dest_path)
                size_mb = backup_size / (1024 * 1024)
                self.progress.emit(100)
                self.finished.emit(True, f"Backup created successfully ({size_mb:.2f} MB)")
            else:
                self.error.emit("Backup verification failed")

        except Exception as e:
            self.error.emit(f"Backup failed: {str(e)}")


# ==================================================================
# Auto Backup Dialog
# ==================================================================

class AutoBackupDialog(QDialog):
    """
    Auto-Backup Settings dialog for configuring automatic database backups.
    
    Features:
    - Enable/disable scheduled backups
    - Configurable interval and retention
    - Destination folder selection
    - Manual backup trigger
    - Backup history with restore capability
    - Compression support
    """

    backup_completed = pyqtSignal(str)

    def __init__(self, parent=None):
        """
        Initialize the Auto-Backup dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.parent = parent
        
        # Configuration
        self.config = self._load_config()
        self.backup_history: List[Dict] = []
        
        # Window setup
        self.setWindowTitle("iMat – Auto‑Backup Configuration")
        self.setMinimumSize(700, 650)
        self.setModal(True)
        
        # Build UI
        self._init_ui()
        
        # Load settings and history
        self._load_settings()
        self._load_backup_history()

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _init_ui(self):
        """Initialize the complete user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Build components
        self._build_header(main_layout)
        self._build_content(main_layout)
        self._build_status_bar(main_layout)

    def _build_header(self, parent_layout: QVBoxLayout):
        """Build the header with logo and title."""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #004D40;
                border-radius: 0px;
            }
            QLabel { color: white; }
        """)
        header.setFixedHeight(70)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 15, 5)

        # Logo
        self.logo_widget = LogoWidget()
        header_layout.addWidget(self.logo_widget)

        # Title
        title = QLabel("⚙️ Auto‑Backup Configuration")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Subtitle
        subtitle = QLabel("Protect your data with automatic backups")
        subtitle.setFont(QFont("Arial", 9))
        subtitle.setStyleSheet("color: #B2DFDB;")
        header_layout.addWidget(subtitle)

        parent_layout.addWidget(header)

    def _build_content(self, parent_layout: QVBoxLayout):
        """Build the main content area with tabs."""
        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #CCC;
                background: white;
            }
            QTabBar::tab {
                background: #E0E0E0;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #004D40;
                color: white;
                font-weight: bold;
            }
        """)

        # Add tabs
        self.tab_widget.addTab(self._build_settings_tab(), "⚙️ Settings")
        self.tab_widget.addTab(self._build_history_tab(), "📋 Backup History")
        self.tab_widget.addTab(self._build_advanced_tab(), "🔧 Advanced")

        parent_layout.addWidget(self.tab_widget)

        # Bottom buttons
        button_frame = QFrame()
        button_frame.setStyleSheet("background: #F5F5F5; border-top: 1px solid #CCC;")
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(15, 10, 15, 10)

        # Manual backup button
        btn_manual = QPushButton("💾 Create Backup Now")
        btn_manual.setStyleSheet(self._get_button_style("primary"))
        btn_manual.clicked.connect(self._create_manual_backup)
        button_layout.addWidget(btn_manual)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setTextVisible(True)
        button_layout.addWidget(self.progress_bar, 1)

        button_layout.addStretch()

        # Save button
        btn_save = QPushButton("💾 Save Settings")
        btn_save.setStyleSheet(self._get_button_style("success"))
        btn_save.clicked.connect(self._save_and_close)
        button_layout.addWidget(btn_save)

        # Cancel button
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet(self._get_button_style("neutral"))
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_cancel)

        parent_layout.addWidget(button_frame)

    def _build_settings_tab(self) -> QWidget:
        """Build the settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)

        # Enable/Disable group
        enable_group = QGroupBox("Enable Automatic Backup")
        enable_group.setStyleSheet(self._get_group_style())
        enable_layout = QVBoxLayout(enable_group)

        self.enable_check = QCheckBox("Enable scheduled automatic backups")
        self.enable_check.setStyleSheet("font-weight: bold; color: #004D40; font-size: 13px;")
        self.enable_check.toggled.connect(self._on_enable_toggled)
        enable_layout.addWidget(self.enable_check)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        enable_layout.addWidget(self.status_label)

        layout.addWidget(enable_group)

        # Backup interval group
        interval_group = QGroupBox("Backup Schedule")
        interval_group.setStyleSheet(self._get_group_style())
        interval_form = QFormLayout(interval_group)
        interval_form.setSpacing(8)

        # Interval value
        interval_layout = QHBoxLayout()
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 168)
        self.interval_spin.setValue(24)
        self.interval_spin.setSuffix(" hours")
        interval_layout.addWidget(self.interval_spin)

        self.interval_unit_combo = QComboBox()
        self.interval_unit_combo.addItems(["Hours", "Days", "Weeks"])
        self.interval_unit_combo.setCurrentIndex(0)
        self.interval_unit_combo.currentIndexChanged.connect(self._on_interval_unit_changed)
        interval_layout.addWidget(self.interval_unit_combo)

        interval_form.addRow("Backup every:", interval_layout)

        # Next backup time
        self.next_backup_label = QLabel("Next backup: Not scheduled")
        self.next_backup_label.setStyleSheet("color: #00695C; font-weight: bold;")
        interval_form.addRow(self.next_backup_label)

        layout.addWidget(interval_group)

        # Retention group
        retention_group = QGroupBox("Backup Retention")
        retention_group.setStyleSheet(self._get_group_style())
        retention_form = QFormLayout(retention_group)
        retention_form.setSpacing(8)

        self.max_backups_spin = QSpinBox()
        self.max_backups_spin.setRange(1, 365)
        self.max_backups_spin.setValue(30)
        self.max_backups_spin.setSuffix(" backups")
        self.max_backups_spin.setToolTip("Maximum number of backup files to retain")
        retention_form.addRow("Keep last:", self.max_backups_spin)

        self.current_backups_label = QLabel("Current backups: 0")
        self.current_backups_label.setStyleSheet("color: #666;")
        retention_form.addRow(self.current_backups_label)

        layout.addWidget(retention_group)

        # Destination group
        dest_group = QGroupBox("Backup Destination")
        dest_group.setStyleSheet(self._get_group_style())
        dest_layout = QHBoxLayout(dest_group)

        self.dest_edit = QLineEdit()
        self.dest_edit.setReadOnly(True)
        self.dest_edit.setStyleSheet("background: #F5F5F5; padding: 6px;")
        self.dest_edit.setPlaceholderText("Select backup destination folder...")
        dest_layout.addWidget(self.dest_edit)

        btn_browse = QPushButton("📂 Browse...")
        btn_browse.setStyleSheet(self._get_button_style("primary"))
        btn_browse.clicked.connect(self._browse_folder)
        dest_layout.addWidget(btn_browse)

        layout.addWidget(dest_group)

        # Space estimate
        self.space_label = QLabel()
        self.space_label.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        layout.addWidget(self.space_label)

        layout.addStretch()
        return widget

    def _build_history_tab(self) -> QWidget:
        """Build the backup history tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)

        # Description
        desc_label = QLabel(
            "Below is a list of recent backups. You can restore from any backup "
            "or delete old backups to free up space."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #555;")
        layout.addWidget(desc_label)

        # Refresh button
        refresh_layout = QHBoxLayout()
        refresh_layout.addStretch()
        btn_refresh = QPushButton("🔄 Refresh List")
        btn_refresh.setStyleSheet(self._get_button_style("neutral"))
        btn_refresh.clicked.connect(self._load_backup_history)
        refresh_layout.addWidget(btn_refresh)
        layout.addLayout(refresh_layout)

        # History table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "Backup File", "Date/Time", "Size", "Type",
            "Status", "Actions"
        ])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background: white;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #004D40;
                color: white;
                font-weight: bold;
                padding: 6px;
            }
        """)

        # Set column widths
        column_widths = [200, 150, 80, 80, 80, 150]
        for i, width in enumerate(column_widths):
            self.history_table.setColumnWidth(i, width)

        layout.addWidget(self.history_table)

        # Action buttons
        action_layout = QHBoxLayout()
        
        btn_restore = QPushButton("🔄 Restore Selected")
        btn_restore.setStyleSheet(self._get_button_style("warning"))
        btn_restore.clicked.connect(self._restore_backup)
        action_layout.addWidget(btn_restore)
        
        btn_delete = QPushButton("🗑️ Delete Selected")
        btn_delete.setStyleSheet(self._get_button_style("danger"))
        btn_delete.clicked.connect(self._delete_backup)
        action_layout.addWidget(btn_delete)
        
        btn_cleanup = QPushButton("🧹 Cleanup Old Backups")
        btn_cleanup.setStyleSheet(self._get_button_style("neutral"))
        btn_cleanup.clicked.connect(self._cleanup_backups)
        action_layout.addWidget(btn_cleanup)
        
        action_layout.addStretch()
        layout.addLayout(action_layout)

        return widget

    def _build_advanced_tab(self) -> QWidget:
        """Build the advanced settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)

        # Compression group
        compress_group = QGroupBox("Compression")
        compress_group.setStyleSheet(self._get_group_style())
        compress_layout = QVBoxLayout(compress_group)

        self.compress_check = QCheckBox("Compress backup files (ZIP)")
        self.compress_check.setToolTip("Reduce backup size by compressing with ZIP")
        compress_layout.addWidget(self.compress_check)

        self.compress_info = QLabel(
            "Compression can reduce backup size by 50-80% but takes longer to create."
        )
        self.compress_info.setStyleSheet("color: #666; font-size: 10px;")
        self.compress_info.setWordWrap(True)
        compress_layout.addWidget(self.compress_info)

        layout.addWidget(compress_group)

        # File naming group
        naming_group = QGroupBox("Backup File Naming")
        naming_group.setStyleSheet(self._get_group_style())
        naming_layout = QVBoxLayout(naming_group)

        self.naming_combo = QComboBox()
        self.naming_combo.addItems(BACKUP_FILENAME_PATTERNS)
        self.naming_combo.setCurrentIndex(0)
        naming_layout.addWidget(self.naming_combo)

        self.naming_preview = QLabel()
        self.naming_preview.setStyleSheet("color: #00695C; font-style: italic;")
        self.naming_preview.setText(self._generate_preview_filename())
        self.naming_combo.currentIndexChanged.connect(
            lambda: self.naming_preview.setText(self._generate_preview_filename())
        )
        naming_layout.addWidget(self.naming_preview)

        layout.addWidget(naming_group)

        # Database info group
        info_group = QGroupBox("Database Information")
        info_group.setStyleSheet(self._get_group_style())
        info_layout = QFormLayout(info_group)
        info_layout.setSpacing(6)

        self.db_path_label = QLabel()
        self.db_path_label.setStyleSheet("font-family: monospace; font-size: 10px;")
        self.db_path_label.setWordWrap(True)
        info_layout.addRow("Database path:", self.db_path_label)

        self.db_size_label = QLabel()
        info_layout.addRow("Current size:", self.db_size_label)

        layout.addWidget(info_group)

        # Update database info
        self._update_database_info()

        layout.addStretch()
        return widget

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready – Configure your backup settings")
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: #E0F2F1;
                border-top: 1px solid #B2DFDB;
                color: #004D40;
                font-weight: bold;
            }
        """)
        parent_layout.addWidget(self.status_bar)

    # ==================================================================
    # Style Methods
    # ==================================================================

    def _get_group_style(self) -> str:
        """Get group box stylesheet."""
        return """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #B2DFDB;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #004D40;
            }
        """

    def _get_button_style(self, button_type: str) -> str:
        """Get button stylesheet by type."""
        styles = {
            "primary": """
                QPushButton {
                    background-color: #00897B;
                    color: white;
                    border: none;
                    padding: 6px 14px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #00695C; }
                QPushButton:disabled { background-color: #999; }
            """,
            "success": """
                QPushButton {
                    background-color: #2E86C1;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #2471A3; }
                QPushButton:disabled { background-color: #999; }
            """,
            "warning": """
                QPushButton {
                    background-color: #FFA000;
                    color: white;
                    border: none;
                    padding: 6px 14px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #FF8F00; }
            """,
            "danger": """
                QPushButton {
                    background-color: #D32F2F;
                    color: white;
                    border: none;
                    padding: 6px 14px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #C62828; }
            """,
            "neutral": """
                QPushButton {
                    background-color: #757575;
                    color: white;
                    border: none;
                    padding: 6px 14px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #616161; }
            """,
        }
        return styles.get(button_type, styles["neutral"])

    # ==================================================================
    # Configuration Methods
    # ==================================================================

    def _load_config(self) -> Dict:
        """Load configuration from file."""
        if os.path.exists(DEFAULT_CONFIG_FILE):
            try:
                with open(DEFAULT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_config(self):
        """Save configuration to file."""
        try:
            with open(DEFAULT_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except IOError:
            return False

    def _load_settings(self):
        """Load settings from config into UI."""
        backup_config = self.config.get('auto_backup', {})

        # Enable/Disable
        self.enable_check.setChecked(backup_config.get('enabled', False))

        # Interval
        interval_hours = backup_config.get('interval_hours', DEFAULT_INTERVAL_HOURS)
        if interval_hours >= 168:  # 7 days = 1 week
            self.interval_spin.setValue(interval_hours // 168)
            self.interval_unit_combo.setCurrentIndex(2)
        elif interval_hours >= 24:  # 1 day
            self.interval_spin.setValue(interval_hours // 24)
            self.interval_unit_combo.setCurrentIndex(1)
        else:
            self.interval_spin.setValue(interval_hours)
            self.interval_unit_combo.setCurrentIndex(0)

        # Max backups
        self.max_backups_spin.setValue(backup_config.get('max_backups', DEFAULT_MAX_BACKUPS))

        # Destination
        dest_dir = backup_config.get('dest_dir', '')
        if not dest_dir:
            dest_dir = DEFAULT_BACKUP_DIR
        self.dest_edit.setText(dest_dir)

        # Compression
        self.compress_check.setChecked(backup_config.get('compression', DEFAULT_COMPRESSION))

        # Update UI state
        self._on_enable_toggled(self.enable_check.isChecked())
        self._update_next_backup_label()
        self._update_space_estimate()

    def _load_backup_history(self):
        """Load backup history from destination folder."""
        self.backup_history = []
        dest_dir = self.dest_edit.text()

        if not dest_dir or not os.path.exists(dest_dir):
            self.history_table.setRowCount(0)
            self.current_backups_label.setText("Current backups: 0")
            return

        # Find backup files
        backup_patterns = ["*.db", "*.zip"]
        backup_files = []
        for pattern in backup_patterns:
            backup_files.extend(glob.glob(os.path.join(dest_dir, pattern)))

        # Also check for backup files in parent directory patterns
        backup_files.extend(glob.glob(os.path.join(dest_dir, "aimat_backup_*")))
        backup_files.extend(glob.glob(os.path.join(dest_dir, "backup_*")))

        # Remove duplicates
        backup_files = list(set(backup_files))

        # Sort by modification time (newest first)
        backup_files.sort(key=os.path.getmtime, reverse=True)

        self.backup_history = []
        for filepath in backup_files:
            try:
                stat = os.stat(filepath)
                size_mb = stat.st_size / (1024 * 1024)
                mod_time = datetime.fromtimestamp(stat.st_mtime)
                
                self.backup_history.append({
                    "filepath": filepath,
                    "filename": os.path.basename(filepath),
                    "datetime": mod_time,
                    "size_mb": size_mb,
                    "type": "Compressed" if filepath.endswith('.zip') else "Direct",
                    "status": "✅ Valid" if size_mb > 0 else "⚠️ Empty",
                })
            except OSError:
                continue

        # Display in table
        self._display_backup_history()
        self.current_backups_label.setText(
            f"Current backups: {len(self.backup_history)}"
        )

    def _display_backup_history(self):
        """Display backup history in the table."""
        self.history_table.setRowCount(len(self.backup_history))

        for row, backup in enumerate(self.backup_history):
            # Filename
            self.history_table.setItem(row, 0, QTableWidgetItem(backup["filename"]))

            # Date/Time
            date_item = QTableWidgetItem(
                backup["datetime"].strftime("%Y-%m-%d %H:%M:%S")
            )
            self.history_table.setItem(row, 1, date_item)

            # Size
            size_item = QTableWidgetItem(f"{backup['size_mb']:.2f} MB")
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.history_table.setItem(row, 2, size_item)

            # Type
            type_item = QTableWidgetItem(backup["type"])
            self.history_table.setItem(row, 3, type_item)

            # Status
            status_item = QTableWidgetItem(backup["status"])
            if "Valid" in backup["status"]:
                status_item.setForeground(QColor("#2E7D32"))
            else:
                status_item.setForeground(QColor("#D32F2F"))
            self.history_table.setItem(row, 4, status_item)

            # Actions - Restore button
            btn_restore = QPushButton("🔄 Restore")
            btn_restore.setStyleSheet(self._get_button_style("warning"))
            btn_restore.clicked.connect(
                lambda checked, p=backup["filepath"]: self._restore_backup_file(p)
            )
            self.history_table.setCellWidget(row, 5, btn_restore)

    # ==================================================================
    # Event Handlers
    # ==================================================================

    def _on_enable_toggled(self, enabled: bool):
        """Handle enable/disable toggle."""
        self.interval_spin.setEnabled(enabled)
        self.interval_unit_combo.setEnabled(enabled)
        self.max_backups_spin.setEnabled(enabled)
        
        if enabled:
            self.status_label.setText("✅ Automatic backups are enabled")
            self.status_label.setStyleSheet("color: #2E7D32; font-weight: bold;")
        else:
            self.status_label.setText("❌ Automatic backups are disabled")
            self.status_label.setStyleSheet("color: #D32F2F; font-weight: bold;")

        self._update_next_backup_label()

    def _on_interval_unit_changed(self, index: int):
        """Handle interval unit change."""
        if index == 0:  # Hours
            self.interval_spin.setRange(1, 168)
            self.interval_spin.setSuffix(" hours")
            self.interval_spin.setValue(24)
        elif index == 1:  # Days
            self.interval_spin.setRange(1, 30)
            self.interval_spin.setSuffix(" days")
            self.interval_spin.setValue(1)
        elif index == 2:  # Weeks
            self.interval_spin.setRange(1, 12)
            self.interval_spin.setSuffix(" weeks")
            self.interval_spin.setValue(1)

        self._update_next_backup_label()

    def _browse_folder(self):
        """Open folder browser dialog."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Backup Destination Folder",
            self.dest_edit.text() or os.path.expanduser("~")
        )
        if folder:
            self.dest_edit.setText(folder)
            self._update_space_estimate()
            self._load_backup_history()

    # ==================================================================
    # Update Methods
    # ==================================================================

    def _update_next_backup_label(self):
        """Update the next backup time label."""
        if not self.enable_check.isChecked():
            self.next_backup_label.setText("Next backup: Not scheduled")
            return

        interval = self.interval_spin.value()
        unit = self.interval_unit_combo.currentIndex()

        if unit == 0:  # Hours
            delta = timedelta(hours=interval)
        elif unit == 1:  # Days
            delta = timedelta(days=interval)
        else:  # Weeks
            delta = timedelta(weeks=interval)

        next_backup = datetime.now() + delta
        self.next_backup_label.setText(
            f"Next backup: {next_backup.strftime('%Y-%m-%d %H:%M')}"
        )

    def _update_space_estimate(self):
        """Update the space estimate label."""
        dest_dir = self.dest_edit.text()
        if not dest_dir:
            self.space_label.setText("")
            return

        # Get source database size
        db_path = os.path.join(os.path.dirname(__file__), '..', 'aimat.db')
        if os.path.exists(db_path):
            db_size = os.path.getsize(db_path) / (1024 * 1024)
            max_backups = self.max_backups_spin.value()
            estimated_space = db_size * max_backups

            if self.compress_check.isChecked():
                estimated_space *= 0.3  # Assume 70% compression

            self.space_label.setText(
                f"📊 Estimated space needed: ~{estimated_space:.1f} MB "
                f"(for {max_backups} backups)"
            )

    def _update_database_info(self):
        """Update database information display."""
        db_path = os.path.join(os.path.dirname(__file__), '..', 'aimat.db')
        self.db_path_label.setText(db_path)

        if os.path.exists(db_path):
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            self.db_size_label.setText(f"{size_mb:.2f} MB")
        else:
            self.db_size_label.setText("Not found")

    def _generate_preview_filename(self) -> str:
        """Generate a preview of the backup filename."""
        now = datetime.now()
        pattern = self.naming_combo.currentText()
        
        preview = pattern.replace("{timestamp}", now.strftime("%Y%m%d_%H%M%S"))
        preview = preview.replace("{datetime}", now.strftime("%Y%m%d_%H%M%S"))
        preview = preview.replace("{date}", now.strftime("%Y%m%d"))
        preview = preview.replace("{time}", now.strftime("%H%M%S"))
        
        return f"Preview: {preview}"

    # ==================================================================
    # Backup Operations
    # ==================================================================

    def _create_manual_backup(self):
        """Create a manual backup now."""
        dest_dir = self.dest_edit.text()
        if not dest_dir:
            QMessageBox.warning(
                self, "No Destination",
                "Please select a backup destination folder first."
            )
            return

        # Generate filename
        now = datetime.now()
        pattern = self.naming_combo.currentText()
        filename = pattern.replace("{timestamp}", now.strftime("%Y%m%d_%H%M%S"))
        filename = filename.replace("{datetime}", now.strftime("%Y%m%d_%H%M%S"))
        filename = filename.replace("{date}", now.strftime("%Y%m%d"))
        filename = filename.replace("{time}", now.strftime("%H%M%S"))
        
        dest_path = os.path.join(dest_dir, filename)
        source_path = os.path.join(os.path.dirname(__file__), '..', 'aimat.db')

        if not os.path.exists(source_path):
            QMessageBox.critical(
                self, "Error",
                f"Source database not found:\n{source_path}"
            )
            return

        # Run backup in background
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Creating backup...")

        self.worker = BackupWorker(
            source_path, dest_path,
            compress=self.compress_check.isChecked()
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._on_backup_complete)
        self.worker.error.connect(self._on_backup_error)
        self.worker.start()

    def _on_backup_complete(self, success: bool, message: str):
        """Handle backup completion."""
        self.progress_bar.setVisible(False)
        
        if success:
            QMessageBox.information(self, "Backup Complete", message)
            self.status_bar.showMessage(message, 5000)
            self._load_backup_history()
            self.backup_completed.emit(message)
        else:
            QMessageBox.critical(self, "Backup Failed", message)
            self.status_bar.showMessage("Backup failed")

    def _on_backup_error(self, error_message: str):
        """Handle backup error."""
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Backup Error", error_message)
        self.status_bar.showMessage("Backup failed", 5000)

    def _restore_backup(self):
        """Restore selected backup file."""
        row = self.history_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a backup to restore.")
            return

        backup_path = self.backup_history[row]["filepath"]
        self._restore_backup_file(backup_path)

    def _restore_backup_file(self, backup_path: str):
        """Restore from a specific backup file."""
        reply = QMessageBox.question(
            self, "Confirm Restore",
            "Are you sure you want to restore from this backup?\n\n"
            "⚠️ This will overwrite the current database!\n"
            "A backup of the current database will be created first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        db_path = os.path.join(os.path.dirname(__file__), '..', 'aimat.db')

        try:
            # Create backup of current database first
            if os.path.exists(db_path):
                safety_backup = db_path + f".before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(db_path, safety_backup)

            # Handle compressed backups
            if backup_path.endswith('.zip'):
                import zipfile
                with zipfile.ZipFile(backup_path, 'r') as zf:
                    zf.extractall(os.path.dirname(db_path))
            else:
                shutil.copy2(backup_path, db_path)

            QMessageBox.information(
                self, "Restore Complete",
                "Database has been restored successfully.\n\n"
                "Please restart the application for changes to take effect."
            )
            self.status_bar.showMessage("Database restored successfully", 5000)

        except Exception as e:
            QMessageBox.critical(self, "Restore Failed", f"Failed to restore backup:\n{str(e)}")

    def _delete_backup(self):
        """Delete selected backup file."""
        row = self.history_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a backup to delete.")
            return

        backup = self.backup_history[row]
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete this backup?\n\n{backup['filename']}\nSize: {backup['size_mb']:.2f} MB",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(backup["filepath"])
                self._load_backup_history()
                self.status_bar.showMessage("Backup deleted", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete backup:\n{str(e)}")

    def _cleanup_backups(self):
        """Remove old backups exceeding the retention limit."""
        max_backups = self.max_backups_spin.value()
        
        if len(self.backup_history) <= max_backups:
            QMessageBox.information(
                self, "Cleanup",
                f"No cleanup needed. You have {len(self.backup_history)} backups "
                f"(limit: {max_backups})."
            )
            return

        reply = QMessageBox.question(
            self, "Confirm Cleanup",
            f"Remove {len(self.backup_history) - max_backups} old backup(s)?\n\n"
            f"You have {len(self.backup_history)} backups, limit is {max_backups}.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            removed = 0
            for backup in self.backup_history[max_backups:]:
                try:
                    os.remove(backup["filepath"])
                    removed += 1
                except Exception:
                    pass

            self._load_backup_history()
            self.status_bar.showMessage(f"Removed {removed} old backup(s)", 3000)

    # ==================================================================
    # Save & Close
    # ==================================================================

    def _save_and_close(self):
        """Save settings and close dialog."""
        # Calculate interval in hours
        interval = self.interval_spin.value()
        unit = self.interval_unit_combo.currentIndex()
        
        if unit == 1:  # Days
            interval *= 24
        elif unit == 2:  # Weeks
            interval *= 168

        # Update config
        self.config['auto_backup'] = {
            'enabled': self.enable_check.isChecked(),
            'interval_hours': interval,
            'max_backups': self.max_backups_spin.value(),
            'dest_dir': self.dest_edit.text(),
            'compression': self.compress_check.isChecked(),
            'filename_pattern': self.naming_combo.currentText(),
        }

        if self._save_config():
            self.status_bar.showMessage("Settings saved successfully", 3000)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to save settings.")

    def get_settings(self) -> Dict:
        """Get the current backup settings."""
        return self.config.get('auto_backup', {})

    def closeEvent(self, event):
        """Handle dialog close event."""
        super().closeEvent(event)