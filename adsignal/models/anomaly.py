"""
Isolation Forest anomaly detector for budget shifts.
Detects weeks where a brand's spend pattern is statistically anomalous —
e.g. sudden channel rebalancing, spend spike, or pullback.

GOTCHA: IsolationForest contamination parameter — set to 0.15 (15% anomaly rate)
for portfolio demo. In production, tune on labelled data or use 'auto'.
"""
import pandas as pd
import structlog
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

log = structlog.get_logger()

FEATURES = [
    "spend_midpoint",
    "channel_share",
    "active_ad_count",
    "impression_upper_sum",
]


def detect_anomalies(
    signals_df: pd.DataFrame,
    brand: str,
    channels: list[str] | None = None,
    contamination: float = 0.15,
) -> dict:
    """
    Run Isolation Forest on brand's weekly signals to detect anomalous weeks.

    Args:
        signals_df: DataFrame with columns matching FEATURES + week_key
        brand: brand slug (for logging)
        channels: optional channel subset to include
        contamination: expected fraction of anomalies

    Returns:
        {
          "brand": str,
          "anomaly_weeks": list[str],    # week_keys flagged as anomalous
          "anomaly_scores": dict[str, float],  # week_key → anomaly score
          "n_anomalies": int,
          "features_used": list[str],
        }
    """
    brand_df = signals_df[signals_df["brand"] == brand].copy()
    if channels is not None:
        brand_df = brand_df[brand_df["channel"].isin(channels)]

    # Aggregate across channels per week for brand-level anomaly detection
    weekly = (
        brand_df
        .groupby("week_key")
        .agg({
            "spend_midpoint": "sum",
            "active_ad_count": "sum",
            "impression_upper_sum": "sum",
            "channel_share": "mean",
        })
        .reset_index()
        .sort_values("week_key")
    )

    if len(weekly) < 8:
        log.warning("insufficient_weeks_for_anomaly", brand=brand, weeks=len(weekly))
        return {
            "brand": brand,
            "anomaly_weeks": [],
            "anomaly_scores": {},
            "n_anomalies": 0,
            "features_used": FEATURES,
        }

    feature_cols = [f for f in FEATURES if f in weekly.columns]
    X = weekly[feature_cols].fillna(0).values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    clf = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
    clf.fit(X_scaled)

    labels = clf.predict(X_scaled)       # -1 = anomaly, 1 = normal
    scores = clf.score_samples(X_scaled)  # lower = more anomalous

    anomaly_mask = labels == -1
    anomaly_weeks = weekly.loc[anomaly_mask, "week_key"].tolist()
    anomaly_scores = dict(zip(weekly["week_key"].tolist(), scores.tolist(), strict=False))

    log.info("anomaly_detection_complete", brand=brand, anomalies=len(anomaly_weeks))

    return {
        "brand": brand,
        "anomaly_weeks": anomaly_weeks,
        "anomaly_scores": {k: round(v, 4) for k, v in anomaly_scores.items()},
        "n_anomalies": len(anomaly_weeks),
        "features_used": feature_cols,
    }
