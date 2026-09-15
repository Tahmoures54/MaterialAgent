# logic/reports.py
"""
Legacy reports module - updated to use Stock/Location models.
Provides inventory summaries, transaction reports, and low stock alerts.
"""

from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from datetime import date, timedelta
from typing import List, Dict, Optional
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db.database import session_scope
from db.models import (
    Product, Transaction,
    Stock, Location, Document, DocumentLine
)


def generate_inventory_summary(db: Optional[Session] = None) -> List[Dict]:
    """
    Generate current inventory summary for all items.
    Uses Stock model for accurate inventory data.
    Products with no stock still appear as OUT OF STOCK.
    """
    with session_scope(db) as session:
        results = session.query(
            Product.item_code,
            Product.description,
            Product.unit_of_measure,
            Product.category,
            Product.discipline,
            Product.min_required_qty,
            func.coalesce(func.sum(Stock.quantity), 0).label('total_qty'),
            func.coalesce(func.sum(Stock.allocated_qty), 0).label('allocated_qty'),
            (func.coalesce(func.sum(Stock.quantity), 0) -
             func.coalesce(func.sum(Stock.allocated_qty), 0)).label('available_qty')
        ).outerjoin(
            Stock,
            and_(Product.item_code == Stock.item_code, Stock.quantity > 0)
        ).group_by(Product.item_code).order_by(Product.description).all()

        data = []
        for row in results:
            stock_status = "OK"
            if row.available_qty <= 0:
                stock_status = "OUT OF STOCK"
            elif row.min_required_qty and row.available_qty <= row.min_required_qty:
                stock_status = "LOW STOCK"

            data.append({
                'Item Code': row.item_code,
                'Description': row.description or "",
                'UOM': row.unit_of_measure or "",
                'Category': row.category or "",
                'Discipline': row.discipline or "",
                'Total Qty': row.total_qty,
                'Allocated Qty': row.allocated_qty,
                'Available Qty': row.available_qty,
                'Min Required': row.min_required_qty or 0,
                'Status': stock_status
            })
        return data


def generate_transaction_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    doc_type: Optional[str] = None,
    db: Optional[Session] = None,
) -> List[Dict]:
    """Generate transaction history report."""
    if start_date is None:
        start_date = date.today() - timedelta(days=30)
    if end_date is None:
        end_date = date.today()

    with session_scope(db) as session:
        query = session.query(
            Transaction.doc_date,
            Transaction.doc_no,
            Transaction.doc_type,
            Transaction.item_code,
            Product.description,
            Transaction.request_qty,
            Transaction.issue_qty,
            Transaction.receive_qty,
            Transaction.contractor_vendor,
            Transaction.heat_no,
            Transaction.remarks
        ).outerjoin(Product, Transaction.item_code == Product.item_code)\
         .filter(Transaction.doc_date.between(start_date, end_date))

        if doc_type:
            query = query.filter(Transaction.doc_type == doc_type)

        results = query.order_by(Transaction.doc_date.desc()).all()

        data = []
        for row in results:
            data.append({
                'Date': row.doc_date.isoformat() if row.doc_date else '',
                'Doc No': row.doc_no or '',
                'Type': row.doc_type or '',
                'Item Code': row.item_code,
                'Description': row.description or '',
                'Request QTY': row.request_qty or 0,
                'Issue QTY': row.issue_qty or 0,
                'Receive QTY': row.receive_qty or 0,
                'Vendor/Contractor': row.contractor_vendor or '',
                'Heat No': row.heat_no or '',
                'Remarks': row.remarks or ''
            })
        return data


def get_low_stock_items(threshold: float = 10, db: Optional[Session] = None) -> List[Dict]:
    """Get items with available stock below threshold."""
    with session_scope(db) as session:
        results = session.query(
            Product.item_code,
            Product.description,
            Product.unit_of_measure,
            Product.min_required_qty,
            func.sum(Stock.quantity).label('total_qty'),
            func.sum(Stock.allocated_qty).label('allocated_qty'),
            (func.sum(Stock.quantity) - func.sum(Stock.allocated_qty)).label('available_qty')
        ).join(Stock, Product.item_code == Stock.item_code)\
         .filter(Stock.quantity > 0)\
         .group_by(Product.item_code)\
         .having(
             (func.sum(Stock.quantity) - func.sum(Stock.allocated_qty)) <= threshold
         ).all()

        data = []
        for row in results:
            data.append({
                'Item Code': row.item_code,
                'Description': row.description or "",
                'UOM': row.unit_of_measure or "",
                'Min Required': row.min_required_qty or 0,
                'Total Qty': row.total_qty,
                'Allocated': row.allocated_qty,
                'Available': row.available_qty,
                'Shortage': max(0, (row.min_required_qty or 0) - (row.available_qty or 0))
            })
        return data


def get_stock_value_report(db: Optional[Session] = None) -> List[Dict]:
    """Calculate stock value report. Requires unit_cost in Product model."""
    with session_scope(db) as session:
        results = session.query(
            Product.item_code,
            Product.description,
            Product.unit_cost,
            func.sum(Stock.quantity).label('total_qty'),
            (func.sum(Stock.quantity) * Product.unit_cost).label('total_value')
        ).join(Stock, Product.item_code == Stock.item_code)\
         .filter(Stock.quantity > 0)\
         .group_by(Product.item_code)\
         .order_by(func.sum(Stock.quantity) * Product.unit_cost.desc()).all()

        data = []
        total_value = 0
        total_qty = 0
        for row in results:
            value = row.total_value or 0
            qty = row.total_qty or 0
            total_value += value
            total_qty += qty
            data.append({
                'Item Code': row.item_code,
                'Description': row.description or "",
                'Unit Cost': row.unit_cost or 0,
                'Total Qty': qty,
                'Total Value': round(value, 2)
            })

        if data:
            data.append({
                'Item Code': 'TOTAL',
                'Description': 'Total Stock Value',
                'Unit Cost': '',
                'Total Qty': total_qty,
                'Total Value': round(total_value, 2)
            })

        return data


def get_movement_report(
    item_code: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Optional[Session] = None,
) -> List[Dict]:
    """Get detailed movement report for a specific item."""
    if start_date is None:
        start_date = date.today() - timedelta(days=90)
    if end_date is None:
        end_date = date.today()

    with session_scope(db) as session:
        doc_movements = session.query(
            Document.doc_date,
            Document.doc_no,
            Document.doc_type,
            DocumentLine.item_code,
            DocumentLine.qty,
            DocumentLine.heat_no,
            Location.code.label('location_code')
        ).join(DocumentLine, Document.id == DocumentLine.document_id)\
         .join(Location, DocumentLine.location_id == Location.id)\
         .filter(
             DocumentLine.item_code == item_code,
             Document.doc_date.between(start_date, end_date)
         ).order_by(Document.doc_date.desc()).all()

        data = []
        for mov in doc_movements:
            data.append({
                'Date': mov.doc_date.isoformat() if mov.doc_date else '',
                'Doc No': mov.doc_no,
                'Type': mov.doc_type,
                'Qty': mov.qty,
                'Heat No': mov.heat_no or '',
                'Location': mov.location_code or ''
            })
        return data
