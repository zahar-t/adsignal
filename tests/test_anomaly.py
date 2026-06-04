from adsignal.models.anomaly import detect_anomalies


def test_detect_anomalies_returns_dict(sample_signals_df):
    result = detect_anomalies(sample_signals_df, "nike")
    assert "anomaly_weeks" in result
    assert isinstance(result["anomaly_weeks"], list)
    assert "n_anomalies" in result
    assert result["n_anomalies"] >= 0


def test_insufficient_data_returns_empty(sample_signals_df):
    tiny = sample_signals_df[sample_signals_df["brand"] == "nike"].head(3)
    result = detect_anomalies(tiny, "nike")
    assert result["anomaly_weeks"] == []


def test_anomaly_count_matches_weeks_list(sample_signals_df):
    result = detect_anomalies(sample_signals_df, "adidas")
    assert result["n_anomalies"] == len(result["anomaly_weeks"])


def test_anomaly_scores_keys_are_week_keys(sample_signals_df):
    result = detect_anomalies(sample_signals_df, "nike")
    for wk in result["anomaly_weeks"]:
        assert wk in result["anomaly_scores"]


def test_features_used_is_list(sample_signals_df):
    result = detect_anomalies(sample_signals_df, "nike")
    assert isinstance(result["features_used"], list)
    assert len(result["features_used"]) > 0
