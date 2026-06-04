from dagster import AssetIn, MetadataValue, Output, asset

from adsignal.spark.etl import run_etl


@asset(
    group_name="etl",
    ins={"raw_ad_creatives": AssetIn()},
    description="Run PySpark ETL: MongoDB → raw_creatives Iceberg table → brand_weekly_signals",
)
def iceberg_brand_signals(context, raw_ad_creatives: dict) -> Output[dict]:
    """Run PySpark ETL pipeline."""
    result = run_etl()

    return Output(
        value=result,
        metadata={
            "raw_rows": MetadataValue.int(result["raw_rows"]),
            "signal_rows": MetadataValue.int(result["signal_rows"]),
        },
    )
