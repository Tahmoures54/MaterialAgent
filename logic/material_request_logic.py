# logic/material_request_logic.py
"""
Material Request business logic.
Handles creation, approval, tracking, and issue fulfillment against open requests.
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
    """Create a new material request with line items."""
    today_str = datetime.now().strftime("%Y%m%d")
    prefix = f"MRQ-{today_str}-"
    last = (
        db.query(MaterialRequest.request_no)
        .filter(MaterialRequest.request_no.like(f"{prefix}%"))
        .order_by(MaterialRequest.request_no.desc())
        .first()
    )
    seq = 1
    if last and last[0]:
        try:
            seq = int(str(last[0]).rsplit("-", 1)[-1]) + 1
        except ValueError:
            seq = 1
    request_no = f"{prefix}{seq:04d}"

    if not lines_data:
        raise ValueError("Material request must have at least one line item")

    for idx, line_data in enumerate(lines_data, start=1):
        if not line_data.get("item_code"):
            raise ValueError(f"Line {idx}: item code is required")
        try:
            qty = float(line_data.get("qty", 0))
        except (TypeError, ValueError):
            raise ValueError(f"Line {idx}: quantity must be a number")
        if qty <= 0:
            raise ValueError(f"Line {idx}: quantity must be greater than zero")

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
    """Update material request status with validated transitions."""
    request = db.query(MaterialRequest).filter(
        MaterialRequest.id == request_id
    ).first()

    if not request:
        raise ValueError(f"Material request with id {request_id} not found")

    valid_transitions = {
        "PENDING": ["APPROVED", "REJECTED", "CANCELLED", "PARTIAL"],
        "APPROVED": ["CONVERTED", "CANCELLED", "PARTIAL"],
        "PARTIAL": ["CONVERTED", "CANCELLED", "APPROVED"],
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
    """Get material requests with optional filters."""
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


def record_issue_fulfillment(
    db: Session,
    item_code: str,
    qty: float,
    reverse: bool = False,
) -> float:
    """
    Apply (or reverse) an issue quantity against open Material Request lines.

    Matching is FIFO by request_no then line_number for lines with remaining qty
    on requests in PENDING / APPROVED / PARTIAL.

    Returns the quantity applied to MR lines (may be less than qty if no open demand).
    """
    if not item_code or qty is None:
        return 0.0

    remaining_to_apply = abs(float(qty))
    if remaining_to_apply <= 0:
        return 0.0

    open_statuses = ("PENDING", "APPROVED", "PARTIAL")

    lines = (
        db.query(MaterialRequestLine)
        .join(MaterialRequest, MaterialRequestLine.request_id == MaterialRequest.id)
        .filter(
            MaterialRequestLine.item_code == item_code.strip(),
            MaterialRequest.status.in_(open_statuses),
        )
        .order_by(
            MaterialRequest.request_no.asc(),
            MaterialRequestLine.line_number.asc(),
        )
        .all()
    )

    applied = 0.0
    touched_request_ids = set()

    for line in lines:
        if remaining_to_apply <= 0:
            break

        needed = float(line.qty or 0)
        already = float(line.fulfilled_qty or 0)

        if reverse:
            can = already
            if can <= 0:
                continue
            take = min(can, remaining_to_apply)
            line.fulfilled_qty = max(0.0, already - take)
        else:
            room = max(0.0, needed - already)
            if room <= 0:
                continue
            take = min(room, remaining_to_apply)
            line.fulfilled_qty = already + take

        remaining_to_apply -= take
        applied += take
        touched_request_ids.add(line.request_id)

    for rid in touched_request_ids:
        _refresh_request_status_from_lines(db, rid)

    return applied


def _refresh_request_status_from_lines(db: Session, request_id: int) -> None:
    """Set PARTIAL / CONVERTED based on line fulfillment totals."""
    req = db.query(MaterialRequest).filter(MaterialRequest.id == request_id).first()
    if not req or req.status in ("REJECTED", "CANCELLED"):
        return

    lines = list(req.lines or [])
    if not lines:
        return

    totals_needed = sum(float(ln.qty or 0) for ln in lines)
    totals_done = sum(float(ln.fulfilled_qty or 0) for ln in lines)

    if totals_needed <= 0:
        return

    if totals_done <= 0:
        return
    if totals_done + 1e-9 >= totals_needed:
        req.status = "CONVERTED"
    else:
        req.status = "PARTIAL"
    req.updated_at = datetime.utcnow()
