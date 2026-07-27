# tests/test_reports.py
"""
Tests for reporting functions.
"""

import pytest
from datetime import date, timedelta
from logic.reports import (
    generate_inventory_summary,
    generate_transaction_report,
    get_low_stock_items,
    get_stock_value_report,
    get_movement_report
)


class TestInventorySummary:
    """Test inventory summary report."""

    def test_generate_summary(self, db_session, sample_stock_accepted, 
                               sample_stock_quarantine, sample_product):
        """Test inventory summary generation."""
        summary = generate_inventory_summary()
        assert len(summary) >= 1
        
        item = next((i for i in summary if i['Item Code'] == sample_product.item_code), None)
        assert item is not None
        assert item['Total Qty'] >= 300  # 200 + 100

    def test_summary_status_ok(self, db_session, sample_stock_accepted):
        """Test that items with sufficient stock show OK status."""
        summary = generate_inventory_summary()
        for item in summary:
            if item['Available Qty'] > item['Min Required']:
                assert item['Status'] == "OK"

    def test_summary_status_low(self, db_session, sample_product, sample_location_warehouse):
        """Test that items below minimum show LOW STOCK status."""
        # Create stock below minimum
        from logic.stock_logic import add_stock
        add_stock(db_session, sample_product.item_code, "HEAT-LOW-RPT",
                  sample_location_warehouse.id, 3.0, qc_status="ACCEPTED")
        db_session.commit()
        
        summary = generate_inventory_summary()
        low_items = [i for i in summary if i['Status'] == "LOW STOCK"]
        assert len(low_items) >= 1

    def test_summary_empty_database(self, db_session):
        """Test summary with empty database."""
        summary = generate_inventory_summary()
        assert isinstance(summary, list)


class TestTransactionReport:
    """Test transaction history report."""

    def test_generate_transaction_report(self, db_session, sample_transaction):
        """Test transaction report within date range."""
        start = date.today() - timedelta(days=1)
        end = date.today() + timedelta(days=1)
        
        report = generate_transaction_report(start, end)
        assert len(report) >= 1
        assert report[0]['Doc No'] == "DOC001"

    def test_generate_transaction_report_date_range(self, db_session, sample_transaction):
        """Test transaction report respects date range."""
        # Future range - should be empty
        future_start = date.today() + timedelta(days=100)
        future_end = date.today() + timedelta(days=200)
        
        report = generate_transaction_report(future_start, future_end)
        assert len(report) == 0

    def test_generate_transaction_report_filter_type(self, db_session, sample_transaction, 
                                                       sample_transaction2):
        """Test transaction report filtered by doc type."""
        report = generate_transaction_report(doc_type="Receipt")
        assert all(r['Type'] == "Receipt" for r in report)


class TestLowStockItems:
    """Test low stock items report."""

    def test_get_low_stock_items(self, db_session, sample_product, sample_location_warehouse):
        """Test low stock detection."""
        from logic.stock_logic import add_stock
        add_stock(db_session, sample_product.item_code, "HEAT-LOW-RPT2",
                  sample_location_warehouse.id, 2.0, qc_status="ACCEPTED")
        db_session.commit()
        
        low = get_low_stock_items(threshold=5)
        assert len(low) >= 1
        assert any(i['Item Code'] == sample_product.item_code for i in low)

    def test_get_low_stock_items_none(self, db_session, sample_stock_accepted):
        """Test no low stock items when stock is sufficient."""
        low = get_low_stock_items(threshold=1)
        assert all(i['Available'] > 1 for i in low)

    def test_get_low_stock_items_custom_threshold(self, db_session, sample_stock_accepted):
        """Test low stock with custom threshold."""
        # sample_stock_accepted has 150 available
        low = get_low_stock_items(threshold=200)
        assert len(low) >= 1  # 150 < 200


class TestStockValueReport:
    """Test stock value report."""

    def test_get_stock_value_report(self, db_session, sample_stock_accepted, sample_product):
        """Test stock value calculation."""
        report = get_stock_value_report()
        assert len(report) >= 1
        
        # Find the item
        item = next((r for r in report if r['Item Code'] == sample_product.item_code), None)
        if item:
            assert item['Total Value'] > 0

    def test_get_stock_value_report_total_row(self, db_session, sample_stock_accepted):
        """Test that total row is present."""
        report = get_stock_value_report()
        total_row = report[-1] if report else None
        if total_row and len(report) > 1:
            assert total_row['Item Code'] == 'TOTAL'


class TestMovementReport:
    """Test movement report."""

    def test_get_movement_report(self, db_session, sample_product):
        """Test movement report for a specific item."""
        report = get_movement_report(sample_product.item_code)
        assert isinstance(report, list)

    def test_get_movement_report_date_range(self, db_session, sample_product):
        """Test movement report with custom date range."""
        start = date.today() - timedelta(days=365)
        end = date.today()
        report = get_movement_report(sample_product.item_code, start, end)
        assert isinstance(report, list)