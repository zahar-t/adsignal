"""
Pure Plotly chart builders for the dashboard.

Deliberately free of any Reflex import so they can be unit-tested cheaply and
independently of the Reflex app/runtime version (see tests/test_dashboard.py).
``dashboard/dashboard.py`` imports these and assigns the figures to state.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.graph_objects import Figure

PALETTE = ["#6366f1", "#f59e0b", "#10b981", "#f43f5e", "#3b82f6", "#8b5cf6"]


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert ``#rrggbb`` + alpha to ``rgba(r,g,b,a)``.

    plotly.py rejects 8-digit ``#rrggbbaa`` hex strings, so the previous
    ``color + "18"`` trick raised a ValueError that bubbled up and crashed the
    whole dashboard to its error page (no charts rendered at all). rgba() is the
    portable way to express a translucent fill.
    """
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def build_trend_figure(bdf: pd.DataFrame) -> Figure:
    """Weekly spend-by-channel trend (smooth spline, transparent fill)."""
    weekly = (
        bdf.groupby(["week_key", "channel"])["spend_midpoint"]
        .sum()
        .reset_index()
        .sort_values("week_key")
    )
    fig_trend = go.Figure()
    for i, ch in enumerate(sorted(weekly["channel"].unique())):
        ch_data = weekly[weekly["channel"] == ch].sort_values("week_key")
        color = PALETTE[i % len(PALETTE)]
        fig_trend.add_trace(
            go.Scatter(
                x=ch_data["week_key"].tolist(),
                y=ch_data["spend_midpoint"].tolist(),
                name=ch,
                mode="lines",
                line=dict(width=2.5, color=color, shape="spline"),
                fill="tozeroy",
                fillcolor=hex_to_rgba(color, 0.09),
                # NOTE: the spend value needs the plotly "%{y}" token. The original
                # template was "${{y:,.0f}}" which renders as the literal text
                # "${y:,.0f}" in tooltips (missing %). Correct token: "$%{y:,.0f}".
                hovertemplate=f"<b>{ch}</b><br>%{{x}}<br>$%{{y:,.0f}}<extra></extra>",
            )
        )
    fig_trend.update_layout(height=280, hovermode="x unified", showlegend=True)
    return fig_trend


def build_donut_figure(bdf: pd.DataFrame) -> Figure:
    """Recent 4-week channel-mix donut with centered total annotation."""
    recent_wks = sorted(bdf["week_key"].unique())[-4:]
    ch_totals = (
        bdf[bdf["week_key"].isin(recent_wks)]
        .groupby("channel")["spend_midpoint"]
        .sum()
        .reset_index()
    )
    total_recent = ch_totals["spend_midpoint"].sum()
    fig_donut = go.Figure(
        go.Pie(
            labels=ch_totals["channel"].tolist(),
            values=ch_totals["spend_midpoint"].tolist(),
            hole=0.65,
            marker=dict(
                colors=PALETTE[: len(ch_totals)],
                line=dict(color="white", width=2),
            ),
            textinfo="percent",
            textfont=dict(size=11),
            hovertemplate="<b>%{label}</b><br>$%{value:,.0f} (%{percent})<extra></extra>",
        )
    )
    fig_donut.add_annotation(
        text=f"${total_recent / 1_000:.0f}K",
        x=0.5,
        y=0.58,
        font=dict(size=20, color="#0f172a", family="Inter"),
        showarrow=False,
    )
    fig_donut.add_annotation(
        text="4-wk spend",
        x=0.5,
        y=0.42,
        font=dict(size=11, color="#64748b", family="Inter"),
        showarrow=False,
    )
    fig_donut.update_layout(
        height=260,
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02),
        margin=dict(l=0, r=90, t=10, b=10),
    )
    return fig_donut
