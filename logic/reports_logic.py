# logic/reports_logic.py
"""
Advanced reporting logic for inventory, traceability, and preservation.
Uses the new Stock/Location/Document models.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, timedelta
from typing import List, Dict, Optional
from db.models import (
    Stock, Product, Location, Document, DocumentLine,
    Transaction, MaterialRequest, MaterialRequestLine
)


def get_current_inventory(
    db: Session, 
    item_code: Optional[str] = None,
    location_id: Optional[int] = None,
    qc_status: Optional[str] = None
) -> List:
    """
    Retrieve live inventory with optional filtering.
    
    Args:
        db: Database session
        item_code: Filter by item code (partial match)
        location_id: Filter by location
        qc_status: Filter by QC status
        
    Returns:
        List of Stock records with Product and Location info
    """
    query = db.query(
        Stock.item_code,
        Product.description,
        Product.discipline,
        Stock.heat_no,
        Location.code.label('location_code'),
        Stock.qc_status,
        Stock.quantity,
        Stock.allocated_qty,
        (Stock.quantity - Stock.allocated_qty).label('available_qty'),
        Stock.expiry_date,
        Stock.next_preservation_due
    ).join(Product, Stock.item_code == Product.item_code)\
     .join(Location, Stock.location_id == Location.id)\
     .filter(Stock.quantity > 0)
    
    if item_code:
        query = query.filter(Stock.item_code.contains(item_code))
    if location_id:
        query = query.filter(Stock.location_id == location_id)
    if qc_status:
        query = query.filter(Stock.qc_status == qc_status)
    
    return query.order_by(Stock.item_code, Stock.heat_no).all()


def get_preservation_alerts(db: Session) -> List:
    """
    Get materials whose preservation due date has passed or is approaching.
    
    Returns:
        List of Stock records needing preservation
    """
    today = date.today()
    warning_date = today + timedelta(days=7)  # Alert 7 days before due
    
    return db.query(
        Stock.item_code,
        Product.description,
        Stock.heat_no,
        Location.code.label('location_code'),
        Location.name.label('location_name'),
        Stock.next_preservation_due,
        Stock.preservation_status,
        Stock.quantity
    ).join(Product)\
     .join(Location)\
     .filter(
         Stock.next_preservation_due <= warning_date,
         Stock.quantity > 0
     ).order_by(Stock.next_preservation_due).all()


def get_traceability_report(db: Session, heat_no: str) -> List:
    """
    Full material traceability for a given heat number.
    Shows all documents (receipts, issues, transfers) and current location.
    
    Args:
        db: Database session
        heat_no: Heat/batch number to trace
        
    Returns:
        List of document line records
    """
    return db.query(
        Document.doc_no,
        Document.doc_type,
        Document.doc_date,
        DocumentLine.item_code,
        DocumentLine.qty,
        DocumentLine.iso_drawing_no,
        DocumentLine.cert_no,
        Location.code.label('location_code'),
        Product.description
    ).join(DocumentLine, Document.id == DocumentLine.document_id)\
     .join(Location, DocumentLine.location_id == Location.id)\
     .join(Product, DocumentLine.item_code == Product.item_code)\
     .filter(DocumentLine.heat_no == heat_no)\
     .order_by(Document.doc_date.desc()).all()


def get_stock_movements(
    db: Session,
    item_code: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List:
    """
    Get stock movement history for an item.
    Combines Transaction and Document data.
    
    Args:
        db: Database session
        item_code: Material code
        start_date: Start date filter
        end_date: End date filter
        
    Returns:
        List of movement records
    """
    if start_date is None:
        start_date = date.today() - timedelta(days=90)
    if end_date is None:
        end_date = date.today()
    
    return db.query(
        Transaction.doc_date,
        Transaction.doc_no,
        Transaction.doc_type,
        Transaction.item_code,
        Product.description,
        Transaction.receive_qty,
        Transaction.issue_qty,
        Transaction.request_qty,
        Transaction.heat_no,
        Transaction.location,
        Transaction.remarks
    ).join(Product, Transaction.item_code == Product.item_code)\
     .filter(
         Transaction.item_code == item_code,
         Transaction.doc_date.between(start_date, end_date)
     ).order_by(Transaction.doc_date.desc()).all()


def get_qc_summary(db: Session) -> Dict:
    """
    Get QC summary statistics.
    
    Returns:
        Dict with counts and quantities by QC status
    """
    results = {}
    for status in ['QUARANTINE', 'ACCEPTED', 'REJECTED']:
        count = db.query(func.count(Stock.id)).filter(
            Stock.qc_status == status,
            Stock.quantity > 0
        ).scalar() or 0
        
        total_qty = db.query(func.sum(Stock.quantity)).filter(
            Stock.qc_status == status,
            Stock.quantity > 0
        ).scalar() or 0
        
        results[status] = {
            "item_count": count,
            "total_quantity": total_qty
        }
    
    return results


def get_expiry_report(db: Session, days_threshold: int = 30) -> List:
    """
    Get items expiring within the given threshold.
    
    Args:
        db: Database session
        days_threshold: Number of days to look ahead
        
    Returns:
        List of Stock records expiring soon
    """
    today = date.today()
    cutoff = today + timedelta(days=days_threshold)
    
    return db.query(
        Stock.item_code,
        Product.description,
        Stock.heat_no,
        Stock.expiry_date,
        Location.code.label('location_code'),
        Stock.quantity,
        Stock.qc_status
    ).join(Product)\
     .join(Location)\
     .filter(
         Stock.expiry_date != None,
         Stock.expiry_date <= cutoff,
         Stock.quantity > 0
     ).order_by(Stock.expiry_date).all()


def get_document_summary(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List:
    """
    Get document summary with total quantities.
    
    Args:
        db: Database session
        start_date: Start date filter
        end_date: End date filter
        
    Returns:
        List of document summaries
    """
    if start_date is None:
        start_date = date.today() - timedelta(days=30)
    if end_date is None:
        end_date = date.today()
    
    documents = db.query(Document).filter(
        Document.doc_date.between(start_date, end_date)
    ).order_by(Document.doc_date.desc()).all()
    
    summary = []
    for doc in documents:
        total_qty = sum(line.qty for line in doc.lines)
        summary.append({
            "doc_no": doc.doc_no,
            "doc_type": doc.doc_type,
            "doc_date": doc.doc_date,
            "status": doc.status,
            "subject": doc.subject or "",
            "vendor": doc.vendor_name or "",
            "line_count": len(doc.lines),
            "total_qty": total_qty,
            "created_by": doc.created_by or "",
        })
    
    return summary