# logic/material_request_logic.py
"""
Material Request business logic.
Handles creation, approval, and tracking of material requests from Technical Office.
"""

from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import List, Dict, Optional
from db.models import (
    MaterialRequest, MaterialRequestLine, 
    Product, Location
)


def create_material_request(
    db: Session,
    request_data: Dict,
    lines_data: List[Dict]
) -> MaterialRequest:
    """
    Create a new material request with line items.
    
    Args:
        db: Database session
        request_data: Header data dict with keys:
            requester, company, project, discipline, wbs_code,
            request_type, iso_drawing_no, target_location_id,
            required_date, remarks
        lines_data: List of line item dicts with keys:
            item_code, description, size1, size2, material,
            material_class, discipline, category, unit,
            subject, qty, unit_price, currency, remarks
            
    Returns:
        Created MaterialRequest object
    """
    # Generate request number
    today_str = datetime.now().strftime("%Y%m%d")
    count = db.query(MaterialRequest).count() + 1
    request_no = f"MRQ-{today_str}-{count:04d}"
    
    # Create request header
    request = MaterialRequest(
        request_no=request_no,
        requester=request_data.get("requester", "unknown"),
        company=request_data.get("company", ""),
        project=request_data.get("project", ""),
        discipline=request_data.get("discipline", ""),
        wbs_code=request_data.get("wbs_code", ""),
        request_type=request_data.get("request_type", "Normal"),
        iso_drawing_no=request_data.get("iso_drawing_no", ""),
        target_location_id=request_data.get("target_location_id"),
        required_date=request_data.get("required_date"),
        remarks=request_data.get("remarks", ""),
        status="PENDING"
    )
    db.add(request)
    db.flush()
    
    # Create line items
    for idx, line_data in enumerate(lines_data, start=1):
        line = MaterialRequestLine(
            request_id=request.id,
            line_number=idx,
            item_code=line_data["item_code"],
            description=line_data.get("description", ""),
            size1=line_data.get("size1", ""),
            size2=line_data.get("size2", ""),
            material=line_data.get("material", ""),
            material_class=line_data.get("material_class", ""),
            discipline=line_data.get("discipline", ""),
            category=line_data.get("category", ""),
            unit=line_data.get("unit", "EA"),
            subject=line_data.get("subject", ""),
            qty=line_data["qty"],
            unit_price=line_data.get("unit_price", 0.0),
            currency=line_data.get("currency", "USD"),
            total_cost=line_data.get("qty", 0) * line_data.get("unit_price", 0.0),
            remarks=line_data.get("remarks", "")
        )
        db.add(line)
    
    db.commit()
    db.refresh(request)
    return request


def update_material_request_status(
    db: Session,
    request_id: int,
    new_status: str,
    approved_by: Optional[str] = None,
    rejection_reason: Optional[str] = None
) -> MaterialRequest:
    """
    Update material request status.
    
    Args:
        db: Database session
        request_id: Material request ID
        new_status: New status (PENDING, APPROVED, REJECTED, CONVERTED, CANCELLED)
        approved_by: Username of approver
        rejection_reason: Reason for rejection
        
    Returns:
        Updated MaterialRequest object
    """
    request = db.query(MaterialRequest).filter(
        MaterialRequest.id == request_id
    ).first()
    
    if not request:
        raise ValueError(f"Material request with id {request_id} not found")
    
    valid_transitions = {
        "PENDING": ["APPROVED", "REJECTED", "CANCELLED"],
        "APPROVED": ["CONVERTED", "CANCELLED"],
        "REJECTED": ["PENDING"],
    }
    
    if new_status not in valid_transitions.get(request.status, []):
        raise ValueError(
            f"Cannot transition from {request.status} to {new_status}"
        )
    
    request.status = new_status
    request.updated_at = datetime.utcnow()
    
    if new_status == "APPROVED":
        request.approved_by = approved_by
        request.approved_at = datetime.utcnow()
    elif new_status == "REJECTED":
        request.rejection_reason = rejection_reason
    
    db.commit()
    db.refresh(request)
    return request


def get_material_requests(
    db: Session,
    status: Optional[str] = None,
    discipline: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 100
) -> List[MaterialRequest]:
    """
    Get material requests with optional filters.
    
    Args:
        db: Database session
        status: Filter by status
        discipline: Filter by discipline
        project: Filter by project
        limit: Maximum results
        
    Returns:
        List of MaterialRequest objects
    """
    query = db.query(MaterialRequest)
    
    if status:
        query = query.filter(MaterialRequest.status == status)
    if discipline:
        query = query.filter(MaterialRequest.discipline == discipline)
    if project:
        query = query.filter(MaterialRequest.project == project)
    
    return query.order_by(
        MaterialRequest.created_at.desc()
    ).limit(limit).all()


def get_material_request_by_no(
    db: Session,
    request_no: str
) -> Optional[MaterialRequest]:
    """Get a material request by its number."""
    return db.query(MaterialRequest).filter(
        MaterialRequest.request_no == request_no
    ).first()