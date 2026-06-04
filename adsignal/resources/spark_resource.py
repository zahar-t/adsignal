from dagster import ConfigurableResource
from pyspark.sql import SparkSession

from adsignal.spark.session import get_spark_session


class SparkResource(ConfigurableResource):
    app_name: str = "adsignal-dagster"

    def get_session(self) -> SparkSession:
        return get_spark_session(self.app_name)
