from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models import AggregatedDailyStat, VisitLog, Visitor
from app.schemas import BrowserSignals
from app.services.fingerprint import ParsedAgent
from app.services.geoip import GeoResult
from app.services.tracking import confidence_score, detect_anomalies, record_visit


def geo(city="Bengaluru", state="Karnataka", country="India", network="Residential ISP"):
    return GeoResult(
        city=city,
        state=state,
        country=country,
        geo_timezone="Asia/Kolkata",
        asn=123,
        organization="Example Broadband",
        network_type=network,
        base_confidence=78,
    )


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_record_visit_updates_visitor_and_daily_aggregates(session_factory):
    with session_factory() as db:
        kwargs = {
            "db": db,
            "visitor_hash": "a" * 64,
            "agent": ParsedAgent("Chrome 120", "Windows", "Desktop"),
            "signals": BrowserSignals(timezone="Asia/Kolkata", language="en-IN"),
            "geo": geo(),
        }
        record_visit(**kwargs)
        record_visit(**kwargs)
        visitor = db.scalar(select(Visitor))
        stat = db.scalar(select(AggregatedDailyStat))
        assert visitor.total_visits == 2
        assert visitor.current_city == "Bengaluru"
        assert stat.visit_count == 2
        assert stat.unique_visitors == 1
        assert db.scalar(select(func.count(VisitLog.id))) == 2


def test_confidence_rewards_timezone_and_history():
    visitor = Visitor(
        visitor_hash="a" * 64,
        first_seen=now(),
        last_seen=now(),
        current_state="Karnataka",
        current_country="India",
    )
    score = confidence_score(geo(), BrowserSignals(timezone="Asia/Kolkata"), visitor)
    mismatch = confidence_score(geo(), BrowserSignals(timezone="America/New_York"), visitor)
    assert score > mismatch
    assert 0 <= score <= 100


def test_anomaly_flags_rapid_change_and_hosting():
    previous = VisitLog(
        visitor_id=1,
        timestamp=now() - timedelta(hours=1),
        city="London",
        country="United Kingdom",
        network_type="Residential ISP",
    )
    reasons = detect_anomalies(
        geo(city="Bengaluru", country="India", network="Hosting Provider"),
        previous,
        now(),
        30,
    )
    assert "hosting_provider" in reasons
    assert "rapid_country_change" in reasons
    assert "historical_location_inconsistency" in reasons
