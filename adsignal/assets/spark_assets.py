from dagster import MetadataValue, Output, asset

from adsignal.spark.etl import run_etl


@asset(
    group_name="etl",
    deps=["raw_ad_creatives"],
    description="Run PySpark ETL: MongoDB → raw_creatives Iceberg table → brand_weekly_signals",
)
def iceberg_brand_signals(context) -> Output[dict]:
    """Run PySpark ETL pipeline."""
    result = run_etl()

    return Output(
        value=result,
        metadata={
            "raw_rows": MetadataValue.int(result["raw_rows"]),
            "signal_rows": MetadataValue.int(result["signal_rows"]),
        },
    )
