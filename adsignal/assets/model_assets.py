import pandas as pd
from dagster import AssetIn, MetadataValue, Output, asset

from adsignal.catalog import get_catalog_reader
from adsignal.config import settings
from adsignal.models.signal_builder import build_signal_summary


@asset(
    group_name="models",
    ins={"iceberg_brand_signals": AssetIn()},
    description="Run Prophet + Isolation Forest per brand; build signal summaries",
)
def brand_signal_summaries(context, iceberg_brand_signals: dict) -> Output[dict]:
    """Build signal summaries for all brands."""
    # Read from Iceberg via PyIceberg
    reader = get_catalog_reader()
    table = reader.load_table("ad_intelligence.brand_weekly_signals")
    signals_df: pd.DataFrame = table.scan().to_pandas()

    summaries = {}
    for brand in settings.brands:
        context.log.info(f"Building signal summary for {brand}")
        summary = build_signal_summary(signals_df, brand)
        summaries[brand] = summary

    return Output(
        value=summaries,
        metadata={"brands_processed": MetadataValue.int(len(summaries))},
    )
