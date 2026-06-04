import pandas as pd
import pytest


@pytest.fixture
def sample_signals_df():
    """Minimal brand_weekly_signals DataFrame for testing."""
    rows = []
    import random
    from datetime import date, timedelta

    brands = ["nike", "adidas"]
    channels = ["display", "video", "social"]
    base_date = date(2024, 1, 1)

    for brand in brands:
        for week_offset in range(20):
            for channel in channels:
                week_date = base_date + timedelta(weeks=week_offset)
                week_key = f"{week_date.isocalendar().year}-W{week_date.isocalendar().week:02d}"
                rows.append({
                    "brand": brand,
                    "week_key": week_key,
                    "channel": channel,
                    "region": "US",
                    "ad_count": random.randint(10, 100),
                    "active_ad_count": random.randint(5, 50),
                    "impression_lower_sum": random.randint(100_000, 1_000_000),
                    "impression_upper_sum": random.randint(1_000_000, 5_000_000),
                    "spend_lower_sum": random.uniform(1000, 10000),
                    "spend_upper_sum": random.uniform(10000, 50000),
                    "spend_midpoint": random.uniform(5000, 30000),
                    "top_ctas": ["Shop Now", "Learn More"],
                    "top_themes": ["performance", "lifestyle"],
                    "channel_share": random.uniform(0.1, 0.5),
                    "etl_timestamp": pd.Timestamp.now(),
                })
    return pd.DataFrame(rows)
