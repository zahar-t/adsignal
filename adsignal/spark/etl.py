"""
Main ETL: MongoDB → PySpark → Iceberg.

Flow:
1. Read raw_creatives from MongoDB via driver (collect to pandas, then parallelize)
2. Apply schema + transforms
3. Write raw_creatives table to Iceberg (append, partitioned by brand + week_key)
4. Compute brand_weekly_signals aggregate
5. Write brand_weekly_signals to Iceberg (overwrite partition for idempotency)
"""
import pandas as pd
import structlog
from pyspark.sql import DataFrame, SparkSession

from adsignal.ingest.mongo_writer import fetch_all_creatives
from adsignal.spark.schemas import RAW_CREATIVES_SCHEMA
from adsignal.spark.session import get_spark_session
from adsignal.spark.transforms import (
    add_spend_midpoint,
    aggregate_weekly_signals,
    cast_date_columns,
    clean_nulls,
)

log = structlog.get_logger()

CATALOG = "adsignal"
NAMESPACE = "ad_intelligence"
RAW_TABLE = f"{CATALOG}.{NAMESPACE}.raw_creatives"
SIGNALS_TABLE = f"{CATALOG}.{NAMESPACE}.brand_weekly_signals"


def run_etl(spark: SparkSession | None = None) -> dict:
    """
    Run the full ETL pipeline.
    Returns {"raw_rows": N, "signal_rows": N}
    """
    if spark is None:
        spark = get_spark_session()

    log.info("etl_start")

    # 1. Read from MongoDB
    log.info("fetching_from_mongodb")
    raw_docs = fetch_all_creatives()
    if not raw_docs:
        log.warning("no_documents_in_mongodb_run_seed_first")
        return {"raw_rows": 0, "signal_rows": 0}

    log.info("mongo_docs_fetched", count=len(raw_docs))

    # 2. Convert to Spark DataFrame via Pandas
    # GOTCHA: ArrayType fields (creative_themes) must be lists, not sets
    for doc in raw_docs:
        if isinstance(doc.get("creative_themes"), set):
            doc["creative_themes"] = list(doc["creative_themes"])

    pdf = pd.DataFrame(raw_docs)
    # Ensure all schema columns exist in pandas df; fill missing with None
    for field in RAW_CREATIVES_SCHEMA.fields:
        if field.name not in pdf.columns:
            pdf[field.name] = None
    pdf = pdf[[field.name for field in RAW_CREATIVES_SCHEMA.fields]]
    pdf = pdf.astype(object).where(pd.notna(pdf), None)

    df_raw: DataFrame = spark.createDataFrame(pdf, schema=RAW_CREATIVES_SCHEMA)
    df_raw = clean_nulls(cast_date_columns(add_spend_midpoint(df_raw)))

    raw_count = df_raw.count()
    log.info("spark_dataframe_created", rows=raw_count)

    # 3. Write raw_creatives to Iceberg
    # GOTCHA: MERGE INTO requires primary keys. For append-only raw layer,
    # use append mode and rely on source_id dedup at query time.
    (
        df_raw.write
        .format("iceberg")
        .mode("append")
        .option("fanout-enabled", "true")
        .partitionBy("brand", "week_key")
        .saveAsTable(RAW_TABLE)
    )
    log.info("raw_creatives_written", table=RAW_TABLE, rows=raw_count)

    # 4. Aggregate → brand_weekly_signals
    df_signals = aggregate_weekly_signals(df_raw)
    signal_count = df_signals.count()

    # 5. Write signals — DYNAMIC OVERWRITE so re-runs are idempotent per partition
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    (
        df_signals.write
        .format("iceberg")
        .mode("overwrite")
        .option("fanout-enabled", "true")
        .partitionBy("brand", "week_key")
        .saveAsTable(SIGNALS_TABLE)
    )
    log.info("brand_weekly_signals_written", table=SIGNALS_TABLE, rows=signal_count)

    return {"raw_rows": raw_count, "signal_rows": signal_count}
