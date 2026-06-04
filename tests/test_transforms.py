"""Test PySpark transform functions using the sample_signals_df fixture."""
from adsignal.models.signal_builder import build_signal_summary


def test_build_signal_summary_returns_expected_keys(sample_signals_df):
    summary = build_signal_summary(sample_signals_df, "nike")
    assert "brand" in summary
    assert "dominant_trend" in summary
    assert "channel_mix_pct" in summary
    assert "anomaly_weeks" in summary
    assert "weeks_analysed" in summary


def test_build_signal_summary_unknown_brand(sample_signals_df):
    summary = build_signal_summary(sample_signals_df, "unknownbrand999")
    assert "error" in summary
    assert summary["error"] == "no_data"


def test_channel_mix_sums_to_100(sample_signals_df):
    summary = build_signal_summary(sample_signals_df, "nike")
    channel_mix = summary.get("channel_mix_pct", {})
    if channel_mix:
        total = sum(channel_mix.values())
        assert abs(total - 100.0) < 1.0, f"Channel mix should sum to ~100, got {total}"


def test_dominant_trend_valid_value(sample_signals_df):
    summary = build_signal_summary(sample_signals_df, "adidas")
    assert summary["dominant_trend"] in ("increasing", "decreasing", "flat")
