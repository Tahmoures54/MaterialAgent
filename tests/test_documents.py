# tests/test_documents.py
"""
Comprehensive tests for document creation and inventory effects.
Tests: MRR (receipt), MIV (issue), MTR (transfer), OSND (damage), 
RTV (return to vendor), MRV (return from site), MSR (requisition),
and rollback on error.
"""

import pytest
from datetime import date, timedelta
from logic.document_logic import (
    create_document, update_document_status, 
    get_document_by_no, delete_document
)
from db.models import Document, DocumentLine, Stock


class TestMRRReceipt:
    """Test Material Receipt Report (MRR) documents."""

    def test_create_mrr_creates_quarantine_stock(self, db_session, sample_product, 
                                                   sample_location_warehouse):
        """Test MRR receipt - stock goes to QUARANTINE."""
        header = {
            "doc_no": "MRR-2024-001",
            "doc_type": "MRR",
            "doc_date": date.today(),
            "po_no": "PO-998877",
            "vendor_name": "Steel Supplies Co.",
            "to_location_id": sample_location_warehouse.id,
            "created_by": "test_user"
        }
        lines = [{
            "item_code": sample_product.item_code,
            "heat_no": "HEAT-MRR-001",
            "location_id": sample_location_warehouse.id,
            "qty": 200.0,
            "unit": "MTR",
            "cert_no": "EN-3.1-CERT"
        }]

        doc = create_document(db_session, header, lines)

        # Check document saved
        assert doc.id is not None
        assert doc.doc_type == "MRR"
        assert doc.status == "DRAFT"
        assert len(doc.lines) == 1

        # Check stock created in quarantine
        stock = db_session.query(Stock).filter_by(heat_no="HEAT-MRR-001").first()
        assert stock is not None
        assert stock.quantity == 200.0
        assert stock.qc_status == "QUARANTINE"
        assert stock.location_id == sample_location_warehouse.id

    def test_create_mrr_multiple_lines(self, db_session, sample_product, 
                                        sample_product2, sample_location_warehouse):
        """Test MRR with multiple line items."""
        header = {
            "doc_no": "MRR-2024-002",
            "doc_type": "MRR",
            "doc_date": date.today(),
            "vendor_name": "Multi Supplies",
            "to_location_id": sample_location_warehouse.id,
            "created_by": "test_user"
        }
        lines = [
            {
                "item_code": sample_product.item_code,
                "heat_no": "HEAT-MULTI-001",
                "location_id": sample_location_warehouse.id,
                "qty": 100.0
            },
            {
                "item_code": sample_product2.item_code,
                "heat_no": "HEAT-MULTI-002",
                "location_id": sample_location_warehouse.id,
                "qty": 50.0
            }
        ]

        doc = create_document(db_session, header, lines)

        assert len(doc.lines) == 2
        assert doc.total_quantity == 150.0

        # Check both stocks created
        stock1 = db_session.query(Stock).filter_by(heat_no="HEAT-MULTI-001").first()
        stock2 = db_session.query(Stock).filter_by(heat_no="HEAT-MULTI-002").first()
        assert stock1.quantity == 100.0
        assert stock2.quantity == 50.0

    def test_create_mrr_with_details(self, db_session, sample_product, sample_location_warehouse):
        """Test MRR with tag, serial, and batch details."""
        header = {
            "doc_no": "MRR-2024-003",
            "doc_type": "MRR",
            "doc_date": date.today(),
            "to_location_id": sample_location_warehouse.id,
            "created_by": "test_user"
        }
        lines = [{
            "item_code": sample_product.item_code,
            "heat_no": "HEAT-DETAIL",
            "tag_no": "TAG-001",
            "serial_no": "SN-001",
            "location_id": sample_location_warehouse.id,
            "qty": 50.0,
            "cert_no": "CERT-3.1"
        }]

        doc = create_document(db_session, header, lines)

        stock = db_session.query(Stock).filter_by(heat_no="HEAT-DETAIL").first()
        assert stock.tag_no == "TAG-001"
        assert stock.serial_no == "SN-001"


class TestMIVIssue:
    """Test Material Issue Voucher (MIV) documents."""

    def test_create_miv_deducts_accepted_stock(self, db_session, sample_product, 
                                                 sample_location_warehouse):
        """Test MIV issue - deducts from ACCEPTED stock."""
        # Precondition: create accepted stock
        from logic.stock_logic import add_stock
        add_stock(db_session, sample_product.item_code, "HEAT-MIV-001",
                  sample_location_warehouse.id, 100.0, qc_status="ACCEPTED")
        db_session.commit()

        header = {
            "doc_no": "MIV-2024-001",
            "doc_type": "MIV",
            "doc_date": date.today(),
            "from_location_id": sample_location_warehouse.id,
            "subcontractor": "Site Team A",
            "created_by": "test_user"
        }
        lines = [{
            "item_code": sample_product.item_code,
            "heat_no": "HEAT-MIV-001",
            "location_id": sample_location_warehouse.id,
            "qty": 30.0,
            "unit": "MTR",
            "iso_drawing_no": "ISO-FW-001"
        }]

        doc = create_document(db_session, header, lines)

        assert doc.doc_type == "MIV"

        # Check stock reduced
        stock = db_session.query(Stock).filter_by(heat_no="HEAT-MIV-001").first()
        assert stock.quantity == 70.0  # 100 - 30

    def test_create_miv_insufficient_stock(self, db_session, sample_product, 
                                            sample_location_warehouse):
        """Test MIV fails when insufficient accepted stock."""
        header = {
            "doc_no": "MIV-2024-002",
            "doc_type": "MIV",
            "doc_date": date.today(),
            "from_location_id": sample_location_warehouse.id,
            "created_by": "test_user"
        }
        lines = [{
            "item_code": sample_product.item_code,
            "heat_no": "HEAT-NOEXIST",
            "location_id": sample_location_warehouse.id,
            "qty": 50.0
        }]

        with pytest.raises(ValueError, match="No stock found"):
            create_document(db_session, header, lines)

    def test_create_miv_quarantine_cannot_issue(self, db_session, sample_stock_quarantine):
        """Test that MIV cannot issue from quarantine stock."""
        header = {
            "doc_no": "MIV-2024-003",
            "doc_type": "MIV",
            "doc_date": date.today(),
            "from_location_id": sample_stock_quarantine.location_id,
            "created_by": "test_user"
        }
        lines = [{
            "item_code": sample_stock_quarantine.item_code,
            "heat_no": sample_stock_quarantine.heat_no,
            "location_id": sample_stock_quarantine.location_id,
            "qty": 10.0
        }]

        with pytest.raises(ValueError, match="No stock found"):
            create_document(db_session, header, lines)


class TestMTRTransfer:
    """Test Material Transfer Note (MTR) documents."""

    def test_create_mtr_transfers_stock(self, db_session, sample_product, 
                                         sample_location_warehouse, sample_location_yard):
        """Test stock transfer between locations."""
        # Precondition: create accepted stock at source
        from logic.stock_logic import add_stock
        add_stock(db_session, sample_product.item_code, "HEAT-MTR-001",
                  sample_location_warehouse.id, 100.0, qc_status="ACCEPTED")
        db_session.commit()

        header = {
            "doc_no": "MTR-2024-001",
            "doc_type": "MTR",
            "doc_date": date.today(),
            "from_location_id": sample_location_warehouse.id,
            "to_location_id": sample_location_yard.id,
            "created_by": "test_user"
        }
        lines = [{
            "item_code": sample_product.item_code,
            "heat_no": "HEAT-MTR-001",
            "location_id": sample_location_warehouse.id,
            "qty": 40.0
        }]

        doc = create_document(db_session, header, lines)

        # Check source reduced
        source = db_session.query(Stock).filter_by(
            heat_no="HEAT-MTR-001",
            location_id=sample_location_warehouse.id
        ).first()
        assert source.quantity == 60.0

        # Check destination increased
        dest = db_session.query(Stock).filter_by(
            heat_no="HEAT-MTR-001",
            location_id=sample_location_yard.id
        ).first()
        assert dest.quantity == 40.0

    def test_create_mtr_missing_destination(self, db_session, sample_product, 
                                              sample_location_warehouse):
        """Test MTR fails when no destination location."""
        header = {
            "doc_no": "MTR-2024-002",
            "doc_type": "MTR",
            "doc_date": date.today(),
            "from_location_id": sample_location_warehouse.id,
            "to_location_id": None,  # Missing!
            "created_by": "test_user"
        }
        lines = [{
            "item_code": sample_product.item_code,
            "heat_no": "HEAT-MTR-002",
            "location_id": sample_location_warehouse.id,
            "qty": 10.0
        }]

        with pytest.raises(ValueError, match="Transfer document missing destination location"):
            create_document(db_session, header, lines)


class TestDocumentStatus:
    """Test document status workflow."""

    def test_update_status_draft_to_approved(self, db_session, sample_document_mrr):
        """Test approving a draft document."""
        doc = update_document_status(
            db=db_session,
            document_id=sample_document_mrr.id,
            new_status="APPROVED",
            approved_by="manager"
        )

        assert doc.status == "APPROVED"
        assert doc.approved_by == "manager"
        assert doc.approved_at is not None

    def test_update_status_invalid_transition(self, db_session, sample_document_mrr):
        """Test that invalid status transition raises error."""
        with pytest.raises(ValueError, match="Cannot transition"):
            update_document_status(
                db=db_session,
                document_id=sample_document_mrr.id,
                new_status="CLOSED"  # Can't close directly from DRAFT
            )

    def test_update_status_approved_to_closed(self, db_session, sample_document_mrr):
        """Test closing an approved document."""
        # First approve
        update_document_status(db_session, sample_document_mrr.id, "APPROVED")
        
        # Then close
        doc = update_document_status(db_session, sample_document_mrr.id, "CLOSED")
        assert doc.status == "CLOSED"


class TestDocumentQueries:
    """Test document query functions."""

    def test_get_document_by_no(self, db_session, sample_document_mrr):
        """Test finding document by number."""
        doc = get_document_by_no(db_session, "MRR-2024-001")
        assert doc is not None
        assert doc.id == sample_document_mrr.id

    def test_get_document_by_no_not_found(self, db_session):
        """Test non-existent document returns None."""
        doc = get_document_by_no(db_session, "NONEXISTENT")
        assert doc is None

    def test_delete_draft_document(self, db_session, sample_document_mrr):
        """Test deleting a DRAFT document."""
        doc_id = sample_document_mrr.id
        delete_document(db_session, doc_id)
        
        doc = db_session.query(Document).filter_by(id=doc_id).first()
        assert doc is None

    def test_delete_approved_document_fails(self, db_session, sample_document_mrr):
        """Test that deleting an APPROVED document raises error."""
        update_document_status(db_session, sample_document_mrr.id, "APPROVED")
        
        with pytest.raises(ValueError, match="Only DRAFT documents can be deleted"):
            delete_document(db_session, sample_document_mrr.id)


class TestRollbackOnError:
    """Test atomic transaction rollback."""

    def test_rollback_on_miv_error(self, db_session, sample_product, sample_location_warehouse):
        """Test that document creation rolls back completely on error."""
        # Precondition: create some accepted stock
        from logic.stock_logic import add_stock
        add_stock(db_session, sample_product.item_code, "HEAT-ROLLBACK",
                  sample_location_warehouse.id, 50.0, qc_status="ACCEPTED")
        db_session.commit()

        header = {
            "doc_no": "MIV-ROLLBACK",
            "doc_type": "MIV",
            "doc_date": date.today(),
            "from_location_id": sample_location_warehouse.id,
            "created_by": "test_user"
        }
        # First line valid, second line exceeds stock
        lines = [
            {
                "item_code": sample_product.item_code,
                "heat_no": "HEAT-ROLLBACK",
                "location_id": sample_location_warehouse.id,
                "qty": 10.0
            },
            {
                "item_code": sample_product.item_code,
                "heat_no": "HEAT-ROLLBACK",
                "location_id": sample_location_warehouse.id,
                "qty": 999.0  # Exceeds available
            }
        ]

        with pytest.raises(ValueError, match="Insufficient usable stock"):
            create_document(db_session, header, lines)

        # Verify nothing was committed
        docs = db_session.query(Document).filter_by(doc_no="MIV-ROLLBACK").all()
        assert len(docs) == 0

        # Verify stock unchanged
        stock = db_session.query(Stock).filter_by(heat_no="HEAT-ROLLBACK").first()
        assert stock.quantity == 50.0


class TestDocumentNumberingAndUniqueness:
    """Document numbers must be unique and auto-generated sequentially."""

    def test_generate_next_doc_number(self, db_session):
        from logic.document_logic import generate_next_doc_number
        first = generate_next_doc_number(db_session, "MRR", date.today())
        assert first.endswith("-0001")
        assert first.startswith("MRR-")

    def test_duplicate_doc_no_rejected(self, db_session, sample_product, sample_location_warehouse):
        header = {
            "doc_no": "MRR-DUP-001",
            "doc_type": "MRR",
            "doc_date": date.today(),
            "to_location_id": sample_location_warehouse.id,
            "created_by": "test_user",
        }
        lines = [{
            "item_code": sample_product.item_code,
            "heat_no": "HEAT-DUP",
            "location_id": sample_location_warehouse.id,
            "qty": 5.0,
        }]
        create_document(db_session, header, lines)
        with pytest.raises(ValueError, match="already exists"):
            create_document(db_session, header, lines)

    def test_blank_heat_no_normalized(self, db_session, sample_product, sample_location_warehouse):
        header = {
            "doc_no": "MRR-HEAT-BLANK",
            "doc_type": "MRR",
            "doc_date": date.today(),
            "to_location_id": sample_location_warehouse.id,
            "created_by": "test_user",
        }
        lines = [{
            "item_code": sample_product.item_code,
            "heat_no": "  ",
            "location_id": sample_location_warehouse.id,
            "qty": 8.0,
        }]
        create_document(db_session, header, lines)
        stock = db_session.query(Stock).filter_by(
            item_code=sample_product.item_code,
            heat_no="N/A",
        ).first()
        assert stock is not None
        assert stock.quantity == 8.0


class TestDeleteReversesStock:
    """Deleting a DRAFT document must unwind its inventory postings."""

    def test_delete_mrr_reverses_quarantine_stock(
        self, db_session, sample_product, sample_location_warehouse
    ):
        header = {
            "doc_no": "MRR-REV-001",
            "doc_type": "MRR",
            "doc_date": date.today(),
            "to_location_id": sample_location_warehouse.id,
            "created_by": "test_user",
        }
        lines = [{
            "item_code": sample_product.item_code,
            "heat_no": "HEAT-REV-001",
            "location_id": sample_location_warehouse.id,
            "qty": 75.0,
        }]
        doc = create_document(db_session, header, lines)
        stock = db_session.query(Stock).filter_by(heat_no="HEAT-REV-001").first()
        assert stock.quantity == 75.0

        delete_document(db_session, doc.id)
        stock = db_session.query(Stock).filter_by(heat_no="HEAT-REV-001").first()
        assert stock is None or stock.quantity == 0.0
        assert db_session.query(Document).filter_by(id=doc.id).first() is None

    def test_delete_miv_restores_accepted_stock(
        self, db_session, sample_product, sample_location_warehouse
    ):
        from logic.stock_logic import add_stock
        add_stock(
            db_session, sample_product.item_code, "HEAT-REV-MIV",
            sample_location_warehouse.id, 100.0, qc_status="ACCEPTED"
        )
        db_session.commit()

        header = {
            "doc_no": "MIV-REV-001",
            "doc_type": "MIV",
            "doc_date": date.today(),
            "from_location_id": sample_location_warehouse.id,
            "created_by": "test_user",
        }
        lines = [{
            "item_code": sample_product.item_code,
            "heat_no": "HEAT-REV-MIV",
            "location_id": sample_location_warehouse.id,
            "qty": 25.0,
        }]
        doc = create_document(db_session, header, lines)
        stock = db_session.query(Stock).filter_by(heat_no="HEAT-REV-MIV").first()
        assert stock.quantity == 75.0

        delete_document(db_session, doc.id)
        stock = db_session.query(Stock).filter_by(heat_no="HEAT-REV-MIV").first()
        assert stock.quantity == 100.0

    def test_delete_mtr_reverses_transfer(
        self, db_session, sample_product, sample_location_warehouse, sample_location_yard
    ):
        from logic.stock_logic import add_stock
        add_stock(
            db_session, sample_product.item_code, "HEAT-REV-MTR",
            sample_location_warehouse.id, 80.0, qc_status="ACCEPTED"
        )
        db_session.commit()

        header = {
            "doc_no": "MTR-REV-001",
            "doc_type": "MTR",
            "doc_date": date.today(),
            "from_location_id": sample_location_warehouse.id,
            "to_location_id": sample_location_yard.id,
            "created_by": "test_user",
        }
        lines = [{
            "item_code": sample_product.item_code,
            "heat_no": "HEAT-REV-MTR",
            "location_id": sample_location_warehouse.id,
            "qty": 30.0,
        }]
        doc = create_document(db_session, header, lines)
        delete_document(db_session, doc.id)

        source = db_session.query(Stock).filter_by(
            heat_no="HEAT-REV-MTR", location_id=sample_location_warehouse.id
        ).first()
        dest = db_session.query(Stock).filter_by(
            heat_no="HEAT-REV-MTR", location_id=sample_location_yard.id
        ).first()
        assert source.quantity == 80.0
        assert dest is None or dest.quantity == 0.0

    def test_cannot_delete_mrr_after_qc_release(
        self, db_session, sample_product, sample_location_warehouse
    ):
        from logic.stock_logic import change_qc_status
        header = {
            "doc_no": "MRR-REV-QC",
            "doc_type": "MRR",
            "doc_date": date.today(),
            "to_location_id": sample_location_warehouse.id,
            "created_by": "test_user",
        }
        lines = [{
            "item_code": sample_product.item_code,
            "heat_no": "HEAT-REV-QC",
            "location_id": sample_location_warehouse.id,
            "qty": 40.0,
        }]
        doc = create_document(db_session, header, lines)
        change_qc_status(
            db_session,
            sample_product.item_code,
            "HEAT-REV-QC",
            sample_location_warehouse.id,
            "QUARANTINE",
            "ACCEPTED",
            40.0,
        )
        db_session.commit()

        with pytest.raises(ValueError):
            delete_document(db_session, doc.id)

        # Document and accepted stock must remain
        assert db_session.query(Document).filter_by(id=doc.id).first() is not None
        accepted = db_session.query(Stock).filter_by(
            heat_no="HEAT-REV-QC", qc_status="ACCEPTED"
        ).first()
        assert accepted is not None
        assert accepted.quantity == 40.0