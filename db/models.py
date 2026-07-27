# db/models.py
"""
SQLAlchemy ORM models for iMat Material Control System (EPC Edition).
Complete database schema with all relationships and indexes.
"""

from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, 
    ForeignKey, Index, Boolean, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from .database import Base


class Product(Base):
    """Material/Product Master Data (Coding System)."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_code = Column(String(50), unique=True, index=True, nullable=False)
    part_number = Column(String(100), nullable=True)
    description = Column(String(200))
    size1 = Column(String(50))
    size2 = Column(String(50))
    material = Column(String(100))
    material_class = Column(String(50))
    discipline = Column(String(50))
    category = Column(String(50))
    unit_of_measure = Column(String(20))
    weight = Column(Float, nullable=True)
    unit_cost = Column(Float, default=0.0)
    storage_condition = Column(String(100), nullable=True)
    min_required_qty = Column(Float, default=0.0)
    lifecycle_status = Column(String(20), default='ACTIVE')
    preservation_status = Column(String(30), default='PRESERVED')
    preservation_required = Column(Boolean, default=False)
    preservation_interval_days = Column(Integer, nullable=True)
    remarks = Column(String(255))
    created_by = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String(50), nullable=True)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    # Relationships
    transactions = relationship("Transaction", back_populates="product", cascade="all, delete-orphan")
    inventory_summary = relationship("InventorySummary", back_populates="product", uselist=False)
    stocks = relationship("Stock", back_populates="product", cascade="all, delete-orphan")
    document_lines = relationship("DocumentLine", back_populates="product")
    material_request_lines = relationship("MaterialRequestLine", back_populates="product")

    @hybrid_property
    def total_stock(self):
        """Total quantity across all stocks (all QC statuses)."""
        return sum(s.quantity for s in self.stocks)

    @hybrid_property
    def available_stock(self):
        """Total available (not allocated) accepted stock."""
        return sum(s.available_qty for s in self.stocks if s.qc_status == 'ACCEPTED')

    def __repr__(self):
        return f"<Product(item_code='{self.item_code}', description='{self.description}')>"


class Transaction(Base):
    """Material Transaction History (legacy - being migrated to Document/Stock system)."""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_code = Column(String(50), ForeignKey("products.item_code"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)

    doc_date = Column(Date, nullable=False)
    doc_no = Column(String(50))
    doc_name = Column(String(100))
    doc_type = Column(String(20))
    po_no = Column(String(50))
    mr_no = Column(String(50))

    subject = Column(String(200))
    remarks = Column(String(255))

    tag_no = Column(String(50))
    project_code = Column(String(50))
    manufacturer = Column(String(100))
    cert_no = Column(String(100))
    expiry_date = Column(Date)
    heat_no = Column(String(50))
    serial_no = Column(String(100))
    pkg_no = Column(String(50))

    contractor_vendor = Column(String(200))

    receive_qty = Column(Float, default=0.0)
    issue_qty = Column(Float, default=0.0)
    request_qty = Column(Float, default=0.0)

    location = Column(String(100))

    created_by = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="transactions")
    document = relationship("Document", back_populates="transactions")

    __table_args__ = (
        Index('idx_transaction_item_doc', 'item_code', 'doc_no'),
        Index('idx_transaction_date', 'doc_date'),
        Index('idx_transaction_type_date', 'doc_type', 'doc_date'),
        Index('idx_transaction_item_date', 'item_code', 'doc_date'),
    )

    def __repr__(self):
        return f"<Transaction(id={self.id}, item='{self.item_code}', type='{self.doc_type}')>"


class InventorySummary(Base):
    """Aggregated inventory summary per item (legacy - use Stock for new code)."""
    __tablename__ = "inventory_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_code = Column(String(50), ForeignKey("products.item_code"), unique=True, nullable=False, index=True)
    sum_receive = Column(Float, default=0.0)
    sum_issue = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @hybrid_property
    def inventory(self):
        """Current calculated inventory (receive - issue)."""
        return self.sum_receive - self.sum_issue

    product = relationship("Product", back_populates="inventory_summary")

    def __repr__(self):
        return f"<InventorySummary(item='{self.item_code}', inventory={self.inventory})>"


class User(Base):
    """Application users with role-based access control."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), nullable=False, default="viewer")
    full_name = Column(String(100))
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(50), nullable=True)

    __table_args__ = (
        Index('idx_user_role', 'role'),
        Index('idx_user_active', 'is_active'),
    )

    @property
    def is_locked(self):
        """Check if user account is temporarily locked."""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False

    def __repr__(self):
        return f"<User(username='{self.username}', role='{self.role}')>"


class Location(Base):
    """Physical warehouse locations hierarchy."""
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    location_type = Column(String(20), nullable=False)  # WAREHOUSE, OPEN_YARD, RACK, BIN, QUARANTINE
    parent_id = Column(Integer, ForeignKey('locations.id'), nullable=True)

    description = Column(String(200), default="")
    capacity = Column(String(50), nullable=True)
    notes = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Self-referential relationship
    parent = relationship("Location", remote_side=[id], backref="children")
    
    # Other relationships
    stocks = relationship("Stock", back_populates="location")
    documents_from = relationship("Document", foreign_keys="Document.from_location_id", back_populates="from_location")
    documents_to = relationship("Document", foreign_keys="Document.to_location_id", back_populates="to_location")
    document_lines = relationship("DocumentLine", back_populates="location")
    material_requests = relationship("MaterialRequest", back_populates="target_location")

    @property
    def full_path(self):
        """Get full location path (e.g., WH-A > RACK-01 > BIN-03)."""
        path = [self.code]
        current = self.parent
        while current:
            path.insert(0, current.code)
            current = current.parent
        return " > ".join(path)

    def __repr__(self):
        return f"<Location(code='{self.code}', type='{self.location_type}')>"


class Stock(Base):
    """Current stock levels with QC status tracking."""
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_code = Column(String(50), ForeignKey("products.item_code"), nullable=False, index=True)
    heat_no = Column(String(50), nullable=False)
    tag_no = Column(String(50), nullable=True)
    serial_no = Column(String(100), nullable=True)
    batch_no = Column(String(50), nullable=True)
    expiry_date = Column(Date, nullable=True)

    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False, index=True)
    qc_status = Column(String(20), nullable=False, default="QUARANTINE", index=True)  # QUARANTINE, ACCEPTED, REJECTED
    quantity = Column(Float, default=0.0)
    allocated_qty = Column(Float, default=0.0)
    received_date = Column(Date, nullable=False)
    next_preservation_due = Column(Date, nullable=True)
    preservation_status = Column(String(20), nullable=True)
    last_movement_date = Column(DateTime, default=datetime.utcnow)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="stocks")
    location = relationship("Location", back_populates="stocks")

    @hybrid_property
    def available_qty(self):
        """Quantity available for issue (total - allocated)."""
        return max(0, self.quantity - self.allocated_qty)

    @property
    def is_expired(self):
        """Check if stock has expired."""
        if self.expiry_date:
            return self.expiry_date < date.today()
        return False

    @property
    def days_to_expiry(self):
        """Days remaining until expiry (negative if expired)."""
        if self.expiry_date:
            return (self.expiry_date - date.today()).days
        return None

    @property
    def preservation_overdue(self):
        """Check if preservation is overdue."""
        if self.next_preservation_due:
            return self.next_preservation_due <= date.today()
        return False

    __table_args__ = (
        Index('idx_stock_item_heat', 'item_code', 'heat_no'),
        Index('idx_stock_qc', 'qc_status'),
        Index('idx_stock_location', 'location_id'),
        Index('idx_stock_expiry', 'expiry_date'),
        UniqueConstraint('item_code', 'heat_no', 'location_id', 'qc_status', name='uq_stock_unique'),
    )

    def __repr__(self):
        return f"<Stock(item='{self.item_code}', heat='{self.heat_no}', qty={self.quantity}, qc='{self.qc_status}')>"


class Document(Base):
    """Warehouse document headers (MRR, MIV, MSR, etc.)."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_no = Column(String(50), nullable=False, index=True)
    doc_type = Column(String(20), nullable=False, index=True)  # MRR, MIV, MSR, OSND, MTR, etc.
    doc_date = Column(Date, nullable=False, index=True)
    status = Column(String(20), default="DRAFT", nullable=False, index=True)  # DRAFT, APPROVED, REJECTED, CLOSED
    subject = Column(String(200), nullable=True)
    po_no = Column(String(50), nullable=True)
    reference_no = Column(String(100), nullable=True)
    delivery_note_no = Column(String(100), nullable=True)
    vendor_name = Column(String(200), nullable=True)
    subcontractor = Column(String(200), nullable=True)
    remarks = Column(String(255), nullable=True)

    from_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    to_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    
    # Audit
    created_by = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    approved_by = Column(String(50), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Relationships
    from_location = relationship("Location", foreign_keys=[from_location_id], back_populates="documents_from")
    to_location = relationship("Location", foreign_keys=[to_location_id], back_populates="documents_to")
    lines = relationship("DocumentLine", back_populates="document", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="document")

    @property
    def total_quantity(self):
        """Total quantity in all document lines."""
        return sum(line.qty for line in self.lines)

    @property
    def line_count(self):
        """Number of lines in the document."""
        return len(self.lines)

    def __repr__(self):
        return f"<Document(no='{self.doc_no}', type='{self.doc_type}', status='{self.status}')>"


class DocumentLine(Base):
    """Document line items with detailed material information."""
    __tablename__ = "document_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number = Column(Integer, nullable=False, default=1)
    item_code = Column(String(50), ForeignKey("products.item_code"), nullable=False, index=True)
    heat_no = Column(String(50), nullable=True)
    tag_no = Column(String(50), nullable=True)
    serial_no = Column(String(100), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)

    qty = Column(Float, nullable=False)
    damaged_qty = Column(Float, default=0.0)
    shortage_qty = Column(Float, default=0.0)
    received_qty = Column(Float, default=0.0)

    unit = Column(String(20), default="EA")
    iso_drawing_no = Column(String(100), nullable=True)
    cert_no = Column(String(100), nullable=True)
    qc_status = Column(String(20), nullable=True)
    remarks = Column(String(255), nullable=True)

    # Relationships
    document = relationship("Document", back_populates="lines")
    product = relationship("Product", back_populates="document_lines")
    location = relationship("Location", back_populates="document_lines")

    def __repr__(self):
        return f"<DocumentLine(item='{self.item_code}', qty={self.qty})>"


class ProjectInfo(Base):
    """Company and project information."""
    __tablename__ = "project_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(200), nullable=False, default="iMat International")
    project_name = Column(String(200), nullable=False, default="Default Project")
    project_code = Column(String(50), nullable=True)
    client_name = Column(String(200), nullable=True)
    contract_no = Column(String(100), nullable=True)
    location = Column(String(200), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(50), nullable=True)

    def __repr__(self):
        return f"<ProjectInfo(company='{self.company_name}', project='{self.project_name}')>"


class MaterialRequest(Base):
    """Material Request from Technical Office to Warehouse."""
    __tablename__ = "material_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_no = Column(String(50), unique=True, nullable=False, index=True)
    requester = Column(String(50), nullable=False)
    company = Column(String(200), nullable=True)
    project = Column(String(100), nullable=True)
    discipline = Column(String(50), nullable=True)
    wbs_code = Column(String(50), nullable=True)
    request_type = Column(String(20), default="Normal")  # Normal, Urgent, Replacement
    iso_drawing_no = Column(String(100), nullable=True)
    target_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    required_date = Column(Date, nullable=True)
    status = Column(String(20), default="PENDING", index=True)  # PENDING, APPROVED, REJECTED, CONVERTED, CANCELLED
    
    # Approval workflow
    approved_by = Column(String(50), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(255), nullable=True)
    
    remarks = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lines = relationship("MaterialRequestLine", back_populates="request", cascade="all, delete-orphan")
    target_location = relationship("Location", back_populates="material_requests")

    @property
    def total_cost(self):
        """Calculate total estimated cost of the request."""
        return sum(line.total_cost for line in self.lines)

    @property
    def line_count(self):
        """Number of line items in the request."""
        return len(self.lines)

    def __repr__(self):
        return f"<MaterialRequest(no='{self.request_no}', status='{self.status}')>"


class MaterialRequestLine(Base):
    """Material Request line items."""
    __tablename__ = "material_request_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("material_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number = Column(Integer, nullable=False, default=1)
    item_code = Column(String(50), ForeignKey("products.item_code"), nullable=False)

    # Product snapshot fields (saved at request time for audit trail)
    description = Column(String(200), nullable=True)
    size1 = Column(String(50), nullable=True)
    size2 = Column(String(50), nullable=True)
    material = Column(String(100), nullable=True)
    material_class = Column(String(50), nullable=True)
    discipline = Column(String(50), nullable=True)
    category = Column(String(50), nullable=True)

    unit = Column(String(20), default="EA")
    subject = Column(String(200), nullable=True)
    qty = Column(Float, nullable=False)
    unit_price = Column(Float, default=0.0)
    currency = Column(String(10), default="USD")
    total_cost = Column(Float, default=0.0)
    
    # Fulfillment tracking
    fulfilled_qty = Column(Float, default=0.0)
    
    remarks = Column(String(255), nullable=True)

    # Relationships
    request = relationship("MaterialRequest", back_populates="lines")
    product = relationship("Product", back_populates="material_request_lines")

    @property
    def remaining_qty(self):
        """Quantity still to be fulfilled."""
        return max(0, self.qty - self.fulfilled_qty)

    @property
    def is_fulfilled(self):
        """Check if the line is fully fulfilled."""
        return self.fulfilled_qty >= self.qty

    def __repr__(self):
        return f"<MaterialRequestLine(item='{self.item_code}', qty={self.qty})>"


# ------------------------------------------------------------------
# Additional utility models (optional)
# ------------------------------------------------------------------

class AuditLog(Base):
    """System audit log for tracking important actions."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    user = Column(String(50), nullable=True)
    action = Column(String(50), nullable=False)  # CREATE, UPDATE, DELETE, LOGIN, LOGOUT, EXPORT
    entity_type = Column(String(50), nullable=True)  # Product, Document, Stock, etc.
    entity_id = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)

    def __repr__(self):
        return f"<AuditLog(user='{self.user}', action='{self.action}')>"


class SystemSetting(Base):
    """Key-value store for system settings."""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(50), nullable=True)

    def __repr__(self):
        return f"<SystemSetting(key='{self.key}')>"