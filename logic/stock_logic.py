# logic/stock_logic.py
"""
Stock management business logic.
Handles all stock movements, QC status changes, and inventory adjustments.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
from db.models import Stock, Product, Location


def get_stock_record(
    db: Session, 
    item_code: str, 
    heat_no: str, 
    location_id: int, 
    qc_status: str
) -> Optional[Stock]:
    """Find a unique stock record by composite key."""
    return db.query(Stock).filter(
        Stock.item_code == item_code,
        Stock.heat_no == heat_no,
        Stock.location_id == location_id,
        Stock.qc_status == qc_status
    ).first()


def get_stock_by_item(db: Session, item_code: str) -> List[Stock]:
    """Get all stock records for an item with quantity > 0."""
    return db.query(Stock).filter(
        Stock.item_code == item_code,
        Stock.quantity > 0
    ).order_by(Stock.qc_status).all()


def get_stock_by_location(db: Session, location_id: int) -> List[Stock]:
    """Get all stock records at a specific location."""
    return db.query(Stock).filter(
        Stock.location_id == location_id,
        Stock.quantity > 0
    ).all()


def add_stock(
    db: Session, 
    item_code: str, 
    heat_no: str, 
    location_id: int, 
    qty: float, 
    qc_status: str = "QUARANTINE",
    tag_no: Optional[str] = None,
    serial_no: Optional[str] = None,
    batch_no: Optional[str] = None,
    expiry_date: Optional[date] = None,
    received_date: Optional[date] = None
) -> Stock:
    """
    Add stock to inventory (e.g., when receiving goods via MRR).
    
    Args:
        db: Database session
        item_code: Material code
        heat_no: Heat/batch number
        location_id: Storage location ID
        qty: Quantity to add
        qc_status: Initial QC status (default: QUARANTINE)
        tag_no: Tag number
        serial_no: Serial number
        batch_no: Batch number
        expiry_date: Expiry date
        received_date: Date received (default: today)
        
    Returns:
        Updated Stock record
    """
    if received_date is None:
        received_date = date.today()

    stock = get_stock_record(db, item_code, heat_no, location_id, qc_status)
    
    if stock:
        # Update existing stock
        stock.quantity += qty
        stock.last_movement_date = date.today()
        if expiry_date:
            stock.expiry_date = expiry_date
        if tag_no:
            stock.tag_no = tag_no
        if serial_no:
            stock.serial_no = serial_no
        if batch_no:
            stock.batch_no = batch_no
    else:
        # Create new stock record
        stock = Stock(
            item_code=item_code,
            heat_no=heat_no,
            location_id=location_id,
            qc_status=qc_status,
            quantity=qty,
            received_date=received_date,
            tag_no=tag_no,
            serial_no=serial_no,
            batch_no=batch_no,
            expiry_date=expiry_date,
            last_movement_date=date.today()
        )
        
        # Calculate preservation due date if the product requires it
        product = db.query(Product).filter(Product.item_code == item_code).first()
        if product and product.preservation_required and product.preservation_interval_days:
            stock.next_preservation_due = date.today() + timedelta(
                days=product.preservation_interval_days
            )
            stock.preservation_status = "DUE"
            
        db.add(stock)

    db.flush()
    return stock


def remove_stock(
    db: Session, 
    item_code: str, 
    heat_no: str, 
    location_id: int, 
    qty: float, 
    qc_status: str = "ACCEPTED"
) -> Stock:
    """
    Remove stock from inventory (e.g., when issuing material via MIV).
    
    Args:
        db: Database session
        item_code: Material code
        heat_no: Heat/batch number
        location_id: Storage location ID
        qty: Quantity to remove
        qc_status: QC status to deduct from (default: ACCEPTED)
        
    Returns:
        Updated Stock record
        
    Raises:
        ValueError: If insufficient stock or stock not found
    """
    stock = get_stock_record(db, item_code, heat_no, location_id, qc_status)
    
    if not stock:
        raise ValueError(
            f"No stock found for item {item_code} with heat number {heat_no} "
            f"at location {location_id} with status {qc_status}"
        )
    
    available = stock.quantity - stock.allocated_qty
    if available < qty:
        raise ValueError(
            f"Insufficient usable stock. "
            f"(Available: {available}, Requested: {qty})"
        )
        
    stock.quantity -= qty
    stock.last_movement_date = date.today()
    db.flush()
    return stock


def move_stock(
    db: Session, 
    item_code: str, 
    heat_no: str,
    from_location_id: int, 
    to_location_id: int,
    qty: float, 
    qc_status: str = "ACCEPTED"
) -> Tuple[Stock, Stock]:
    """
    Move stock from one location to another.
    
    Args:
        db: Database session
        item_code: Material code
        heat_no: Heat/batch number
        from_location_id: Source location ID
        to_location_id: Destination location ID
        qty: Quantity to move
        qc_status: QC status (must be same for source and destination)
        
    Returns:
        Tuple of (source_stock, destination_stock)
    """
    if from_location_id == to_location_id:
        raise ValueError("Source and destination locations must be different")
    
    # Remove from source
    source_stock = remove_stock(db, item_code, heat_no, from_location_id, qty, qc_status)
    
    # Add to destination
    dest_stock = add_stock(
        db, item_code, heat_no, to_location_id, qty, qc_status,
        tag_no=source_stock.tag_no,
        serial_no=source_stock.serial_no,
        batch_no=source_stock.batch_no,
        expiry_date=source_stock.expiry_date
    )
    
    return source_stock, dest_stock


def change_qc_status(
    db: Session, 
    item_code: str, 
    heat_no: str, 
    location_id: int, 
    old_status: str, 
    new_status: str, 
    qty: float
) -> Tuple[Stock, Stock]:
    """
    Change QC status of material (e.g., from QUARANTINE to ACCEPTED).
    
    Args:
        db: Database session
        item_code: Material code
        heat_no: Heat/batch number
        location_id: Storage location ID
        old_status: Current QC status
        new_status: New QC status
        qty: Quantity to change
        
    Returns:
        Tuple of (old_status_stock, new_status_stock)
    """
    if old_status == new_status:
        raise ValueError("Old and new status must be different")
    
    # Remove from old status
    old_stock = remove_stock(db, item_code, heat_no, location_id, qty, qc_status=old_status)
    
    # Add to new status
    new_stock = add_stock(
        db, item_code, heat_no, location_id, qty, qc_status=new_status,
        tag_no=old_stock.tag_no,
        serial_no=old_stock.serial_no,
        batch_no=old_stock.batch_no,
        expiry_date=old_stock.expiry_date
    )
    
    db.commit()
    return old_stock, new_stock


def get_stock_summary(db: Session) -> Dict:
    """
    Get inventory summary statistics.
    
    Returns:
        Dict with total_items, total_qty, qc_summary, etc.
    """
    from sqlalchemy import func
    
    total_items = db.query(func.count(func.distinct(Stock.item_code))).filter(
        Stock.quantity > 0
    ).scalar() or 0
    
    total_qty = db.query(func.sum(Stock.quantity)).filter(
        Stock.quantity > 0
    ).scalar() or 0
    
    total_allocated = db.query(func.sum(Stock.allocated_qty)).filter(
        Stock.quantity > 0
    ).scalar() or 0
    
    # QC breakdown
    qc_summary = {}
    for status in ['QUARANTINE', 'ACCEPTED', 'REJECTED']:
        qty = db.query(func.sum(Stock.quantity)).filter(
            Stock.qc_status == status,
            Stock.quantity > 0
        ).scalar() or 0
        qc_summary[status] = qty
    
    # Location count
    location_count = db.query(func.count(Location.id)).filter(
        Location.is_active == True
    ).scalar() or 0
    
    # Expired items
    expired_count = db.query(func.count(Stock.id)).filter(
        Stock.expiry_date <= date.today(),
        Stock.quantity > 0
    ).scalar() or 0
    
    return {
        "total_items": total_items,
        "total_quantity": total_qty,
        "total_allocated": total_allocated,
        "total_available": total_qty - total_allocated,
        "qc_summary": qc_summary,
        "location_count": location_count,
        "expired_items": expired_count,
    }