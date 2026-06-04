"""GET /signals/{brand} — return weekly signal data from Iceberg."""
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from adsignal.catalog import get_catalog_reader
from api.models import SignalResponse

router = APIRouter()


@router.get("/signals/{brand}", response_model=list[SignalResponse])
def get_signals(
    brand: str,
    channel: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
) -> list[SignalResponse]:
    brand = brand.lower()

    try:
        catalog = get_catalog_reader()
        table = catalog.load_table("ad_intelligence.brand_weekly_signals")
        df: pd.DataFrame = table.scan().to_pandas()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Iceberg read failed: {e}") from e

    result = df[df["brand"] == brand]
    if channel:
        result = result[result["channel"] == channel]

    if result.empty:
        raise HTTPException(status_code=404, detail=f"No signals for brand: {brand}")

    result = result.sort_values("week_key", ascending=False).head(limit)

    return [
        SignalResponse(
            brand=row["brand"],
            channel=row["channel"],
            week_key=row["week_key"],
            spend_midpoint=float(row.get("spend_midpoint", 0)),
            ad_count=int(row.get("ad_count", 0)),
            channel_share=float(row.get("channel_share", 0)),
        )
        for _, row in result.iterrows()
    ]
