from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

# Minimal empty DataFrame with the columns the API expects
EMPTY_SIGNALS_DF = pd.DataFrame(columns=["brand", "channel", "week_key", "spend_midpoint", "ad_count", "channel_share"])


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_brief_not_found():
    with patch("api.routes.briefs.get_catalog_reader") as mock_catalog:
        mock_table = MagicMock()
        mock_table.scan.return_value.to_pandas.return_value = EMPTY_SIGNALS_DF.copy()
        mock_catalog.return_value.load_table.return_value = mock_table
        response = client.get("/brief/nonexistent-brand-xyz")
        assert response.status_code == 404


def test_signals_not_found():
    with patch("api.routes.signals.get_catalog_reader") as mock_catalog:
        mock_table = MagicMock()
        mock_table.scan.return_value.to_pandas.return_value = EMPTY_SIGNALS_DF.copy()
        mock_catalog.return_value.load_table.return_value = mock_table
        response = client.get("/signals/nonexistent-brand-xyz")
        assert response.status_code == 404


def test_health_returns_service_name():
    response = client.get("/health")
    body = response.json()
    assert "service" in body
    assert body["service"] == "adsignal-api"
