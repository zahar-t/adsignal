#!/usr/bin/env python3
"""
Bootstrap Iceberg: create namespace and empty tables in Lakekeeper.
Run ONCE before the first ETL job.

Usage: python scripts/bootstrap_iceberg.py
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from pyiceberg.catalog import load_catalog
from pyiceberg.partitioning import PartitionField, PartitionSpec
from pyiceberg.schema import Schema
from pyiceberg.transforms import IdentityTransform
from pyiceberg.types import (
    DoubleType,
    IntegerType,
    ListType,
    LongType,
    NestedField,
    StringType,
    TimestampType,
)

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


def _management_url(path: str) -> str:
    base_url = settings.iceberg_rest_uri.removesuffix("/catalog").rstrip("/")
    return f"{base_url}/management/v1/{path.lstrip('/')}"


def _ensure_lakekeeper_warehouse() -> None:
    """Initialize Lakekeeper management state and create the configured warehouse."""
    with httpx.Client(timeout=30) as client:
        bootstrap_response = client.post(
            _management_url("bootstrap"),
            json={
                "accept-terms-of-use": True,
                "is-operator": True,
                "user-name": "adsignal-local",
                "user-type": "application",
            },
        )
        already_bootstrapped = (
            bootstrap_response.status_code == 400
            and bootstrap_response.json().get("error", {}).get("type")
            == "CatalogAlreadyBootstrapped"
        )
        if bootstrap_response.status_code not in {204, 409} and not already_bootstrapped:
            bootstrap_response.raise_for_status()

        warehouses_response = client.get(_management_url("warehouse"))
        warehouses_response.raise_for_status()
        warehouses = warehouses_response.json().get("warehouses", [])
        if any(warehouse.get("name") == settings.iceberg_warehouse for warehouse in warehouses):
            return

        warehouse_response = client.post(
            _management_url("warehouse"),
            json={
                "warehouse-name": settings.iceberg_warehouse,
                "storage-profile": {
                    "type": "s3",
                    "bucket": settings.iceberg_warehouse.removeprefix("s3://").strip("/"),
                    "region": "us-east-1",
                    "endpoint": settings.iceberg_s3_endpoint,
                    "path-style-access": True,
                    "sts-enabled": False,
                },
                "storage-credential": {
                    "type": "s3",
                    "credential-type": "access-key",
                    "access-key-id": settings.iceberg_s3_access_key,
                    "secret-access-key": settings.iceberg_s3_secret_key,
                },
            },
        )
        if warehouse_response.status_code not in {201, 409}:
            warehouse_response.raise_for_status()


def main():
    _ensure_lakekeeper_warehouse()
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
