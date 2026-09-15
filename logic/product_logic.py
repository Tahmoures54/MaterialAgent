# logic/product_logic.py
"""
Product master data management logic.
Handles CRUD operations for the material coding system.
"""

from sqlalchemy.orm import Session
from sqlalchemy import exc, or_
from typing import List, Dict, Optional
from db.models import Product


def create_product(db: Session, product_data: Dict) -> Product:
    """
    Create a new product in the engineering catalog.
    
    Args:
        db: Database session
        product_data: Dict with Product model fields
        
    Returns:
        Created Product object
        
    Raises:
        ValueError: If product code already exists or required fields are missing
    """
    item_code = (product_data.get("item_code") or "").strip()
    if not item_code:
        raise ValueError("Item code is required")
    product_data = dict(product_data)
    product_data["item_code"] = item_code

    try:
        new_product = Product(**product_data)
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        return new_product
    except exc.IntegrityError:
        db.rollback()
        raise ValueError(
            f"Product code '{product_data.get('item_code')}' already exists."
        )


def update_product(db: Session, item_code: str, update_data: Dict) -> Product:
    """
    Update product information.
    
    Args:
        db: Database session
        item_code: Product item code
        update_data: Dict with fields to update
        
    Returns:
        Updated Product object
        
    Raises:
        ValueError: If product not found
    """
    product = db.query(Product).filter(Product.item_code == item_code).first()
    if not product:
        raise ValueError(f"Product with code '{item_code}' not found.")
    
    for key, value in update_data.items():
        if key == "id":
            continue
        if hasattr(product, key):
            setattr(product, key, value)
        
    db.commit()
    db.refresh(product)
    return product


def get_product(db: Session, item_code: str) -> Optional[Product]:
    """Get a product by item code."""
    return db.query(Product).filter(Product.item_code == item_code).first()


def get_all_products(db: Session) -> List[Product]:
    """Get all active products."""
    return db.query(Product).order_by(Product.item_code).all()


def search_products(
    db: Session, 
    search_text: Optional[str] = None,
    discipline: Optional[str] = None,
    category: Optional[str] = None,
    lifecycle_status: Optional[str] = None,
    limit: int = 500
) -> List[Product]:
    """
    Search products with filters.
    
    Args:
        db: Database session
        search_text: Search in item_code and description
        discipline: Filter by discipline
        category: Filter by category
        lifecycle_status: Filter by lifecycle status
        limit: Maximum results
        
    Returns:
        List of Product objects
    """
    query = db.query(Product)
    
    if search_text:
        pattern = f'%{search_text}%'
        query = query.filter(
            or_(
                Product.item_code.ilike(pattern),
                Product.description.ilike(pattern),
                Product.part_number.ilike(pattern)
            )
        )
    
    if discipline:
        query = query.filter(Product.discipline == discipline)
    
    if category:
        query = query.filter(Product.category == category)
    
    if lifecycle_status:
        query = query.filter(Product.lifecycle_status == lifecycle_status)
    
    return query.order_by(Product.item_code).limit(limit).all()


def delete_product(db: Session, item_code: str) -> None:
    """
    Delete a product from the catalog.
    Only possible if no stock or transactions exist.
    
    Args:
        db: Database session
        item_code: Product item code
        
    Raises:
        ValueError: If product not found or has existing stock/transactions
    """
    product = db.query(Product).filter(Product.item_code == item_code).first()
    if not product:
        raise ValueError(f"Product with code '{item_code}' not found.")
    
    # Check for existing stock
    if product.stocks and any(s.quantity > 0 for s in product.stocks):
        raise ValueError(
            f"Cannot delete product '{item_code}' - it has existing stock."
        )
    
    # Check for existing transactions
    if product.transactions:
        raise ValueError(
            f"Cannot delete product '{item_code}' - it has transaction history."
        )
    
    db.delete(product)
    db.commit()


def get_product_stats(db: Session) -> Dict:
    """
    Get product catalog statistics.
    
    Returns:
        Dict with counts by discipline, category, status
    """
    from sqlalchemy import func
    
    total = db.query(func.count(Product.id)).scalar() or 0
    active = db.query(func.count(Product.id)).filter(
        Product.lifecycle_status == 'ACTIVE'
    ).scalar() or 0
    
    # By discipline
    disciplines = {}
    results = db.query(
        Product.discipline, 
        func.count(Product.id)
    ).group_by(Product.discipline).all()
    for disc, count in results:
        if disc:
            disciplines[disc] = count
    
    return {
        "total": total,
        "active": active,
        "obsolete": total - active,
        "by_discipline": disciplines
    }