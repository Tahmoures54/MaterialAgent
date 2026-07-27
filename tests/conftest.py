# tests/conftest.py
"""
Pytest fixtures and configuration for iMat tests.
Provides database sessions, sample data, and common test utilities.
"""

import pytest
import os
import sys
from datetime import date, datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.database import Base
from db.models import (
    Product, Transaction, InventorySummary, User,
    Location, Stock, Document, DocumentLine,
    ProjectInfo, MaterialRequest, MaterialRequestLine
)
from utils.password_manager import hash_password


# ------------------------------------------------------------------
# Database fixtures
# ------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a new database session for each test."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_engine
    )
    session = TestingSessionLocal()
    yield session
    session.rollback()
    session.close()


# ------------------------------------------------------------------
# Sample data fixtures - Products
# ------------------------------------------------------------------

@pytest.fixture
def sample_product(db_session):
    """Create a sample product."""
    product = Product(
        item_code="PIPE-6-CS",
        description="Carbon Steel Pipe 6 inch",
        size1="6\"",
        size2="SCH 40",
        material="ASTM A106 Gr.B",
        material_class="Carbon Steel",
        discipline="Piping",
        category="Pipe",
        unit_of_measure="MTR",
        weight=42.5,
        unit_cost=25.0,
        storage_condition="Covered",
        min_required_qty=10.0,
        lifecycle_status="ACTIVE",
        preservation_status="PRESERVED",
        preservation_required=True,
        preservation_interval_days=180,
        remarks="Test product",
        created_by="test_user"
    )
    db_session.add(product)
    db_session.commit()
    return product


@pytest.fixture
def sample_product2(db_session):
    """Create a second sample product."""
    product = Product(
        item_code="FLG-WN-300-8",
        description="Flange Weld Neck 8\" Class 300",
        size1="8\"",
        size2="CL300",
        material="ASTM A105",
        material_class="Carbon Steel",
        discipline="Piping",
        category="Flange",
        unit_of_measure="NOS",
        weight=15.0,
        unit_cost=85.0,
        min_required_qty=5.0,
        lifecycle_status="ACTIVE",
        created_by="test_user"
    )
    db_session.add(product)
    db_session.commit()
    return product


@pytest.fixture
def sample_product3(db_session):
    """Create a third sample product (electrical)."""
    product = Product(
        item_code="CBL-PWR-3C95",
        description="Power Cable 3x95 mm2 Cu/XLPE",
        size1="3x95",
        size2="mm2",
        material="Copper",
        material_class="Copper",
        discipline="Electrical",
        category="Power Cable",
        unit_of_measure="MTR",
        weight=3.2,
        unit_cost=45.0,
        min_required_qty=100.0,
        lifecycle_status="ACTIVE",
        created_by="test_user"
    )
    db_session.add(product)
    db_session.commit()
    return product


# ------------------------------------------------------------------
# Sample data fixtures - Locations
# ------------------------------------------------------------------

@pytest.fixture
def sample_location_warehouse(db_session):
    """Create a warehouse location."""
    loc = Location(
        code="WH-A",
        name="Main Warehouse",
        location_type="WAREHOUSE",
        description="Primary storage warehouse",
        capacity="Large",
        notes="Main building"
    )
    db_session.add(loc)
    db_session.commit()
    return loc


@pytest.fixture
def sample_location_rack(db_session, sample_location_warehouse):
    """Create a rack location inside warehouse."""
    loc = Location(
        code="WH-A-R01",
        name="Rack 01",
        location_type="RACK",
        parent_id=sample_location_warehouse.id,
        description="First rack in main warehouse"
    )
    db_session.add(loc)
    db_session.commit()
    return loc


@pytest.fixture
def sample_location_bin(db_session, sample_location_rack):
    """Create a bin location inside rack."""
    loc = Location(
        code="WH-A-R01-B03",
        name="Bin 03",
        location_type="BIN",
        parent_id=sample_location_rack.id,
        description="Third bin in rack 01"
    )
    db_session.add(loc)
    db_session.commit()
    return loc


@pytest.fixture
def sample_location_yard(db_session):
    """Create an open yard location."""
    loc = Location(
        code="YD-B",
        name="Open Yard B",
        location_type="OPEN_YARD",
        description="Outdoor storage yard",
        capacity="Extra Large"
    )
    db_session.add(loc)
    db_session.commit()
    return loc


# ------------------------------------------------------------------
# Sample data fixtures - Stock
# ------------------------------------------------------------------

@pytest.fixture
def sample_stock_quarantine(db_session, sample_product, sample_location_warehouse):
    """Create stock in quarantine."""
    stock = Stock(
        item_code=sample_product.item_code,
        heat_no="HEAT-2024-001",
        tag_no="TAG-001",
        serial_no="SN-001",
        batch_no="BATCH-A",
        location_id=sample_location_warehouse.id,
        qc_status="QUARANTINE",
        quantity=100.0,
        allocated_qty=0.0,
        received_date=date.today(),
        expiry_date=date.today() + timedelta(days=365)
    )
    db_session.add(stock)
    db_session.commit()
    return stock


@pytest.fixture
def sample_stock_accepted(db_session, sample_product, sample_location_warehouse):
    """Create accepted (issuable) stock."""
    stock = Stock(
        item_code=sample_product.item_code,
        heat_no="HEAT-2024-002",
        tag_no="TAG-002",
        location_id=sample_location_warehouse.id,
        qc_status="ACCEPTED",
        quantity=200.0,
        allocated_qty=50.0,
        received_date=date.today() - timedelta(days=10),
        expiry_date=date.today() + timedelta(days=365)
    )
    db_session.add(stock)
    db_session.commit()
    return stock


@pytest.fixture
def sample_stock_rejected(db_session, sample_product, sample_location_warehouse):
    """Create rejected stock."""
    stock = Stock(
        item_code=sample_product.item_code,
        heat_no="HEAT-2024-003",
        location_id=sample_location_warehouse.id,
        qc_status="REJECTED",
        quantity=10.0,
        allocated_qty=0.0,
        received_date=date.today() - timedelta(days=5)
    )
    db_session.add(stock)
    db_session.commit()
    return stock


@pytest.fixture
def sample_stock_accepted_flange(db_session, sample_product2, sample_location_rack):
    """Create accepted stock for flange product."""
    stock = Stock(
        item_code=sample_product2.item_code,
        heat_no="HEAT-FLG-001",
        tag_no="TAG-FLG-001",
        location_id=sample_location_rack.id,
        qc_status="ACCEPTED",
        quantity=50.0,
        allocated_qty=10.0,
        received_date=date.today() - timedelta(days=20),
        expiry_date=None
    )
    db_session.add(stock)
    db_session.commit()
    return stock


# ------------------------------------------------------------------
# Sample data fixtures - Documents
# ------------------------------------------------------------------

@pytest.fixture
def sample_document_mrr(db_session, sample_location_warehouse):
    """Create an MRR document."""
    doc = Document(
        doc_no="MRR-2024-001",
        doc_type="MRR",
        doc_date=date.today(),
        status="DRAFT",
        subject="Pipe Receipt",
        po_no="PO-2024-100",
        reference_no="INV-5001",
        vendor_name="Steel Supplies Co.",
        to_location_id=sample_location_warehouse.id,
        created_by="test_user"
    )
    db_session.add(doc)
    db_session.commit()
    return doc


@pytest.fixture
def sample_document_miv(db_session, sample_location_warehouse):
    """Create an MIV document."""
    doc = Document(
        doc_no="MIV-2024-001",
        doc_type="MIV",
        doc_date=date.today(),
        status="DRAFT",
        subject="Pipe Issue to Site",
        from_location_id=sample_location_warehouse.id,
        subcontractor="Site Team A",
        created_by="test_user"
    )
    db_session.add(doc)
    db_session.commit()
    return doc


@pytest.fixture
def sample_document_transfer(db_session, sample_location_warehouse, sample_location_yard):
    """Create a transfer document."""
    doc = Document(
        doc_no="MTR-2024-001",
        doc_type="MTR",
        doc_date=date.today(),
        status="DRAFT",
        subject="Transfer to Yard",
        from_location_id=sample_location_warehouse.id,
        to_location_id=sample_location_yard.id,
        created_by="test_user"
    )
    db_session.add(doc)
    db_session.commit()
    return doc


# ------------------------------------------------------------------
# Sample data fixtures - Document Lines
# ------------------------------------------------------------------

@pytest.fixture
def sample_document_lines(db_session, sample_document_mrr, sample_product, sample_location_warehouse):
    """Create document lines for MRR."""
    line = DocumentLine(
        document_id=sample_document_mrr.id,
        line_number=1,
        item_code=sample_product.item_code,
        heat_no="HEAT-2024-001",
        location_id=sample_location_warehouse.id,
        qty=100.0,
        unit="MTR",
        iso_drawing_no="ISO-PIP-001",
        cert_no="CERT-3.1-001",
        qc_status="QUARANTINE"
    )
    db_session.add(line)
    db_session.commit()
    return [line]


# ------------------------------------------------------------------
# Sample data fixtures - Users
# ------------------------------------------------------------------

@pytest.fixture
def sample_admin_user(db_session):
    """Create an admin user."""
    user = User(
        username="admin",
        password_hash=hash_password("admin123"),
        role="admin",
        full_name="System Administrator",
        email="admin@imat.io",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_operator_user(db_session):
    """Create an operator user."""
    user = User(
        username="operator",
        password_hash=hash_password("operator123"),
        role="operator",
        full_name="Warehouse Operator",
        email="operator@imat.io",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_viewer_user(db_session):
    """Create a viewer user."""
    user = User(
        username="viewer",
        password_hash=hash_password("viewer123"),
        role="viewer",
        full_name="Read-only User",
        email="viewer@imat.io",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_inactive_user(db_session):
    """Create an inactive user."""
    user = User(
        username="inactive",
        password_hash=hash_password("inactive123"),
        role="viewer",
        full_name="Inactive User",
        is_active=False
    )
    db_session.add(user)
    db_session.commit()
    return user


# ------------------------------------------------------------------
# Sample data fixtures - Transactions (legacy)
# ------------------------------------------------------------------

@pytest.fixture
def sample_transaction(db_session, sample_product):
    """Create a sample transaction."""
    trans = Transaction(
        item_code=sample_product.item_code,
        doc_date=date.today(),
        doc_no="DOC001",
        doc_name="Test Document",
        doc_type="Receipt",
        receive_qty=50,
        issue_qty=0,
        heat_no="HEAT-2024-001",
        location="WH-A",
        created_by="test_user"
    )
    db_session.add(trans)
    db_session.commit()
    return trans


@pytest.fixture
def sample_transaction2(db_session, sample_product):
    """Create a second transaction."""
    trans = Transaction(
        item_code=sample_product.item_code,
        doc_date=date.today() - timedelta(days=5),
        doc_no="DOC002",
        doc_name="Issue Document",
        doc_type="Issue",
        issue_qty=10,
        receive_qty=0,
        heat_no="HEAT-2024-001",
        location="WH-A",
        created_by="test_user"
    )
    db_session.add(trans)
    db_session.commit()
    return trans


# ------------------------------------------------------------------
# Sample data fixtures - Inventory Summary
# ------------------------------------------------------------------

@pytest.fixture
def sample_inventory_summary(db_session, sample_product):
    """Create inventory summary for a product."""
    inv_sum = InventorySummary(
        item_code=sample_product.item_code,
        sum_receive=100,
        sum_issue=30,
        last_updated=datetime.utcnow()
    )
    db_session.add(inv_sum)
    db_session.commit()
    return inv_sum


# ------------------------------------------------------------------
# Sample data fixtures - Material Requests
# ------------------------------------------------------------------

@pytest.fixture
def sample_material_request(db_session, sample_product, sample_location_warehouse):
    """Create a sample material request."""
    req = MaterialRequest(
        request_no="MRQ-20240101-0001",
        requester="engineer1",
        company="FARASAKOU",
        project="Storage Development",
        discipline="Piping",
        wbs_code="WBS-PIP-001",
        request_type="Normal",
        iso_drawing_no="ISO-PIP-001",
        target_location_id=sample_location_warehouse.id,
        required_date=date.today() + timedelta(days=30),
        status="PENDING",
        remarks="Urgent requirement"
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
    return req


# ------------------------------------------------------------------
# Sample data fixtures - Project Info
# ------------------------------------------------------------------

@pytest.fixture
def sample_project_info(db_session):
    """Create default project info."""
    info = ProjectInfo(
        company_name="FARASAKOU",
        project_name="Storage Development",
        project_code="001"
    )
    db_session.add(info)
    db_session.commit()
    return info


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------

def create_test_product(db_session, item_code, description="Test Product", **kwargs):
    """Helper to quickly create a test product."""
    product = Product(
        item_code=item_code,
        description=description,
        **kwargs
    )
    db_session.add(product)
    db_session.commit()
    return product


def create_test_location(db_session, code, name="Test Location", loc_type="WAREHOUSE", **kwargs):
    """Helper to quickly create a test location."""
    location = Location(
        code=code,
        name=name,
        location_type=loc_type,
        **kwargs
    )
    db_session.add(location)
    db_session.commit()
    return location


def create_test_stock(db_session, item_code, heat_no, location_id, qty, qc_status="QUARANTINE", **kwargs):
    """Helper to quickly create test stock."""
    stock = Stock(
        item_code=item_code,
        heat_no=heat_no,
        location_id=location_id,
        qc_status=qc_status,
        quantity=qty,
        received_date=date.today(),
        **kwargs
    )
    db_session.add(stock)
    db_session.commit()
    return stock