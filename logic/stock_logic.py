# logic/stock_logic.py
"""
Stock management business logic.
Handles all stock movements, QC status changes, allocations, and inventory adjustments.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple

from db.models import Stock, Product, Location


VALID_QC_STATUSES = ("QUARANTINE", "ACCEPTED", "REJECTED")
DEFAULT_HEAT_NO = "N/A"


def normalize_heat_no(heat_no: Optional[str]) -> str:
    """Normalize heat/batch number; blank values become N/A."""
    if heat_no is None:
        return DEFAULT_HEAT_NO
    value = str(heat_no).strip()
    return value if value else DEFAULT_HEAT_NO


def _validate_positive_qty(qty: float, action: str = "adjust") -> None:
    """Reject zero/negative quantities for stock movements."""
    if qty is None:
        raise ValueError("Quantity is required")
    try:
        qty_value = float(qty)
    except (TypeError, ValueError):
        raise ValueError("Quantity must be a number")
    if qty_value <= 0:
        raise ValueError(f"Quantity to {action} must be greater than zero (got {qty})")


def _validate_qc_status(qc_status: str) -> str:
    status = (qc_status or "").strip().upper()
    if status not in VALID_QC_STATUSES:
        raise ValueError(
            f"Invalid QC status '{qc_status}'. "
            f"Allowed: {', '.join(VALID_QC_STATUSES)}"
        )
    return status


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
        Stock.heat_no == normalize_heat_no(heat_no),
        Stock.location_id == location_id,
        Stock.qc_status == (qc_status or "").strip().upper()
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

    Returns:
        Updated Stock record

    Raises:
        ValueError: If quantity is not positive or QC status is invalid
    """
    _validate_positive_qty(qty, action="add")
    qc_status = _validate_qc_status(qc_status)
    heat_no = normalize_heat_no(heat_no)

    if not item_code:
        raise ValueError("Item code is required")
    if not location_id:
        raise ValueError("Location is required")

    if received_date is None:
        received_date = date.today()

    stock = get_stock_record(db, item_code, heat_no, location_id, qc_status)

    if stock:
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

    Raises:
        ValueError: If insufficient stock, stock not found, or quantity is invalid
    """
    _validate_positive_qty(qty, action="remove")
    qc_status = _validate_qc_status(qc_status)
    heat_no = normalize_heat_no(heat_no)

    stock = get_stock_record(db, item_code, heat_no, location_id, qc_status)

    if not stock:
        raise ValueError(
            f"No stock found for item {item_code} with heat number {heat_no} "
            f"at location {location_id} with status {qc_status}"
        )

    available = stock.quantity - (stock.allocated_qty or 0)
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

    Returns:
        Tuple of (source_stock, destination_stock)
    """
    if from_location_id == to_location_id:
        raise ValueError("Source and destination locations must be different")

    source_stock = remove_stock(db, item_code, heat_no, from_location_id, qty, qc_status)

    dest_stock = add_stock(
        db, item_code, heat_no, to_location_id, qty, qc_status,
        tag_no=source_stock.tag_no,
        serial_no=source_stock.serial_no,
        batch_no=source_stock.batch_no,
        expiry_date=source_stock.expiry_date
    )

    # Preserve preservation schedule when transferring lots
    if source_stock.next_preservation_due and not dest_stock.next_preservation_due:
        dest_stock.next_preservation_due = source_stock.next_preservation_due
        dest_stock.preservation_status = source_stock.preservation_status

    db.flush()
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

    Does not commit — the caller owns the transaction so QC batch
    operations and document workflows can roll back together.
    """
    old_status = _validate_qc_status(old_status)
    new_status = _validate_qc_status(new_status)
    if old_status == new_status:
        raise ValueError("Old and new status must be different")

    old_stock = remove_stock(db, item_code, heat_no, location_id, qty, qc_status=old_status)

    new_stock = add_stock(
        db, item_code, heat_no, location_id, qty, qc_status=new_status,
        tag_no=old_stock.tag_no,
        serial_no=old_stock.serial_no,
        batch_no=old_stock.batch_no,
        expiry_date=old_stock.expiry_date
    )

    if old_stock.next_preservation_due and not new_stock.next_preservation_due:
        new_stock.next_preservation_due = old_stock.next_preservation_due
        new_stock.preservation_status = old_stock.preservation_status

    db.flush()
    return old_stock, new_stock


def allocate_stock(
    db: Session,
    item_code: str,
    heat_no: str,
    location_id: int,
    qty: float,
    qc_status: str = "ACCEPTED"
) -> Stock:
    """Reserve available accepted stock (e.g. for an approved material request)."""
    _validate_positive_qty(qty, action="allocate")
    qc_status = _validate_qc_status(qc_status)

    stock = get_stock_record(db, item_code, heat_no, location_id, qc_status)
    if not stock:
        raise ValueError(
            f"No stock found for item {item_code} with heat number "
            f"{normalize_heat_no(heat_no)} at location {location_id}"
        )

    if stock.available_qty < qty:
        raise ValueError(
            f"Insufficient available stock to allocate. "
            f"(Available: {stock.available_qty}, Requested: {qty})"
        )

    stock.allocated_qty = (stock.allocated_qty or 0) + qty
    stock.last_movement_date = date.today()
    db.flush()
    return stock


def deallocate_stock(
    db: Session,
    item_code: str,
    heat_no: str,
    location_id: int,
    qty: float,
    qc_status: str = "ACCEPTED"
) -> Stock:
    """Release a previous allocation."""
    _validate_positive_qty(qty, action="deallocate")
    qc_status = _validate_qc_status(qc_status)

    stock = get_stock_record(db, item_code, heat_no, location_id, qc_status)
    if not stock:
        raise ValueError(
            f"No stock found for item {item_code} with heat number "
            f"{normalize_heat_no(heat_no)} at location {location_id}"
        )

    current_alloc = stock.allocated_qty or 0
    if qty > current_alloc:
        raise ValueError(
            f"Cannot deallocate {qty}; only {current_alloc} is allocated"
        )

    stock.allocated_qty = current_alloc - qty
    stock.last_movement_date = date.today()
    db.flush()
    return stock


def get_stock_summary(db: Session) -> Dict:
    """Get inventory summary statistics."""
    total_items = db.query(func.count(func.distinct(Stock.item_code))).filter(
        Stock.quantity > 0
    ).scalar() or 0

    total_qty = db.query(func.sum(Stock.quantity)).filter(
        Stock.quantity > 0
    ).scalar() or 0

    total_allocated = db.query(func.sum(Stock.allocated_qty)).filter(
        Stock.quantity > 0
    ).scalar() or 0

    qc_summary = {}
    for status in VALID_QC_STATUSES:
        qty = db.query(func.sum(Stock.quantity)).filter(
            Stock.qc_status == status,
            Stock.quantity > 0
        ).scalar() or 0
        qc_summary[status] = qty

    location_count = db.query(func.count(Location.id)).filter(
        Location.is_active == True  # noqa: E712
    ).scalar() or 0

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
