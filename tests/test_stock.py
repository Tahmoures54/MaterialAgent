# tests/test_stock.py
"""
Comprehensive tests for stock management logic.
Tests: add_stock, remove_stock, move_stock, change_qc_status, and edge cases.
"""

import pytest
from datetime import date, timedelta
from logic.stock_logic import (
    add_stock, remove_stock, move_stock, change_qc_status,
    get_stock_record, get_stock_by_item, get_stock_by_location,
    get_stock_summary, allocate_stock, deallocate_stock
)
from db.models import Stock


class TestAddStock:
    """Test adding stock to inventory."""

    def test_add_new_stock_quarantine(self, db_session, sample_product, sample_location_warehouse):
        """Test receiving new material into quarantine."""
        stock = add_stock(
            db=db_session,
            item_code=sample_product.item_code,
            heat_no="HEAT-NEW-001",
            location_id=sample_location_warehouse.id,
            qty=100.0,
            qc_status="QUARANTINE"
        )
        db_session.commit()

        assert stock.quantity == 100.0
        assert stock.qc_status == "QUARANTINE"
        assert stock.heat_no == "HEAT-NEW-001"
        assert stock.location_id == sample_location_warehouse.id
        assert stock.allocated_qty == 0.0
        assert stock.available_qty == 100.0

    def test_add_stock_with_details(self, db_session, sample_product, sample_location_warehouse):
        """Test receiving material with full details."""
        expiry = date.today() + timedelta(days=365)
        stock = add_stock(
            db=db_session,
            item_code=sample_product.item_code,
            heat_no="HEAT-DETAIL-001",
            location_id=sample_location_warehouse.id,
            qty=50.0,
            qc_status="QUARANTINE",
            tag_no="TAG-DETAIL-001",
            serial_no="SN-DETAIL-001",
            batch_no="BATCH-DETAIL-A",
            expiry_date=expiry
        )
        db_session.commit()

        assert stock.tag_no == "TAG-DETAIL-001"
        assert stock.serial_no == "SN-DETAIL-001"
        assert stock.batch_no == "BATCH-DETAIL-A"
        assert stock.expiry_date == expiry

    def test_add_stock_preservation_required(self, db_session, sample_product, sample_location_warehouse):
        """Test that preservation due date is set for products requiring it."""
        stock = add_stock(
            db=db_session,
            item_code=sample_product.item_code,
            heat_no="HEAT-PRES-001",
            location_id=sample_location_warehouse.id,
            qty=50.0,
            qc_status="QUARANTINE"
        )
        db_session.commit()

        assert stock.next_preservation_due is not None
        expected_due = date.today() + timedelta(days=sample_product.preservation_interval_days)
        assert stock.next_preservation_due == expected_due
        assert stock.preservation_status == "DUE"

    def test_add_existing_stock_same_status(self, db_session, sample_stock_quarantine):
        """Test adding to existing stock with same QC status."""
        stock = add_stock(
            db=db_session,
            item_code=sample_stock_quarantine.item_code,
            heat_no=sample_stock_quarantine.heat_no,
            location_id=sample_stock_quarantine.location_id,
            qty=30.0,
            qc_status="QUARANTINE"
        )
        db_session.commit()

        assert stock.id == sample_stock_quarantine.id  # Same record
        assert stock.quantity == 130.0  # 100 + 30

    def test_add_stock_different_qc_status(self, db_session, sample_stock_quarantine):
        """Test adding stock with different QC status creates new record."""
        stock = add_stock(
            db=db_session,
            item_code=sample_stock_quarantine.item_code,
            heat_no=sample_stock_quarantine.heat_no,
            location_id=sample_stock_quarantine.location_id,
            qty=50.0,
            qc_status="ACCEPTED"
        )
        db_session.commit()

        assert stock.id != sample_stock_quarantine.id  # Different record
        assert stock.quantity == 50.0
        assert stock.qc_status == "ACCEPTED"


class TestRemoveStock:
    """Test removing stock from inventory."""

    def test_remove_stock_success(self, db_session, sample_stock_accepted):
        """Test successful material issue."""
        stock = remove_stock(
            db=db_session,
            item_code=sample_stock_accepted.item_code,
            heat_no=sample_stock_accepted.heat_no,
            location_id=sample_stock_accepted.location_id,
            qty=40.0,
            qc_status="ACCEPTED"
        )
        db_session.commit()

        assert stock.quantity == 160.0  # 200 - 40
        assert stock.available_qty == 110.0  # 150 - 40

    def test_remove_stock_insufficient_available(self, db_session, sample_stock_accepted):
        """Test prevention of issuing more than available (accounting for allocations)."""
        # Available: 200 - 50 = 150, try to remove 160
        with pytest.raises(ValueError, match="Insufficient usable stock"):
            remove_stock(
                db=db_session,
                item_code=sample_stock_accepted.item_code,
                heat_no=sample_stock_accepted.heat_no,
                location_id=sample_stock_accepted.location_id,
                qty=160.0,
                qc_status="ACCEPTED"
            )

    def test_remove_stock_insufficient_total(self, db_session, sample_stock_accepted):
        """Test prevention of issuing more than total quantity."""
        with pytest.raises(ValueError, match="Insufficient usable stock"):
            remove_stock(
                db=db_session,
                item_code=sample_stock_accepted.item_code,
                heat_no=sample_stock_accepted.heat_no,
                location_id=sample_stock_accepted.location_id,
                qty=250.0,
                qc_status="ACCEPTED"
            )

    def test_remove_stock_not_found(self, db_session, sample_location_warehouse):
        """Test error when stock record doesn't exist."""
        with pytest.raises(ValueError, match="No stock found"):
            remove_stock(
                db=db_session,
                item_code="NONEXISTENT",
                heat_no="HEAT-000",
                location_id=sample_location_warehouse.id,
                qty=10.0,
                qc_status="ACCEPTED"
            )

    def test_remove_stock_wrong_qc_status(self, db_session, sample_stock_quarantine):
        """Test error when trying to issue from quarantine (should be ACCEPTED)."""
        with pytest.raises(ValueError, match="No stock found"):
            remove_stock(
                db=db_session,
                item_code=sample_stock_quarantine.item_code,
                heat_no=sample_stock_quarantine.heat_no,
                location_id=sample_stock_quarantine.location_id,
                qty=10.0,
                qc_status="ACCEPTED"  # Stock is in QUARANTINE
            )

    def test_remove_stock_exact_quantity(self, db_session, sample_stock_accepted):
        """Test removing exactly available quantity."""
        available = sample_stock_accepted.available_qty  # 150
        stock = remove_stock(
            db=db_session,
            item_code=sample_stock_accepted.item_code,
            heat_no=sample_stock_accepted.heat_no,
            location_id=sample_stock_accepted.location_id,
            qty=available,
            qc_status="ACCEPTED"
        )
        db_session.commit()

        assert stock.quantity == 200.0 - available
        assert stock.available_qty == 0.0


class TestMoveStock:
    """Test moving stock between locations."""

    def test_move_stock_success(self, db_session, sample_stock_accepted, sample_location_yard):
        """Test successful stock transfer."""
        source_stock, dest_stock = move_stock(
            db=db_session,
            item_code=sample_stock_accepted.item_code,
            heat_no=sample_stock_accepted.heat_no,
            from_location_id=sample_stock_accepted.location_id,
            to_location_id=sample_location_yard.id,
            qty=50.0,
            qc_status="ACCEPTED"
        )
        db_session.commit()

        assert source_stock.quantity == 150.0  # 200 - 50
        assert dest_stock.quantity == 50.0
        assert dest_stock.location_id == sample_location_yard.id
        assert dest_stock.tag_no == sample_stock_accepted.tag_no  # Preserved

    def test_move_stock_same_location(self, db_session, sample_stock_accepted):
        """Test error when source and destination are the same."""
        with pytest.raises(ValueError, match="Source and destination locations must be different"):
            move_stock(
                db=db_session,
                item_code=sample_stock_accepted.item_code,
                heat_no=sample_stock_accepted.heat_no,
                from_location_id=sample_stock_accepted.location_id,
                to_location_id=sample_stock_accepted.location_id,
                qty=10.0,
                qc_status="ACCEPTED"
            )

    def test_move_stock_insufficient(self, db_session, sample_stock_accepted, sample_location_yard):
        """Test error when trying to move more than available."""
        with pytest.raises(ValueError, match="Insufficient usable stock"):
            move_stock(
                db=db_session,
                item_code=sample_stock_accepted.item_code,
                heat_no=sample_stock_accepted.heat_no,
                from_location_id=sample_stock_accepted.location_id,
                to_location_id=sample_location_yard.id,
                qty=999.0,
                qc_status="ACCEPTED"
            )


class TestChangeQCStatus:
    """Test QC status changes."""

    def test_change_quarantine_to_accepted(self, db_session, sample_stock_quarantine):
        """Test QC release from quarantine to accepted."""
        old_stock, new_stock = change_qc_status(
            db=db_session,
            item_code=sample_stock_quarantine.item_code,
            heat_no=sample_stock_quarantine.heat_no,
            location_id=sample_stock_quarantine.location_id,
            old_status="QUARANTINE",
            new_status="ACCEPTED",
            qty=40.0
        )

        assert old_stock.quantity == 60.0  # 100 - 40
        assert old_stock.qc_status == "QUARANTINE"
        assert new_stock.quantity == 40.0
        assert new_stock.qc_status == "ACCEPTED"

    def test_change_quarantine_to_rejected(self, db_session, sample_stock_quarantine):
        """Test QC rejection."""
        old_stock, new_stock = change_qc_status(
            db=db_session,
            item_code=sample_stock_quarantine.item_code,
            heat_no=sample_stock_quarantine.heat_no,
            location_id=sample_stock_quarantine.location_id,
            old_status="QUARANTINE",
            new_status="REJECTED",
            qty=20.0
        )

        assert old_stock.quantity == 80.0  # 100 - 20
        assert new_stock.quantity == 20.0
        assert new_stock.qc_status == "REJECTED"

    def test_change_same_status(self, db_session, sample_stock_quarantine):
        """Test error when old and new status are the same."""
        with pytest.raises(ValueError, match="Old and new status must be different"):
            change_qc_status(
                db=db_session,
                item_code=sample_stock_quarantine.item_code,
                heat_no=sample_stock_quarantine.heat_no,
                location_id=sample_stock_quarantine.location_id,
                old_status="QUARANTINE",
                new_status="QUARANTINE",
                qty=10.0
            )

    def test_change_entire_quantity(self, db_session, sample_stock_quarantine):
        """Test changing QC status for entire stock quantity."""
        old_stock, new_stock = change_qc_status(
            db=db_session,
            item_code=sample_stock_quarantine.item_code,
            heat_no=sample_stock_quarantine.heat_no,
            location_id=sample_stock_quarantine.location_id,
            old_status="QUARANTINE",
            new_status="ACCEPTED",
            qty=100.0
        )

        assert old_stock.quantity == 0.0
        assert new_stock.quantity == 100.0


class TestStockQueries:
    """Test stock query functions."""

    def test_get_stock_record_exists(self, db_session, sample_stock_quarantine):
        """Test finding an existing stock record."""
        stock = get_stock_record(
            db=db_session,
            item_code=sample_stock_quarantine.item_code,
            heat_no=sample_stock_quarantine.heat_no,
            location_id=sample_stock_quarantine.location_id,
            qc_status="QUARANTINE"
        )
        assert stock is not None
        assert stock.id == sample_stock_quarantine.id

    def test_get_stock_record_not_found(self, db_session, sample_location_warehouse):
        """Test non-existent stock record returns None."""
        stock = get_stock_record(
            db=db_session,
            item_code="NONEXISTENT",
            heat_no="HEAT-000",
            location_id=sample_location_warehouse.id,
            qc_status="QUARANTINE"
        )
        assert stock is None

    def test_get_stock_by_item(self, db_session, sample_stock_quarantine, sample_stock_accepted):
        """Test getting all stock for an item."""
        stocks = get_stock_by_item(
            db=db_session,
            item_code=sample_stock_quarantine.item_code
        )
        assert len(stocks) >= 2

    def test_get_stock_by_location(self, db_session, sample_stock_quarantine, sample_location_warehouse):
        """Test getting all stock at a location."""
        stocks = get_stock_by_location(
            db=db_session,
            location_id=sample_location_warehouse.id
        )
        assert len(stocks) >= 1

    def test_get_stock_summary(self, db_session, sample_stock_quarantine, 
                                sample_stock_accepted, sample_stock_rejected):
        """Test inventory summary statistics."""
        summary = get_stock_summary(db_session)
        
        assert summary["total_items"] >= 1
        assert summary["total_quantity"] == 310.0  # 100 + 200 + 10
        assert summary["total_allocated"] == 50.0  # from accepted stock
        assert summary["total_available"] == 260.0  # 310 - 50
        assert summary["qc_summary"]["QUARANTINE"] == 100.0
        assert summary["qc_summary"]["ACCEPTED"] == 200.0
        assert summary["qc_summary"]["REJECTED"] == 10.0


class TestStockEdgeCases:
    """Test stock edge cases and boundary conditions."""

    def test_add_zero_quantity(self, db_session, sample_product, sample_location_warehouse):
        """Test adding zero quantity is rejected."""
        with pytest.raises(ValueError, match="greater than zero"):
            add_stock(
                db=db_session,
                item_code=sample_product.item_code,
                heat_no="HEAT-ZERO",
                location_id=sample_location_warehouse.id,
                qty=0.0
            )

    def test_remove_zero_quantity(self, db_session, sample_stock_accepted):
        """Test removing zero quantity is rejected."""
        with pytest.raises(ValueError, match="greater than zero"):
            remove_stock(
                db=db_session,
                item_code=sample_stock_accepted.item_code,
                heat_no=sample_stock_accepted.heat_no,
                location_id=sample_stock_accepted.location_id,
                qty=0.0,
                qc_status="ACCEPTED"
            )

    def test_add_negative_quantity(self, db_session, sample_product, sample_location_warehouse):
        """Test that negative quantity is rejected at the logic layer."""
        with pytest.raises(ValueError, match="greater than zero"):
            add_stock(
                db=db_session,
                item_code=sample_product.item_code,
                heat_no="HEAT-NEG",
                location_id=sample_location_warehouse.id,
                qty=-10.0
            )

    def test_stock_available_property(self, db_session, sample_stock_accepted):
        """Test the available_qty hybrid property."""
        assert sample_stock_accepted.available_qty == 150.0  # 200 - 50

    def test_stock_is_expired(self, db_session, sample_product, sample_location_warehouse):
        """Test expiry detection."""
        # Expired stock
        expired_stock = Stock(
            item_code=sample_product.item_code,
            heat_no="HEAT-EXPIRED",
            location_id=sample_location_warehouse.id,
            qc_status="ACCEPTED",
            quantity=10.0,
            received_date=date.today() - timedelta(days=400),
            expiry_date=date.today() - timedelta(days=1)
        )
        db_session.add(expired_stock)
        db_session.commit()

        assert expired_stock.is_expired is True
        assert expired_stock.days_to_expiry < 0

    def test_stock_not_expired(self, db_session, sample_stock_accepted):
        """Test non-expired stock."""
        assert sample_stock_accepted.is_expired is False
        assert sample_stock_accepted.days_to_expiry > 0

    def test_preservation_overdue(self, db_session, sample_product, sample_location_warehouse):
        """Test preservation overdue detection."""
        overdue_stock = Stock(
            item_code=sample_product.item_code,
            heat_no="HEAT-OVERDUE",
            location_id=sample_location_warehouse.id,
            qc_status="ACCEPTED",
            quantity=10.0,
            received_date=date.today() - timedelta(days=400),
            next_preservation_due=date.today() - timedelta(days=1),
            preservation_status="DUE"
        )
        db_session.add(overdue_stock)
        db_session.commit()

        assert overdue_stock.preservation_overdue is True

    def test_unique_constraint(self, db_session, sample_stock_quarantine):
        """Test that duplicate stock record raises integrity error."""
        from sqlalchemy.exc import IntegrityError
        
        duplicate = Stock(
            item_code=sample_stock_quarantine.item_code,
            heat_no=sample_stock_quarantine.heat_no,
            location_id=sample_stock_quarantine.location_id,
            qc_status=sample_stock_quarantine.qc_status,
            quantity=50.0,
            received_date=date.today()
        )
        db_session.add(duplicate)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestStockAllocation:
    """Test stock reservation / allocation."""

    def test_allocate_and_deallocate(self, db_session, sample_stock_accepted):
        original_alloc = sample_stock_accepted.allocated_qty
        stock = allocate_stock(
            db_session,
            sample_stock_accepted.item_code,
            sample_stock_accepted.heat_no,
            sample_stock_accepted.location_id,
            20.0,
        )
        assert stock.allocated_qty == original_alloc + 20.0
        assert stock.available_qty == sample_stock_accepted.quantity - stock.allocated_qty

        stock = deallocate_stock(
            db_session,
            sample_stock_accepted.item_code,
            sample_stock_accepted.heat_no,
            sample_stock_accepted.location_id,
            20.0,
        )
        assert stock.allocated_qty == original_alloc

    def test_allocate_more_than_available(self, db_session, sample_stock_accepted):
        with pytest.raises(ValueError, match="Insufficient available stock"):
            allocate_stock(
                db_session,
                sample_stock_accepted.item_code,
                sample_stock_accepted.heat_no,
                sample_stock_accepted.location_id,
                999.0,
            )

    def test_invalid_qc_status(self, db_session, sample_product, sample_location_warehouse):
        with pytest.raises(ValueError, match="Invalid QC status"):
            add_stock(
                db_session,
                sample_product.item_code,
                "HEAT-BAD-QC",
                sample_location_warehouse.id,
                10.0,
                qc_status="MAYBE",
            )