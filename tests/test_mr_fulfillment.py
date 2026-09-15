"""Tests for MIV → Material Request fulfillment linkage."""
from logic.material_request_logic import (
    create_material_request,
    record_issue_fulfillment,
)
from logic.reports_logic import get_material_shortage_report


def test_fulfillment_reduces_remaining(db_session):
    try:
        from db.models import Product
        if not db_session.query(Product).filter_by(item_code="PIPE-001").first():
            db_session.add(Product(item_code="PIPE-001", description="Test pipe", unit="M"))
            db_session.commit()
    except Exception:
        pass

    req = create_material_request(
        db_session,
        {"requester": "eng1"},
        [{"item_code": "PIPE-001", "qty": 10.0, "unit": "M"}],
    )

    applied = record_issue_fulfillment(db_session, "PIPE-001", 4.0)
    assert applied == 4.0
    db_session.commit()

    rows = get_material_shortage_report(db_session)
    mr_rows = [r for r in rows if r.get("request_no") == req.request_no]
    assert mr_rows
    assert mr_rows[0]["fulfilled_qty"] == 4.0
    assert mr_rows[0]["remaining_qty"] == 6.0

    back = record_issue_fulfillment(db_session, "PIPE-001", 4.0, reverse=True)
    assert back == 4.0
