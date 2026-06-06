"""
Deterministic sample ``brand_weekly_signals`` data for the dashboard.

Why this exists:
    The dashboard reads from the Iceberg ``brand_weekly_signals`` table. That
    table is only populated after the full pipeline runs (``make up`` →
    ``bootstrap`` → ``seed`` → ``etl``), and the Spark ETL needs Java 17. On a
    machine without the populated lakehouse, ``_signals()`` returns an empty
    frame and every chart renders blank — which looks exactly like "the charts
    are broken."

    To make the UI demonstrable out-of-the-box, the dashboard falls back to this
    sample dataset whenever the live table is empty or unreachable, and shows a
    clearly-labelled "sample data" banner so it is never mistaken for live data.

The sample is produced through the *real* synthetic + aggregation path
(``generate_brand_batch`` → ``aggregate_creatives_pandas``) with a fixed seed, so
its schema and shape match production output exactly.
"""
from __future__ import annotations

import random

import pandas as pd

from adsignal.etl_pandas import aggregate_creatives_pandas
from adsignal.ingest.synthetic import generate_brand_batch

SAMPLE_BRANDS = ["nike", "adidas", "apple", "samsung", "coca-cola"]


def build_sample_signals(seed: int = 42) -> pd.DataFrame:
    """Return a deterministic brand_weekly_signals DataFrame for demo/offline use."""
    state = random.getstate()
    try:
        random.seed(seed)
        raw: list[dict] = []
        for brand in SAMPLE_BRANDS:
            raw.extend(generate_brand_batch(brand, n_weeks=16, ads_per_week=40))
        agg = aggregate_creatives_pandas(pd.DataFrame(raw))
    finally:
        random.setstate(state)
    return agg
