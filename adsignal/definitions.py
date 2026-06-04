"""
Dagster Definitions entrypoint.

Registers:
- All software-defined assets (4 groups: ingestion, etl, models, intelligence)
- Resources (MongoDB, Spark)
- Schedules (nightly_full_pipeline — runs automatically at midnight UTC)
- Sensors (new_mongo_data_sensor — off by default, enable in UI for event-driven mode)
"""
from dagster import Definitions, load_assets_from_modules

from adsignal.assets import brief_assets, ingest_assets, model_assets, spark_assets
from adsignal.resources.mongo_resource import MongoResource
from adsignal.resources.spark_resource import SparkResource
from adsignal.schedules import mongo_sensor, nightly_schedule

all_assets = load_assets_from_modules([
    ingest_assets,
    spark_assets,
    model_assets,
    brief_assets,
])

defs = Definitions(
    assets=all_assets,
    resources={
        "mongo": MongoResource(),
        "spark": SparkResource(),
    },
    schedules=[nightly_schedule],
    sensors=[mongo_sensor],
)
