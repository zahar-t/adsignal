"""PySpark StructType schemas for all Iceberg tables."""
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

RAW_CREATIVES_SCHEMA = StructType([
    StructField("source_id", StringType(), False),
    StructField("source", StringType(), False),
    StructField("brand", StringType(), False),
    StructField("brand_display", StringType(), True),
    StructField("ad_text", StringType(), True),
    StructField("cta", StringType(), True),
    StructField("channel", StringType(), False),
    StructField("platform", StringType(), True),
    StructField("impression_lower", LongType(), True),
    StructField("impression_upper", LongType(), True),
    StructField("spend_lower", DoubleType(), True),
    StructField("spend_upper", DoubleType(), True),
    StructField("started_running", StringType(), True),    # kept as string, cast in transforms
    StructField("stopped_running", StringType(), True),
    StructField("is_active", BooleanType(), True),
    StructField("currency", StringType(), True),
    StructField("region", StringType(), True),
    StructField("creative_themes", ArrayType(StringType()), True),
    StructField("ingested_at", StringType(), True),
    StructField("week_key", StringType(), False),
])

BRAND_WEEKLY_SIGNALS_SCHEMA = StructType([
    StructField("brand", StringType(), False),
    StructField("week_key", StringType(), False),
    StructField("channel", StringType(), False),
    StructField("region", StringType(), True),
    StructField("ad_count", IntegerType(), True),
    StructField("active_ad_count", IntegerType(), True),
    StructField("impression_lower_sum", LongType(), True),
    StructField("impression_upper_sum", LongType(), True),
    StructField("spend_lower_sum", DoubleType(), True),
    StructField("spend_upper_sum", DoubleType(), True),
    StructField("spend_midpoint", DoubleType(), True),        # summed midpoint spend
    StructField("top_ctas", ArrayType(StringType()), True),
    StructField("top_themes", ArrayType(StringType()), True),
    StructField("channel_share", DoubleType(), True),         # this channel / total for brand+week
    StructField("etl_timestamp", TimestampType(), True),
])
