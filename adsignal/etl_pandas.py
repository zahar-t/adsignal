"""
Spark-free ETL: MongoDB → pandas → Iceberg (via PyIceberg).

This is a drop-in fallback for adsignal/spark/etl.py that produces an identical
``brand_weekly_signals`` table without requiring a JVM / Java 17 / PySpark.

Why this exists:
    PySpark 4.x needs Java 17+. On machines (and CI runners) that only have an
    older JRE — or no Java at all — ``make etl`` fails and the Iceberg table is
    never populated, which leaves the dashboard with no data and blank charts.
    This module reproduces the aggregation in pure pandas and writes the result
    to the same Iceberg table through PyIceberg, so the pipeline runs anywhere.

The aggregation mirrors ``adsignal.spark.transforms.aggregate_weekly_signals``:
group by (brand, week_key, channel, region) and compute counts, impression/spend
sums, the summed spend midpoint, top distinct CTAs/themes, and channel share.
"""
from __future__ import annotations

import pandas as pd
import pyarrow as pa
import structlog

from adsignal.ingest.mongo_writer import fetch_all_creatives

log = structlog.get_logger()

NAMESPACE = "ad_intelligence"
SIGNALS_TABLE = f"{NAMESPACE}.brand_weekly_signals"


def _first_n_distinct(values: list, n: int) -> list[str]:
    """First ``n`` distinct, non-null values preserving order (≈ Spark array_distinct + slice)."""
    seen: list[str] = []
    for v in values:
        if v is None or v in seen:
            continue
        seen.append(v)
        if len(seen) >= n:
            break
    return seen


def _flatten_distinct(list_of_lists: list, n: int) -> list[str]:
    """Flatten lists, keep first ``n`` distinct values (≈ Spark flatten + array_distinct + slice)."""
    seen: list[str] = []
    for inner in list_of_lists:
        if not isinstance(inner, list):
            continue
        for v in inner:
            if v is not None and v not in seen:
                seen.append(v)
    return seen[:n]


def aggregate_creatives_pandas(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate raw creative documents to brand_weekly_signals (pure pandas).

    Faithful port of ``aggregate_weekly_signals`` + ``add_spend_midpoint``:
    one row per (brand, week_key, channel, region).
    """
    if raw_df.empty:
        return pd.DataFrame()

    df = raw_df.copy()

    # spend_midpoint per row = (spend_lower + spend_upper) / 2  (add_spend_midpoint)
    df["spend_lower"] = pd.to_numeric(df.get("spend_lower"), errors="coerce").fillna(0.0)
    df["spend_upper"] = pd.to_numeric(df.get("spend_upper"), errors="coerce").fillna(0.0)
    df["impression_lower"] = pd.to_numeric(df.get("impression_lower"), errors="coerce").fillna(0)
    df["impression_upper"] = pd.to_numeric(df.get("impression_upper"), errors="coerce").fillna(0)
    df["_spend_mid_row"] = (df["spend_lower"] + df["spend_upper"]) / 2.0
    df["_is_active_int"] = df.get("is_active").fillna(False).astype(int)
    df["region"] = df.get("region").fillna("unknown")

    rows = []
    for (brand, week_key, channel, region), sub in df.groupby(
        ["brand", "week_key", "channel", "region"], dropna=False
    ):
        rows.append(
            {
                "brand": brand,
                "week_key": week_key,
                "channel": channel,
                "region": region,
                "ad_count": int(len(sub)),
                "active_ad_count": int(sub["_is_active_int"].sum()),
                "impression_lower_sum": int(sub["impression_lower"].sum()),
                "impression_upper_sum": int(sub["impression_upper"].sum()),
                "spend_lower_sum": float(sub["spend_lower"].sum()),
                "spend_upper_sum": float(sub["spend_upper"].sum()),
                "spend_midpoint": float(sub["_spend_mid_row"].sum()),
                "top_ctas": _first_n_distinct(sub["cta"].tolist(), 3),
                "top_themes": _flatten_distinct(sub["creative_themes"].tolist(), 5),
            }
        )

    agg = pd.DataFrame(rows)
    if agg.empty:
        return agg

    # channel_share = this channel's spend / total brand+week spend (Window partitionBy brand, week_key)
    brand_week_total = agg.groupby(["brand", "week_key"])["spend_midpoint"].transform("sum")
    agg["channel_share"] = agg["spend_midpoint"] / brand_week_total.replace(0, pd.NA)
    agg["channel_share"] = agg["channel_share"].fillna(0.0)
    agg["etl_timestamp"] = pd.Timestamp.now()
    return agg


def _to_iceberg_arrow(agg: pd.DataFrame, arrow_schema: pa.Schema) -> pa.Table:
    """Build a pyarrow Table matching the target Iceberg schema exactly (order + types)."""
    columns = {}
    for field in arrow_schema:
        col = agg[field.name]
        columns[field.name] = pa.array(col.tolist(), type=field.type)
    return pa.table(columns, schema=arrow_schema)


def run_pandas_etl(catalog=None, mode: str = "overwrite") -> dict:
    """
    Run the Spark-free ETL: read MongoDB, aggregate, write to Iceberg.

    Args:
        catalog: optional PyIceberg catalog (defaults to the configured REST catalog).
        mode: "overwrite" (idempotent — replaces the table, creates a new snapshot)
              or "append" (adds a new snapshot on top of existing data).

    Returns:
        {"raw_rows": N, "signal_rows": N}
    """
    if catalog is None:
        from adsignal.catalog import get_catalog_reader

        catalog = get_catalog_reader()

    log.info("pandas_etl_start")
    raw_docs = fetch_all_creatives()
    if not raw_docs:
        log.warning("no_documents_in_mongodb_run_seed_first")
        return {"raw_rows": 0, "signal_rows": 0}

    log.info("mongo_docs_fetched", count=len(raw_docs))
    agg = aggregate_creatives_pandas(pd.DataFrame(raw_docs))
    if agg.empty:
        log.warning("aggregation_produced_no_rows")
        return {"raw_rows": len(raw_docs), "signal_rows": 0}

    table = catalog.load_table(SIGNALS_TABLE)
    arrow_table = _to_iceberg_arrow(agg, table.schema().as_arrow())

    if mode == "append":
        table.append(arrow_table)
    else:
        table.overwrite(arrow_table)

    log.info("brand_weekly_signals_written", table=SIGNALS_TABLE, rows=len(agg), mode=mode)
    return {"raw_rows": len(raw_docs), "signal_rows": len(agg)}
