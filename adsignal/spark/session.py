"""
SparkSession factory with full Iceberg + S3/MinIO catalog configuration.

GOTCHA: s3a:// is the Hadoop S3A connector. When using MinIO locally,
set fs.s3a.endpoint to the MinIO URL and fs.s3a.path.style.access=true.
"""
from pyspark.sql import SparkSession

from adsignal.config import settings
from adsignal.spark.java import MIN_JAVA_MAJOR, ensure_java


def get_spark_session(app_name: str | None = None) -> SparkSession:
    # PySpark 4.x needs Java 17+. Point the JVM at a suitable JDK (e.g. a
    # keg-only Homebrew openjdk@17) so the session starts without the user
    # having to export JAVA_HOME by hand.
    if ensure_java(MIN_JAVA_MAJOR) is None:
        raise RuntimeError(
            f"PySpark requires Java {MIN_JAVA_MAJOR}+ but none was found. Install it "
            "(macOS: `brew install openjdk@17`) or run the ETL with --engine pandas."
        )

    # Lakekeeper vends MinIO's docker-internal hostname (e.g. "minio") to the
    # Spark JVM. When that name doesn't resolve on this host, point the JVM at a
    # custom hosts file so its S3 writes reach the published MinIO port. The file
    # replaces all JVM resolution, so bind the driver to loopback to avoid relying
    # on the machine hostname.
    from adsignal.lakehouse_dns import jvm_hosts_file

    driver_java_opts = "-Dlog4j.logLevel=WARN"
    builder = SparkSession.builder
    hosts_file = jvm_hosts_file()
    if hosts_file:
        driver_java_opts = f"{driver_java_opts} -Djdk.net.hosts.file={hosts_file}"
        builder = builder.config("spark.driver.host", "127.0.0.1").config(
            "spark.driver.bindAddress", "127.0.0.1"
        )

    return (
        builder
        .master(settings.spark_master)
        .appName(app_name or settings.spark_app_name)
        # Iceberg runtime jars for Spark 4.x and S3-compatible storage.
        .config(
            "spark.jars.packages",
            ",".join([
                "org.apache.iceberg:iceberg-spark-runtime-4.0_2.13:1.10.1",
                "org.apache.iceberg:iceberg-aws-bundle:1.10.1",
            ]),
        )
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
        # Silence verbose logging (+ optional JVM hosts file for MinIO resolution)
        .config("spark.driver.extraJavaOptions", driver_java_opts)
        .config("spark.executor.extraJavaOptions", driver_java_opts)
        .getOrCreate()
    )
