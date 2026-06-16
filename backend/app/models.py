from datetime import date as DateValue
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Visitor(Base):
    __tablename__ = "visitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    visitor_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    total_visits: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_city: Mapped[str | None] = mapped_column(String(120))
    current_state: Mapped[str | None] = mapped_column(String(120))
    current_country: Mapped[str | None] = mapped_column(String(120))
    confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    country_confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    state_confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    city_confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_asn: Mapped[int | None] = mapped_column(Integer)
    current_isp: Mapped[str | None] = mapped_column(String(200))
    current_network_type: Mapped[str] = mapped_column(String(40), default="Unknown", nullable=False)
    current_location_source: Mapped[str] = mapped_column(String(80), default="IP/ASN Inference", nullable=False)
    is_crawler: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    classification: Mapped[str] = mapped_column(String(50), default="Unknown", nullable=False)
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    classification_reason: Mapped[str | None] = mapped_column(String(255))
    current_country_confidence: Mapped[str] = mapped_column(String(20), default="Low", nullable=False)
    current_state_confidence: Mapped[str] = mapped_column(String(20), default="Low", nullable=False)
    current_city_confidence: Mapped[str] = mapped_column(String(20), default="Low", nullable=False)
    current_location_confidence: Mapped[str] = mapped_column(String(20), default="Low", nullable=False)
    visits: Mapped[list["VisitLog"]] = relationship(back_populates="visitor", cascade="all, delete-orphan")


class VisitLog(Base):
    __tablename__ = "visit_logs"
    __table_args__ = (Index("ix_visit_logs_visitor_timestamp", "visitor_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    visitor_id: Mapped[int] = mapped_column(ForeignKey("visitors.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(120))
    city_raw: Mapped[str | None] = mapped_column(String(120))
    state_raw: Mapped[str | None] = mapped_column(String(120))
    country_raw: Mapped[str | None] = mapped_column(String(120))
    city_normalized: Mapped[str | None] = mapped_column(String(120))
    state_normalized: Mapped[str | None] = mapped_column(String(120))
    country_normalized: Mapped[str | None] = mapped_column(String(120))
    confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    country_confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    state_confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    city_confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    location_source: Mapped[str] = mapped_column(String(80), default="IP/ASN Inference", nullable=False)
    location_source_detail: Mapped[str | None] = mapped_column(String(240))
    browser: Mapped[str | None] = mapped_column(String(80))
    os: Mapped[str | None] = mapped_column(String(80))
    device_type: Mapped[str | None] = mapped_column(String(40))
    network_type: Mapped[str] = mapped_column(String(40), default="Unknown", nullable=False)
    asn: Mapped[int | None] = mapped_column(Integer)
    isp: Mapped[str | None] = mapped_column(String(200))
    network_organization: Mapped[str | None] = mapped_column(String(200))
    timezone: Mapped[str | None] = mapped_column(String(80))
    language: Mapped[str | None] = mapped_column(String(32))
    accept_language: Mapped[str | None] = mapped_column(String(256))
    screen_resolution: Mapped[str | None] = mapped_column(String(32))
    geolocation_accuracy_meters: Mapped[int | None] = mapped_column(Integer)
    is_crawler: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    crawler_type: Mapped[str | None] = mapped_column(String(80))
    is_anomalous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anomaly_reasons: Mapped[list[str] | None] = mapped_column(JSON)
    tracking_status: Mapped[str] = mapped_column(String(30), default="received", nullable=False)
    tracking_failure_reason: Mapped[str | None] = mapped_column(String(255))
    classification: Mapped[str] = mapped_column(String(50), default="Unknown", nullable=False)
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    classification_reason: Mapped[str | None] = mapped_column(String(255))
    country_confidence: Mapped[str] = mapped_column(String(20), default="Low", nullable=False)
    state_confidence: Mapped[str] = mapped_column(String(20), default="Low", nullable=False)
    city_confidence: Mapped[str] = mapped_column(String(20), default="Low", nullable=False)
    location_confidence: Mapped[str] = mapped_column(String(20), default="Low", nullable=False)
    cores: Mapped[int | None] = mapped_column(Integer)
    memory: Mapped[float | None] = mapped_column(Float)
    gpu: Mapped[str | None] = mapped_column(String(256))
    rtt: Mapped[int | None] = mapped_column(Integer)
    downlink: Mapped[float | None] = mapped_column(Float)
    save_data: Mapped[bool | None] = mapped_column(Boolean)
    has_private_ip: Mapped[bool | None] = mapped_column(Boolean)
    ping_jitter: Mapped[float | None] = mapped_column(Float)
    canvas_hash: Mapped[str | None] = mapped_column(String(64))
    webgl_hash: Mapped[str | None] = mapped_column(String(64))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    visitor: Mapped[Visitor] = relationship(back_populates="visits")


class AggregatedDailyStat(Base):
    __tablename__ = "aggregated_daily_stats"
    __table_args__ = (UniqueConstraint("date", "city", "state", name="uq_daily_location"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[DateValue] = mapped_column(Date, nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(120), default="Unknown", nullable=False)
    city: Mapped[str] = mapped_column(String(120), default="Unknown", nullable=False)
    state: Mapped[str] = mapped_column(String(120), default="Unknown", nullable=False)
    visit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_visitors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DailyStatVisitor(Base):
    __tablename__ = "daily_stat_visitors"

    daily_stat_id: Mapped[int] = mapped_column(
        ForeignKey("aggregated_daily_stats.id", ondelete="CASCADE"), primary_key=True
    )
    visitor_id: Mapped[int] = mapped_column(ForeignKey("visitors.id", ondelete="CASCADE"), primary_key=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class CrawlerVisitLog(Base):
    __tablename__ = "crawler_visit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    crawler_type: Mapped[str] = mapped_column(String(80), default="Unknown crawler", nullable=False)
    user_agent_family: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(120))
    confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    asn: Mapped[int | None] = mapped_column(Integer)
    isp: Mapped[str | None] = mapped_column(String(200))
    network_type: Mapped[str] = mapped_column(String(40), default="Unknown", nullable=False)
    location_source: Mapped[str] = mapped_column(String(80), default="IP/ASN Inference", nullable=False)


class Geofence(Base):
    __tablename__ = "geofences"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="circle", nullable=False)  # "circle" or "polygon"
    center_latitude: Mapped[float | None] = mapped_column(Float)
    center_longitude: Mapped[float | None] = mapped_column(Float)
    radius_meters: Mapped[float | None] = mapped_column(Float)
    coordinates: Mapped[list[list[float]] | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

