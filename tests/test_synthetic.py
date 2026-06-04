from datetime import date

from adsignal.ingest.synthetic import _week_key, generate_brand_batch, generate_creative


def test_generate_creative_schema():
    doc = generate_creative("nike")
    required_fields = [
        "source_id", "source", "brand", "channel", "impression_lower",
        "spend_lower", "week_key", "ingested_at", "creative_themes"
    ]
    for field in required_fields:
        assert field in doc, f"Missing field: {field}"


def test_generate_creative_brand_slug():
    doc = generate_creative("nike")
    assert doc["brand"] == "nike"
    assert isinstance(doc["creative_themes"], list)


def test_generate_batch_count():
    docs = generate_brand_batch("adidas", n_weeks=4, ads_per_week=10)
    # Should be approx 4 * 10 docs (±10 per week jitter)
    assert 20 <= len(docs) <= 80


def test_week_key_format():
    wk = _week_key(date(2024, 10, 14))
    assert wk.startswith("2024-W")
    parts = wk.split("-W")
    assert len(parts) == 2
    assert parts[1].isdigit()


def test_generate_creative_spend_positive():
    doc = generate_creative("apple")
    assert doc["spend_lower"] >= 0
    assert doc["spend_upper"] >= doc["spend_lower"]


def test_generate_creative_impression_range():
    doc = generate_creative("samsung")
    assert doc["impression_upper"] >= doc["impression_lower"]
    assert doc["impression_lower"] > 0


def test_generate_creative_channel_valid():
    valid_channels = {"display", "video", "search", "ctv", "social"}
    for _ in range(10):
        doc = generate_creative("nike")
        assert doc["channel"] in valid_channels
