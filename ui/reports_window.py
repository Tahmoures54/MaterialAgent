# ui/reports_window.py
"""Load full ReportsWindow implementation from split part files (upload size workaround)."""
from pathlib import Path

_parts_dir = Path(__file__).with_name("_report_parts")
_source = "".join(
    (_parts_dir / f"part_{i}.pyfrag").read_text(encoding="utf-8")
    for i in range(3)
)
exec(compile(_source, str(Path(__file__).resolve()), "exec"), globals())
