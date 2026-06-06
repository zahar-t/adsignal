"""
Prophet spend trend forecaster.
Trains per brand + channel on weekly spend_midpoint.
Returns forecast DataFrame and trend summary dict.

GOTCHA: Prophet requires a DataFrame with columns 'ds' (datetime) and 'y' (float).
GOTCHA: Prophet prints verbose Stan output — suppress with suppress_stdout_stderr().
"""
import contextlib
import io
import warnings

import pandas as pd
import structlog
from prophet import Prophet

log = structlog.get_logger()


@contextlib.contextmanager
def suppress_prophet_output():
    """Suppress Prophet's verbose Stan/cmdstan output."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            yield


def train_and_forecast(
    weekly_df: pd.DataFrame,
    brand: str,
    channel: str,
    forecast_periods: int = 4,
) -> dict:
    """
    Train Prophet on weekly spend_midpoint for brand+channel.
    Returns summary dict with trend direction, forecast, and confidence interval.

    Args:
        weekly_df: DataFrame with columns [week_key, spend_midpoint, channel]
        brand: brand slug
        channel: channel to forecast
        forecast_periods: number of future weeks to forecast

    Returns:
        {
          "brand": str,
          "channel": str,
          "trend_direction": "increasing" | "decreasing" | "flat",
          "trend_pct_change": float,  # % change last 4 weeks
          "forecast_next_4w": list[float],
          "weekly_actuals": list[float],
          "weekly_dates": list[str],
        }
    """
    channel_df = weekly_df[weekly_df["channel"] == channel].copy()

    if len(channel_df) < 4:
        log.warning("insufficient_data_for_prophet", brand=brand, channel=channel, rows=len(channel_df))
        return _empty_forecast(brand, channel)

    # Prophet expects ds and y
    prophet_df = pd.DataFrame({
        "ds": pd.to_datetime(channel_df["week_key"].apply(_week_key_to_date)),
        "y": channel_df["spend_midpoint"].fillna(0).values,
    }).sort_values("ds")

    try:
        with suppress_prophet_output():
            model = Prophet(
                weekly_seasonality=False,
                daily_seasonality=False,
                yearly_seasonality=False,
                seasonality_mode="additive",
                changepoint_prior_scale=0.1,
            )
            model.fit(prophet_df)
            future = model.make_future_dataframe(periods=forecast_periods, freq="W")
            forecast = model.predict(future)
    except Exception as e:
        # Prophet may fail if Stan backend is not properly installed (e.g. Python 3.13 compat).
        # Fall back to a simple linear extrapolation so the pipeline stays functional.
        log.warning("prophet_failed_falling_back_to_linear", brand=brand, channel=channel, error=str(e))
        return _linear_fallback(brand, channel, prophet_df, forecast_periods)

    actuals = prophet_df["y"].tolist()
    forecast_values = forecast["yhat"].tail(forecast_periods).tolist()
    forecast_values = [max(0, v) for v in forecast_values]  # no negative spend

    # Trend: compare last 4 weeks to previous 4 weeks
    if len(actuals) >= 8:
        recent = sum(actuals[-4:])
        prior = sum(actuals[-8:-4])
        pct_change = ((recent - prior) / (prior + 1e-9)) * 100
    elif len(actuals) >= 2:
        pct_change = ((actuals[-1] - actuals[0]) / (actuals[0] + 1e-9)) * 100
    else:
        pct_change = 0.0

    if pct_change > 10:
        direction = "increasing"
    elif pct_change < -10:
        direction = "decreasing"
    else:
        direction = "flat"

    return {
        "brand": brand,
        "channel": channel,
        "trend_direction": direction,
        "trend_pct_change": round(pct_change, 2),
        "forecast_next_4w": [round(v, 2) for v in forecast_values],
        "weekly_actuals": [round(v, 2) for v in actuals[-12:]],  # last 12 weeks
        "weekly_dates": [d.strftime("%Y-W%V") for d in prophet_df["ds"].tail(12).tolist()],
    }


def _week_key_to_date(week_key: str):
    """Convert '2024-W42' to a Monday date."""
    import datetime
    year, week = week_key.split("-W")
    return datetime.datetime.strptime(f"{year}-W{week}-1", "%G-W%V-%u").date()


def _linear_fallback(brand: str, channel: str, prophet_df: pd.DataFrame, periods: int) -> dict:
    """Simple linear extrapolation when Prophet/Stan fails (e.g. Python 3.13 compat issue)."""
    actuals = prophet_df["y"].tolist()
    if len(actuals) >= 2:
        slope = (actuals[-1] - actuals[0]) / max(len(actuals) - 1, 1)
        forecast_values = [max(0, actuals[-1] + slope * (i + 1)) for i in range(periods)]
        pct_change = ((actuals[-1] - actuals[0]) / (actuals[0] + 1e-9)) * 100
    else:
        forecast_values = []
        pct_change = 0.0

    if pct_change > 10:
        direction = "increasing"
    elif pct_change < -10:
        direction = "decreasing"
    else:
        direction = "flat"

    return {
        "brand": brand,
        "channel": channel,
        "trend_direction": direction,
        "trend_pct_change": round(pct_change, 2),
        "forecast_next_4w": [round(v, 2) for v in forecast_values],
        "weekly_actuals": [round(v, 2) for v in actuals[-12:]],
        "weekly_dates": [d.strftime("%Y-W%V") for d in prophet_df["ds"].tail(12).tolist()],
    }


def _empty_forecast(brand: str, channel: str) -> dict:
    return {
        "brand": brand,
        "channel": channel,
        "trend_direction": "flat",
        "trend_pct_change": 0.0,
        "forecast_next_4w": [],
        "weekly_actuals": [],
        "weekly_dates": [],
    }
