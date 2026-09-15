# logic/document_logic.py
"""
Business logic for creating warehouse documents and updating inventory.
Supports all common EPC material document types with appropriate stock changes.
Issue documents (MIV/ISS/WOM) also update Material Request fulfilled_qty (FIFO).
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import date, datetime
from typing import Dict, List, Optional

from db.models import Document, DocumentLine, AuditLog
from logic.stock_logic import (
    add_stock, remove_stock, move_stock, normalize_heat_no
)
from logic.material_request_logic import record_issue_fulfillment


RECEIPT_TYPES = {"MRR", "RCT", "MRV"}
ISSUE_TYPES = {"MIV", "ISS", "WOM"}
TRANSFER_TYPES = {"MTR", "TRN"}
RETURN_TYPES = {"RTV", "SRN"}
ADJUSTMENT_TYPES = {"OSND", "ADJ"}
NO_STOCK_CHANGE = {"MSR", "RES", "GAT"}

VALID_DOC_TYPES = (
    RECEIPT_TYPES | ISSUE_TYPES | TRANSFER_TYPES |
    RETURN_TYPES | ADJUSTMENT_TYPES | NO_STOCK_CHANGE
)


def _receipt_qc_status(doc_type: str) -> str:
    return "ACCEPTED" if doc_type == "MRV" else "QUARANTINE"


def _normalize_line(line: Dict) -> Dict:
    normalized = dict(line)
    normalized["heat_no"] = normalize_heat_no(line.get("heat_no"))
    return normalized


def _log_audit(
    db: Session,
    user: Optional[str],
    action: str,
    entity_id: Optional[str],
    details: str = ""
) -> None:
    try:
        db.add(AuditLog(
            user=user,
            action=action,
            entity_type="Document",
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details,
        ))
        db.flush()
    except SQLAlchemyError:
        pass


def generate_next_doc_number(
    db: Session,
    doc_type: str,
    doc_date: Optional[date] = None
) -> str:
    doc_type = (doc_type or "").upper().strip()
    if not doc_type:
        raise ValueError("Document type is required")

    day = doc_date or date.today()
    prefix = f"{doc_type}-{day.strftime('%Y%m%d')}-"
    last = (
        db.query(Document.doc_no)
        .filter(Document.doc_no.like(f"{prefix}%"))
        .order_by(Document.doc_no.desc())
        .first()
    )

    seq = 1
    if last and last[0]:
        try:
            seq = int(str(last[0]).rsplit("-", 1)[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


def _apply_line_stock(db: Session, document: Document, line: DocumentLine, reverse: bool = False) -> None:
    doc_type = document.doc_type.upper().strip()
    qty = line.qty
    heat_no = normalize_heat_no(line.heat_no)

    if doc_type in NO_STOCK_CHANGE:
        return

    if doc_type in RECEIPT_TYPES:
        qc = _receipt_qc_status(doc_type)
        if reverse:
            remove_stock(
                db, line.item_code, heat_no, line.location_id, qty, qc_status=qc
            )
        else:
            add_stock(
                db=db,
                item_code=line.item_code,
                heat_no=heat_no,
                location_id=line.location_id,
                qty=qty,
                qc_status=qc,
                tag_no=line.tag_no,
                serial_no=line.serial_no,
            )

    elif doc_type in ISSUE_TYPES:
        if reverse:
            add_stock(
                db, line.item_code, heat_no, line.location_id, qty, qc_status="ACCEPTED"
            )
        else:
            remove_stock(
                db, line.item_code, heat_no, line.location_id, qty, qc_status="ACCEPTED"
            )

    elif doc_type in ADJUSTMENT_TYPES:
        qc = (line.qc_status or "ACCEPTED").upper()
        if reverse:
            add_stock(
                db, line.item_code, heat_no, line.location_id, qty, qc_status=qc
            )
        else:
            remove_stock(
                db, line.item_code, heat_no, line.location_id, qty, qc_status=qc
            )

    elif doc_type in RETURN_TYPES:
        if reverse:
            add_stock(
                db, line.item_code, heat_no, line.location_id, qty, qc_status="ACCEPTED"
            )
        else:
            remove_stock(
                db, line.item_code, heat_no, line.location_id, qty, qc_status="ACCEPTED"
            )

    elif doc_type in TRANSFER_TYPES:
        dest_loc = document.to_location_id
        if dest_loc is None:
            raise ValueError("Transfer document missing destination location.")
        if reverse:
            move_stock(
                db,
                item_code=line.item_code,
                heat_no=heat_no,
                from_location_id=dest_loc,
                to_location_id=line.location_id,
                qty=qty,
                qc_status="ACCEPTED",
            )
        else:
            move_stock(
                db,
                item_code=line.item_code,
                heat_no=heat_no,
                from_location_id=line.location_id,
                to_location_id=dest_loc,
                qty=qty,
                qc_status="ACCEPTED",
            )

    else:
        raise ValueError(f"Unsupported document type: {doc_type}")


def _validate_header(db: Session, header_data: Dict, lines_data: List[Dict]) -> str:
    doc_no = (header_data.get("doc_no") or "").strip()
    if not doc_no:
        raise ValueError("Document number is required")

    existing = db.query(Document).filter(Document.doc_no == doc_no).first()
    if existing:
        raise ValueError(f"Document number '{doc_no}' already exists")

    doc_type = (header_data.get("doc_type") or "").upper().strip()
    if not doc_type:
        raise ValueError("Document type is required")
    if doc_type not in VALID_DOC_TYPES:
        raise ValueError(
            f"Unknown document type '{doc_type}'. "
            f"Supported: {', '.join(sorted(VALID_DOC_TYPES))}"
        )

    if not header_data.get("doc_date"):
        raise ValueError("Document date is required")

    if not lines_data:
        raise ValueError("Document must have at least one line item")

    for idx, line in enumerate(lines_data, start=1):
        if not line.get("item_code"):
            raise ValueError(f"Line {idx}: item code is required")
        if not line.get("location_id"):
            raise ValueError(f"Line {idx}: location is required")
        try:
            qty = float(line.get("qty", 0))
        except (TypeError, ValueError):
            raise ValueError(f"Line {idx}: quantity must be a number")
        if qty <= 0:
            raise ValueError(f"Line {idx}: quantity must be greater than zero")

    if doc_type in TRANSFER_TYPES and not header_data.get("to_location_id"):
        raise ValueError("Transfer document missing destination location.")

    return doc_type


def create_document(
    db: Session,
    header_data: Dict,
    lines_data: List[Dict]
) -> Document:
    """
    Create a document and its lines, then update inventory according to document type.
    For MIV/ISS/WOM, also applies qty to open Material Request lines (FIFO).
    """
    try:
        doc_type = _validate_header(db, header_data, lines_data)

        document = Document(
            doc_no=header_data["doc_no"].strip(),
            doc_type=doc_type,
            doc_date=header_data["doc_date"],
            po_no=header_data.get("po_no"),
            reference_no=header_data.get("reference_no"),
            delivery_note_no=header_data.get("delivery_note_no"),
            vendor_name=header_data.get("vendor_name"),
            subcontractor=header_data.get("subcontractor"),
            remarks=header_data.get("remarks"),
            from_location_id=header_data.get("from_location_id"),
            to_location_id=header_data.get("to_location_id"),
            subject=header_data.get("subject"),
            created_by=header_data.get("created_by", "system"),
            status="DRAFT"
        )
        db.add(document)
        db.flush()

        for idx, raw_line in enumerate(lines_data, start=1):
            line = _normalize_line(raw_line)
            doc_line = DocumentLine(
                document_id=document.id,
                line_number=idx,
                item_code=line["item_code"],
                heat_no=line.get("heat_no"),
                tag_no=line.get("tag_no"),
                serial_no=line.get("serial_no"),
                location_id=line["location_id"],
                qty=float(line["qty"]),
                unit=line.get("unit", "EA"),
                iso_drawing_no=line.get("iso_drawing_no"),
                cert_no=line.get("cert_no"),
                qc_status=line.get("qc_status"),
                remarks=line.get("remarks")
            )
            db.add(doc_line)
            db.flush()
            _apply_line_stock(db, document, doc_line, reverse=False)
            if doc_type in ISSUE_TYPES:
                record_issue_fulfillment(
                    db, doc_line.item_code, float(doc_line.qty or 0), reverse=False
                )

        _log_audit(
            db,
            header_data.get("created_by", "system"),
            "CREATE",
            document.doc_no,
            f"{doc_type} with {len(lines_data)} line(s)"
        )

        db.commit()
        db.refresh(document)
        return document

    except ValueError:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        raise Exception(f"Database error during document creation: {str(e)}")


def update_document_status(
    db: Session,
    document_id: int,
    new_status: str,
    approved_by: Optional[str] = None
) -> Document:
    """Update document status (DRAFT → APPROVED → CLOSED)."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document with id {document_id} not found")

    new_status = (new_status or "").upper().strip()
    valid_transitions = {
        "DRAFT": ["APPROVED", "REJECTED"],
        "APPROVED": ["CLOSED"],
        "REJECTED": ["DRAFT"],
    }

    if new_status not in valid_transitions.get(doc.status, []):
        raise ValueError(
            f"Cannot transition from {doc.status} to {new_status}. "
            f"Valid transitions: {valid_transitions.get(doc.status, [])}"
        )

    doc.status = new_status
    doc.updated_at = datetime.utcnow()

    if new_status == "APPROVED":
        doc.approved_by = approved_by
        doc.approved_at = datetime.utcnow()

    _log_audit(db, approved_by, "UPDATE", doc.doc_no, f"status → {new_status}")
    db.commit()
    db.refresh(doc)
    return doc


def get_document_by_no(db: Session, doc_no: str) -> Optional[Document]:
    return db.query(Document).filter(Document.doc_no == doc_no).first()


def get_documents_by_date(
    db: Session,
    start_date: date,
    end_date: date,
    doc_type: Optional[str] = None
) -> List[Document]:
    query = db.query(Document).filter(
        Document.doc_date.between(start_date, end_date)
    ).order_by(Document.doc_date.desc())

    if doc_type:
        query = query.filter(Document.doc_type == doc_type)

    return query.all()


def delete_document(db: Session, document_id: int) -> None:
    """Delete a DRAFT document, reverse stock, and reverse MR fulfillment if issue."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document with id {document_id} not found")

    if doc.status != "DRAFT":
        raise ValueError("Only DRAFT documents can be deleted")

    try:
        for line in reversed(list(doc.lines)):
            _apply_line_stock(db, doc, line, reverse=True)
            if doc.doc_type in ISSUE_TYPES:
                record_issue_fulfillment(
                    db, line.item_code, float(line.qty or 0), reverse=True
                )

        _log_audit(db, None, "DELETE", doc.doc_no, f"reversed {len(doc.lines)} line(s)")
        db.delete(doc)
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        raise Exception(f"Database error during document deletion: {str(e)}")
