"""
Assembles a SignalSummary dict from model outputs.
This is the structured context passed to the LLM narrative engine.
"""
import pandas as pd

from adsignal.models.anomaly import detect_anomalies
from adsignal.models.forecaster import train_and_forecast


def build_signal_summary(
    signals_df: pd.DataFrame,
    brand: str,
    channels: list[str] | None = None,
) -> dict:
    """
    Build a comprehensive signal summary for a brand.
    Combines Prophet forecasts + Isolation Forest anomaly flags.

    Args:
        signals_df: Pandas DataFrame of brand_weekly_signals
        brand: brand slug
        channels: list of channels to forecast (defaults to all in data)

    Returns:
        SignalSummary dict consumed by llm/narrative.py
    """
    brand_df = signals_df[signals_df["brand"] == brand]

    if brand_df.empty:
        return {"brand": brand, "error": "no_data"}

    if channels is None:
        channels = brand_df["channel"].unique().tolist()

    # Per-channel forecasts
    channel_forecasts = {}
    for ch in channels:
        channel_forecasts[ch] = train_and_forecast(brand_df, brand, ch)

    # Anomaly detection (brand-level, across all channels)
    anomaly_result = detect_anomalies(signals_df, brand)

    # Recent channel mix: last 4 weeks spend by channel
    recent_weeks = sorted(brand_df["week_key"].unique())[-4:]
    recent_df = brand_df[brand_df["week_key"].isin(recent_weeks)]
    channel_mix = (
        recent_df
        .groupby("channel")["spend_midpoint"]
        .sum()
        .to_dict()
    )
    total_recent = sum(channel_mix.values()) or 1
    channel_mix_pct = {k: round(v / total_recent * 100, 1) for k, v in channel_mix.items()}

    # Weekly deltas (last 8 weeks total spend)
    last_8 = sorted(brand_df["week_key"].unique())[-8:]
    weekly_totals = (
        brand_df[brand_df["week_key"].isin(last_8)]
        .groupby("week_key")["spend_midpoint"]
        .sum()
        .to_dict()
    )

    # Top creative themes (all time for brand)
    all_themes: list[str] = []
    for themes in brand_df["top_themes"].dropna():
        if isinstance(themes, list):
            all_themes.extend(themes)
        elif isinstance(themes, str):
            all_themes.append(themes)

    from collections import Counter
    theme_counts = Counter(all_themes)
    top_themes = [t for t, _ in theme_counts.most_common(5)]

    # Dominant trend direction across channels
    directions = [cf["trend_direction"] for cf in channel_forecasts.values()]
    direction_count = Counter(directions)
    dominant_trend = direction_count.most_common(1)[0][0] if direction_count else "flat"

    return {
        "brand": brand,
        "dominant_trend": dominant_trend,
        "channel_forecasts": channel_forecasts,
        "channel_mix_pct": channel_mix_pct,
        "weekly_deltas": weekly_totals,
        "anomaly_weeks": anomaly_result["anomaly_weeks"],
        "n_anomalies": anomaly_result["n_anomalies"],
        "top_themes": top_themes,
        "weeks_analysed": len(brand_df["week_key"].unique()),
        "recent_weeks": recent_weeks,
    }
