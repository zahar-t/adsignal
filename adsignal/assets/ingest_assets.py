from dagster import MetadataValue, Output, asset

from adsignal.config import settings
from adsignal.ingest.meta_client import fetch_brand_ads
from adsignal.ingest.mongo_writer import upsert_creatives


@asset(
    group_name="ingestion",
    description="Fetch ad creatives from Meta Ad Library (or synthetic fallback) for all brands",
)
def raw_ad_creatives(context) -> Output[dict]:
    """Ingest all brand creatives into MongoDB."""
    total_upserted = 0
    results = {}

    for brand in settings.brands:
        docs = fetch_brand_ads(brand, n_weeks=16)
        result = upsert_creatives(docs)
        results[brand] = result
        total_upserted += result["upserted"]
        context.log.info(f"Brand {brand}: {result['upserted']} docs upserted")

    return Output(
        value=results,
        metadata={
            "total_upserted": MetadataValue.int(total_upserted),
            "brands": MetadataValue.text(", ".join(settings.brands)),
        },
    )
