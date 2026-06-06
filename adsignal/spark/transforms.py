"""
PySpark transform functions: raw creatives → brand_weekly_signals.

All functions take and return Spark DataFrames.
Pure functions — no side effects, no SparkSession dependency (passed in via df).
"""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def cast_date_columns(df: DataFrame) -> DataFrame:
    """Cast string date columns to DateType."""
    return (
        df
        .withColumn("started_running", F.to_date("started_running"))
        .withColumn("stopped_running", F.to_date("stopped_running"))
        .withColumn("ingested_at", F.to_timestamp("ingested_at"))
    )


def add_spend_midpoint(df: DataFrame) -> DataFrame:
    """Add spend_midpoint = (spend_lower + spend_upper) / 2."""
    return df.withColumn(
        "spend_midpoint",
        (F.col("spend_lower") + F.col("spend_upper")) / 2.0
    )


def aggregate_weekly_signals(df: DataFrame) -> DataFrame:
    """
    Aggregate raw creatives to brand_weekly_signals.
    Groups by brand + week_key + channel + region.
    Computes: ad counts, impression sums, spend sums, top CTAs/themes.
    """
    agg_df = (
        df
        .groupBy("brand", "week_key", "channel", "region")
        .agg(
            F.count("*").alias("ad_count"),
            F.sum(F.col("is_active").cast("int")).alias("active_ad_count"),
            F.sum("impression_lower").alias("impression_lower_sum"),
            F.sum("impression_upper").alias("impression_upper_sum"),
            F.sum("spend_lower").alias("spend_lower_sum"),
            F.sum("spend_upper").alias("spend_upper_sum"),
            F.sum("spend_midpoint").alias("spend_midpoint"),
            F.collect_list("cta").alias("all_ctas"),
            F.flatten(F.collect_list("creative_themes")).alias("all_themes"),
        )
        .withColumn("top_ctas", F.slice(F.array_distinct("all_ctas"), 1, 3))
        .withColumn("top_themes", F.slice(F.array_distinct("all_themes"), 1, 5))
        .drop("all_ctas", "all_themes")
    )

    # Channel share: this channel's total estimated spend / total brand+week spend.
    brand_week_window = Window.partitionBy("brand", "week_key")
    agg_df = agg_df.withColumn(
        "channel_share",
        F.col("spend_midpoint") / F.sum("spend_midpoint").over(brand_week_window)
    )

    return agg_df.withColumn("etl_timestamp", F.current_timestamp())


def clean_nulls(df: DataFrame) -> DataFrame:
    """Fill nulls for numeric columns with 0, strings with 'unknown'."""
    numeric_cols = ["impression_lower", "impression_upper", "spend_lower", "spend_upper", "spend_midpoint"]
    string_cols = ["region", "platform", "cta"]

    for col in numeric_cols:
        if col in df.columns:
            df = df.fillna({col: 0})
    for col in string_cols:
        if col in df.columns:
            df = df.fillna({col: "unknown"})
    return df
