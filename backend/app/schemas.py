from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class BrowserSignals(BaseModel):
    timezone: str | None = Field(default=None, max_length=80)
    language: str | None = Field(default=None, max_length=32)
    accept_language: str | None = Field(default=None, max_length=256)
    platform: str | None = Field(default=None, max_length=80)
    screen_resolution: str | None = Field(default=None, max_length=32)
    latency_mumbai: float | None = Field(default=None, ge=0)
    latency_hyderabad: float | None = Field(default=None, ge=0)
    latency_delhi: float | None = Field(default=None, ge=0)
    latency_bangalore: float | None = Field(default=None, ge=0)
    latency_chennai: float | None = Field(default=None, ge=0)
    latency_kochi: float | None = Field(default=None, ge=0)
    latency_mangalore: float | None = Field(default=None, ge=0)
    latency_kolkata: float | None = Field(default=None, ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_meters: int | None = Field(default=None, ge=0, le=10_000_000)
    connection_type: str | None = Field(default=None, max_length=32)
    effective_type: str | None = Field(default=None, max_length=32)
    cores: int | None = Field(default=None, ge=0)
    memory: float | None = Field(default=None, ge=0)
    gpu: str | None = Field(default=None, max_length=256)
    rtt: int | None = Field(default=None, ge=0)
    downlink: float | None = Field(default=None, ge=0)
    ua_platform: str | None = Field(default=None, max_length=64)
    ua_mobile: bool | None = Field(default=None)
    ua_brands: str | None = Field(default=None, max_length=256)
    save_data: bool | None = Field(default=None)
    has_private_ip: bool | None = Field(default=None)
    ping_jitter: float | None = Field(default=None, ge=0)


    @field_validator("*")
    @classmethod
    def strip_controls(cls, value: any) -> any:
        if not isinstance(value, str):
            return value
        return "".join(char for char in value.strip() if char.isprintable()) or None


class TrackResponse(BaseModel):
    redirect_url: str
    location_update_token: str | None = None


class LocationConsentRequest(BaseModel):
    token: str = Field(min_length=16, max_length=2048)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: int | None = Field(default=None, ge=0, le=10_000_000)


class LocationConsentResponse(BaseModel):
    accepted: bool
    geocoded: bool
    redirect_url: str
    detail: str


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
    country_confidence_score: int
    state_confidence_score: int
    city_confidence_score: int
    current_asn: int | None
    current_isp: str | None
    current_network_type: str
    current_location_source: str
    classification: str
    classification_confidence: float
    classification_reason: str | None
    current_country_confidence: str
    current_state_confidence: str
    current_city_confidence: str
    current_location_confidence: str


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
    country_confidence_score: int
    state_confidence_score: int
    city_confidence_score: int
    location_source: str
    location_source_detail: str | None
    browser: str | None
    os: str | None
    device_type: str | None
    network_type: str
    asn: int | None
    isp: str | None
    network_organization: str | None
    geolocation_accuracy_meters: int | None
    is_anomalous: bool
    anomaly_reasons: list[str] | None
    tracking_status: str
    tracking_failure_reason: str | None
    classification: str
    classification_confidence: float
    classification_reason: str | None
    country_confidence: str
    state_confidence: str
    city_confidence: str
    location_confidence: str
    cores: int | None = None
    memory: float | None = None
    gpu: str | None = None
    rtt: int | None = None
    downlink: float | None = None
    save_data: bool | None = None
    has_private_ip: bool | None = None
    ping_jitter: float | None = None
    screen_resolution: str | None = None



class VisitPage(BaseModel):
    items: list[VisitItem]
    meta: PageMeta


class Summary(BaseModel):
    total_visits: int
    unique_visitors: int
    returning_visitors: int
    crawler_visits: int
    top_country: str | None
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


class CrawlerPoint(BaseModel):
    crawler_type: str
    visits: int
    last_seen: datetime | None


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
    redirect_target_url: str
    geoip_update_in_progress: bool
    geoip_last_error: str | None = None


class UpdateRedirectRequest(BaseModel):
    redirect_target_url: str = Field(min_length=1, max_length=2048)

    @field_validator("redirect_target_url")
    @classmethod
    def validate_redirect_url(cls, value: str) -> str:
        value = value.strip()
        from urllib.parse import urlparse
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("must be an absolute HTTP(S) URL")
        if any(ord(char) < 32 for char in value):
            raise ValueError("URL contains control characters")
        return value


class BulkDeleteRequest(BaseModel):
    ids: list[int] | None = None
    all: bool = False
