from dagster import ConfigurableResource
from pymongo import MongoClient

from adsignal.config import settings


class MongoResource(ConfigurableResource):
    uri: str = settings.mongo_uri
    db_name: str = settings.mongo_db

    def get_client(self) -> MongoClient:
        return MongoClient(self.uri, serverSelectionTimeoutMS=5000)

    def get_db(self):
        return self.get_client()[self.db_name]
