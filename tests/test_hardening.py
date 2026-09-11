# tests/test_hardening.py
"""Regression tests for inventory integrity, numbering, and validation hardening."""

from datetime import date

import pytest

from logic.document_logic import generate_next_doc_number
from logic.location_logic import create_location
from logic.material_request_logic import create_material_request
from logic.product_logic import create_product
from logic.reports_logic import get_dashboard_kpis


class TestMaterialRequestNumbering:
    def test_sequential_numbers_survive_count_gaps(self, db_session, sample_product):
        req1 = create_material_request(
            db_session,
            {"requester": "eng1", "company": "ACME"},
            [{"item_code": sample_product.item_code, "qty": 2, "unit_price": 10}],
        )
        req2 = create_material_request(
            db_session,
            {"requester": "eng2", "company": "ACME"},
            [{"item_code": sample_product.item_code, "qty": 3, "unit_price": 10}],
        )
        assert req1.request_no != req2.request_no
        assert req1.request_no.endswith("-0001")
        assert req2.request_no.endswith("-0002")

    def test_empty_lines_rejected(self, db_session):
        with pytest.raises(ValueError, match="at least one line"):
            create_material_request(db_session, {"requester": "eng1"}, [])


class TestProductAndLocationValidation:
    def test_product_requires_item_code(self, db_session):
        with pytest.raises(ValueError, match="Item code is required"):
            create_product(db_session, {"description": "No code"})

    def test_location_rejects_invalid_type(self, db_session):
        with pytest.raises(ValueError, match="Invalid location type"):
            create_location(db_session, "XX-1", "Bad", "GARAGE")

    def test_location_requires_code(self, db_session):
        with pytest.raises(ValueError, match="Location code is required"):
            create_location(db_session, "  ", "Name", "WAREHOUSE")


class TestDashboardKpis:
    def test_dashboard_includes_qc_and_alerts(
        self, db_session, sample_stock_quarantine, sample_stock_accepted, sample_material_request
    ):
        kpis = get_dashboard_kpis(db_session)
        assert kpis["qc_summary"]["QUARANTINE"] == 100.0
        assert kpis["qc_summary"]["ACCEPTED"] == 200.0
        assert kpis["pending_material_requests"] >= 1
        assert "expiring_soon" in kpis
        assert "preservation_due" in kpis


class TestDocumentSequence:
    def test_sequence_increments_after_create(
        self, db_session, sample_product, sample_location_warehouse
    ):
        from logic.document_logic import create_document

        first = generate_next_doc_number(db_session, "MRR", date.today())
        create_document(
            db_session,
            {
                "doc_no": first,
                "doc_type": "MRR",
                "doc_date": date.today(),
                "to_location_id": sample_location_warehouse.id,
                "created_by": "test",
            },
            [{
                "item_code": sample_product.item_code,
                "heat_no": "HEAT-SEQ",
                "location_id": sample_location_warehouse.id,
                "qty": 1.0,
            }],
        )
        second = generate_next_doc_number(db_session, "MRR", date.today())
        assert second != first
        assert second.endswith("-0002")
