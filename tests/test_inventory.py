# tests/test_inventory.py
"""
Tests for inventory search and filtering logic.
Tests the search_inventory function with various filter combinations.
"""

import pytest
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from logic.inventory import (
    search_inventory, get_filter_options, 
    get_inventory_by_item, get_all_inventory
)


class TestSearchInventory:
    """Test inventory search functionality."""

    def test_search_all(self, db_session, sample_stock_accepted, sample_stock_quarantine):
        """Test searching without filters returns all stock."""
        results = search_inventory(db=db_session)
        assert len(results) >= 2

    def test_search_by_text_item_code(self, db_session, sample_stock_accepted):
        """Test search by item code."""
        results = search_inventory(search_text="PIPE-6-CS", db=db_session)
        assert len(results) >= 1
        assert results[0]["Item Code"] == "PIPE-6-CS"

    def test_search_by_text_description(self, db_session, sample_stock_accepted):
        """Test search by description text."""
        results = search_inventory(search_text="Carbon Steel", db=db_session)
        assert len(results) >= 1
        assert "Carbon Steel" in results[0]["Description"]

    def test_search_by_text_heat_no(self, db_session, sample_stock_accepted):
        """Test search by heat number."""
        results = search_inventory(search_text="HEAT-2024-002", db=db_session)
        assert len(results) >= 1
        assert results[0]["Heat No"] == "HEAT-2024-002"

    def test_search_by_qc_status(self, db_session, sample_stock_quarantine, 
                                  sample_stock_accepted):
        """Test filter by QC status."""
        results = search_inventory(qc_status="QUARANTINE", db=db_session)
        assert all(r["QC Status"] == "QUARANTINE" for r in results)

        results = search_inventory(qc_status="ACCEPTED", db=db_session)
        assert all(r["QC Status"] == "ACCEPTED" for r in results)

    def test_search_by_discipline(self, db_session, sample_stock_accepted, 
                                   sample_stock_accepted_flange):
        """Test filter by discipline."""
        results = search_inventory(discipline="Piping", db=db_session)
        assert all(r["Discipline"] == "Piping" for r in results)
        assert len(results) >= 2  # Both pipe and flange

    def test_search_by_location(self, db_session, sample_stock_accepted, 
                                 sample_stock_accepted_flange):
        """Test filter by location code."""
        results = search_inventory(location_code="WH-A", db=db_session)
        assert len(results) >= 1
        assert all("WH-A" in r["Location Code"] for r in results)

    def test_search_low_stock(self, db_session, sample_product, sample_location_warehouse):
        """Test low stock filter."""
        # Create stock below minimum
        from logic.stock_logic import add_stock
        add_stock(db_session, sample_product.item_code, "HEAT-LOW",
                  sample_location_warehouse.id, 3.0, qc_status="ACCEPTED")
        db_session.commit()

        results = search_inventory(low_stock_only=True, db=db_session)
        assert len(results) >= 1
        assert results[0]["Available Qty"] < results[0]["Min Required Qty"]

    def test_search_expired(self, db_session, sample_product, sample_location_warehouse):
        """Test expired items filter."""
        # Create expired stock
        from logic.stock_logic import add_stock
        add_stock(db_session, sample_product.item_code, "HEAT-EXP",
                  sample_location_warehouse.id, 10.0, qc_status="ACCEPTED",
                  expiry_date=date.today() - timedelta(days=1))
        db_session.commit()

        results = search_inventory(expired_only=True, db=db_session)
        assert len(results) >= 1
        assert results[0]["Days to Expiry"] < 0

    def test_search_combined_filters(self, db_session, sample_stock_accepted):
        """Test combining multiple filters."""
        results = search_inventory(
            search_text="PIPE",
            qc_status="ACCEPTED",
            discipline="Piping",
            db=db_session,
        )
        assert len(results) >= 1
        for r in results:
            assert "PIPE" in r["Item Code"]
            assert r["QC Status"] == "ACCEPTED"
            assert r["Discipline"] == "Piping"

    def test_search_no_results(self, db_session):
        """Test search returns empty list when no matches."""
        results = search_inventory(search_text="NONEXISTENT_ITEM_XYZ", db=db_session)
        assert len(results) == 0

    def test_search_pagination(self, db_session, sample_stock_quarantine, 
                                sample_stock_accepted, sample_stock_rejected):
        """Test pagination with limit and offset."""
        # Test limit
        results = search_inventory(limit=1, db=db_session)
        assert len(results) <= 1

        # Test offset
        all_results = search_inventory(db=db_session)
        if len(all_results) >= 2:
            results_offset = search_inventory(limit=1, offset=1, db=db_session)
            assert results_offset[0]["Heat No"] != all_results[0]["Heat No"]

    def test_search_result_fields(self, db_session, sample_stock_accepted):
        """Test that all expected fields are present in results."""
        results = search_inventory(search_text="HEAT-2024-002", db=db_session)
        assert len(results) >= 1
        
        result = results[0]
        expected_fields = [
            "Item Code", "Description", "Discipline", "Material Class",
            "Category", "UOM", "Min Required Qty", "Heat No", "Tag No",
            "Location Code", "QC Status", "Total Qty", "Allocated Qty",
            "Available Qty", "Expiry Date", "Preservation Due"
        ]
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"


class TestFilterOptions:
    """Test filter options retrieval."""

    def test_get_filter_options(self, db_session, sample_stock_quarantine, 
                                 sample_stock_accepted, sample_product):
        """Test getting filter options for dropdowns."""
        options = get_filter_options(db=db_session)
        
        assert "qc_statuses" in options
        assert "disciplines" in options
        assert "locations" in options
        assert "categories" in options
        assert "material_classes" in options
        
        assert "QUARANTINE" in options["qc_statuses"]
        assert "ACCEPTED" in options["qc_statuses"]
        assert "Piping" in options["disciplines"]
        assert "Pipe" in options["categories"]
        assert "Carbon Steel" in options["material_classes"]

    def test_get_filter_options_empty_db(self, db_session):
        """Test filter options with empty database."""
        options = get_filter_options(db=db_session)
        assert options["qc_statuses"] == []
        assert options["disciplines"] == []


class TestInventoryByItem:
    """Test get_inventory_by_item function."""

    def test_get_inventory_by_item(self, db_session, sample_stock_quarantine, 
                                    sample_stock_accepted):
        """Test getting all stock for a specific item."""
        results = get_inventory_by_item(sample_stock_quarantine.item_code, db=db_session)
        assert len(results) >= 2

    def test_get_inventory_by_item_not_found(self, db_session):
        """Test getting inventory for non-existent item."""
        results = get_inventory_by_item("NONEXISTENT", db=db_session)
        assert len(results) == 0