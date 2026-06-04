#!/usr/bin/env python3
"""
Bootstrap Iceberg: create namespace and empty tables in Lakekeeper.
Run ONCE before the first ETL job.

Usage: python scripts/bootstrap_iceberg.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    NestedField, StringType, LongType, DoubleType,
    BooleanType, TimestampType, ListType, IntegerType
)
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import IdentityTransform
from adsignal.config import settings

CATALOG_CONFIG = {
    "type": "rest",
    "uri": settings.iceberg_rest_uri,
    "warehouse": settings.iceberg_warehouse,
    "s3.endpoint": settings.iceberg_s3_endpoint,
    "s3.access-key-id": settings.iceberg_s3_access_key,
    "s3.secret-access-key": settings.iceberg_s3_secret_key,
    "s3.path-style-access": "true",
}

NAMESPACE = ("ad_intelligence",)


def main():
    catalog = load_catalog("adsignal", **CATALOG_CONFIG)

    # Create namespace
    if NAMESPACE not in [tuple(ns) for ns in catalog.list_namespaces()]:
        catalog.create_namespace(NAMESPACE)
        print(f"✓ Created namespace: {'.'.join(NAMESPACE)}")
    else:
        print(f"  Namespace already exists: {'.'.join(NAMESPACE)}")

    # Create brand_weekly_signals table
    signals_identifier = (*NAMESPACE, "brand_weekly_signals")
    if not catalog.table_exists(signals_identifier):
        signals_schema = Schema(
            NestedField(1, "brand", StringType(), required=True),
            NestedField(2, "week_key", StringType(), required=True),
            NestedField(3, "channel", StringType(), required=True),
            NestedField(4, "region", StringType()),
            NestedField(5, "ad_count", IntegerType()),
            NestedField(6, "active_ad_count", IntegerType()),
            NestedField(7, "impression_lower_sum", LongType()),
            NestedField(8, "impression_upper_sum", LongType()),
            NestedField(9, "spend_lower_sum", DoubleType()),
            NestedField(10, "spend_upper_sum", DoubleType()),
            NestedField(11, "spend_midpoint", DoubleType()),
            NestedField(12, "top_ctas", ListType(element_id=20, element_type=StringType())),
            NestedField(13, "top_themes", ListType(element_id=21, element_type=StringType())),
            NestedField(14, "channel_share", DoubleType()),
            NestedField(15, "etl_timestamp", TimestampType()),
        )
        partition_spec = PartitionSpec(
            PartitionField(source_id=1, field_id=1000, transform=IdentityTransform(), name="brand"),
            PartitionField(source_id=2, field_id=1001, transform=IdentityTransform(), name="week_key"),
        )
        catalog.create_table(
            identifier=signals_identifier,
            schema=signals_schema,
            partition_spec=partition_spec,
        )
        print(f"✓ Created table: {'.'.join(signals_identifier)}")
    else:
        print(f"  Table already exists: {'.'.join(signals_identifier)}")

    print("\nBootstrap complete. Run 'make seed' then 'make etl' to populate.")


if __name__ == "__main__":
    main()
