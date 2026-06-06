"""AdSignal Intelligence Dashboard — redesigned with Reflex."""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import reflex as rx
from plotly.graph_objects import Figure
from pyiceberg.catalog import load_catalog

from adsignal.config import settings
from adsignal.llm.narrative import generate_brief
from adsignal.models.signal_builder import build_signal_summary

# ── Custom Plotly template ────────────────────────────────────────────────────

PALETTE = ["#6366f1", "#f59e0b", "#10b981", "#f43f5e", "#3b82f6", "#8b5cf6"]

pio.templates["adsignal"] = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=12, color="#64748b"),
        colorway=PALETTE,
        xaxis=dict(
            gridcolor="#f1f5f9",
            linecolor="#e2e8f0",
            zeroline=False,
            showgrid=True,
            tickfont=dict(size=11, color="#94a3b8"),
        ),
        yaxis=dict(
            gridcolor="#f1f5f9",
            linecolor="#e2e8f0",
            zeroline=False,
            showgrid=True,
            tickfont=dict(size=11, color="#94a3b8"),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color="#64748b"),
        ),
        margin=dict(l=0, r=0, t=10, b=0),
        hoverlabel=dict(
            bgcolor="#1e293b",
            font=dict(color="white", size=12, family="Inter"),
            bordercolor="#334155",
        ),
    )
)
pio.templates.default = "adsignal"

# ── Module-level data cache ───────────────────────────────────────────────────

_catalog = None
_df: pd.DataFrame | None = None


def _get_catalog():
    global _catalog
    if _catalog is None:
        _catalog = load_catalog(
            "adsignal",
            **{
                "type": "rest",
                "uri": settings.iceberg_rest_uri,
                "warehouse": settings.iceberg_warehouse,
                "s3.endpoint": settings.iceberg_s3_endpoint,
                "s3.access-key-id": settings.iceberg_s3_access_key,
                "s3.secret-access-key": settings.iceberg_s3_secret_key,
                "s3.path-style-access": "true",
            },
        )
    return _catalog


def _signals() -> pd.DataFrame:
    global _df
    if _df is None:
        tbl = _get_catalog().load_table("ad_intelligence.brand_weekly_signals")
        _df = tbl.scan().to_pandas()
    return _df


def _get_snapshots() -> list[dict]:
    tbl = _get_catalog().load_table("ad_intelligence.brand_weekly_signals")
    return [
        {
            "snapshot_id": str(s.snapshot_id)[:18] + "...",
            "committed_at": str(pd.to_datetime(s.timestamp_ms, unit="ms")),
            "operation": (s.summary or {}).get("operation", "unknown"),
            "added_records": str(int((s.summary or {}).get("added-records", 0))),
        }
        for s in tbl.snapshots()
    ]


# ── State ─────────────────────────────────────────────────────────────────────


class State(rx.State):
    brands: list[str] = []
    channels: list[str] = []
    selected_brand: str = ""
    selected_channels: list[str] = []

    kpi_spend: str = "—"
    kpi_ads: str = "—"
    kpi_weeks: str = "—"
    kpi_channels: str = "—"
    spend_delta: str = ""
    spend_delta_up: bool = True
    ads_delta: str = ""
    ads_delta_up: bool = True

    trend_fig: Figure = Figure()
    donut_fig: Figure = Figure()

    has_anomalies: bool = False
    anomaly_summary: str = ""
    recent_anomalies: list[str] = []
    anomaly_error: str = ""

    brief: str = ""
    brief_loading: bool = False

    snapshots: list[dict] = []
    has_snapshots: bool = False

    load_error: str = ""
    llm_info: str = ""

    @rx.event
    async def on_load(self):
        try:
            df = _signals()
            self.brands = sorted(df["brand"].unique().tolist())
            self.channels = sorted(df["channel"].unique().tolist())
            self.selected_channels = list(self.channels)
            self.llm_info = f"{settings.llm_provider} / {settings.llm_model}"
            if self.brands:
                self.selected_brand = self.brands[0]
                self._refresh(df)
            snaps = _get_snapshots()
            self.snapshots = snaps
            self.has_snapshots = len(snaps) > 0
        except Exception as exc:
            self.load_error = str(exc)

    @rx.event
    async def set_brand(self, brand: str):
        self.selected_brand = brand
        self.brief = ""
        self._refresh(_signals())

    @rx.event
    async def toggle_channel(self, channel: str):
        if channel in self.selected_channels:
            self.selected_channels = [c for c in self.selected_channels if c != channel]
        else:
            self.selected_channels = sorted([*self.selected_channels, channel])
        self._refresh(_signals())

    @rx.event
    async def generate_brief(self):
        self.brief_loading = True
        yield
        try:
            df = _signals()
            summary = build_signal_summary(df, self.selected_brand, self.selected_channels)
            self.brief = generate_brief(self.selected_brand, summary)
        except Exception as exc:
            self.brief = f"Brief generation failed: {exc}"
        self.brief_loading = False

    def _refresh(self, df: pd.DataFrame):
        bdf = df[
            (df["brand"] == self.selected_brand)
            & (df["channel"].isin(self.selected_channels))
        ]
        if bdf.empty:
            self.kpi_spend = "$0"
            self.kpi_ads = "0"
            self.kpi_weeks = "0"
            self.kpi_channels = "0"
            self.spend_delta = ""
            self.ads_delta = ""
            self.trend_fig = Figure()
            self.donut_fig = Figure()
            self.has_anomalies = False
            self.anomaly_summary = ""
            self.recent_anomalies = []
            self.anomaly_error = ""
            return

        # KPI totals
        total_spend = bdf["spend_midpoint"].sum()
        total_ads = int(bdf["ad_count"].sum())
        self.kpi_spend = f"${total_spend:,.0f}"
        self.kpi_ads = f"{total_ads:,}"
        self.kpi_weeks = str(bdf["week_key"].nunique())
        self.kpi_channels = str(bdf["channel"].nunique())

        # Week-over-week deltas
        weeks = sorted(bdf["week_key"].unique())
        if len(weeks) >= 2:
            curr_spend = bdf[bdf["week_key"] == weeks[-1]]["spend_midpoint"].sum()
            prev_spend = bdf[bdf["week_key"] == weeks[-2]]["spend_midpoint"].sum()
            if prev_spend > 0:
                pct = ((curr_spend - prev_spend) / prev_spend) * 100
                self.spend_delta = f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"
                self.spend_delta_up = bool(pct >= 0)

            curr_ads = int(bdf[bdf["week_key"] == weeks[-1]]["ad_count"].sum())
            prev_ads = int(bdf[bdf["week_key"] == weeks[-2]]["ad_count"].sum())
            if prev_ads > 0:
                pct_ads = ((curr_ads - prev_ads) / prev_ads) * 100
                self.ads_delta = f"+{pct_ads:.1f}%" if pct_ads >= 0 else f"{pct_ads:.1f}%"
                self.ads_delta_up = bool(pct_ads >= 0)

        # Trend chart — smooth spline with transparent fill
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
                    fillcolor=color + "18",
                    hovertemplate=f"<b>{ch}</b><br>%{{x}}<br>${{y:,.0f}}<extra></extra>",
                )
            )
        fig_trend.update_layout(height=280, hovermode="x unified", showlegend=True)
        self.trend_fig = fig_trend

        # Donut chart with center annotation
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
        self.donut_fig = fig_donut

        # Anomalies
        try:
            summary = build_signal_summary(df, self.selected_brand, self.selected_channels)
            all_anomalies = [str(w) for w in summary.get("anomaly_weeks", [])]
            self.has_anomalies = len(all_anomalies) > 0
            self.anomaly_summary = f"{len(all_anomalies)} anomalous week(s) detected"
            self.recent_anomalies = all_anomalies[-5:]
            self.anomaly_error = ""
        except Exception as exc:
            self.anomaly_error = str(exc)


# ── Shared card wrapper ───────────────────────────────────────────────────────


def section_card(*children) -> rx.Component:
    return rx.box(
        *children,
        background="white",
        border="1px solid #f1f5f9",
        border_radius="12px",
        box_shadow="0 1px 3px 0 rgba(0,0,0,0.07)",
        padding="5",
        width="100%",
    )


def section_header(icon: str, title: str, subtitle: str) -> rx.Component:
    return rx.hstack(
        rx.box(
            rx.icon(tag=icon, size=14, color="#6366f1"),
            background="#eef2ff",
            border_radius="6px",
            padding="6px",
            display="flex",
            align_items="center",
            justify_content="center",
        ),
        rx.vstack(
            rx.text(title, size="3", weight="bold", color="#0f172a"),
            rx.text(subtitle, size="1", color="#94a3b8"),
            spacing="0",
            align="start",
        ),
        spacing="3",
        align="center",
        width="100%",
    )


# ── KPI card ─────────────────────────────────────────────────────────────────


def kpi_card(
    label: str,
    value: rx.Var,
    icon: str,
    delta: rx.Var = "",
    delta_up: rx.Var = True,
) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text(label, size="2", color="#64748b", weight="medium"),
                rx.spacer(),
                rx.box(
                    rx.icon(tag=icon, size=15, color="#6366f1"),
                    background="#eef2ff",
                    border_radius="8px",
                    padding="6px",
                    display="flex",
                    align_items="center",
                    justify_content="center",
                ),
                align="center",
                width="100%",
            ),
            rx.heading(value, size="7", weight="bold", color="#0f172a"),
            rx.cond(
                delta != "",
                rx.hstack(
                    rx.cond(
                        delta_up,
                        rx.icon(tag="trending-up", size=12, color="#10b981"),
                        rx.icon(tag="trending-down", size=12, color="#f43f5e"),
                    ),
                    rx.text(
                        delta + " vs last wk",
                        size="1",
                        weight="medium",
                        color=rx.cond(delta_up, "#10b981", "#f43f5e"),
                    ),
                    spacing="1",
                    align="center",
                ),
                rx.box(height="16px"),
            ),
            spacing="2",
            align="start",
            width="100%",
        ),
        padding="5",
        flex="1",
        background="white",
        border_radius="12px",
        border="1px solid #f1f5f9",
        box_shadow="0 1px 3px 0 rgba(0,0,0,0.07)",
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────


def channel_toggle(ch: rx.Var) -> rx.Component:
    return rx.button(
        ch,
        variant=rx.cond(State.selected_channels.contains(ch), "solid", "ghost"),
        color_scheme="indigo",
        on_click=State.toggle_channel(ch),
        size="1",
        cursor="pointer",
    )


def sidebar() -> rx.Component:
    return rx.box(
        rx.vstack(
            # Logo
            rx.hstack(
                rx.box(
                    rx.text("A", weight="bold", size="3", color="white"),
                    background="linear-gradient(135deg, #6366f1, #8b5cf6)",
                    border_radius="8px",
                    width="32px",
                    height="32px",
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    flex_shrink="0",
                ),
                rx.vstack(
                    rx.text("AdSignal", weight="bold", color="white", size="3"),
                    rx.text("Intelligence Platform", size="1", color="#475569"),
                    spacing="0",
                    align="start",
                ),
                spacing="3",
                align="center",
                width="100%",
            ),
            rx.box(width="100%", height="1px", background="#1e293b", margin_y="2"),
            # Brand selector
            rx.vstack(
                rx.text(
                    "BRAND",
                    size="1",
                    weight="bold",
                    color="#475569",
                    letter_spacing="0.08em",
                ),
                rx.select(
                    State.brands,
                    value=State.selected_brand,
                    on_change=State.set_brand,
                    width="100%",
                    color_scheme="indigo",
                ),
                spacing="2",
                width="100%",
            ),
            # Channel toggles
            rx.vstack(
                rx.text(
                    "CHANNELS",
                    size="1",
                    weight="bold",
                    color="#475569",
                    letter_spacing="0.08em",
                ),
                rx.flex(
                    rx.foreach(State.channels, channel_toggle),
                    flex_wrap="wrap",
                    gap="2",
                ),
                spacing="2",
                width="100%",
            ),
            rx.spacer(),
            # Footer
            rx.vstack(
                rx.box(width="100%", height="1px", background="#1e293b"),
                rx.hstack(
                    rx.icon(tag="cpu", size=13, color="#475569"),
                    rx.text(State.llm_info, size="1", color="#475569"),
                    spacing="2",
                    align="center",
                ),
                spacing="3",
                width="100%",
                align="start",
            ),
            spacing="5",
            align="start",
            padding="5",
            width="100%",
            height="100%",
            min_height="100vh",
        ),
        width="260px",
        background="#0f172a",
        flex_shrink="0",
        position="sticky",
        top="0",
        height="100vh",
        overflow_y="auto",
    )


# ── Anomaly panel ─────────────────────────────────────────────────────────────


def anomaly_panel() -> rx.Component:
    return rx.vstack(
        section_header("activity", "Anomaly Detection", "Isolation Forest — flagged spend weeks"),
        rx.separator(width="100%", color_scheme="gray"),
        rx.cond(
            State.anomaly_error != "",
            rx.box(
                rx.hstack(
                    rx.icon(tag="triangle-alert", size=14, color="#f59e0b"),
                    rx.text(State.anomaly_error, size="2", color="#92400e"),
                    spacing="2",
                ),
                background="#fffbeb",
                border="1px solid #fde68a",
                border_radius="8px",
                padding="3",
                width="100%",
            ),
            rx.cond(
                State.has_anomalies,
                rx.vstack(
                    rx.box(
                        rx.hstack(
                            rx.icon(tag="zap", size=14, color="#f43f5e"),
                            rx.text(
                                State.anomaly_summary,
                                size="2",
                                weight="medium",
                                color="#be123c",
                            ),
                            spacing="2",
                        ),
                        background="#fff1f2",
                        border="1px solid #fecdd3",
                        border_radius="8px",
                        padding="3",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.foreach(
                            State.recent_anomalies,
                            lambda w: rx.hstack(
                                rx.box(
                                    width="6px",
                                    height="6px",
                                    border_radius="50%",
                                    background="#f43f5e",
                                    flex_shrink="0",
                                ),
                                rx.text(
                                    w,
                                    size="2",
                                    font_family="monospace",
                                    color="#374151",
                                ),
                                spacing="3",
                                align="center",
                                padding_y="2px",
                            ),
                        ),
                        spacing="2",
                        padding_left="2",
                        width="100%",
                    ),
                    spacing="3",
                    width="100%",
                ),
                rx.box(
                    rx.hstack(
                        rx.icon(tag="circle-check", size=14, color="#10b981"),
                        rx.text(
                            "No anomalies detected in recent history",
                            size="2",
                            color="#065f46",
                        ),
                        spacing="2",
                    ),
                    background="#ecfdf5",
                    border="1px solid #a7f3d0",
                    border_radius="8px",
                    padding="3",
                    width="100%",
                ),
            ),
        ),
        spacing="4",
        align="start",
        width="100%",
        height="100%",
    )


# ── Brief panel ───────────────────────────────────────────────────────────────


def brief_panel() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            section_header(
                "bot",
                "AI Intelligence Brief",
                State.llm_info,
            ),
            rx.spacer(),
            rx.button(
                rx.icon(tag="refresh-cw", size=13),
                "Generate",
                on_click=State.generate_brief,
                loading=State.brief_loading,
                size="2",
                color_scheme="indigo",
                variant="soft",
            ),
            align="center",
            width="100%",
        ),
        rx.separator(width="100%", color_scheme="gray"),
        rx.cond(
            State.brief_loading,
            rx.vstack(
                rx.skeleton(height="18px", width="100%"),
                rx.skeleton(height="18px", width="92%"),
                rx.skeleton(height="18px", width="97%"),
                spacing="2",
                width="100%",
            ),
            rx.cond(
                State.brief != "",
                rx.box(
                    rx.text(State.brief, size="3", color="#1e293b", line_height="1.75"),
                    background="#f8fafc",
                    border="1px solid #e2e8f0",
                    border_left="3px solid #6366f1",
                    border_radius="0 8px 8px 0",
                    padding="4",
                    width="100%",
                ),
                rx.box(
                    rx.hstack(
                        rx.icon(tag="sparkles", size=14, color="#94a3b8"),
                        rx.text(
                            "Click Generate to produce an AI narrative for this brand.",
                            size="2",
                            color="#94a3b8",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    padding="4",
                    background="#f8fafc",
                    border="1px dashed #e2e8f0",
                    border_radius="8px",
                    width="100%",
                ),
            ),
        ),
        spacing="4",
        width="100%",
    )


# ── Snapshots panel ───────────────────────────────────────────────────────────


def snapshots_panel() -> rx.Component:
    return rx.vstack(
        section_header(
            "database",
            "Iceberg Snapshot History",
            "Each row is an ETL run — queryable point-in-time via time-travel",
        ),
        rx.separator(width="100%", color_scheme="gray"),
        rx.cond(
            State.has_snapshots,
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Snapshot ID"),
                            rx.table.column_header_cell("Committed At"),
                            rx.table.column_header_cell("Operation"),
                            rx.table.column_header_cell("Records Added"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            State.snapshots,
                            lambda s: rx.table.row(
                                rx.table.cell(
                                    rx.text(
                                        s["snapshot_id"],
                                        font_family="monospace",
                                        size="1",
                                        color="#64748b",
                                    )
                                ),
                                rx.table.cell(rx.text(s["committed_at"], size="2")),
                                rx.table.cell(
                                    rx.badge(
                                        s["operation"],
                                        color_scheme=rx.cond(
                                            s["operation"] == "append", "green", "blue"
                                        ),
                                        variant="soft",
                                        size="1",
                                    )
                                ),
                                rx.table.cell(
                                    rx.text(
                                        s["added_records"],
                                        size="2",
                                        font_family="monospace",
                                    )
                                ),
                            ),
                        ),
                    ),
                    variant="surface",
                    size="2",
                    width="100%",
                ),
                max_height="220px",
                overflow_y="auto",
                width="100%",
            ),
            rx.box(
                rx.hstack(
                    rx.icon(tag="inbox", size=14, color="#94a3b8"),
                    rx.text(
                        "No snapshots yet — run the ETL pipeline first.",
                        size="2",
                        color="#94a3b8",
                    ),
                    spacing="2",
                    align="center",
                ),
                padding="4",
                background="#f8fafc",
                border="1px dashed #e2e8f0",
                border_radius="8px",
                width="100%",
            ),
        ),
        spacing="4",
        width="100%",
    )


# ── Main content ──────────────────────────────────────────────────────────────


def main_content() -> rx.Component:
    return rx.box(
        rx.vstack(
            # Page header
            rx.vstack(
                rx.heading(
                    State.selected_brand + " — Competitive Intelligence",
                    size="8",
                    weight="bold",
                    color="#0f172a",
                ),
                rx.text(
                    "Real-time ad spend analysis powered by Iceberg + LLM",
                    size="3",
                    color="#64748b",
                ),
                spacing="1",
                align="start",
                width="100%",
            ),
            # KPI row
            rx.flex(
                kpi_card(
                    "Total Est. Spend",
                    State.kpi_spend,
                    "trending-up",
                    State.spend_delta,
                    State.spend_delta_up,
                ),
                kpi_card(
                    "Total Ads Tracked",
                    State.kpi_ads,
                    "layout-grid",
                    State.ads_delta,
                    State.ads_delta_up,
                ),
                kpi_card("Weeks Tracked", State.kpi_weeks, "calendar-days"),
                kpi_card("Active Channels", State.kpi_channels, "radio"),
                gap="4",
                width="100%",
            ),
            # Trend chart
            section_card(
                rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.text(
                                "Weekly Spend Trend",
                                size="3",
                                weight="bold",
                                color="#0f172a",
                            ),
                            rx.text(
                                "Estimated spend by channel over time",
                                size="2",
                                color="#94a3b8",
                            ),
                            spacing="0",
                        ),
                        rx.spacer(),
                        rx.badge("Live", color_scheme="green", variant="soft", size="1"),
                        align="center",
                        width="100%",
                    ),
                    rx.plotly(data=State.trend_fig, width="100%"),
                    spacing="3",
                    width="100%",
                ),
            ),
            # Channel mix + anomaly
            rx.grid(
                section_card(
                    rx.vstack(
                        rx.vstack(
                            rx.text(
                                "Channel Mix",
                                size="3",
                                weight="bold",
                                color="#0f172a",
                            ),
                            rx.text(
                                "Recent 4-week spend distribution",
                                size="2",
                                color="#94a3b8",
                            ),
                            spacing="0",
                        ),
                        rx.plotly(data=State.donut_fig, width="100%"),
                        spacing="3",
                        width="100%",
                    ),
                ),
                section_card(anomaly_panel()),
                columns="2",
                gap="4",
                width="100%",
            ),
            # Brief
            section_card(brief_panel()),
            # Snapshots
            section_card(snapshots_panel()),
            spacing="5",
            width="100%",
        ),
        padding="6",
        flex="1",
        background="#f8fafc",
        min_height="100vh",
        overflow_y="auto",
    )


# ── Error page ────────────────────────────────────────────────────────────────


def error_page() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.icon(tag="server-crash", size=40, color="#f43f5e"),
            rx.heading("Could not connect to data", size="5", color="#0f172a"),
            rx.box(
                rx.text(
                    State.load_error,
                    size="2",
                    font_family="monospace",
                    color="#64748b",
                ),
                background="#f8fafc",
                border="1px solid #e2e8f0",
                border_radius="8px",
                padding="3",
                width="100%",
            ),
            rx.text(
                "Run `make bootstrap && make seed && make etl` to initialize the pipeline.",
                size="2",
                color="#94a3b8",
            ),
            spacing="4",
            align="center",
            max_width="480px",
        ),
        height="100vh",
        background="#f8fafc",
    )


# ── Root page ─────────────────────────────────────────────────────────────────


def index() -> rx.Component:
    return rx.cond(
        State.load_error != "",
        error_page(),
        rx.hstack(
            sidebar(),
            main_content(),
            spacing="0",
            align="start",
            width="100%",
        ),
    )


app = rx.App(
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    ],
)
app.add_page(index, route="/", on_load=State.on_load)
