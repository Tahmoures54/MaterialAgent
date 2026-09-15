# Changelog

All notable changes to iMat Warehouse (MaterialAgent) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Planned
- Packaging (Windows executable)
- UI polish and first-run experience improvements
- Deeper AI forecasting validation
- Full Persian UI strings

## [2.0.0] - 2026-09-15

### Added
- `requirements.txt` and `pytest.ini`
- Regression tests for inventory integrity, document numbering, allocation, and QC rules
- Portable backup path (`backups/` folder)
- Support for injected database session in inventory/report helpers (better test isolation)

### Fixed / Hardened
- Deleting a **DRAFT** document now correctly reverses posted stock (MRR / MIV / MTR / RTV / OSND)
- Stock movements reject zero, negative, and invalid QC statuses
- Document numbers are unique and sequential (`TYPE-YYYYMMDD-NNNN`)
- Blank heat numbers normalize to `N/A`
- SQLite now enables WAL mode, foreign keys, and busy timeout
- Single-instance lock is kept alive for the process lifetime
- Config manager deep-merges settings without writing env overlays back to JSON

### Documentation
- README rewritten and completed (correct clone URL, Quick Start, Roles, Testing, Development sections)
- This CHANGELOG added

## [1.0.0] - 2026-07-27

### Added
- Initial full project release (PyQt6 + SQLite material control system for EPC projects)
