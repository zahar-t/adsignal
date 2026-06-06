"""
Dagster schedules and sensors for automated ingestion.

Two automation mechanisms:
1. NightlySchedule  — time-based, runs the full asset graph every night at midnight.
                      Good for predictable daily refresh; shows up in Dagster UI run history.
2. NewDataSensor    — event-based, polls MongoDB for new documents since the last run
                      and triggers the ETL only when there is genuinely new data to process.
                      More efficient; better story in interviews ("event-driven, not clock-driven").

Both are registered in definitions.py. Toggle which is active via DAGSTER_AUTOMATION env var.
Default: nightly schedule (simpler, more visible for portfolio demo).
"""
from dagster import (
    DefaultScheduleStatus,
    DefaultSensorStatus,
    RunRequest,
    ScheduleDefinition,
    SensorDefinition,
    SensorEvaluationContext,
    define_asset_job,
)
from pymongo import MongoClient
from pymongo.synchronous.collection import Collection

from adsignal.config import settings

# ── Job definitions ────────────────────────────────────────────────────────────

# Full pipeline: ingest → ETL → models → briefs
full_pipeline_job = define_asset_job(
    name="full_pipeline_job",
    selection="*",  # all assets
    description="Full AdSignal pipeline: ingest → Spark ETL → DS models → LLM briefs",
)

# ETL-only job: skip ingestion, re-process existing MongoDB data
etl_only_job = define_asset_job(
    name="etl_only_job",
    selection=["iceberg_brand_signals", "brand_signal_summaries", "brand_briefs"],
    description="Re-run ETL + models + briefs without re-ingesting",
)

# ── Nightly Schedule ───────────────────────────────────────────────────────────

nightly_schedule = ScheduleDefinition(
    name="nightly_full_pipeline",
    job=full_pipeline_job,
    cron_schedule="0 0 * * *",          # midnight UTC daily
    default_status=DefaultScheduleStatus.RUNNING,  # auto-starts when dagster dev runs
    description="Nightly full pipeline refresh at midnight UTC",
)

# ── MongoDB New-Data Sensor ────────────────────────────────────────────────────

def _get_mongo_doc_count() -> int:
    """Return total document count in raw_creatives collection."""
    try:
        client: MongoClient = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
        collection: Collection = client[settings.mongo_db]["raw_creatives"]
        count = collection.count_documents({})
        client.close()
        return count
    except Exception:
        return 0


def new_mongo_data_sensor(context: SensorEvaluationContext):
    """
    Polls MongoDB every 5 minutes. Triggers the ETL-only job when the document
    count has increased since the last sensor run.

    cursor = last known document count, stored in Dagster's cursor store.
    """
    current_count = _get_mongo_doc_count()
    last_count = int(context.cursor or "0")

    if current_count > last_count:
        context.update_cursor(str(current_count))
        context.log.info(
            f"New documents detected: {current_count - last_count} new "
            f"(total: {current_count}). Triggering ETL."
        )
        yield RunRequest(
            run_key=f"new_data_{current_count}",
            tags={"trigger": "mongo_sensor", "new_docs": str(current_count - last_count)},
        )
    else:
        context.log.debug(f"No new documents (count: {current_count}). Skipping.")


mongo_sensor = SensorDefinition(
    name="new_mongo_data_sensor",
    job=etl_only_job,
    evaluation_fn=new_mongo_data_sensor,
    minimum_interval_seconds=300,       # poll every 5 minutes
    default_status=DefaultSensorStatus.STOPPED,  # off by default; enable in UI
    description=(
        "Triggers ETL when new documents appear in MongoDB raw_creatives. "
        "Enable in the Dagster UI to switch from schedule-based to event-driven ingestion."
    ),
)
