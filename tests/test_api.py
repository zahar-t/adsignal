from unittest.mock import MagicMock, patch

import httpx
import pandas as pd
import pytest

from api.main import app

# Minimal empty DataFrame with the columns the API expects
EMPTY_SIGNALS_DF = pd.DataFrame(columns=["brand", "channel", "week_key", "spend_midpoint", "ad_count", "channel_share"])


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_brief_not_found(client):
    with patch("api.routes.briefs.get_catalog_reader") as mock_catalog:
        mock_table = MagicMock()
        mock_table.scan.return_value.to_pandas.return_value = EMPTY_SIGNALS_DF.copy()
        mock_catalog.return_value.load_table.return_value = mock_table
        response = await client.get("/brief/nonexistent-brand-xyz")
        assert response.status_code == 404


async def test_signals_not_found(client):
    with patch("api.routes.signals.get_catalog_reader") as mock_catalog:
        mock_table = MagicMock()
        mock_table.scan.return_value.to_pandas.return_value = EMPTY_SIGNALS_DF.copy()
        mock_catalog.return_value.load_table.return_value = mock_table
        response = await client.get("/signals/nonexistent-brand-xyz")
        assert response.status_code == 404


async def test_health_returns_service_name(client):
    response = await client.get("/health")
    body = response.json()
    assert "service" in body
    assert body["service"] == "adsignal-api"
