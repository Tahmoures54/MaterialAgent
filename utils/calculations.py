# utils/calculations.py
"""
Inventory Calculation Utilities – iMat Material Control System (EPC Edition).

Comprehensive inventory management calculations including:
- Economic Order Quantity (EOQ)
- Reorder Point (ROP)
- Safety Stock (multiple methods)
- Inventory Turnover Ratio
- Days of Inventory
- ABC Classification
- Carrying Cost Calculation
- Order Cycle Time
- Fill Rate
- Stockout Probability
- Service Level Optimization
- Demand Forecasting Metrics
"""

import math
from typing import List, Dict, Tuple, Optional, Union


# ==================================================================
# Economic Order Quantity (EOQ)
# ==================================================================

def calculate_eoq(
    annual_demand: float,
    ordering_cost: float,
    holding_cost_per_unit: float
) -> float:
    """
    Calculate Economic Order Quantity (EOQ).
    
    Formula: EOQ = sqrt((2 * D * S) / H)
    
    Args:
        annual_demand: Annual demand in units (D)
        ordering_cost: Cost per order (S)
        holding_cost_per_unit: Annual holding cost per unit (H)
    
    Returns:
        Optimal order quantity in units.
        Returns infinity if holding cost is zero or negative.
        Returns 0 if annual demand is 0.
    
    Example:
        >>> calculate_eoq(1000, 50, 2)
        223.6
    """
    if annual_demand <= 0:
        return 0.0
    
    if holding_cost_per_unit <= 0:
        return float('inf')
    
    return math.sqrt((2 * annual_demand * ordering_cost) / holding_cost_per_unit)


def calculate_eoq_with_shortages(
    annual_demand: float,
    ordering_cost: float,
    holding_cost_per_unit: float,
    shortage_cost_per_unit: float
) -> Tuple[float, float]:
    """
    Calculate EOQ when backorders (planned shortages) are allowed.
    
    Args:
        annual_demand: Annual demand in units
        ordering_cost: Cost per order
        holding_cost_per_unit: Annual holding cost per unit
        shortage_cost_per_unit: Annual shortage cost per unit
    
    Returns:
        Tuple of (optimal_order_quantity, maximum_shortage_quantity)
    """
    if holding_cost_per_unit <= 0 or shortage_cost_per_unit <= 0:
        return (float('inf'), 0)
    
    ratio = shortage_cost_per_unit / (holding_cost_per_unit + shortage_cost_per_unit)
    Q = math.sqrt((2 * annual_demand * ordering_cost) / (holding_cost_per_unit * ratio))
    S = Q * (holding_cost_per_unit / (holding_cost_per_unit + shortage_cost_per_unit))
    
    return Q, S


# ==================================================================
# Reorder Point (ROP)
# ==================================================================

def calculate_reorder_point(
    lead_time_days: float,
    avg_daily_demand: float,
    safety_stock: float = 0.0
) -> float:
    """
    Calculate Reorder Point (ROP).
    
    Formula: ROP = (Lead Time * Average Daily Demand) + Safety Stock
    
    Args:
        lead_time_days: Lead time in days
        avg_daily_demand: Average daily demand
        safety_stock: Safety stock quantity
    
    Returns:
        Reorder point quantity
    
    Example:
        >>> calculate_reorder_point(7, 20, 30)
        170.0
    """
    return (lead_time_days * avg_daily_demand) + safety_stock


# ==================================================================
# Safety Stock
# ==================================================================

def calculate_safety_stock_simple(
    max_daily_demand: float,
    avg_daily_demand: float,
    max_lead_time_days: float,
    avg_lead_time_days: float
) -> float:
    """
    Calculate safety stock using the simple (max-min) method.
    
    Formula: SS = (Max Daily Demand * Max Lead Time) - (Avg Daily Demand * Avg Lead Time)
    
    Args:
        max_daily_demand: Maximum daily demand
        avg_daily_demand: Average daily demand
        max_lead_time_days: Maximum lead time in days
        avg_lead_time_days: Average lead time in days
    
    Returns:
        Safety stock quantity
    """
    max_demand = max_daily_demand * max_lead_time_days
    avg_demand = avg_daily_demand * avg_lead_time_days
    return max(0.0, max_demand - avg_demand)


def calculate_safety_stock_service_level(
    z_score: float,
    demand_std: float,
    lead_time_days: float,
    lead_time_std: float = 0.0
) -> float:
    """
    Calculate safety stock based on desired service level (Z-score method).
    
    Formula: SS = Z * sqrt(LT * σd²)
    
    Args:
        z_score: Z-score for desired service level
        demand_std: Standard deviation of demand
        lead_time_days: Average lead time in days
        lead_time_std: Standard deviation of lead time (0 if constant)
    
    Returns:
        Safety stock quantity
    
    Example:
        >>> calculate_safety_stock_service_level(1.65, 5, 7)
        21.8
    """
    variance = lead_time_days * (demand_std ** 2)
    
    if lead_time_std > 0:
        variance += (lead_time_std ** 2) * (demand_std ** 2)
    
    return z_score * math.sqrt(variance)


def calculate_safety_stock_fixed(quantity: float) -> float:
    """
    Use a fixed safety stock quantity.
    
    Args:
        quantity: Fixed safety stock quantity
    
    Returns:
        Safety stock quantity
    """
    return max(0.0, quantity)


def calculate_safety_stock_percentage(
    lead_time_days: float,
    avg_daily_demand: float,
    percentage: float
) -> float:
    """
    Calculate safety stock as percentage of lead time demand.
    
    Args:
        lead_time_days: Lead time in days
        avg_daily_demand: Average daily demand
        percentage: Percentage as decimal (e.g., 0.20 for 20%)
    
    Returns:
        Safety stock quantity
    """
    lead_time_demand = lead_time_days * avg_daily_demand
    return lead_time_demand * percentage


def get_z_score(service_level: float) -> float:
    """
    Get Z-score for a given service level.
    
    Args:
        service_level: Desired service level (0.0 to 1.0)
    
    Returns:
        Corresponding Z-score
    """
    z_scores = {
        0.50: 0.00, 0.55: 0.13, 0.60: 0.25, 0.65: 0.39,
        0.70: 0.52, 0.75: 0.67, 0.80: 0.84, 0.85: 1.04,
        0.90: 1.28, 0.91: 1.34, 0.92: 1.41, 0.93: 1.48,
        0.94: 1.55, 0.95: 1.645, 0.96: 1.75, 0.97: 1.88,
        0.98: 2.05, 0.99: 2.33, 0.995: 2.58, 0.999: 3.09,
    }
    
    closest = min(z_scores.keys(), key=lambda x: abs(x - service_level))
    return z_scores[closest]


# ==================================================================
# Inventory Performance Metrics
# ==================================================================

def calculate_inventory_turnover(
    cost_of_goods_sold: float = 0.0,
    average_inventory_value: float = None,
    cogs: float = None,
    average_inventory: float = None,
) -> float:
    """
    Calculate Inventory Turnover Ratio.

    Formula: Turnover = COGS / Average Inventory Value

    Accepts either positional names (cost_of_goods_sold, average_inventory_value)
    or the shorter aliases used by older callers (cogs, average_inventory).
    """
    cogs_value = cost_of_goods_sold if cogs is None else cogs
    inventory_value = (
        average_inventory_value if average_inventory is None else average_inventory
    )
    if inventory_value is None:
        inventory_value = 0.0
    if inventory_value <= 0:
        return 0.0
    return cogs_value / inventory_value


def calculate_days_of_inventory(
    inventory_turnover: float,
    days_in_period: int = 365
) -> float:
    """
    Calculate Days of Inventory (DOI).
    
    Formula: DOI = Days in Period / Inventory Turnover
    
    Args:
        inventory_turnover: Inventory turnover ratio
        days_in_period: Number of days in the period
    
    Returns:
        Days of inventory on hand
    """
    if inventory_turnover <= 0:
        return float('inf')
    return days_in_period / inventory_turnover


# ==================================================================
# ABC Analysis
# ==================================================================

def abc_classification(
    items_with_value: List[Tuple[str, float]],
    a_threshold: float = 0.70,
    b_threshold: float = 0.90
) -> Dict[str, str]:
    """
    Classify items into A, B, C categories based on cumulative value.
    
    Pareto principle: Typically 20% of items account for 80% of value.
    
    Args:
        items_with_value: List of (item_code, annual_value) tuples
        a_threshold: Cumulative percentage for Class A (default: 0.70 = 70%)
        b_threshold: Cumulative percentage for Class B (default: 0.90 = 90%)
    
    Returns:
        Dictionary mapping item_code to class ('A', 'B', or 'C')
    
    Example:
        >>> items = [("ITEM1", 5000), ("ITEM2", 3000), ("ITEM3", 1500), ("ITEM4", 500)]
        >>> abc_classification(items)
        {'ITEM1': 'A', 'ITEM2': 'B', 'ITEM3': 'C', 'ITEM4': 'C'}
    """
    if not items_with_value:
        return {}
    
    sorted_items = sorted(items_with_value, key=lambda x: x[1], reverse=True)
    total_value = sum(val for _, val in sorted_items)
    
    if total_value <= 0:
        return {item: 'C' for item, _ in sorted_items}
    
    classification = {}
    cumulative = 0.0
    
    for index, (item, val) in enumerate(sorted_items):
        cumulative += val
        cumulative_pct = cumulative / total_value
        
        if index == 0 or cumulative_pct <= a_threshold:
            classification[item] = 'A'
        elif cumulative_pct <= b_threshold:
            classification[item] = 'B'
        else:
            classification[item] = 'C'
    
    return classification


# ==================================================================
# Forecast Accuracy Metrics
# ==================================================================

def calculate_mae(actual: List[float], forecast: List[float]) -> float:
    """Calculate Mean Absolute Error (MAE)."""
    if len(actual) != len(forecast) or len(actual) == 0:
        return 0.0
    errors = [abs(a - f) for a, f in zip(actual, forecast)]
    return sum(errors) / len(errors)


def calculate_mse(actual: List[float], forecast: List[float]) -> float:
    """Calculate Mean Squared Error (MSE)."""
    if len(actual) != len(forecast) or len(actual) == 0:
        return 0.0
    errors = [(a - f) ** 2 for a, f in zip(actual, forecast)]
    return sum(errors) / len(errors)


def calculate_rmse(actual: List[float], forecast: List[float]) -> float:
    """Calculate Root Mean Squared Error (RMSE)."""
    return math.sqrt(calculate_mse(actual, forecast))


# ==================================================================
# Demand Statistics
# ==================================================================

def calculate_mean(demand_data: List[float]) -> float:
    """Calculate mean (average) of demand data."""
    if not demand_data:
        return 0.0
    return sum(demand_data) / len(demand_data)


def calculate_std_dev(demand_data: List[float]) -> float:
    """Calculate standard deviation of demand data."""
    if len(demand_data) < 2:
        return 0.0
    mean = calculate_mean(demand_data)
    variance = sum((x - mean) ** 2 for x in demand_data) / len(demand_data)
    return math.sqrt(variance)


# ==================================================================
# Backward Compatibility Aliases (IMPORTANT!)
# ==================================================================
# این خطوط برای سازگاری با کدهای قدیمی اضافه شده‌اند
# DO NOT REMOVE these aliases

def calculate_safety_stock(*args, **kwargs):
    """
    Backward-compatible safety stock helper.

    Supports the service-level signature and the older keyword form:
        z_score, lead_time_std, avg_demand_std, avg_lead_time
    """
    if "avg_demand_std" in kwargs or "avg_lead_time" in kwargs:
        z_score = kwargs.get("z_score", 1.65)
        lead_time_std = float(kwargs.get("lead_time_std") or 0.0)
        avg_demand_std = float(kwargs.get("avg_demand_std") or 0.0)
        avg_lead_time = float(kwargs.get("avg_lead_time") or 0.0)
        return z_score * avg_demand_std * (lead_time_std + avg_lead_time)
    return calculate_safety_stock_service_level(*args, **kwargs)

# ==================================================================
# Module Exports
# ==================================================================

__all__ = [
    # EOQ
    'calculate_eoq',
    'calculate_eoq_with_shortages',
    
    # Reorder Point
    'calculate_reorder_point',
    
    # Safety Stock
    'calculate_safety_stock',                    # Alias for backward compatibility
    'calculate_safety_stock_simple',
    'calculate_safety_stock_service_level',
    'calculate_safety_stock_fixed',
    'calculate_safety_stock_percentage',
    'get_z_score',
    
    # Performance Metrics
    'calculate_inventory_turnover',
    'calculate_days_of_inventory',
    
    # ABC Analysis
    'abc_classification',
    
    # Forecast Accuracy
    'calculate_mae',
    'calculate_mse',
    'calculate_rmse',
    
    # Demand Statistics
    'calculate_mean',
    'calculate_std_dev',
]