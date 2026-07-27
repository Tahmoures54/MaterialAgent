# ai/predictor.py
"""
Demand Prediction Engine for iMat – Material Control System.

Provides:
- Multiple forecasting methods (moving average, exponential smoothing,
  linear regression, Holt‑Winters, seasonal naive)
- Automatic model selection based on historical accuracy
- Confidence intervals and demand variability
- Batch prediction for many items
- Cached database integration for performance
"""

import math
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
import numpy as np
from sqlalchemy import func
from db.database import SessionLocal
from db.models import Transaction


class DemandPredictor:
    """
    Predict future demand using multiple forecasting algorithms.
    """

    def __init__(self, historical_data: Optional[List[float]] = None):
        """
        Initialize with a list of daily demand values in chronological order.
        """
        self.data = historical_data if historical_data else []

    # ------------------------------------------------------------------
    # Basic forecasting methods
    # ------------------------------------------------------------------
    def moving_average(self, window: int = 7) -> float:
        """Simple moving average of the last 'window' days."""
        if not self.data:
            return 0.0
        if len(self.data) < window:
            window = len(self.data)
        return float(np.mean(self.data[-window:]))

    def weighted_moving_average(self, window: int = 7) -> float:
        """Weighted moving average: recent days have higher weight."""
        if not self.data:
            return 0.0
        if len(self.data) < window:
            window = len(self.data)
        weights = np.arange(1, window + 1)
        return float(np.average(self.data[-window:], weights=weights))

    def exponential_smoothing(self, alpha: float = 0.3) -> float:
        """Single exponential smoothing forecast for next period."""
        if not self.data:
            return 0.0
        forecast = self.data[0]
        for actual in self.data[1:]:
            forecast = alpha * actual + (1 - alpha) * forecast
        return forecast

    def linear_regression_forecast(self, steps: int = 7) -> float:
        """
        Fit y = a + b * day_index and return average daily demand
        for the next 'steps' days.
        """
        n = len(self.data)
        if n < 2:
            return self.moving_average()
        x = np.arange(n)
        y = np.array(self.data)
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)
        if denominator == 0:
            b = 0.0
        else:
            b = numerator / denominator
        a = y_mean - b * x_mean
        # average daily demand over next 'steps' days
        future_x = n + steps - 1
        forecast_total = a + b * future_x
        return max(0.0, forecast_total / steps)

    def seasonal_naive(self, seasonal_period: int = 7) -> float:
        """Repeat the average of the last complete seasonal period."""
        if len(self.data) < seasonal_period:
            return self.moving_average()
        return float(np.mean(self.data[-seasonal_period:]))

    # ------------------------------------------------------------------
    # Advanced: Holt‑Winters (simplified)
    # ------------------------------------------------------------------
    def holt_winters(
        self,
        seasonal_period: int = 7,
        alpha: float = 0.3,
        beta: float = 0.1,
        gamma: float = 0.1,
    ) -> float:
        """
        Holt‑Winters triple exponential smoothing (additive seasonality).
        Returns the forecast for the NEXT period (one day ahead).
        """
        if len(self.data) < 2 * seasonal_period:
            return self.exponential_smoothing(alpha)

        series = self.data
        # Initialization
        seasonals = [series[i + seasonal_period] - series[i] for i in range(seasonal_period)]
        level = series[seasonal_period - 1]
        trend = (series[seasonal_period - 1] - series[0]) / seasonal_period
        forecasts = []

        for i in range(seasonal_period, len(series)):
            last_level = level
            level = alpha * (series[i] - seasonals[i - seasonal_period]) + (1 - alpha) * (last_level + trend)
            trend = beta * (level - last_level) + (1 - beta) * trend
            seasonals.append(gamma * (series[i] - level) + (1 - gamma) * seasonals[i - seasonal_period])
            forecasts.append(level + trend + seasonals[i - seasonal_period])

        # Forecast for next period
        next_level = level + trend  # no actual observation
        next_season = seasonals[-seasonal_period] if len(seasonals) >= seasonal_period else 0
        return next_level + next_season

    # ------------------------------------------------------------------
    # Model evaluation
    # ------------------------------------------------------------------
    def evaluate_models(self, forecast_horizon: int = 7) -> Dict[str, float]:
        """
        Perform backtesting: compute mean absolute error (MAE) for each method.
        Returns a dict {method_name: MAE}.
        """
        methods = {
            "ma7": lambda: self.moving_average(7),
            "wma7": lambda: self.weighted_moving_average(7),
            "exp": lambda: self.exponential_smoothing(0.3),
            "lin_reg": lambda: self.linear_regression_forecast(forecast_horizon),
            "season7": lambda: self.seasonal_naive(7),
        }

        # We need at least 2*forecast_horizon points for testing
        if len(self.data) < 2 * forecast_horizon:
            return {name: 0.0 for name in methods}

        test_data = self.data[-forecast_horizon:]
        train_data = self.data[:-forecast_horizon]

        original_data = self.data
        errors = {}
        for name, method_func in methods.items():
            self.data = train_data
            pred_daily = method_func()   # this is average daily demand
            actual_daily = float(np.mean(test_data))
            errors[name] = abs(pred_daily - actual_daily)

        self.data = original_data
        return errors

    def best_method(self, forecast_horizon: int = 7) -> str:
        """Select the method with the lowest MAE based on backtesting."""
        errors = self.evaluate_models(forecast_horizon)
        if not errors:
            return "exp"
        return min(errors, key=errors.get)

    # ------------------------------------------------------------------
    # Unified prediction
    # ------------------------------------------------------------------
    def predict_demand(
        self, method: str = "auto", days: int = 7
    ) -> Tuple[float, float]:
        """
        Predict total demand over the next 'days' days.

        Returns:
            (predicted_total_demand, confidence_interval_half)
        """
        if not self.data:
            return 0.0, 0.0

        if method == "auto":
            method = self.best_method(forecast_horizon=min(days, len(self.data)))

        daily = 0.0
        if method == "ma":
            daily = self.moving_average(window=min(days, len(self.data)))
        elif method == "wma":
            daily = self.weighted_moving_average(window=min(days, len(self.data)))
        elif method == "exp":
            daily = self.exponential_smoothing()
        elif method == "reg":
            daily = self.linear_regression_forecast(steps=days)
        elif method == "season":
            daily = self.seasonal_naive(7)
        elif method == "hw":
            daily = self.holt_winters()
        else:
            daily = self.linear_regression_forecast(steps=days)

        total_pred = daily * days

        # Confidence interval: use standard deviation of recent data
        recent = self.data[-min(30, len(self.data)):]
        if recent:
            std = float(np.std(recent))
        else:
            std = 0.0
        # 95% confidence half-width
        ci = 1.96 * std * math.sqrt(days)

        return total_pred, ci

    def predict_with_confidence(self, days: int = 7) -> dict:
        """Return detailed forecast including prediction and confidence interval."""
        pred, ci = self.predict_demand(method="auto", days=days)
        return {
            "forecast_days": days,
            "predicted_total": round(pred, 2),
            "predicted_daily": round(pred / days, 2) if days else 0,
            "confidence_interval": f"{max(0, pred - ci):.1f} – {pred + ci:.1f}",
            "confidence_level": "95%"
        }


# ------------------------------------------------------------------
# Database helper functions
# ------------------------------------------------------------------
def load_demand_history(
    item_code: str,
    session=None,
    days_back: int = 90
) -> List[float]:
    """
    Retrieve daily demand for a specific item from the database.
    Returns a list of daily issue quantities (0 if no issue on a day).
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        cutoff_date = date.today() - timedelta(days=days_back)
        results = session.query(
            Transaction.doc_date,
            func.sum(Transaction.issue_qty).label("daily_issue")
        ).filter(
            Transaction.item_code == item_code,
            Transaction.doc_type.in_(['MIV', 'ISS', 'WOM', 'GAT']),
            Transaction.doc_date >= cutoff_date
        ).group_by(Transaction.doc_date).order_by(Transaction.doc_date).all()

        date_demand = {r[0]: float(r[1]) for r in results}
        all_dates = [cutoff_date + timedelta(days=i) for i in range(days_back)]
        return [date_demand.get(d, 0.0) for d in all_dates]
    finally:
        if close_session:
            session.close()


def predict_item_demand(
    item_code: str, days: int = 7, session=None
) -> dict:
    """
    Convenience function: load data and return prediction with confidence.
    """
    data = load_demand_history(item_code, session, days_back=90)
    predictor = DemandPredictor(data)
    result = predictor.predict_with_confidence(days)
    result["item_code"] = item_code
    return result


def batch_predict(
    item_codes: List[str], days: int = 7, session=None
) -> List[dict]:
    """
    Predict demand for multiple items at once.
    Returns a list of prediction dicts.
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        predictions = []
        for code in item_codes:
            pred = predict_item_demand(code, days, session)
            predictions.append(pred)
        return predictions
    finally:
        if close_session:
            session.close()