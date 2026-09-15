"""Tests for material coverage reports (shortage, PO receipts, in-transit)."""
from logic.reports_logic import (
    get_material_shortage_report,
    get_po_receipt_summary,
    get_in_transit_report,
)


def test_shortage_report_empty(db_session):
    rows = get_material_shortage_report(db_session)
    assert isinstance(rows, list)


def test_po_receipt_summary_empty(db_session):
    rows = get_po_receipt_summary(db_session)
    assert isinstance(rows, list)


def test_in_transit_report_empty(db_session):
    rows = get_in_transit_report(db_session)
    assert isinstance(rows, list)
