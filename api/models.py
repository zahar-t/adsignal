
from pydantic import BaseModel


class BriefResponse(BaseModel):
    brand: str
    brief: str
    dominant_trend: str
    anomaly_weeks: list[str]
    top_themes: list[str]
    weeks_analysed: int


class SignalResponse(BaseModel):
    brand: str
    channel: str
    week_key: str
    spend_midpoint: float
    ad_count: int
    channel_share: float


class SnapshotResponse(BaseModel):
    table: str
    snapshot_id: int
    committed_at: str
    operation: str
    added_records: int | None
