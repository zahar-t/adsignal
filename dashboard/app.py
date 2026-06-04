"""
AdSignal Streamlit Dashboard.

Features:
- Brand selector
- Weekly spend trend chart (Plotly)
- Channel mix donut chart
- Anomaly flags overlay
- LLM brief panel with regenerate button
- Iceberg snapshot inspector (time-travel)

Usage: streamlit run dashboard/app.py
"""
import pandas as pd
import plotly.express as px
import streamlit as st
from pyiceberg.catalog import load_catalog

from adsignal.config import settings
from adsignal.llm.narrative import generate_brief
from adsignal.models.signal_builder import build_signal_summary

st.set_page_config(
    page_title="AdSignal Intelligence",
    page_icon="💡",
    layout="wide",
)

# ── Cache catalog + data ───────────────────────────────────────────────────────

@st.cache_resource
def get_catalog():
    return load_catalog(
        "adsignal",
        **{
            "type": "rest",
            "uri": settings.iceberg_rest_uri,
            "warehouse": settings.iceberg_warehouse,
            "s3.endpoint": settings.iceberg_s3_endpoint,
            "s3.access-key-id": settings.iceberg_s3_access_key,
            "s3.secret-access-key": settings.iceberg_s3_secret_key,
            "s3.path-style-access": "true",
        }
    )


@st.cache_data(ttl=300)
def load_signals_df() -> pd.DataFrame:
    catalog = get_catalog()
    table = catalog.load_table("ad_intelligence.brand_weekly_signals")
    return table.scan().to_pandas()


@st.cache_data(ttl=60)
def load_snapshots(table_name: str) -> list[dict]:
    catalog = get_catalog()
    table = catalog.load_table(f"ad_intelligence.{table_name}")
    return [
        {
            "snapshot_id": s.snapshot_id,
            "committed_at": pd.to_datetime(s.timestamp_ms, unit="ms"),
            "operation": (s.summary or {}).get("operation", "unknown"),
            "added_records": int((s.summary or {}).get("added-records", 0)),
        }
        for s in table.snapshots()
    ]


# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("💡 AdSignal")
st.sidebar.caption("Competitive Ad Intelligence Platform")

try:
    df = load_signals_df()
    available_brands = sorted(df["brand"].unique().tolist())
except Exception as e:
    st.error(f"Could not load data from Iceberg: {e}")
    st.info("Run `make bootstrap && make seed && make etl` first.")
    st.stop()

selected_brand = st.sidebar.selectbox("Select Brand", available_brands)
selected_channels = st.sidebar.multiselect(
    "Channels",
    options=sorted(df["channel"].unique().tolist()),
    default=sorted(df["channel"].unique().tolist()),
)

st.sidebar.divider()
st.sidebar.caption(f"LLM Provider: `{settings.llm_provider}` ({settings.llm_model})")

# ── Main content ──────────────────────────────────────────────────────────────

st.title(f"📊 {selected_brand.upper()} — Competitive Intelligence")

brand_df = df[(df["brand"] == selected_brand) & (df["channel"].isin(selected_channels))]

if brand_df.empty:
    st.warning(f"No data for brand: {selected_brand}")
    st.stop()

# KPI row
col1, col2, col3, col4 = st.columns(4)
with col1:
    total_spend = brand_df["spend_midpoint"].sum()
    st.metric("Total Est. Spend", f"${total_spend:,.0f}")
with col2:
    total_ads = brand_df["ad_count"].sum()
    st.metric("Total Ads Tracked", f"{int(total_ads):,}")
with col3:
    weeks_tracked = brand_df["week_key"].nunique()
    st.metric("Weeks Tracked", weeks_tracked)
with col4:
    active_channels = brand_df["channel"].nunique()
    st.metric("Active Channels", active_channels)

st.divider()

# ── Spend Trend Chart ─────────────────────────────────────────────────────────
st.subheader("Weekly Spend Trend by Channel")

weekly_trend = (
    brand_df
    .groupby(["week_key", "channel"])["spend_midpoint"]
    .sum()
    .reset_index()
    .sort_values("week_key")
)

fig_trend = px.line(
    weekly_trend,
    x="week_key",
    y="spend_midpoint",
    color="channel",
    title=f"{selected_brand.upper()} — Weekly Spend Midpoint Estimate",
    labels={"spend_midpoint": "Est. Spend ($)", "week_key": "Week"},
)
fig_trend.update_layout(height=350)
st.plotly_chart(fig_trend, use_container_width=True)

# ── Channel Mix Donut ─────────────────────────────────────────────────────────
col_mix, col_anomaly = st.columns(2)

with col_mix:
    st.subheader("Channel Mix (Recent 4 Weeks)")
    recent_weeks = sorted(brand_df["week_key"].unique())[-4:]
    recent_df = brand_df[brand_df["week_key"].isin(recent_weeks)]
    channel_totals = recent_df.groupby("channel")["spend_midpoint"].sum().reset_index()

    fig_donut = px.pie(
        channel_totals,
        names="channel",
        values="spend_midpoint",
        hole=0.4,
        title="Recent Channel Mix",
    )
    fig_donut.update_layout(height=300)
    st.plotly_chart(fig_donut, use_container_width=True)

# ── Anomaly Flags ─────────────────────────────────────────────────────────────
with col_anomaly:
    st.subheader("Anomaly Detection")
    st.caption("Isolation Forest — flagged weeks with anomalous spend patterns")

    try:
        summary = build_signal_summary(df, selected_brand)
        anomaly_weeks = summary.get("anomaly_weeks", [])
        if anomaly_weeks:
            st.error(f"🚨 {len(anomaly_weeks)} anomalous week(s) detected")
            for w in anomaly_weeks[-5:]:
                st.write(f"  • `{w}`")
        else:
            st.success("✅ No anomalies detected in recent history")
    except Exception as e:
        st.warning(f"Anomaly detection error: {e}")

st.divider()

# ── LLM Intelligence Brief ────────────────────────────────────────────────────
st.subheader("🤖 AI Intelligence Brief")
st.caption(f"Generated by {settings.llm_provider} / {settings.llm_model}")

if "brief" not in st.session_state or st.session_state.get("brief_brand") != selected_brand:
    with st.spinner("Generating intelligence brief..."):
        try:
            summary = build_signal_summary(df, selected_brand)
            brief = generate_brief(selected_brand, summary)
            st.session_state["brief"] = brief
            st.session_state["brief_brand"] = selected_brand
        except Exception as e:
            st.session_state["brief"] = f"Brief generation failed: {e}"

st.info(st.session_state.get("brief", ""))

if st.button("🔄 Regenerate Brief"):
    del st.session_state["brief"]
    st.rerun()

st.divider()

# ── Iceberg Time-Travel ───────────────────────────────────────────────────────
st.subheader("🕰️ Iceberg Snapshot History")
st.caption("Time-travel: each row is an Iceberg snapshot (ETL run) you can query point-in-time")

try:
    snapshots = load_snapshots("brand_weekly_signals")
    if snapshots:
        snap_df = pd.DataFrame(snapshots).sort_values("committed_at", ascending=False)
        st.dataframe(snap_df, use_container_width=True, height=200)
    else:
        st.info("No snapshots yet — run the ETL pipeline first.")
except Exception as e:
    st.warning(f"Could not load snapshots: {e}")
