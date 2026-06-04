from dagster import ConfigurableResource

from adsignal.catalog import get_catalog_reader


class IcebergResource(ConfigurableResource):
    """Provides a PyIceberg catalog connection."""

    def get_catalog(self):
        return get_catalog_reader()
