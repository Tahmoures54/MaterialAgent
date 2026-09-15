"""Tests for MIV → Material Request fulfillment (FIFO + explicit request_no)."""
from logic.material_request_logic import (
    create_material_request,
    record_issue_fulfillment,
)
from logic.reports_logic import get_material_shortage_report


def _ensure_product(db, code="PIPE-001"):
    from db.models import Product
    if not db.query(Product).filter_by(item_code=code).first():
        db.add(Product(item_code=code, description="Test pipe", unit="M"))
        db.commit()


def test_fulfillment_reduces_remaining(db_session):
    _ensure_product(db_session)
    req = create_material_request(
        db_session,
        {"requester": "eng1"},
        [{"item_code": "PIPE-001", "qty": 10.0, "unit": "M"}],
    )
    applied = record_issue_fulfillment(db_session, "PIPE-001", 4.0)
    assert applied == 4.0
    db_session.commit()
    rows = [r for r in get_material_shortage_report(db_session) if r.get("request_no") == req.request_no]
    assert rows and rows[0]["fulfilled_qty"] == 4.0 and rows[0]["remaining_qty"] == 6.0


def test_explicit_request_no_only_hits_that_mr(db_session):
    _ensure_product(db_session)
    a = create_material_request(db_session, {"requester": "a"}, [{"item_code": "PIPE-001", "qty": 5.0}])
    b = create_material_request(db_session, {"requester": "b"}, [{"item_code": "PIPE-001", "qty": 5.0}])
    applied = record_issue_fulfillment(db_session, "PIPE-001", 3.0, request_no=b.request_no)
    assert applied == 3.0
    db_session.commit()
    rows = {r["request_no"]: r for r in get_material_shortage_report(db_session)
            if r.get("request_no") in (a.request_no, b.request_no)}
    assert rows[a.request_no]["fulfilled_qty"] == 0.0
    assert rows[b.request_no]["fulfilled_qty"] == 3.0
