# logic/location_logic.py
"""
Location management business logic.
Handles warehouse hierarchy CRUD operations.
"""

from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from db.models import Location


def create_location(
    db: Session,
    code: str,
    name: str,
    loc_type: str,
    parent_id: Optional[int] = None,
    description: str = "",
    capacity: str = "",
    notes: str = ""
) -> Location:
    """
    Create a new physical location (warehouse, yard, shelf, bin, etc.).
    
    Args:
        db: Database session
        code: Unique location code (e.g., WH-A, RACK-01)
        name: Human-readable name
        loc_type: Location type (WAREHOUSE, OPEN_YARD, RACK, BIN, QUARANTINE)
        parent_id: Parent location ID for hierarchy
        description: Optional description
        capacity: Storage capacity description
        notes: Additional notes
        
    Returns:
        Created Location object
        
    Raises:
        ValueError: If location code already exists or parent not found
    """
    existing = db.query(Location).filter(Location.code == code).first()
    if existing:
        raise ValueError(f"A location with code '{code}' already exists.")
    
    if parent_id:
        parent = db.query(Location).filter(Location.id == parent_id).first()
        if not parent:
            raise ValueError(f"Parent location with ID {parent_id} not found.")

    new_loc = Location(
        code=code,
        name=name,
        location_type=loc_type,
        parent_id=parent_id,
        description=description,
        capacity=capacity,
        notes=notes
    )
    db.add(new_loc)
    db.commit()
    db.refresh(new_loc)
    return new_loc


def get_all_locations(db: Session) -> List[Location]:
    """Retrieve all active locations ordered by code."""
    return db.query(Location).filter(
        Location.is_active == True
    ).order_by(Location.code).all()


def get_location_by_code(db: Session, code: str) -> Optional[Location]:
    """Get a location by its unique code."""
    return db.query(Location).filter(Location.code == code).first()


def get_location_by_id(db: Session, loc_id: int) -> Optional[Location]:
    """Get a location by its ID."""
    return db.query(Location).filter(Location.id == loc_id).first()


def update_location(db: Session, location_id: int, **kwargs) -> Location:
    """
    Update an existing location.
    
    Args:
        db: Database session
        location_id: Location ID
        **kwargs: Fields to update
        
    Returns:
        Updated Location object
        
    Raises:
        ValueError: If location not found
    """
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise ValueError(f"Location with id {location_id} not found")

    for attr, value in kwargs.items():
        if hasattr(Location, attr):
            setattr(loc, attr, value)
    db.commit()
    db.refresh(loc)
    return loc


def delete_location(db: Session, location_id: int) -> None:
    """
    Soft-delete a location by setting is_active=False.
    Cannot delete if location has stock or children.
    
    Args:
        db: Database session
        location_id: Location ID
        
    Raises:
        ValueError: If location has stock, children, or not found
    """
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise ValueError(f"Location with id {location_id} not found")
    
    # Check for active stock
    if loc.stocks and any(s.quantity > 0 for s in loc.stocks):
        raise ValueError(
            f"Cannot delete location '{loc.code}' - it contains active stock."
        )
    
    # Check for children
    children = db.query(Location).filter(
        Location.parent_id == location_id,
        Location.is_active == True
    ).all()
    if children:
        child_codes = ', '.join(c.code for c in children)
        raise ValueError(
            f"Cannot delete location '{loc.code}' - "
            f"it has active children: {child_codes}"
        )
    
    # Soft delete
    loc.is_active = False
    db.commit()


def get_location_tree(db: Session) -> List[Dict]:
    """
    Build a hierarchical location tree for display.
    
    Returns:
        Nested list of dicts with id, code, name, type, children
    """
    locations = get_all_locations(db)
    
    # Create lookup dictionary
    lookup = {}
    for loc in locations:
        lookup[loc.id] = {
            "id": loc.id,
            "code": loc.code,
            "name": loc.name,
            "type": loc.location_type,
            "description": loc.description,
            "capacity": loc.capacity,
            "children": []
        }
    
    # Build tree
    tree = []
    for loc in locations:
        node = lookup[loc.id]
        if loc.parent_id and loc.parent_id in lookup:
            lookup[loc.parent_id]["children"].append(node)
        else:
            tree.append(node)
    
    return tree


def get_location_path(db: Session, location_id: int) -> str:
    """
    Get the full path of a location (e.g., "WH-A > RACK-01 > BIN-03").
    
    Args:
        db: Database session
        location_id: Location ID
        
    Returns:
        Full path string
    """
    loc = get_location_by_id(db, location_id)
    if not loc:
        return ""
    return loc.full_path