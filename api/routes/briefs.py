"""GET /brief/{brand} — generate or return cached competitive intelligence brief."""
import pandas as pd
from fastapi import APIRouter, HTTPException

from adsignal.catalog import get_catalog_reader
from adsignal.llm.narrative import generate_brief
from adsignal.models.signal_builder import build_signal_summary
from api.models import BriefResponse

router = APIRouter()

# Simple in-memory cache — keyed by brand
_cache: dict[str, BriefResponse] = {}


@router.get("/brief/{brand}", response_model=BriefResponse)
def get_brief(brand: str, refresh: bool = False) -> BriefResponse:
    """
    Get competitive intelligence brief for a brand.
    Cached per process lifetime unless ?refresh=true.
    """
    brand = brand.lower().replace(" ", "-")

    if brand in _cache and not refresh:
        return _cache[brand]

    try:
        catalog = get_catalog_reader()
        table = catalog.load_table("ad_intelligence.brand_weekly_signals")
        df: pd.DataFrame = table.scan().to_pandas()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Iceberg read failed: {e}") from e

    brand_df = df[df["brand"] == brand]
    if brand_df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for brand: {brand}")

    summary = build_signal_summary(df, brand)
    brief_text = generate_brief(brand, summary)

    response = BriefResponse(
        brand=brand,
        brief=brief_text,
        dominant_trend=summary.get("dominant_trend", "flat"),
        anomaly_weeks=summary.get("anomaly_weeks", []),
        top_themes=summary.get("top_themes", []),
        weeks_analysed=summary.get("weeks_analysed", 0),
    )

    _cache[brand] = response
    return response
