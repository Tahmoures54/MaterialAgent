# logic/document_logic.py
"""
Business logic for creating warehouse documents and updating inventory.
Supports all common EPC material document types with appropriate stock changes.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import date, datetime
from typing import Dict, List, Optional
from db.models import Document, DocumentLine
from logic.stock_logic import add_stock, remove_stock, move_stock


# Document type categories
RECEIPT_TYPES = {"MRR", "RCT", "MRV"}
ISSUE_TYPES = {"MIV", "ISS", "WOM"}
TRANSFER_TYPES = {"MTR", "TRN"}
RETURN_TYPES = {"RTV", "SRN"}
ADJUSTMENT_TYPES = {"OSND", "ADJ"}
NO_STOCK_CHANGE = {"MSR", "RES", "GAT"}


def create_document(
    db: Session, 
    header_data: Dict, 
    lines_data: List[Dict]
) -> Document:
    """
    Create a document and its lines, then update inventory according to document type.

    Supported document types and their inventory effects:
        MRR, RCT  – receipt into QUARANTINE
        MIV, ISS, WOM – issue from ACCEPTED stock
        MSR, RES, GAT – no stock change
        OSND – over/short/damaged adjustment (remove stock)
        MTR, TRN – transfer between locations
        RTV, SRN – return to vendor (remove from ACCEPTED)
        MRV – return from site (add to ACCEPTED)
        ADJ – generic adjustment
        
    Args:
        db: Database session
        header_data: Document header dict with keys:
            doc_no, doc_type, doc_date, po_no, reference_no, 
            remarks, from_location_id, to_location_id, created_by
        lines_data: List of line item dicts with keys:
            item_code, heat_no, location_id, qty, unit, 
            iso_drawing_no, cert_no, qc_status
            
    Returns:
        Created Document object
        
    Raises:
        ValueError: If validation fails
        SQLAlchemyError: If database operation fails
    """
    try:
        # --- Build document header ---
        document = Document(
            doc_no=header_data["doc_no"],
            doc_type=header_data["doc_type"],
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
        db.flush()  # Get document.id

        doc_type = document.doc_type.upper().strip()

        # --- Process each line ---
        for idx, line in enumerate(lines_data, start=1):
            # Create the DocumentLine record
            doc_line = DocumentLine(
                document_id=document.id,
                line_number=idx,
                item_code=line["item_code"],
                heat_no=line.get("heat_no"),
                tag_no=line.get("tag_no"),
                serial_no=line.get("serial_no"),
                location_id=line["location_id"],
                qty=line["qty"],
                unit=line.get("unit", "EA"),
                iso_drawing_no=line.get("iso_drawing_no"),
                cert_no=line.get("cert_no"),
                qc_status=line.get("qc_status"),
                remarks=line.get("remarks")
            )
            db.add(doc_line)

            # --- Inventory update based on document type ---
            if doc_type in RECEIPT_TYPES:
                # Receipt: add to QUARANTINE (or ACCEPTED for MRV)
                qc = "ACCEPTED" if doc_type == "MRV" else "QUARANTINE"
                add_stock(
                    db=db,
                    item_code=doc_line.item_code,
                    heat_no=doc_line.heat_no,
                    location_id=doc_line.location_id,
                    qty=doc_line.qty,
                    qc_status=qc,
                    tag_no=doc_line.tag_no,
                    serial_no=doc_line.serial_no
                )

            elif doc_type in ISSUE_TYPES:
                # Issue: remove from ACCEPTED stock
                remove_stock(
                    db=db,
                    item_code=doc_line.item_code,
                    heat_no=doc_line.heat_no,
                    location_id=doc_line.location_id,
                    qty=doc_line.qty,
                    qc_status="ACCEPTED"
                )

            elif doc_type in NO_STOCK_CHANGE:
                # Requisition / Reservation / Gate Pass – no stock change
                pass

            elif doc_type in ADJUSTMENT_TYPES:
                # OSND: remove damaged/short stock
                remove_stock(
                    db=db,
                    item_code=doc_line.item_code,
                    heat_no=doc_line.heat_no,
                    location_id=doc_line.location_id,
                    qty=doc_line.qty,
                    qc_status=doc_line.qc_status or "ACCEPTED"
                )

            elif doc_type in RETURN_TYPES:
                # Return to vendor: remove from ACCEPTED
                remove_stock(
                    db=db,
                    item_code=doc_line.item_code,
                    heat_no=doc_line.heat_no,
                    location_id=doc_line.location_id,
                    qty=doc_line.qty,
                    qc_status="ACCEPTED"
                )

            elif doc_type in TRANSFER_TYPES:
                # Transfer between locations
                dest_loc = document.to_location_id
                if dest_loc is None:
                    raise ValueError("Transfer document missing destination location.")
                move_stock(
                    db=db,
                    item_code=doc_line.item_code,
                    heat_no=doc_line.heat_no,
                    from_location_id=doc_line.location_id,
                    to_location_id=dest_loc,
                    qty=doc_line.qty,
                    qc_status="ACCEPTED"
                )

        db.commit()
        db.refresh(document)
        return document

    except ValueError as e:
        db.rollback()
        raise e
    except SQLAlchemyError as e:
        db.rollback()
        raise Exception(f"Database error during document creation: {str(e)}")


def update_document_status(
    db: Session, 
    document_id: int, 
    new_status: str, 
    approved_by: Optional[str] = None
) -> Document:
    """
    Update document status (DRAFT → APPROVED → CLOSED).
    
    Args:
        db: Database session
        document_id: Document ID
        new_status: New status (APPROVED, REJECTED, CLOSED)
        approved_by: Username of approver
        
    Returns:
        Updated Document object
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document with id {document_id} not found")
    
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
    
    db.commit()
    db.refresh(doc)
    return doc


def get_document_by_no(db: Session, doc_no: str) -> Optional[Document]:
    """Get a document by its number."""
    return db.query(Document).filter(Document.doc_no == doc_no).first()


def get_documents_by_date(
    db: Session, 
    start_date: date, 
    end_date: date,
    doc_type: Optional[str] = None
) -> List[Document]:
    """Get documents within a date range, optionally filtered by type."""
    query = db.query(Document).filter(
        Document.doc_date.between(start_date, end_date)
    ).order_by(Document.doc_date.desc())
    
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)
    
    return query.all()


def delete_document(db: Session, document_id: int) -> None:
    """
    Delete a document and its lines.
    Only DRAFT documents can be deleted.
    
    Args:
        db: Database session
        document_id: Document ID
        
    Raises:
        ValueError: If document not found or not in DRAFT status
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document with id {document_id} not found")
    
    if doc.status != "DRAFT":
        raise ValueError("Only DRAFT documents can be deleted")
    
    db.delete(doc)
    db.commit()