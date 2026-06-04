"""GET /snapshots/{table} — Iceberg time-travel: list snapshots for a table."""
from fastapi import APIRouter, HTTPException

from adsignal.catalog import get_catalog_reader
from api.models import SnapshotResponse

router = APIRouter()


@router.get("/snapshots/{table_name}", response_model=list[SnapshotResponse])
def get_snapshots(table_name: str) -> list[SnapshotResponse]:
    """
    List Iceberg snapshots for a table.
    Enables time-travel queries — see which ETL runs produced which data.
    """
    try:
        catalog = get_catalog_reader()
        table = catalog.load_table(f"ad_intelligence.{table_name}")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Table not found: {e}") from e

    snapshots = []
    for snap in table.snapshots():
        summaries = snap.summary or {}
        snapshots.append(SnapshotResponse(
            table=table_name,
            snapshot_id=snap.snapshot_id,
            committed_at=str(snap.timestamp_ms),
            operation=summaries.get("operation", "unknown"),
            added_records=int(summaries.get("added-records", 0)) if "added-records" in summaries else None,
        ))

    return sorted(snapshots, key=lambda s: s.snapshot_id, reverse=True)
