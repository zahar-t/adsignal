"""PyIceberg REST catalog factory for reading Iceberg tables."""
from pyiceberg.catalog import load_catalog

from adsignal.config import settings


def get_catalog_reader():
    """Return a PyIceberg catalog connected to Lakekeeper."""
    return load_catalog(
        "adsignal",
        **{
            "type": "rest",
            "uri": settings.iceberg_rest_uri,
            "warehouse": settings.iceberg_warehouse,
            "s3.endpoint": settings.iceberg_s3_endpoint,
            "s3.access-key-id": settings.iceberg_s3_access_key,
            "s3.secret-access-key": settings.iceberg_s3_secret_key,
            "s3.path-style-access": "true",
        }
    )
