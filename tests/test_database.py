# tests/test_database.py
"""
Tests for database models, relationships, and basic CRUD operations.
"""

import pytest
from datetime import date, datetime, timedelta
from db.models import (
    Product, Transaction, InventorySummary, User,
    Location, Stock, Document, DocumentLine,
    ProjectInfo, MaterialRequest, MaterialRequestLine
)


class TestProductModel:
    """Test Product model operations."""

    def test_create_product(self, db_session):
        """Test basic product creation."""
        product = Product(
            item_code="TEST-001",
            description="Test Product",
            unit_of_measure="EA"
        )
        db_session.add(product)
        db_session.commit()

        retrieved = db_session.query(Product).filter_by(item_code="TEST-001").first()
        assert retrieved is not None
        assert retrieved.description == "Test Product"
        assert retrieved.unit_of_measure == "EA"

    def test_unique_item_code(self, db_session, sample_product):
        """Test that duplicate item codes raise IntegrityError."""
        from sqlalchemy.exc import IntegrityError
        
        duplicate = Product(
            item_code=sample_product.item_code,  # Same code
            description="Duplicate"
        )
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_product_relationships(self, db_session, sample_product, sample_stock_accepted):
        """Test product-stock relationship."""
        assert len(sample_product.stocks) >= 1
        assert sample_product.stocks[0].heat_no == sample_stock_accepted.heat_no

    def test_product_total_stock(self, db_session, sample_product, 
                                  sample_stock_quarantine, sample_stock_accepted):
        """Test total_stock hybrid property."""
        # 100 (quarantine) + 200 (accepted) = 300
        assert sample_product.total_stock == 300.0

    def test_product_available_stock(self, db_session, sample_product,
                                      sample_stock_quarantine, sample_stock_accepted):
        """Test available_stock hybrid property (only accepted)."""
        assert sample_product.available_stock == 150.0  # 200 - 50

    def test_product_lifecycle_default(self, db_session):
        """Test default lifecycle status."""
        product = Product(item_code="TEST-LC", description="Test Lifecycle")
        db_session.add(product)
        db_session.commit()
        assert product.lifecycle_status == "ACTIVE"


class TestLocationModel:
    """Test Location model and hierarchy."""

    def test_create_location(self, db_session):
        """Test basic location creation."""
        loc = Location(
            code="WH-TEST",
            name="Test Warehouse",
            location_type="WAREHOUSE"
        )
        db_session.add(loc)
        db_session.commit()
        assert loc.id is not None

    def test_location_hierarchy(self, db_session, sample_location_warehouse, 
                                 sample_location_rack, sample_location_bin):
        """Test parent-child location hierarchy."""
        assert sample_location_rack.parent_id == sample_location_warehouse.id
        assert sample_location_bin.parent_id == sample_location_rack.id
        
        # Check children
        assert len(sample_location_warehouse.children) >= 1
        assert sample_location_warehouse.children[0].code == "WH-A-R01"

    def test_location_full_path(self, db_session, sample_location_bin):
        """Test full path property."""
        path = sample_location_bin.full_path
        assert "WH-A" in path
        assert "WH-A-R01" in path
        assert "WH-A-R01-B03" in path

    def test_location_soft_delete(self, db_session, sample_location_warehouse):
        """Test soft delete (is_active = False)."""
        sample_location_warehouse.is_active = False
        db_session.commit()
        
        retrieved = db_session.query(Location).filter_by(id=sample_location_warehouse.id).first()
        assert retrieved.is_active is False


class TestUserModel:
    """Test User model operations."""

    def test_create_user(self, db_session):
        """Test user creation."""
        from utils.password_manager import hash_password
        
        user = User(
            username="testuser",
            password_hash=hash_password("password123"),
            role="operator",
            full_name="Test User"
        )
        db_session.add(user)
        db_session.commit()

        assert user.id is not None
        assert user.role == "operator"
        assert user.is_active is True

    def test_user_authentication(self, db_session, sample_admin_user):
        """Test password verification."""
        from utils.password_manager import verify_password
        
        assert verify_password(sample_admin_user.password_hash, "admin123") is True
        assert verify_password(sample_admin_user.password_hash, "wrong") is False

    def test_user_lock(self, db_session):
        """Test account locking mechanism."""
        from utils.password_manager import hash_password
        
        user = User(
            username="locked_user",
            password_hash=hash_password("password"),
            role="viewer",
            locked_until=datetime.utcnow() + timedelta(minutes=30)
        )
        db_session.add(user)
        db_session.commit()

        assert user.is_locked is True

    def test_user_not_locked(self, db_session, sample_admin_user):
        """Test unlocked user."""
        assert sample_admin_user.is_locked is False


class TestDocumentModel:
    """Test Document model operations."""

    def test_create_document(self, db_session):
        """Test basic document creation."""
        doc = Document(
            doc_no="TEST-DOC-001",
            doc_type="MRR",
            doc_date=date.today(),
            status="DRAFT"
        )
        db_session.add(doc)
        db_session.commit()

        assert doc.id is not None
        assert doc.status == "DRAFT"

    def test_document_with_lines(self, db_session, sample_product, sample_location_warehouse):
        """Test document with line items."""
        doc = Document(
            doc_no="TEST-DOC-LINES",
            doc_type="MRR",
            doc_date=date.today()
        )
        db_session.add(doc)
        db_session.flush()

        line1 = DocumentLine(
            document_id=doc.id,
            line_number=1,
            item_code=sample_product.item_code,
            location_id=sample_location_warehouse.id,
            qty=100.0
        )
        line2 = DocumentLine(
            document_id=doc.id,
            line_number=2,
            item_code=sample_product.item_code,
            location_id=sample_location_warehouse.id,
            qty=50.0
        )
        db_session.add_all([line1, line2])
        db_session.commit()

        assert len(doc.lines) == 2
        assert doc.total_quantity == 150.0
        assert doc.line_count == 2

    def test_document_cascade_delete(self, db_session, sample_product, sample_location_warehouse):
        """Test that deleting document also deletes its lines."""
        doc = Document(
            doc_no="TEST-CASCADE",
            doc_type="MRR",
            doc_date=date.today()
        )
        db_session.add(doc)
        db_session.flush()

        line = DocumentLine(
            document_id=doc.id,
            line_number=1,
            item_code=sample_product.item_code,
            location_id=sample_location_warehouse.id,
            qty=100.0
        )
        db_session.add(line)
        db_session.commit()

        doc_id = doc.id
        db_session.delete(doc)
        db_session.commit()

        # Check lines deleted
        lines = db_session.query(DocumentLine).filter_by(document_id=doc_id).all()
        assert len(lines) == 0


class TestMaterialRequestModel:
    """Test Material Request model operations."""

    def test_create_material_request(self, db_session, sample_product, sample_location_warehouse):
        """Test creating a material request with lines."""
        req = MaterialRequest(
            request_no="MRQ-TEST-001",
            requester="engineer1",
            company="Test Co.",
            project="Test Project",
            status="PENDING"
        )
        db_session.add(req)
        db_session.flush()

        line = MaterialRequestLine(
            request_id=req.id,
            line_number=1,
            item_code=sample_product.item_code,
            description=sample_product.description,
            qty=50.0,
            unit_price=25.0,
            currency="USD",
            total_cost=1250.0
        )
        db_session.add(line)
        db_session.commit()

        assert req.total_cost == 1250.0
        assert req.line_count == 1

    def test_material_request_status_flow(self, db_session):
        """Test material request status transitions."""
        req = MaterialRequest(
            request_no="MRQ-STATUS-001",
            requester="test_user",
            status="PENDING"
        )
        db_session.add(req)
        db_session.commit()

        req.status = "APPROVED"
        req.approved_by = "manager"
        req.approved_at = datetime.utcnow()
        db_session.commit()

        assert req.status == "APPROVED"
        assert req.approved_by == "manager"