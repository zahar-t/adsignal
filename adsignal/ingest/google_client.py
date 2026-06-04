"""
Google Ads Transparency stub.
Real scraping of ads.google.com/transparency requires browser automation.
This stub returns synthetic data with google-style platform labels.

NOTE: Chose synthetic stub over Selenium/Playwright to keep the portfolio
project dependency-light. The synthetic data uses google_search/youtube
platforms to simulate what real Google Transparency data would look like.
"""
import structlog

from adsignal.ingest.synthetic import generate_brand_batch

log = structlog.get_logger()

GOOGLE_PLATFORMS = ["google_search", "youtube", "google_display"]


def fetch_brand_ads(brand: str, n_weeks: int = 16) -> list[dict]:
    """Return synthetic google-flavoured ad docs."""
    log.info("google_client_stub_using_synthetic", brand=brand)
    docs = generate_brand_batch(brand, n_weeks=n_weeks)

    # Override platform to google channels for realism
    import random
    for doc in docs:
        if doc["channel"] in ("search", "video", "display"):
            doc["platform"] = random.choice(GOOGLE_PLATFORMS)
            doc["source"] = "google"

    return docs
