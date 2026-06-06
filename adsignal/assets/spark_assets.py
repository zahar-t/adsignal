from dagster import MetadataValue, Output, asset


@asset(
    group_name="etl",
    deps=["raw_ad_creatives"],
    description="Run ETL: MongoDB → raw_creatives Iceberg table → brand_weekly_signals",
)
def iceberg_brand_signals(context) -> Output[dict]:
    """Run the ETL pipeline.

    Prefers the PySpark engine, but transparently falls back to the Spark-free
    pandas/PyIceberg engine when Spark can't start (e.g. no Java 17 on the runner),
    so the asset still materializes instead of failing the whole pipeline.
    """
    engine = "spark"
    try:
        from adsignal.spark.etl import run_etl

        result = run_etl()
    except Exception as exc:  # JVM missing, Spark init failure, etc.
        context.log.warning(f"Spark ETL failed ({exc}); falling back to pandas engine.")
        from adsignal.etl_pandas import run_pandas_etl

        result = run_pandas_etl()
        engine = "pandas"

    return Output(
        value=result,
        metadata={
            "engine": MetadataValue.text(engine),
            "raw_rows": MetadataValue.int(result["raw_rows"]),
            "signal_rows": MetadataValue.int(result["signal_rows"]),
        },
    )
