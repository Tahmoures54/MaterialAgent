# ai/optimizer.py
"""
Inventory Optimization Module – Economic Order Quantity, Safety Stock,
Reorder Point, ABC Classification, and KPI calculations.

This module provides static methods for common inventory management
calculations used throughout iMat, with optional database integration.
"""

import math
from datetime import date, timedelta
from typing import List, Dict, Tuple, Optional, Union
from sqlalchemy import func
from db.database import SessionLocal
from db.models import Transaction, Stock, Product, Location


class InventoryOptimizer:
    """Collection of static methods for inventory optimisation."""

    # ------------------------------------------------------------------
    # Economic Order Quantity (EOQ)
    # ------------------------------------------------------------------
    @staticmethod
    def eoq(annual_demand: float,
            ordering_cost: float,
            holding_cost_per_unit: float) -> float:
        """
        Basic Economic Order Quantity (EOQ).

        Args:
            annual_demand: units demanded per year.
            ordering_cost: fixed cost per order.
            holding_cost_per_unit: cost to hold one unit for one year.

        Returns:
            Optimal order quantity (units). Returns inf if holding cost ≤ 0.
        """
        if holding_cost_per_unit <= 0:
            return float('inf')
        return math.sqrt((2 * annual_demand * ordering_cost) / holding_cost_per_unit)

    @staticmethod
    def eoq_with_shortages(annual_demand: float,
                           ordering_cost: float,
                           holding_cost_per_unit: float,
                           shortage_cost_per_unit: float) -> Tuple[float, float]:
        """
        EOQ when backorders are allowed (planned shortages).

        Returns:
            (optimal_order_quantity, maximum_shortage_quantity)
        """
        if holding_cost_per_unit <= 0 or shortage_cost_per_unit <= 0:
            return (float('inf'), 0)
        ratio = shortage_cost_per_unit / (holding_cost_per_unit + shortage_cost_per_unit)
        Q = math.sqrt((2 * annual_demand * ordering_cost) /
                      (holding_cost_per_unit * ratio))
        S = Q * (holding_cost_per_unit / (holding_cost_per_unit + shortage_cost_per_unit))
        return Q, S

    # ------------------------------------------------------------------
    # Safety Stock & Reorder Point
    # ------------------------------------------------------------------
    @staticmethod
    def safety_stock_simple(max_lead_time_days: float,
                            avg_lead_time_days: float,
                            avg_daily_demand: float) -> float:
        """Simple safety stock based on maximum lead time."""
        return max(0.0, (max_lead_time_days - avg_lead_time_days)) * avg_daily_demand

    @staticmethod
    def safety_stock_service_level(service_level: float,
                                   demand_std_dev: float,
                                   lead_time_days: float) -> float:
        """
        Safety stock for a given service level assuming demand is normally distributed.

        Args:
            service_level: desired probability of not stocking out (0.0 – 1.0).
            demand_std_dev: standard deviation of daily demand.
            lead_time_days: lead time in days.

        Returns:
            Safety stock quantity.
        """
        z_map = {
            0.90: 1.28,
            0.95: 1.645,
            0.99: 2.33,
        }
        z = z_map.get(round(service_level, 2))
        if z is None:
            if service_level >= 0.99:
                z = 2.33
            elif service_level >= 0.95:
                z = 1.645
            elif service_level >= 0.90:
                z = 1.28
            else:
                z = 0.84  # ~80%
        return z * demand_std_dev * math.sqrt(lead_time_days)

    @staticmethod
    def reorder_point(lead_time_days: float,
                      avg_daily_demand: float,
                      safety_stock: float = 0.0) -> float:
        """Reorder point = (lead time * avg daily demand) + safety stock."""
        return lead_time_days * avg_daily_demand + safety_stock

    @staticmethod
    def recommended_order_quantity(current_stock: float,
                                   reorder_point: float,
                                   eoq: float,
                                   min_order_qty: float = 0.0) -> float:
        """
        Recommend how much to order given current stock and reorder point.
        Returns the quantity to raise stock up to reorder_point + eoq.
        """
        target = reorder_point + eoq
        order_qty = max(0.0, target - current_stock)
        return max(order_qty, min_order_qty)

    # ------------------------------------------------------------------
    # ABC Analysis
    # ------------------------------------------------------------------
    @staticmethod
    def abc_classification(items_with_value: List[Tuple[str, float]],
                           a_percent: float = 0.7,
                           b_percent: float = 0.9) -> Dict[str, str]:
        """
        Classify items into A, B, C based on cumulative annual usage value.

        Args:
            items_with_value: list of (item_code, annual_value).
            a_percent: cumulative percentage for class A (default 0.7).
            b_percent: cumulative percentage for class B (default 0.9).

        Returns:
            Dict mapping item_code to 'A', 'B', or 'C'.
        """
        if not items_with_value:
            return {}
        sorted_items = sorted(items_with_value, key=lambda x: x[1], reverse=True)
        total_value = sum(v for _, v in sorted_items)
        cumulative = 0.0
        classification = {}
        for index, (item, val) in enumerate(sorted_items):
            cumulative += val
            cum_ratio = cumulative / total_value if total_value > 0 else 0
            if index == 0 or cum_ratio <= a_percent:
                classification[item] = 'A'
            elif cum_ratio <= b_percent:
                classification[item] = 'B'
            else:
                classification[item] = 'C'
        return classification

    # ------------------------------------------------------------------
    # KPI Calculations
    # ------------------------------------------------------------------
    @staticmethod
    def calculate_kpi(inventory_data: List[Dict]) -> Dict:
        """
        Calculate key inventory KPIs.

        Each item in inventory_data should be a dict with:
            'inventory': current stock level
            'annual_demand': total annual demand
            'unit_cost': cost per unit (optional, default 0)

        Returns dict with total_inventory_value, inventory_turnover_ratio,
        and days_of_inventory.
        """
        total_value = 0.0
        total_demand_cost = 0.0
        for item in inventory_data:
            inv = float(item.get('inventory', 0))
            demand = float(item.get('annual_demand', 0))
            cost = float(item.get('unit_cost', 0))
            total_value += inv * cost
            total_demand_cost += demand * cost

        if total_value == 0:
            turnover = 0.0
        else:
            turnover = total_demand_cost / total_value

        if turnover > 0:
            days_of_inventory = 365.0 / turnover
        else:
            days_of_inventory = float('inf')

        return {
            'total_inventory_value': total_value,
            'inventory_turnover_ratio': turnover,
            'days_of_inventory': days_of_inventory
        }


# ------------------------------------------------------------------
# Database helpers (kept outside the class for easy reuse)
# ------------------------------------------------------------------
def get_annual_demand(item_code: str, session=None, year: Optional[int] = None) -> float:
    """
    Return the total issued quantity for an item over a given year.

    Args:
        item_code: material code.
        session: SQLAlchemy session (if None, a temporary session is used).
        year: target year (default: current year).

    Returns:
        Sum of issued quantities (float).
    """
    if year is None:
        year = date.today().year
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        result = session.query(func.sum(Transaction.issue_qty)).filter(
            Transaction.item_code == item_code,
            Transaction.doc_type.in_(['MIV', 'ISS', 'WOM', 'GAT']),
            Transaction.doc_date.between(start_date, end_date)
        ).scalar()
        return result or 0.0
    finally:
        if close_session:
            session.close()


def get_daily_demand_stats(item_code: str, session=None, days: int = 90) -> Tuple[float, float]:
    """
    Calculate average daily demand and standard deviation over the last `days`.

    Returns:
        (avg_daily_demand, daily_std_dev)
    """
    if session is None:
        session = SessionLocal()
        close_session = True
    else:
        close_session = False

    try:
        start_date = date.today() - timedelta(days=days)
        records = session.query(
            Transaction.doc_date,
            func.sum(Transaction.issue_qty)
        ).filter(
            Transaction.item_code == item_code,
            Transaction.doc_type.in_(['MIV', 'ISS', 'WOM', 'GAT']),
            Transaction.doc_date >= start_date
        ).group_by(Transaction.doc_date).order_by(Transaction.doc_date).all()

        if not records:
            return 0.0, 0.0

        daily_demands = [qty for _, qty in records]
        avg = sum(daily_demands) / len(daily_demands)
        variance = sum((d - avg) ** 2 for d in daily_demands) / len(daily_demands)
        std_dev = math.sqrt(variance)
        return avg, std_dev
    finally:
        if close_session:
            session.close()


def get_current_stock(item_code: str, session=None) -> float:
    """
    Get current available stock for an item (sum of available quantity from Stock).
    Only considers ACCEPTED QC status for available stock.
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True
    try:
        total = session.query(func.sum(Stock.quantity - Stock.allocated_qty)).filter(
            Stock.item_code == item_code,
            Stock.qc_status == 'ACCEPTED'
        ).scalar()
        return total or 0.0
    finally:
        if close_session:
            session.close()


def get_unit_cost(item_code: str, session=None) -> float:
    """Get the unit cost from the Product master (placeholder; can be extended)."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True
    try:
        product = session.query(Product).filter_by(item_code=item_code).first()
        # In real app, you might have a cost field. Fallback to 1.0
        return product.unit_cost if hasattr(product, 'unit_cost') else 1.0
    finally:
        if close_session:
            session.close()


def generate_replenishment_plan(session, items: List[str], lead_time_days: float = 7,
                                service_level: float = 0.95) -> List[Dict]:
    """
    Create a recommended order list for given items.

    Returns list of dicts with keys:
        item_code, current_stock, avg_daily_demand, safety_stock,
        reorder_point, eoq, recommended_order_qty
    """
    plan = []
    for item_code in items:
        # Retrieve current stock from Stock table (available ACCEPTED only)
        current_stock = get_current_stock(item_code, session)
        if current_stock == 0:
            continue  # skip items with no accepted stock; they may need reorder anyway

        avg_demand, std_dev = get_daily_demand_stats(item_code, session)
        if avg_demand == 0:
            continue

        # Estimate annual demand
        annual_demand = avg_demand * 365
        # Simple ordering & holding cost assumptions (can be configured)
        ordering_cost = 50.0
        unit_cost = get_unit_cost(item_code, session)
        holding_cost_per_unit = unit_cost * 0.1  # assume 10% holding cost

        eoq = InventoryOptimizer.eoq(annual_demand, ordering_cost, holding_cost_per_unit)
        safety = InventoryOptimizer.safety_stock_service_level(service_level, std_dev, lead_time_days)
        reorder = InventoryOptimizer.reorder_point(lead_time_days, avg_demand, safety)
        recommend = InventoryOptimizer.recommended_order_quantity(current_stock, reorder, eoq)

        plan.append({
            'item_code': item_code,
            'current_stock': round(current_stock, 2),
            'avg_daily_demand': round(avg_demand, 2),
            'safety_stock': round(safety, 2),
            'reorder_point': round(reorder, 2),
            'eoq': round(eoq, 2),
            'recommended_order_qty': round(recommend, 2)
        })
    return plan