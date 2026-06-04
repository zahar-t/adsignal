from datetime import date

import pandas as pd

from adsignal.models.forecaster import _week_key_to_date, train_and_forecast


def test_week_key_to_date():
    d = _week_key_to_date("2024-W01")
    assert isinstance(d, date)


def test_train_and_forecast_returns_dict(sample_signals_df):
    result = train_and_forecast(
        sample_signals_df[sample_signals_df["brand"] == "nike"],
        brand="nike",
        channel="display",
        forecast_periods=4,
    )
    assert "trend_direction" in result
    assert result["trend_direction"] in ("increasing", "decreasing", "flat")
    assert "forecast_next_4w" in result
    assert isinstance(result["forecast_next_4w"], list)


def test_insufficient_data_returns_empty_forecast():
    tiny_df = pd.DataFrame([{
        "brand": "tiny", "channel": "display",
        "week_key": "2024-W01", "spend_midpoint": 1000,
    }])
    result = train_and_forecast(tiny_df, "tiny", "display")
    assert result["forecast_next_4w"] == []
    assert result["trend_direction"] == "flat"


def test_forecast_no_negative_values(sample_signals_df):
    result = train_and_forecast(
        sample_signals_df[sample_signals_df["brand"] == "adidas"],
        brand="adidas",
        channel="video",
        forecast_periods=4,
    )
    for v in result["forecast_next_4w"]:
        assert v >= 0, f"Forecast should not be negative: {v}"


def test_weekly_actuals_capped_at_12(sample_signals_df):
    result = train_and_forecast(
        sample_signals_df[sample_signals_df["brand"] == "nike"],
        brand="nike",
        channel="social",
        forecast_periods=4,
    )
    assert len(result["weekly_actuals"]) <= 12
