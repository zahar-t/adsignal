"""Tests for dashboard chart builders and the offline sample fallback.

These guard the "charts broken / missing entirely" bug: an 8-digit #rrggbbaa
fillcolor raised a ValueError inside the trend builder, which bubbled up through
on_load and crashed the whole dashboard to its error page.
"""
import pandas as pd
import pytest

from dashboard.charts import build_donut_figure, build_trend_figure, hex_to_rgba
from dashboard.sample_data import build_sample_signals


@pytest.fixture
def nike_signals():
    df = build_sample_signals()
    return df[df["brand"] == "nike"]


def test_sample_signals_has_expected_shape():
    df = build_sample_signals()
    assert not df.empty
    assert {"brand", "week_key", "channel", "spend_midpoint", "ad_count"}.issubset(df.columns)
    assert df["brand"].nunique() >= 3


def test_sample_signals_deterministic():
    assert len(build_sample_signals()) == len(build_sample_signals())


def test_hex_to_rgba_is_valid_for_plotly():
    # The original `color + "18"` produced '#6366f118', which plotly rejects.
    assert hex_to_rgba("#6366f1", 0.09) == "rgba(99, 102, 241, 0.09)"


def test_trend_figure_builds_without_error(nike_signals):
    fig = build_trend_figure(nike_signals)
    assert len(fig.data) >= 1
    # Each trace must carry data points (otherwise the chart is blank).
    assert all(len(trace.x) > 0 for trace in fig.data)
    # fillcolor must be a plotly-valid rgba(), not an 8-digit hex.
    assert all(str(trace.fillcolor).startswith("rgba(") for trace in fig.data)


def test_trend_hovertemplate_uses_percent_token(nike_signals):
    fig = build_trend_figure(nike_signals)
    # Must use the plotly value token '$%{y...}', not the literal '${y...}'.
    assert "$%{y:,.0f}" in fig.data[0].hovertemplate


def test_trend_figure_serializes_to_json(nike_signals):
    # Reflex sends the figure to the browser as JSON — it must serialize.
    fig = build_trend_figure(nike_signals)
    assert len(fig.to_json()) > 0


def test_donut_figure_builds_without_error(nike_signals):
    fig = build_donut_figure(nike_signals)
    assert len(fig.data) == 1
    assert len(fig.data[0].labels) >= 1
    assert sum(fig.data[0].values) > 0
    assert len(fig.to_json()) > 0


def test_builders_handle_single_week():
    one = pd.DataFrame(
        [
            {"brand": "z", "week_key": "2024-W01", "channel": "video", "spend_midpoint": 100.0},
            {"brand": "z", "week_key": "2024-W01", "channel": "social", "spend_midpoint": 50.0},
        ]
    )
    assert len(build_trend_figure(one).data) == 2
    assert len(build_donut_figure(one).data[0].labels) == 2
