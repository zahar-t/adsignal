"""
Synthetic ad signal generator using Faker.
Produces documents matching the raw_creatives MongoDB schema.

Schema per document:
{
  "source_id": str,           # unique identifier from source platform
  "source": str,              # "meta" | "google" | "synthetic"
  "brand": str,               # normalised brand slug e.g. "nike"
  "brand_display": str,       # display name e.g. "Nike"
  "ad_text": str,             # primary creative copy
  "cta": str,                 # call to action button text
  "channel": str,             # "display" | "video" | "search" | "ctv" | "social"
  "platform": str,            # "facebook" | "instagram" | "youtube" | "google_search"
  "impression_lower": int,    # Meta gives range lower bound
  "impression_upper": int,    # Meta gives range upper bound
  "spend_lower": float,       # estimated spend USD lower
  "spend_upper": float,       # estimated spend USD upper
  "started_running": date,    # ISO date string
  "stopped_running": date | None,
  "is_active": bool,
  "currency": str,
  "region": str,              # "US" | "GB" | "DE" etc
  "creative_themes": list[str],  # extracted topic tags
  "ingested_at": datetime,    # UTC now
  "week_key": str,            # ISO week e.g. "2024-W42"
}
"""

import random
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import TypedDict

from faker import Faker

fake = Faker()


class BrandConfig(TypedDict):
    display: str
    spend_scale: float

CHANNELS = ["display", "video", "search", "ctv", "social"]
PLATFORMS = {
    "display": ["dv360", "ttd", "xandr"],
    "video": ["youtube", "connected_tv", "hulu"],
    "search": ["google_search", "bing_search"],
    "ctv": ["connected_tv", "roku", "peacock"],
    "social": ["facebook", "instagram", "tiktok", "snapchat"],
}
CTAS = ["Shop Now", "Learn More", "Sign Up", "Get Offer", "Download", "Watch Now", "Book Now"]
THEMES = [
    "performance", "lifestyle", "sustainability", "innovation", "price-promo",
    "brand-awareness", "product-launch", "seasonal", "loyalty", "retargeting"
]
REGIONS = ["US", "GB", "DE", "FR", "AU", "CA", "NL", "ES"]

BRAND_CONFIG: dict[str, BrandConfig] = {
    "nike": {"display": "Nike", "spend_scale": 5.0},
    "adidas": {"display": "Adidas", "spend_scale": 3.5},
    "apple": {"display": "Apple", "spend_scale": 8.0},
    "samsung": {"display": "Samsung", "spend_scale": 6.0},
    "coca-cola": {"display": "Coca-Cola", "spend_scale": 4.0},
    "amazon": {"display": "Amazon", "spend_scale": 10.0},
    "netflix": {"display": "Netflix", "spend_scale": 7.0},
    "mcdonalds": {"display": "McDonald's", "spend_scale": 3.0},
}


def _week_key(d: date) -> str:
    return f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"


def generate_creative(brand: str, reference_date: date | None = None) -> dict:
    """Generate one synthetic ad creative document."""
    if reference_date is None:
        reference_date = date.today() - timedelta(days=random.randint(0, 90))

    cfg = BRAND_CONFIG.get(brand, {"display": brand.title(), "spend_scale": 2.0})
    channel = random.choice(CHANNELS)
    platform = random.choice(PLATFORMS[channel])
    spend_scale = cfg["spend_scale"]

    impression_lower = random.randint(1_000, 500_000) * 100
    impression_upper = impression_lower + random.randint(50_000, 200_000) * 100
    spend_lower = round(impression_lower * random.uniform(0.002, 0.008) * spend_scale, 2)
    spend_upper = round(impression_upper * random.uniform(0.003, 0.010) * spend_scale, 2)

    started = reference_date - timedelta(days=random.randint(0, 30))
    is_active = random.random() > 0.3
    stopped = None if is_active else started + timedelta(days=random.randint(3, 25))

    n_themes = random.randint(1, 3)
    selected_themes = random.sample(THEMES, n_themes)

    return {
        "source_id": str(uuid.uuid4()),
        "source": "synthetic",
        "brand": brand,
        "brand_display": cfg["display"],
        "ad_text": fake.sentence(nb_words=random.randint(8, 20)),
        "cta": random.choice(CTAS),
        "channel": channel,
        "platform": platform,
        "impression_lower": impression_lower,
        "impression_upper": impression_upper,
        "spend_lower": spend_lower,
        "spend_upper": spend_upper,
        "started_running": started.isoformat(),
        "stopped_running": stopped.isoformat() if stopped else None,
        "is_active": is_active,
        "currency": "USD",
        "region": random.choice(REGIONS),
        "creative_themes": selected_themes,
        "ingested_at": datetime.now(UTC).isoformat(),
        "week_key": _week_key(started),
    }


def generate_brand_batch(brand: str, n_weeks: int = 16, ads_per_week: int = 50) -> list[dict]:
    """Generate a full batch for a brand across n_weeks of history."""
    docs = []
    today = date.today()
    for week_offset in range(n_weeks):
        reference = today - timedelta(weeks=week_offset)
        for _ in range(ads_per_week + random.randint(-10, 10)):
            docs.append(generate_creative(brand, reference))
    return docs
