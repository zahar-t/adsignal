"""
SparkSession factory with full Iceberg + S3/MinIO catalog configuration.

GOTCHA: PySpark 4.x ships with its own bundled Iceberg runtime.
Do NOT add iceberg JARs manually — use the built-in Iceberg support via
spark.sql.extensions and spark.sql.catalog.* config.
GOTCHA: s3a:// is the Hadoop S3A connector. When using MinIO locally,
set fs.s3a.endpoint to the MinIO URL and fs.s3a.path.style.access=true.
"""
from pyspark.sql import SparkSession

from adsignal.config import settings


def get_spark_session(app_name: str | None = None) -> SparkSession:
    return (
        SparkSession.builder
        .master(settings.spark_master)
        .appName(app_name or settings.spark_app_name)
        # Iceberg extensions
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
        )
        # Iceberg REST catalog — named "adsignal"
        .config("spark.sql.catalog.adsignal", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.adsignal.type", "rest")
        .config("spark.sql.catalog.adsignal.uri", settings.iceberg_rest_uri)
        .config("spark.sql.catalog.adsignal.warehouse", settings.iceberg_warehouse)
        # S3A connector config for MinIO
        .config("spark.sql.catalog.adsignal.s3.endpoint", settings.iceberg_s3_endpoint)
        .config("spark.sql.catalog.adsignal.s3.access-key-id", settings.iceberg_s3_access_key)
        .config("spark.sql.catalog.adsignal.s3.secret-access-key", settings.iceberg_s3_secret_key)
        .config("spark.sql.catalog.adsignal.s3.path-style-access", "true")
        # Hadoop S3A config (needed for the Spark job to actually read/write files)
        .config("spark.hadoop.fs.s3a.endpoint", settings.iceberg_s3_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", settings.iceberg_s3_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", settings.iceberg_s3_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        # Performance
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        # Silence verbose logging
        .config("spark.driver.extraJavaOptions", "-Dlog4j.logLevel=WARN")
        .getOrCreate()
    )
