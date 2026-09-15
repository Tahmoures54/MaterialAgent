#!/usr/bin/env python3
"""Restore ui/reports_window.py from artifacts if corrupted on GitHub.

Usage (from repo root, after downloading the restored file):
  python scripts/restore_reports_ui.py path/to/reports_window_RESTORED.py
"""
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/restore_reports_ui.py <restored_reports_window.py>")
        return 1
    src = Path(sys.argv[1])
    dst = Path(__file__).resolve().parents[1] / "ui" / "reports_window.py"
    text = src.read_text(encoding="utf-8")
    if "class ReportsWindow" not in text:
        print("Source does not look like reports_window.py")
        return 1
    dst.write_text(text, encoding="utf-8")
    print(f"Restored {dst} ({len(text)} bytes)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
