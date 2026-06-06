from datetime import date as DateValue
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
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
    confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    browser: Mapped[str | None] = mapped_column(String(80))
    os: Mapped[str | None] = mapped_column(String(80))
    device_type: Mapped[str | None] = mapped_column(String(40))
    network_type: Mapped[str] = mapped_column(String(40), default="Unknown", nullable=False)
    asn: Mapped[int | None] = mapped_column(Integer)
    network_organization: Mapped[str | None] = mapped_column(String(200))
    timezone: Mapped[str | None] = mapped_column(String(80))
    language: Mapped[str | None] = mapped_column(String(32))
    screen_resolution: Mapped[str | None] = mapped_column(String(32))
    is_anomalous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anomaly_reasons: Mapped[list[str] | None] = mapped_column(JSON)
    visitor: Mapped[Visitor] = relationship(back_populates="visits")


class AggregatedDailyStat(Base):
    __tablename__ = "aggregated_daily_stats"
    __table_args__ = (UniqueConstraint("date", "city", "state", name="uq_daily_location"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[DateValue] = mapped_column(Date, nullable=False, index=True)
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
