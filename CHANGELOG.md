# Changelog

## [Unreleased]

### Planned
- Restore full visual style of help_fa/help_en from git history if needed
- Wire remaining Persian UI strings across all dialogs
- Deeper offline AI backtesting on real project extracts

## [2.3.0] - 2026-09-15

### Added
- `ui/database_settings_dialog.py` — GUI to switch SQLite ↔ SQL Server (save to config, restart required)
- `docs/DEPLOYMENT.md` — single-user and multi-user network checklist
- `docs/DEVELOPER.md` — architecture and API notes for contributors
- `packaging/imat.spec` + `packaging/build_windows.ps1` — PyInstaller Windows build
- SQL Server URL builder tests

### Fixed
- Module-level `engine` proxy restored (`from db.database import engine` works again)

### Improved
- Start dialog shows SQL Server + ensemble AI highlights (v2.2 branding)

### Note for integrators
Open database settings from code:
```python
from ui.database_settings_dialog import DatabaseSettingsDialog
DatabaseSettingsDialog(parent).exec()
```
Hook into `MainWindow.on_settings` (admin only) if not already wired in your branch.

## [2.2.0] - 2026-09-15

### Added
- SQL Server support via `app_config.json` (`database.engine` + `sqlserver` block)

## [2.1.0] - 2026-09-15

### Added (AI)
- Ensemble forecasting, intermittent demand, `demand_profile()`

## [2.0.0] - 2026-09-15

### Hardened
- Draft delete reverses stock, unique doc numbers, SQLite WAL/FK, session injection for tests

## [1.0.0] - 2026-07-27

### Added
- Initial release
