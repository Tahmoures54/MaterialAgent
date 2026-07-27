# tests/test_utils.py
"""
Tests for utility modules: password manager, calculations, license, exports.
"""

import pytest
import os
import tempfile
from datetime import date, datetime, timedelta

from utils.password_manager import hash_password, verify_password
from utils.calculations import (
    calculate_eoq, calculate_reorder_point, 
    calculate_inventory_turnover, abc_classification,
    calculate_safety_stock
)
from utils.excel_export import export_to_excel
from utils.pdf_export import export_to_pdf


class TestPasswordManager:
    """Test password hashing and verification."""

    def test_hash_password_returns_string(self):
        """Test that hash_password returns a string."""
        result = hash_password("mypassword")
        assert isinstance(result, str)
        assert ":" in result  # Format: salt:hash

    def test_hash_password_different_each_time(self):
        """Test that each hash is unique (different salt)."""
        hash1 = hash_password("password")
        hash2 = hash_password("password")
        assert hash1 != hash2  # Different salts

    def test_verify_correct_password(self):
        """Test that correct password verifies successfully."""
        stored = hash_password("secure_password")
        assert verify_password(stored, "secure_password") is True

    def test_verify_wrong_password(self):
        """Test that wrong password fails verification."""
        stored = hash_password("correct_password")
        assert verify_password(stored, "wrong_password") is False

    def test_verify_empty_password(self):
        """Test verification with empty password."""
        stored = hash_password("somepass")
        assert verify_password(stored, "") is False

    def test_verify_corrupted_hash(self):
        """Test verification with corrupted hash string."""
        assert verify_password("corrupted", "anything") is False
        assert verify_password("", "anything") is False
        assert verify_password("no_colon_here", "test") is False

    def test_hash_and_verify_special_characters(self):
        """Test with special characters in password."""
        password = "p@$$w0rd!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        stored = hash_password(password)
        assert verify_password(stored, password) is True

    def test_hash_and_verify_unicode(self):
        """Test with unicode characters."""
        password = "پسورد فارسی 🔐"
        stored = hash_password(password)
        assert verify_password(stored, password) is True


class TestCalculations:
    """Test inventory calculation functions."""

    def test_calculate_eoq(self):
        """Test EOQ calculation."""
        eoq = calculate_eoq(annual_demand=1000, ordering_cost=50, holding_cost_per_unit=2)
        assert round(eoq, 1) == 223.6

    def test_calculate_eoq_zero_holding_cost(self):
        """Test EOQ with zero holding cost."""
        eoq = calculate_eoq(1000, 50, 0)
        assert eoq == float('inf')

    def test_calculate_eoq_zero_demand(self):
        """Test EOQ with zero demand."""
        eoq = calculate_eoq(0, 50, 2)
        assert eoq == 0.0

    def test_calculate_reorder_point(self):
        """Test reorder point calculation."""
        rop = calculate_reorder_point(
            lead_time_days=5,
            avg_daily_demand=20,
            safety_stock=10
        )
        assert rop == 110

    def test_calculate_reorder_point_no_safety(self):
        """Test reorder point without safety stock."""
        rop = calculate_reorder_point(5, 20)
        assert rop == 100

    def test_calculate_inventory_turnover(self):
        """Test inventory turnover ratio."""
        turnover = calculate_inventory_turnover(
            cogs=50000,
            average_inventory=10000
        )
        assert turnover == 5.0

    def test_calculate_inventory_turnover_zero_inventory(self):
        """Test turnover with zero inventory."""
        turnover = calculate_inventory_turnover(50000, 0)
        assert turnover == 0

    def test_abc_classification(self):
        """Test ABC classification."""
        items = [("A", 5000), ("B", 3000), ("C", 1500), ("D", 500)]
        classes = abc_classification(items)
        
        assert classes["A"] == 'A'
        assert classes["B"] == 'B'
        assert classes["C"] == 'C'
        assert classes["D"] == 'C'

    def test_abc_classification_empty(self):
        """Test ABC with empty list."""
        assert abc_classification([]) == {}

    def test_calculate_safety_stock(self):
        """Test safety stock calculation."""
        ss = calculate_safety_stock(
            z_score=1.96,
            lead_time_std=2,
            avg_demand_std=5,
            avg_lead_time=7
        )
        # 1.96 * (2 * 5 + 7 * 5) = 1.96 * (10 + 35) = 1.96 * 45 = 88.2
        assert ss == 88.2


class TestExcelExport:
    """Test Excel export functionality."""

    def test_export_to_excel_basic(self):
        """Test basic Excel export."""
        data = [
            {"Name": "Test Item 1", "Qty": 10, "Price": 25.5},
            {"Name": "Test Item 2", "Qty": 20, "Price": 30.0}
        ]
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name
        
        try:
            result = export_to_excel(data, ["Name", "Qty", "Price"], path)
            assert os.path.exists(result)
            assert os.path.getsize(result) > 0
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_export_to_excel_empty_data(self):
        """Test export with empty data."""
        data = []
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name
        
        try:
            result = export_to_excel(data, ["Name", "Qty"], path)
            assert os.path.exists(result)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_export_to_excel_custom_sheet_name(self):
        """Test export with custom sheet name."""
        data = [{"Item": "A", "Value": 100}]
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name
        
        try:
            result = export_to_excel(data, ["Item", "Value"], path, sheet_name="CustomReport")
            assert os.path.exists(result)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_export_to_excel_missing_columns(self):
        """Test export with columns not in data."""
        data = [{"Name": "Test", "Qty": 10}]
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name
        
        try:
            # "Price" column doesn't exist in data
            result = export_to_excel(data, ["Name", "Qty", "Price"], path)
            assert os.path.exists(result)
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestPDFExport:
    """Test PDF export functionality."""

    def test_export_to_pdf_basic(self):
        """Test basic PDF export."""
        data = [
            {"Item": "Product A", "Quantity": 100, "Value": 5000},
            {"Item": "Product B", "Quantity": 200, "Value": 8000}
        ]
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            path = tmp.name
        
        try:
            result = export_to_pdf(data, ["Item", "Quantity", "Value"], path, title="Test Report")
            assert os.path.exists(result)
            assert os.path.getsize(result) > 0
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_export_to_pdf_empty_data(self):
        """Test PDF export with empty data."""
        data = []
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            path = tmp.name
        
        try:
            result = export_to_pdf(data, ["Item", "Value"], path)
            assert os.path.exists(result)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_export_to_pdf_custom_title(self):
        """Test PDF export with custom title."""
        data = [{"Name": "Test", "Count": 1}]
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            path = tmp.name
        
        try:
            result = export_to_pdf(data, ["Name", "Count"], path, title="Custom Inventory Report")
            assert os.path.exists(result)
        finally:
            if os.path.exists(path):
                os.unlink(path)