from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AggregatedDailyStat, DailyStatVisitor, VisitLog, Visitor
from app.schemas import BrowserSignals
from app.services.fingerprint import ParsedAgent
from app.services.geoip import GeoResult


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def confidence_score(geo: GeoResult, signals: BrowserSignals, visitor: Visitor | None) -> int:
    score = geo.base_confidence
    if geo.geo_timezone and signals.timezone:
        score += 8 if geo.geo_timezone == signals.timezone else -12
    if visitor and visitor.current_country:
        score += 5 if visitor.current_country == geo.country else -15
    if visitor and visitor.current_state and geo.state:
        score += 4 if visitor.current_state == geo.state else -8
    return max(0, min(100, score))


def detect_anomalies(
    geo: GeoResult, previous: VisitLog | None, now: datetime, confidence: int
) -> list[str]:
    reasons: list[str] = []
    if geo.network_type == "VPN Candidate":
        reasons.append("probable_vpn")
    if geo.network_type == "Hosting Provider":
        reasons.append("hosting_provider")
    if previous and now - previous.timestamp <= timedelta(hours=6):
        if previous.country and geo.country and previous.country != geo.country:
            reasons.append("rapid_country_change")
        elif previous.city and geo.city and previous.city != geo.city:
            reasons.append("rapid_city_change")
    if previous and previous.country and geo.country and previous.country != geo.country and confidence < 55:
        reasons.append("historical_location_inconsistency")
    return reasons


def record_visit(
    db: Session,
    *,
    visitor_hash: str,
    agent: ParsedAgent,
    signals: BrowserSignals,
    geo: GeoResult,
) -> VisitLog:
    now = utcnow()
    visitor = db.scalar(select(Visitor).where(Visitor.visitor_hash == visitor_hash))
    previous = None
    if visitor:
        previous = db.scalar(
            select(VisitLog)
            .where(VisitLog.visitor_id == visitor.id)
            .order_by(VisitLog.timestamp.desc())
            .limit(1)
        )
    score = confidence_score(geo, signals, visitor)
    if visitor is None:
        visitor = Visitor(
            visitor_hash=visitor_hash,
            first_seen=now,
            last_seen=now,
            total_visits=1,
        )
        db.add(visitor)
        db.flush()
    else:
        visitor.last_seen = now
        visitor.total_visits += 1
    visitor.current_city = geo.city
    visitor.current_state = geo.state
    visitor.current_country = geo.country
    visitor.confidence_score = score

    reasons = detect_anomalies(geo, previous, now, score)
    visit = VisitLog(
        visitor_id=visitor.id,
        timestamp=now,
        city=geo.city,
        state=geo.state,
        country=geo.country,
        confidence_score=score,
        browser=agent.browser,
        os=agent.os,
        device_type=agent.device_type,
        network_type=geo.network_type,
        asn=geo.asn,
        network_organization=geo.organization,
        timezone=signals.timezone,
        language=signals.language,
        screen_resolution=signals.screen_resolution,
        is_anomalous=bool(reasons),
        anomaly_reasons=reasons or None,
    )
    db.add(visit)

    city = geo.city or "Unknown"
    state = geo.state or "Unknown"
    stat = db.scalar(
        select(AggregatedDailyStat).where(
            AggregatedDailyStat.date == now.date(),
            AggregatedDailyStat.city == city,
            AggregatedDailyStat.state == state,
        )
    )
    if stat is None:
        stat = AggregatedDailyStat(date=now.date(), city=city, state=state, visit_count=0, unique_visitors=0)
        db.add(stat)
        db.flush()
    stat.visit_count += 1
    seen = db.get(DailyStatVisitor, (stat.id, visitor.id))
    if seen is None:
        db.add(DailyStatVisitor(daily_stat_id=stat.id, visitor_id=visitor.id))
        stat.unique_visitors += 1
    db.commit()
    db.refresh(visit)
    return visit
