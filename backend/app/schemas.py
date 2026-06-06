from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class BrowserSignals(BaseModel):
    timezone: str | None = Field(default=None, max_length=80)
    language: str | None = Field(default=None, max_length=32)
    platform: str | None = Field(default=None, max_length=80)
    screen_resolution: str | None = Field(default=None, max_length=32)

    @field_validator("*")
    @classmethod
    def strip_controls(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return "".join(char for char in value.strip() if char.isprintable()) or None


class TrackResponse(BaseModel):
    redirect_url: str


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class VisitorItem(BaseModel):
    id: int
    anonymous_id: str
    first_seen: datetime
    last_seen: datetime
    total_visits: int
    current_city: str | None
    current_state: str | None
    current_country: str | None
    confidence_score: int


class VisitorPage(BaseModel):
    items: list[VisitorItem]
    meta: PageMeta


class VisitItem(BaseModel):
    id: int
    anonymous_id: str
    timestamp: datetime
    city: str | None
    state: str | None
    country: str | None
    confidence_score: int
    browser: str | None
    os: str | None
    device_type: str | None
    network_type: str
    is_anomalous: bool
    anomaly_reasons: list[str] | None


class VisitPage(BaseModel):
    items: list[VisitItem]
    meta: PageMeta


class Summary(BaseModel):
    total_visits: int
    unique_visitors: int
    returning_visitors: int
    top_city: str | None
    top_state: str | None
    average_confidence: float


class TrendPoint(BaseModel):
    period: str
    visits: int
    unique_visitors: int


class LocationPoint(BaseModel):
    name: str
    visits: int
    unique_visitors: int
    average_confidence: float


class RetentionPoint(BaseModel):
    cohort: str
    cohort_size: int
    returned: int
    retention_rate: float


class FrequencyPoint(BaseModel):
    bucket: str
    visitors: int


class LocationTrendPoint(BaseModel):
    period: str
    location: str
    visits: int


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    database_status: str
    database_size_bytes: int
    disk_used_percent: float
    memory_used_percent: float
    geoip_city_status: str
    geoip_asn_status: str
    last_backup_time: datetime | None
    uptime_seconds: int
    raw_retention_days: int
