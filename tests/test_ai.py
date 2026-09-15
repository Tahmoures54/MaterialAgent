# tests/test_ai.py
"""
Tests for AI modules: DemandPredictor and InventoryOptimizer.
"""

import pytest
from datetime import date, timedelta
from ai.predictor import DemandPredictor
from ai.optimizer import InventoryOptimizer


class TestDemandPredictor:
    """Test demand prediction algorithms."""

    def test_moving_average(self):
        """Test simple moving average."""
        predictor = DemandPredictor([10, 20, 30, 40, 50])
        ma = predictor.moving_average(window=3)
        assert ma == 40  # Average of 30, 40, 50

    def test_moving_average_empty_data(self):
        """Test moving average with empty data."""
        predictor = DemandPredictor([])
        assert predictor.moving_average() == 0.0

    def test_moving_average_window_larger_than_data(self):
        """Test moving average when window > data length."""
        predictor = DemandPredictor([10, 20])
        ma = predictor.moving_average(window=10)
        assert ma == 15  # Average of all available data

    def test_weighted_moving_average(self):
        """Test weighted moving average (recent values higher weight)."""
        predictor = DemandPredictor([10, 20, 30])
        wma = predictor.weighted_moving_average(window=3)
        # Weights: 1, 2, 3 → (10*1 + 20*2 + 30*3) / 6 = 140/6 ≈ 23.33
        assert round(wma, 2) == 23.33

    def test_exponential_smoothing(self):
        """Test exponential smoothing."""
        predictor = DemandPredictor([100, 120, 110, 130])
        forecast = predictor.exponential_smoothing(alpha=0.3)
        # Manual calculation:
        # f1 = 100
        # f2 = 0.3*120 + 0.7*100 = 36 + 70 = 106
        # f3 = 0.3*110 + 0.7*106 = 33 + 74.2 = 107.2
        # f4 = 0.3*130 + 0.7*107.2 = 39 + 75.04 = 114.04
        assert round(forecast, 2) == 114.04

    def test_exponential_smoothing_single_value(self):
        """Test exponential smoothing with single data point."""
        predictor = DemandPredictor([50])
        assert predictor.exponential_smoothing() == 50.0

    def test_linear_regression_forecast(self):
        """Test linear regression forecast."""
        predictor = DemandPredictor([10, 20, 30, 40])
        forecast = predictor.linear_regression_forecast(steps=1)
        assert forecast > 40  # Should predict upward trend

    def test_linear_regression_two_points(self):
        """Test linear regression with exactly 2 points."""
        predictor = DemandPredictor([10, 20])
        forecast = predictor.linear_regression_forecast(steps=1)
        assert forecast >= 25  # Continue upward trend

    def test_seasonal_naive(self):
        """Test seasonal naive forecast."""
        data = [5, 10, 5, 10, 5, 10, 5]  # Pattern of 5, 10
        predictor = DemandPredictor(data)
        forecast = predictor.seasonal_naive(seasonal_period=2)
        assert forecast == 7.5  # Average of last period (5, 10)

    def test_predict_demand(self):
        """Test combined demand prediction."""
        predictor = DemandPredictor([5, 7, 6, 8, 7, 9, 10])
        total, ci = predictor.predict_demand(method='ma', days=7)
        assert total > 0
        assert ci >= 0

    def test_predict_with_confidence(self):
        """Test prediction with confidence interval output."""
        predictor = DemandPredictor([5, 7, 6, 8, 7, 9, 10])
        result = predictor.predict_with_confidence(days=7)
        
        assert "forecast_days" in result
        assert "predicted_total" in result
        assert "predicted_daily" in result
        assert "confidence_interval" in result
        assert result["confidence_level"] == "95%"
        assert "method_used" in result

    def test_best_method_selection(self):
        """Test automatic best method selection."""
        # Create clear trend data
        data = list(range(1, 50))  # 1, 2, 3, ..., 49
        predictor = DemandPredictor(data)
        best = predictor.best_method(forecast_horizon=7)
        assert best in ["ma7", "wma7", "exp", "lin_reg", "season7", "intermittent"]

    def test_holt_winters_insufficient_data(self):
        """Test Holt-Winters falls back to exponential smoothing with limited data."""
        predictor = DemandPredictor([10, 20, 30])
        hw = predictor.holt_winters()
        exp = predictor.exponential_smoothing()
        assert hw == exp

    def test_predict_empty_data(self):
        """Test prediction with empty data returns zero."""
        predictor = DemandPredictor([])
        total, ci = predictor.predict_demand()
        assert total == 0.0
        assert ci == 0.0

    def test_evaluate_models(self):
        """Test model evaluation returns error metrics."""
        data = [10, 12, 11, 13, 12, 14, 13, 15, 14, 16, 15, 17, 16, 18]
        predictor = DemandPredictor(data)
        errors = predictor.evaluate_models(forecast_horizon=4)
        
        assert "ma7" in errors
        assert "exp" in errors
        assert "intermittent" in errors
        assert all(v >= 0 for v in errors.values())

    def test_intermittent_demand(self):
        """Test intermittent (sparse) demand forecast."""
        # Mostly zeros with occasional demand
        data = [0, 0, 10, 0, 0, 0, 15, 0, 0, 0, 0, 12]
        predictor = DemandPredictor(data)
        forecast = predictor.intermittent_demand()
        assert forecast > 0
        assert forecast < 10  # Should be diluted by the zeros

    def test_ensemble_forecast(self):
        """Test ensemble of top methods."""
        data = list(range(1, 30))
        predictor = DemandPredictor(data)
        ens = predictor.ensemble_forecast(days=7, top_n=3)
        assert ens > 0

    def test_demand_profile(self):
        """Test demand profile diagnostics."""
        data = [0, 0, 5, 0, 0, 8, 0, 0, 0, 12]
        predictor = DemandPredictor(data)
        profile = predictor.demand_profile()
        assert profile["total_days"] == 10
        assert profile["non_zero_days"] == 3
        assert profile["is_intermittent"] is True
        assert profile["avg_when_demand"] > 0

    def test_demand_profile_regular(self):
        """Test demand profile for regular demand."""
        data = [5, 6, 7, 8, 9, 10]
        predictor = DemandPredictor(data)
        profile = predictor.demand_profile()
        assert profile["is_intermittent"] is False
        assert profile["zero_ratio"] == 0.0


class TestInventoryOptimizer:
    """Test inventory optimization calculations."""

    def test_eoq_basic(self):
        """Test basic EOQ calculation."""
        eoq = InventoryOptimizer.eoq(
            annual_demand=1000,
            ordering_cost=50,
            holding_cost_per_unit=2
        )
        # sqrt((2 * 1000 * 50) / 2) = sqrt(50000) ≈ 223.6
        assert round(eoq, 1) == 223.6

    def test_eoq_zero_holding_cost(self):
        """Test EOQ with zero holding cost returns infinity."""
        eoq = InventoryOptimizer.eoq(1000, 50, 0)
        assert eoq == float('inf')

    def test_eoq_zero_demand(self):
        """Test EOQ with zero demand."""
        eoq = InventoryOptimizer.eoq(0, 50, 2)
        assert eoq == 0.0

    def test_eoq_with_shortages(self):
        """Test EOQ with planned shortages."""
        Q, S = InventoryOptimizer.eoq_with_shortages(
            annual_demand=1000,
            ordering_cost=50,
            holding_cost_per_unit=2,
            shortage_cost_per_unit=10
        )
        assert Q > 0
        assert S >= 0
        assert S < Q  # Shortage quantity should be less than order quantity

    def test_safety_stock_simple(self):
        """Test simple safety stock calculation."""
        ss = InventoryOptimizer.safety_stock_simple(
            max_lead_time_days=10,
            avg_lead_time_days=7,
            avg_daily_demand=20
        )
        assert ss == 60  # (10 - 7) * 20

    def test_safety_stock_zero(self):
        """Test safety stock when max <= average lead time."""
        ss = InventoryOptimizer.safety_stock_simple(
            max_lead_time_days=5,
            avg_lead_time_days=7,
            avg_daily_demand=20
        )
        assert ss == 0.0

    def test_safety_stock_service_level(self):
        """Test safety stock for service level."""
        ss = InventoryOptimizer.safety_stock_service_level(
            service_level=0.95,
            demand_std_dev=5,
            lead_time_days=7
        )
        # z=1.645 for 95%, sqrt(7) ≈ 2.64575 → 1.645 * 5 * 2.64575 ≈ 21.76
        assert ss == pytest.approx(21.76, abs=0.02)

    def test_safety_stock_service_level_99(self):
        """Test safety stock for 99% service level."""
        ss = InventoryOptimizer.safety_stock_service_level(
            service_level=0.99,
            demand_std_dev=5,
            lead_time_days=7
        )
        # z=2.33 for 99%, sqrt(7) ≈ 2.64575 → 2.33 * 5 * 2.64575 ≈ 30.82
        assert ss == pytest.approx(30.82, abs=0.02)

    def test_reorder_point(self):
        """Test reorder point calculation."""
        rop = InventoryOptimizer.reorder_point(
            lead_time_days=5,
            avg_daily_demand=20,
            safety_stock=10
        )
        assert rop == 110  # 5 * 20 + 10

    def test_reorder_point_no_safety(self):
        """Test reorder point without safety stock."""
        rop = InventoryOptimizer.reorder_point(
            lead_time_days=5,
            avg_daily_demand=20
        )
        assert rop == 100

    def test_recommended_order_quantity(self):
        """Test recommended order quantity."""
        qty = InventoryOptimizer.recommended_order_quantity(
            current_stock=50,
            reorder_point=100,
            eoq=200
        )
        # target = 100 + 200 = 300, order = 300 - 50 = 250
        assert qty == 250

    def test_recommended_order_quantity_sufficient(self):
        """Test recommended order when stock is sufficient."""
        qty = InventoryOptimizer.recommended_order_quantity(
            current_stock=500,
            reorder_point=100,
            eoq=200
        )
        assert qty == 0.0  # No order needed

    def test_recommended_order_minimum(self):
        """Test minimum order quantity."""
        qty = InventoryOptimizer.recommended_order_quantity(
            current_stock=290,
            reorder_point=100,
            eoq=200,
            min_order_qty=50
        )
        # target = 300, order = 10, but min is 50
        assert qty == 50

    def test_abc_classification(self):
        """Test ABC analysis classification."""
        items = [
            ("ITEM-A", 5000),
            ("ITEM-B", 3000),
            ("ITEM-C", 1500),
            ("ITEM-D", 500)
        ]
        classes = InventoryOptimizer.abc_classification(items, a_percent=0.7, b_percent=0.9)

        # 50% ≤ 70% → A; 80% → B; 95%/100% → C. Highest-value item is always A.
        assert classes["ITEM-A"] == 'A'
        assert classes["ITEM-B"] == 'B'
        assert classes["ITEM-C"] == 'C'
        assert classes["ITEM-D"] == 'C'

    def test_abc_classification_empty(self):
        """Test ABC with empty list."""
        classes = InventoryOptimizer.abc_classification([])
        assert classes == {}

    def test_abc_classification_single(self):
        """Test ABC with single item."""
        classes = InventoryOptimizer.abc_classification([("ITEM", 100)])
        assert classes["ITEM"] == 'A'

    def test_calculate_kpi(self):
        """Test KPI calculations."""
        inventory_data = [
            {"inventory": 100, "annual_demand": 500, "unit_cost": 10},
            {"inventory": 200, "annual_demand": 800, "unit_cost": 20},
        ]
        kpi = InventoryOptimizer.calculate_kpi(inventory_data)
        
        # total_inventory_value = 100*10 + 200*20 = 1000 + 4000 = 5000
        # total_demand_cost = 500*10 + 800*20 = 5000 + 16000 = 21000
        # turnover = 21000 / 5000 = 4.2
        # days = 365 / 4.2 ≈ 86.9
        assert kpi["total_inventory_value"] == 5000.0
        assert kpi["inventory_turnover_ratio"] == 4.2
        assert round(kpi["days_of_inventory"], 1) == 86.9

    def test_calculate_kpi_zero_inventory(self):
        """Test KPI with zero inventory."""
        inventory_data = [{"inventory": 0, "annual_demand": 100, "unit_cost": 10}]
        kpi = InventoryOptimizer.calculate_kpi(inventory_data)
        
        assert kpi["total_inventory_value"] == 0.0
        assert kpi["inventory_turnover_ratio"] == 0.0
        assert kpi["days_of_inventory"] == float('inf')
