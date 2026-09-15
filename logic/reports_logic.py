# logic/reports_logic.py
"""
Advanced reporting logic for inventory, traceability, and preservation.
Uses the new Stock/Location/Document models.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, timedelta
from typing import List, Dict, Optional, Any
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
    """Retrieve live inventory with optional filtering."""
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
    """Materials whose preservation due date has passed or is approaching."""
    today = date.today()
    warning_date = today + timedelta(days=7)

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
    """Full material traceability for a given heat number."""
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
    """Stock movement history for an item."""
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
    """QC summary statistics by status."""
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
        results[status] = {"item_count": count, "total_quantity": total_qty}
    return results


def get_expiry_report(db: Session, days_threshold: int = 30) -> List:
    """Items expiring within the given threshold."""
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
    """Document summary with total quantities."""
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


def get_dashboard_kpis(db: Session) -> Dict:
    """Warehouse health snapshot for the home dashboard."""
    from logic.stock_logic import get_stock_summary

    summary = get_stock_summary(db)
    today = date.today()
    expiry_cutoff = today + timedelta(days=30)
    preservation_cutoff = today + timedelta(days=7)

    expiring_soon = db.query(func.count(Stock.id)).filter(
        Stock.expiry_date != None,
        Stock.expiry_date <= expiry_cutoff,
        Stock.quantity > 0
    ).scalar() or 0

    preservation_due = db.query(func.count(Stock.id)).filter(
        Stock.next_preservation_due != None,
        Stock.next_preservation_due <= preservation_cutoff,
        Stock.quantity > 0
    ).scalar() or 0

    pending_requests = db.query(func.count(MaterialRequest.id)).filter(
        MaterialRequest.status == "PENDING"
    ).scalar() or 0

    draft_documents = db.query(func.count(Document.id)).filter(
        Document.status == "DRAFT"
    ).scalar() or 0

    return {
        **summary,
        "expiring_soon": expiring_soon,
        "preservation_due": preservation_due,
        "pending_material_requests": pending_requests,
        "draft_documents": draft_documents,
    }


def get_material_shortage_report(
    db: Session,
    include_closed: bool = False,
) -> List[Dict[str, Any]]:
    """
    Compare open Material Request lines with available ACCEPTED stock.
    Returns coverage status: FULFILLED / COVERED / PARTIAL / SHORTAGE.
    """
    open_statuses = ("PENDING", "APPROVED", "PARTIAL")
    q = (
        db.query(MaterialRequestLine, MaterialRequest, Product)
        .join(MaterialRequest, MaterialRequestLine.request_id == MaterialRequest.id)
        .outerjoin(Product, MaterialRequestLine.item_code == Product.item_code)
    )
    if not include_closed:
        q = q.filter(MaterialRequest.status.in_(open_statuses))

    rows: List[Dict[str, Any]] = []
    for line, req, product in q.order_by(
        MaterialRequest.request_no, MaterialRequestLine.line_number
    ).all():
        needed = float(line.qty or 0)
        fulfilled = float(getattr(line, "fulfilled_qty", 0) or 0)
        remaining = max(0.0, needed - fulfilled)

        stock_rows = (
            db.query(Stock)
            .filter(
                Stock.item_code == line.item_code,
                Stock.qc_status == "ACCEPTED",
            )
            .all()
        )
        available = 0.0
        for s in stock_rows:
            qty = float(s.quantity or 0)
            allocated = float(getattr(s, "allocated_qty", 0) or 0)
            available += max(0.0, qty - allocated)

        shortage = max(0.0, remaining - available)
        if remaining <= 0:
            status = "FULFILLED"
        elif shortage <= 0:
            status = "COVERED"
        elif available > 0:
            status = "PARTIAL"
        else:
            status = "SHORTAGE"

        rows.append({
            "request_no": req.request_no,
            "request_status": req.status,
            "requester": req.requester,
            "discipline": req.discipline or (product.discipline if product else ""),
            "wbs_code": req.wbs_code or "",
            "iso_drawing_no": req.iso_drawing_no or "",
            "required_date": req.required_date.isoformat() if req.required_date else "",
            "item_code": line.item_code,
            "description": (line.description or (product.description if product else "") or ""),
            "unit": line.unit or "EA",
            "requested_qty": needed,
            "fulfilled_qty": fulfilled,
            "remaining_qty": remaining,
            "available_stock": round(available, 3),
            "shortage_qty": round(shortage, 3),
            "coverage_status": status,
        })
    return rows


def get_po_receipt_summary(db: Session) -> List[Dict[str, Any]]:
    """MRR/related receipts linked to PO, vendor, and delivery note."""
    docs = (
        db.query(Document)
        .filter(Document.doc_type.in_(("MRR", "MSR", "OSND")))
        .order_by(Document.doc_date.desc())
        .all()
    )
    rows: List[Dict[str, Any]] = []
    for doc in docs:
        lines = doc.lines or []
        total_qty = sum(float(ln.qty or 0) for ln in lines)
        damage = sum(float(getattr(ln, "damaged_qty", 0) or 0) for ln in lines)
        short = sum(float(getattr(ln, "shortage_qty", 0) or 0) for ln in lines)
        rows.append({
            "doc_no": doc.doc_no,
            "doc_type": doc.doc_type,
            "doc_date": doc.doc_date.isoformat() if doc.doc_date else "",
            "status": doc.status,
            "po_no": doc.po_no or "",
            "delivery_note_no": doc.delivery_note_no or "",
            "reference_no": doc.reference_no or "",
            "vendor_name": doc.vendor_name or "",
            "line_count": len(lines),
            "total_qty": round(total_qty, 3),
            "damaged_qty": round(damage, 3),
            "shortage_qty": round(short, 3),
            "remarks": doc.remarks or "",
        })
    return rows


def get_in_transit_report(db: Session) -> List[Dict[str, Any]]:
    """Open MTR transfers between locations (simple in-transit view)."""
    docs = (
        db.query(Document)
        .filter(Document.doc_type == "MTR")
        .filter(Document.status.in_(("DRAFT", "APPROVED", "IN_TRANSIT", "PENDING")))
        .order_by(Document.doc_date.desc())
        .all()
    )
    rows: List[Dict[str, Any]] = []
    for doc in docs:
        from_code = doc.from_location.code if doc.from_location else ""
        to_code = doc.to_location.code if doc.to_location else ""
        lines = doc.lines or []
        if not lines:
            rows.append({
                "doc_no": doc.doc_no,
                "doc_date": doc.doc_date.isoformat() if doc.doc_date else "",
                "status": doc.status,
                "item_code": "",
                "heat_no": "",
                "qty": 0.0,
                "unit": "",
                "from_location": from_code,
                "to_location": to_code,
                "remarks": doc.remarks or "",
            })
            continue
        for ln in lines:
            rows.append({
                "doc_no": doc.doc_no,
                "doc_date": doc.doc_date.isoformat() if doc.doc_date else "",
                "status": doc.status,
                "item_code": ln.item_code,
                "heat_no": ln.heat_no or "",
                "qty": float(ln.qty or 0),
                "unit": ln.unit or "EA",
                "from_location": from_code,
                "to_location": to_code,
                "remarks": doc.remarks or "",
            })
    return rows
