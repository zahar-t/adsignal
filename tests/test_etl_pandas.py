"""Tests for the Spark-free pandas ETL aggregation (adsignal/etl_pandas.py)."""
import pandas as pd

from adsignal.etl_pandas import aggregate_creatives_pandas
from adsignal.ingest.synthetic import generate_brand_batch


def _raw_df():
    docs = []
    for brand in ("nike", "adidas"):
        docs.extend(generate_brand_batch(brand, n_weeks=6, ads_per_week=20))
    return pd.DataFrame(docs)


def test_aggregate_produces_signal_schema():
    agg = aggregate_creatives_pandas(_raw_df())
    expected = {
        "brand", "week_key", "channel", "region", "ad_count", "active_ad_count",
        "impression_lower_sum", "impression_upper_sum", "spend_lower_sum",
        "spend_upper_sum", "spend_midpoint", "top_ctas", "top_themes",
        "channel_share", "etl_timestamp",
    }
    assert expected.issubset(set(agg.columns))
    assert not agg.empty


def test_spend_midpoint_is_sum_of_row_midpoints():
    raw = pd.DataFrame(
        [
            {"brand": "x", "week_key": "2024-W01", "channel": "video", "region": "US",
             "spend_lower": 100.0, "spend_upper": 300.0, "impression_lower": 10,
             "impression_upper": 20, "is_active": True, "cta": "Buy", "creative_themes": ["a"]},
            {"brand": "x", "week_key": "2024-W01", "channel": "video", "region": "US",
             "spend_lower": 0.0, "spend_upper": 100.0, "impression_lower": 5,
             "impression_upper": 15, "is_active": False, "cta": "Buy", "creative_themes": ["b"]},
        ]
    )
    agg = aggregate_creatives_pandas(raw)
    row = agg.iloc[0]
    # (100+300)/2 + (0+100)/2 = 200 + 50 = 250
    assert row["spend_midpoint"] == 250.0
    assert row["ad_count"] == 2
    assert row["active_ad_count"] == 1


def test_channel_share_sums_to_one_per_brand_week():
    agg = aggregate_creatives_pandas(_raw_df())
    totals = agg.groupby(["brand", "week_key"])["channel_share"].sum()
    for t in totals:
        assert abs(t - 1.0) < 1e-6


def test_top_themes_and_ctas_bounded_and_distinct():
    agg = aggregate_creatives_pandas(_raw_df())
    for themes in agg["top_themes"]:
        assert len(themes) <= 5
        assert len(themes) == len(set(themes))
    for ctas in agg["top_ctas"]:
        assert len(ctas) <= 3
        assert len(ctas) == len(set(ctas))


def test_aggregate_empty_input():
    agg = aggregate_creatives_pandas(pd.DataFrame())
    assert agg.empty
