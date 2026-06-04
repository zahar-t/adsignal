"""
Meta Ad Library API client.
Falls back to synthetic generator when META_API_TOKEN is not set.
Real API docs: https://developers.facebook.com/docs/graph-api/reference/ads_archive/

IMPORTANT: Meta's Ad Library API requires:
  1. A Facebook developer account
  2. An access token with ads_read permission
  3. Identity verification for political ads (not needed for commercial)

For portfolio use, the synthetic fallback produces identical schema output.
"""
from datetime import UTC

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from adsignal.config import settings
from adsignal.ingest.synthetic import generate_brand_batch

log = structlog.get_logger()

META_BASE = "https://graph.facebook.com"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_page(url: str, params: dict) -> dict:
    response = httpx.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_brand_ads(brand: str, n_weeks: int = 16) -> list[dict]:
    """
    Fetch ads for a brand from Meta Ad Library, or synthetic fallback.
    Always returns documents conforming to the raw_creatives schema.
    """
    if not settings.meta_api_token:
        log.info("meta_api_token_not_set_using_synthetic", brand=brand)
        return generate_brand_batch(brand, n_weeks=n_weeks)

    # Real API path — only reached with token
    url = f"{META_BASE}/{settings.meta_api_version}/ads_archive"
    params = {
        "access_token": settings.meta_api_token,
        "search_terms": brand,
        "ad_type": "ALL",
        "ad_reached_countries": ["US"],
        "fields": ",".join([
            "id", "ad_creative_body", "ad_delivery_start_time",
            "ad_delivery_stop_time", "impressions", "spend",
            "publisher_platforms", "demographic_distribution",
        ]),
        "limit": 500,
    }

    docs = []
    page_url = url
    pages_fetched = 0
    max_pages = n_weeks  # approximate pagination limit

    while page_url and pages_fetched < max_pages:
        data = _fetch_page(page_url, params if pages_fetched == 0 else {})
        for ad in data.get("data", []):
            docs.append(_normalise_meta_ad(ad, brand))
        page_url = data.get("paging", {}).get("next")
        pages_fetched += 1
        params = {}  # next page URL is fully formed

    log.info("meta_fetch_complete", brand=brand, total_ads=len(docs))
    return docs


def _normalise_meta_ad(ad: dict, brand: str) -> dict:
    """Normalise a Meta Ad Library response to raw_creatives schema."""
    from datetime import date, datetime

    from adsignal.ingest.synthetic import _week_key

    impressions = ad.get("impressions", {})
    spend = ad.get("spend", {})

    started_str = ad.get("ad_delivery_start_time", "")
    stopped_str = ad.get("ad_delivery_stop_time")

    try:
        started = date.fromisoformat(started_str[:10]) if started_str else date.today()
    except ValueError:
        started = date.today()

    try:
        stopped = date.fromisoformat(stopped_str[:10]) if stopped_str else None
    except (ValueError, TypeError):
        stopped = None

    platforms = ad.get("publisher_platforms", ["facebook"])
    channel_map = {
        "facebook": "social", "instagram": "social",
        "audience_network": "display", "messenger": "social",
        "video": "video",
    }
    channel = channel_map.get(platforms[0] if platforms else "facebook", "social")

    return {
        "source_id": ad.get("id", ""),
        "source": "meta",
        "brand": brand.lower().replace(" ", "-"),
        "brand_display": brand.title(),
        "ad_text": ad.get("ad_creative_body", ""),
        "cta": "Learn More",
        "channel": channel,
        "platform": platforms[0] if platforms else "facebook",
        "impression_lower": int(impressions.get("lower_bound", 0)),
        "impression_upper": int(impressions.get("upper_bound", 0)),
        "spend_lower": float(spend.get("lower_bound", 0)),
        "spend_upper": float(spend.get("upper_bound", 0)),
        "started_running": started.isoformat(),
        "stopped_running": stopped.isoformat() if stopped else None,
        "is_active": stopped is None,
        "currency": spend.get("currency", "USD"),
        "region": "US",
        "creative_themes": [],
        "ingested_at": datetime.now(UTC).isoformat(),
        "week_key": _week_key(started),
    }
