# logic/inventory.py
"""
Inventory management business logic.
Provides search, filtering, and CRUD operations for inventory data.
"""

from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db.database import get_db_session, get_session, session_scope
from db.models import (
    Product, Transaction, InventorySummary,
    Stock, Location, Document, DocumentLine
)


def search_inventory(
    search_text: Optional[str] = None,
    qc_status: Optional[str] = None,
    discipline: Optional[str] = None,
    location_code: Optional[str] = None,
    low_stock_only: bool = False,
    expired_only: bool = False,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    db: Optional[Session] = None,
) -> List[Dict]:
    """
    Search inventory with comprehensive filters using the Stock model.
    
    Args:
        search_text: Text to search in item_code, description, heat_no
        qc_status: Filter by QC status (QUARANTINE, ACCEPTED, REJECTED)
        discipline: Filter by engineering discipline
        location_code: Filter by location code
        low_stock_only: Show only items with available qty < min_required_qty
        expired_only: Show only expired items
        limit: Maximum records to return
        offset: Number of records to skip
        
    Returns:
        List of dicts with inventory data
    """
    with session_scope(db) as session:
        query = session.query(
            Stock.item_code,
            Product.description,
            Product.discipline,
            Product.material_class,
            Product.category,
            Product.unit_of_measure,
            Product.min_required_qty,
            Stock.heat_no,
            Stock.tag_no,
            Stock.serial_no,
            Stock.batch_no,
            Stock.expiry_date,
            Location.code.label('location_code'),
            Location.name.label('location_name'),
            Stock.qc_status,
            Stock.quantity.label('total_qty'),
            Stock.allocated_qty,
            (Stock.quantity - Stock.allocated_qty).label('available_qty'),
            Stock.next_preservation_due,
            Stock.received_date,
            Stock.last_movement_date
        ).join(Product, Stock.item_code == Product.item_code)\
         .join(Location, Stock.location_id == Location.id)\
         .filter(Stock.quantity > 0)

        # Apply filters
        if search_text:
            search_pattern = f'%{search_text}%'
            query = query.filter(
                or_(
                    Stock.item_code.ilike(search_pattern),
                    Product.description.ilike(search_pattern),
                    Stock.heat_no.ilike(search_pattern),
                    Location.code.ilike(search_pattern),
                    Stock.tag_no.ilike(search_pattern)
                )
            )

        if qc_status:
            query = query.filter(Stock.qc_status == qc_status)

        if discipline:
            query = query.filter(Product.discipline == discipline)

        if location_code:
            query = query.filter(Location.code.ilike(f'%{location_code}%'))

        if low_stock_only:
            query = query.filter(
                (Stock.quantity - Stock.allocated_qty) < Product.min_required_qty
            )

        if expired_only:
            query = query.filter(Stock.expiry_date <= date.today())

        # Order and paginate
        query = query.order_by(Stock.item_code, Stock.heat_no)
        
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        results = query.all()
        data = []
        for row in results:
            days_to_expiry = None
            if row.expiry_date:
                days_to_expiry = (row.expiry_date - date.today()).days

            data.append({
                "Item Code": row.item_code,
                "Description": row.description or "",
                "Discipline": row.discipline or "",
                "Material Class": row.material_class or "",
                "Category": row.category or "",
                "UOM": row.unit_of_measure or "",
                "Min Required Qty": row.min_required_qty or 0,
                "Heat No": row.heat_no,
                "Tag No": row.tag_no or "",
                "Serial No": row.serial_no or "",
                "Batch No": row.batch_no or "",
                "Expiry Date": row.expiry_date.isoformat() if row.expiry_date else "",
                "Days to Expiry": days_to_expiry,
                "Location Code": row.location_code,
                "Location Name": row.location_name or "",
                "QC Status": row.qc_status,
                "Total Qty": row.total_qty,
                "Allocated Qty": row.allocated_qty,
                "Available Qty": row.available_qty,
                "Preservation Due": row.next_preservation_due.isoformat() if row.next_preservation_due else "",
                "Received Date": row.received_date.isoformat() if row.received_date else "",
                "Last Movement": row.last_movement_date.isoformat() if row.last_movement_date else "",
            })
        return data


def get_filter_options(db: Optional[Session] = None) -> Dict[str, List[str]]:
    """
    Get distinct filter values for dropdown menus.
    
    Returns:
        Dict with keys: qc_statuses, disciplines, locations, categories, material_classes
    """
    with session_scope(db) as session:
        qc_statuses = [
            row[0] for row in session.query(Stock.qc_status).distinct().all()
            if row[0]
        ]

        disciplines = [
            row[0] for row in session.query(Product.discipline).distinct().all()
            if row[0]
        ]

        locations = [
            row[0] for row in session.query(Location.code).order_by(Location.code).all()
            if row[0]
        ]

        categories = [
            row[0] for row in session.query(Product.category).distinct().all()
            if row[0]
        ]

        material_classes = [
            row[0] for row in session.query(Product.material_class).distinct().all()
            if row[0]
        ]

        return {
            "qc_statuses": sorted(qc_statuses),
            "disciplines": sorted(disciplines),
            "locations": locations,
            "categories": sorted(categories),
            "material_classes": sorted(material_classes),
        }


def get_inventory_by_item(item_code: str, db: Optional[Session] = None) -> List[Dict]:
    """Get all stock records for a specific item."""
    with session_scope(db) as session:
        stocks = session.query(Stock).filter(
            Stock.item_code == item_code,
            Stock.quantity > 0
        ).order_by(Stock.qc_status, Stock.location_id).all()

        result = []
        for stock in stocks:
            location = session.query(Location).filter_by(id=stock.location_id).first()
            product = session.query(Product).filter_by(item_code=stock.item_code).first()

            result.append({
                "item_code": stock.item_code,
                "description": product.description if product else "",
                "heat_no": stock.heat_no,
                "location": location.code if location else "",
                "qc_status": stock.qc_status,
                "quantity": stock.quantity,
                "allocated": stock.allocated_qty,
                "available": stock.quantity - stock.allocated_qty,
                "expiry_date": stock.expiry_date,
                "preservation_due": stock.next_preservation_due,
            })
        return result


def get_all_inventory(limit: int = 1000, db: Optional[Session] = None) -> List[Dict]:
    """Get all inventory records (simplified version)."""
    return search_inventory(limit=limit, db=db)


def add_transaction(transaction_data: Dict, db: Optional[Session] = None) -> int:
    """
    Add a new transaction to the database.
    This is for the legacy transaction system.
    
    Args:
        transaction_data: Dict with Transaction model fields
        db: Optional existing session
        
    Returns:
        ID of the new transaction
    """
    owns_session = db is None
    session = db if db is not None else get_db_session()
    try:
        trans = Transaction(
            item_code=transaction_data.get('item_code'),
            doc_date=transaction_data.get('doc_date', date.today()),
            doc_no=transaction_data.get('doc_no', ''),
            doc_name=transaction_data.get('doc_name', ''),
            doc_type=transaction_data.get('doc_type', ''),
            po_no=transaction_data.get('po_no', ''),
            mr_no=transaction_data.get('mr_no', ''),
            project_code=transaction_data.get('project_code', ''),
            tag_no=transaction_data.get('tag_no', ''),
            manufacturer=transaction_data.get('manufacturer', ''),
            cert_no=transaction_data.get('cert_no', ''),
            expiry_date=transaction_data.get('expiry_date'),
            contractor_vendor=transaction_data.get('contractor_vendor', ''),
            request_qty=transaction_data.get('request_qty', 0),
            issue_qty=transaction_data.get('issue_qty', 0),
            receive_qty=transaction_data.get('receive_qty', 0),
            heat_no=transaction_data.get('heat_no', ''),
            serial_no=transaction_data.get('serial_no', ''),
            pkg_no=transaction_data.get('pkg_no', ''),
            location=transaction_data.get('location', ''),
            subject=transaction_data.get('subject', ''),
            remarks=transaction_data.get('remarks', ''),
            created_by=transaction_data.get('created_by', 'system')
        )
        session.add(trans)
        session.flush()
        
        _update_inventory_summary_internal(session, transaction_data.get('item_code'))
        
        if owns_session:
            session.commit()
        return trans.id
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def update_inventory_summary(item_code: str, db: Optional[Session] = None):
    """Update inventory summary for an item (public wrapper)."""
    if db is not None:
        _update_inventory_summary_internal(db, item_code)
        return
    with get_session() as session:
        _update_inventory_summary_internal(session, item_code)
        session.commit()


def _update_inventory_summary_internal(session, item_code: str):
    """Internal: Update inventory summary for an item."""
    totals = session.query(
        func.sum(Transaction.receive_qty).label('total_receive'),
        func.sum(Transaction.issue_qty).label('total_issue')
    ).filter(Transaction.item_code == item_code).first()

    inv_sum = session.query(InventorySummary).filter(
        InventorySummary.item_code == item_code
    ).first()

    if inv_sum:
        inv_sum.sum_receive = totals.total_receive or 0
        inv_sum.sum_issue = totals.total_issue or 0
        inv_sum.last_updated = datetime.utcnow()
    else:
        inv_sum = InventorySummary(
            item_code=item_code,
            sum_receive=totals.total_receive or 0,
            sum_issue=totals.total_issue or 0
        )
        session.add(inv_sum)