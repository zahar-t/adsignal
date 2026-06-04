"""
Writes raw creative documents to MongoDB with upsert deduplication.
Uses source_id + source as the natural key.
"""
import structlog
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

from adsignal.config import settings

log = structlog.get_logger()


def get_mongo_client() -> MongoClient:
    return MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)


def upsert_creatives(docs: list[dict], collection_name: str = "raw_creatives") -> dict:
    """
    Upsert a list of creative documents.
    Returns {"upserted": N, "modified": N, "errors": N}
    """
    if not docs:
        return {"upserted": 0, "modified": 0, "errors": 0}

    client = get_mongo_client()
    db = client[settings.mongo_db]
    collection = db[collection_name]

    operations = [
        UpdateOne(
            filter={"source_id": doc["source_id"], "source": doc["source"]},
            update={"$setOnInsert": doc},   # only insert, never overwrite
            upsert=True,
        )
        for doc in docs
    ]

    try:
        result = collection.bulk_write(operations, ordered=False)
        log.info(
            "mongo_upsert_complete",
            upserted=result.upserted_count,
            modified=result.modified_count,
            total=len(docs),
        )
        return {
            "upserted": result.upserted_count,
            "modified": result.modified_count,
            "errors": 0,
        }
    except BulkWriteError as e:
        n_errors = len(e.details.get("writeErrors", []))
        log.error("mongo_bulk_write_error", errors=n_errors)
        return {"upserted": 0, "modified": 0, "errors": n_errors}
    finally:
        client.close()


def fetch_creatives_for_brand(
    brand: str,
    limit: int = 50_000,
    collection_name: str = "raw_creatives",
) -> list[dict]:
    """Read all creative docs for a brand from MongoDB."""
    client = get_mongo_client()
    db = client[settings.mongo_db]
    docs = list(
        db[collection_name]
        .find({"brand": brand}, {"_id": 0})
        .sort("ingested_at", -1)
        .limit(limit)
    )
    client.close()
    return docs


def fetch_all_creatives(limit: int = 500_000, collection_name: str = "raw_creatives") -> list[dict]:
    """Read all creative docs — used by PySpark ETL via driver collect."""
    client = get_mongo_client()
    db = client[settings.mongo_db]
    docs = list(db[collection_name].find({}, {"_id": 0}).limit(limit))
    client.close()
    return docs
