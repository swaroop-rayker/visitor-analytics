from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models import AggregatedDailyStat, VisitLog, Visitor
from app.schemas import BrowserSignals
from app.services.fingerprint import ParsedAgent
from app.services.location_intelligence import SOURCE_BROWSER
from app.services.geoip import GeoResult
from app.services.reverse_geocode import ReverseGeocodeResult
from app.services.tracking import apply_consented_location, confidence_score, detect_anomalies, record_visit


def geo(city="Bengaluru", state="Karnataka", country="India", network="Residential Broadband"):
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
        assert visitor.city_confidence_score > 0
        assert stat.visit_count == 2
        assert stat.country == "India"
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
        network_type="Residential Broadband",
    )
    reasons = detect_anomalies(
        geo(city="Bengaluru", country="India", network="Datacenter / Cloud"),
        previous,
        now(),
        30,
    )
    assert "hosting_provider" in reasons
    assert "rapid_country_change" in reasons
    assert "historical_location_inconsistency" in reasons


def test_consented_location_updates_visit_and_aggregate(session_factory, monkeypatch):
    monkeypatch.setattr(
        "app.services.tracking.reverse_geocode",
        lambda _lat, _lon: ReverseGeocodeResult(
            city="Mysuru",
            state="Karnataka",
            country="India",
            raw_city="Mysuru",
            raw_state="Karnataka",
            raw_country="India",
            source_detail="test_reverse_geocode",
        ),
    )
    with session_factory() as db:
        visit = record_visit(
            db,
            visitor_hash="b" * 64,
            agent=ParsedAgent("Chrome 120", "Windows", "Desktop"),
            signals=BrowserSignals(timezone="Asia/Kolkata", language="en-IN"),
            geo=geo(city="Bengaluru"),
        )
        assert apply_consented_location(
            db,
            visit_id=visit.id,
            visitor_hash_prefix="b" * 16,
            latitude=12.30,
            longitude=76.65,
            accuracy_meters=50,
        )
        updated = db.get(VisitLog, visit.id)
        visitor = db.scalar(select(Visitor))
        assert updated.city == "Mysuru"
        assert updated.location_source == SOURCE_BROWSER
        assert updated.city_confidence_score >= 90
        assert visitor.current_city == "Mysuru"
        old_stat = db.scalar(select(AggregatedDailyStat).where(AggregatedDailyStat.city == "Bengaluru"))
        new_stat = db.scalar(select(AggregatedDailyStat).where(AggregatedDailyStat.city == "Mysuru"))
        assert old_stat.visit_count == 0
        assert new_stat.visit_count == 1


def test_classify_visitor_heuristics():
    from app.services.crawlers import classify_visitor
    
    # 1. Known Crawler (Googlebot)
    res = classify_visitor("Googlebot/2.1 (+http://www.google.com/bot.html)", "66.249.66.1", 15169, "Google LLC", "Search Engine Crawler")
    assert res.classification == "Search Engine Crawler"
    assert res.confidence == 1.0
    
    # 2. Datacenter browser (Likely Bot)
    res = classify_visitor("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "3.5.1.1", 16509, "Amazon.com", "Cloud Provider")
    assert res.classification == "Likely Bot"
    assert res.confidence == 0.8
    
    # 3. VPN Human (Likely Human)
    res = classify_visitor("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "185.200.118.4", 9009, "Mullvad VPN", "VPN")
    assert res.classification == "Likely Human"
    assert res.confidence == 0.7
    
    # 4. Residential Human (Human)
    res = classify_visitor("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "1.1.1.1", 13335, "Cloudflare Inc.", "Residential Broadband")
    assert res.classification == "Human"
    assert res.confidence == 0.95

    # 5. Unknown network with standard browser (Human)
    res = classify_visitor("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "127.0.0.1", None, None, "Unknown")
    assert res.classification == "Human"
    assert res.confidence == 0.85


def test_record_failed_visit_stores_correct_reasons(session_factory):
    from app.services.tracking import record_failed_visit
    with session_factory() as db:
        failed = record_failed_visit(
            db,
            visitor_hash="f" * 64,
            user_agent="Mozilla/5.0",
            ip="8.8.8.8",
            failure_reason="test_database_failure",
            classification="Unknown"
        )
        assert failed is not None
        assert failed.tracking_status == "failed"
        assert failed.tracking_failure_reason == "test_database_failure"
        assert failed.visitor.visitor_hash == "f" * 64


def test_historical_location_fallback_and_source_naming(session_factory):
    with session_factory() as db:
        visit1 = record_visit(
            db,
            visitor_hash="c" * 64,
            agent=ParsedAgent("Chrome 120", "Windows", "Desktop"),
            signals=BrowserSignals(timezone="Asia/Kolkata", language="en-IN"),
            geo=geo(city="Bengaluru"),
        )
        assert apply_consented_location(
            db,
            visit_id=visit1.id,
            visitor_hash_prefix="c" * 16,
            latitude=12.97,
            longitude=77.59,
            accuracy_meters=10,
        )
        visitor = db.scalar(select(Visitor).where(Visitor.visitor_hash == "c" * 64))
        assert visitor.current_location_source == SOURCE_BROWSER
        assert visitor.current_city == "Bengaluru"
        
        visit2 = record_visit(
            db,
            visitor_hash="c" * 64,
            agent=ParsedAgent("Chrome 120", "Windows", "Desktop"),
            signals=BrowserSignals(timezone="Asia/Kolkata", language="en-IN"),
            geo=GeoResult(network_type="Unknown"),
        )
        
        assert visit2.city == "Bengaluru"
        assert visit2.location_source == "Browser Geolocation API (historical)"
        assert "historical" in visit2.location_source_detail


def test_historical_consented_location_preferred_over_latency_triangulation(session_factory, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "disable_latency_triangulation", False)
    monkeypatch.setattr(
        "app.services.tracking.reverse_geocode",
        lambda _lat, _lon: ReverseGeocodeResult(
            city="Mangalore",
            state="Karnataka",
            country="India",
            raw_city="Mangalore",
            raw_state="Karnataka",
            raw_country="India",
            source_detail="nominatim_reverse_geocode",
        ),
    )
    with session_factory() as db:
        # Create a visitor with low-accuracy explicit consent location
        # confidence overall score will be around 70 (lower than triangulation's 77)
        visit1 = record_visit(
            db,
            visitor_hash="d" * 64,
            agent=ParsedAgent("Chrome 120", "Windows", "Desktop"),
            signals=BrowserSignals(timezone="Asia/Kolkata", language="en-IN"),
            geo=geo(city="Mangalore"),
        )
        assert apply_consented_location(
            db,
            visit_id=visit1.id,
            visitor_hash_prefix="d" * 16,
            latitude=12.91,
            longitude=74.85,
            accuracy_meters=50_000, # Low accuracy, results in low confidence score (<70)
        )
        visitor = db.scalar(select(Visitor).where(Visitor.visitor_hash == "d" * 64))
        assert visitor.current_location_source == SOURCE_BROWSER
        assert visitor.current_city == "Mangalore"
        
        # Second visit has latency signals pointing to Bangalore (closest)
        # Latency triangulation normally overrides and gets confidence ~77
        visit2 = record_visit(
            db,
            visitor_hash="d" * 64,
            agent=ParsedAgent("Chrome 120", "Windows", "Desktop"),
            signals=BrowserSignals(
                timezone="Asia/Kolkata", 
                language="en-IN",
                latency_bangalore=15.0, # Closest is Bangalore
                latency_mumbai=40.0,
                latency_delhi=60.0,
            ),
            geo=geo(city="Unknown"), # Mismatch from IP lookup
        )
        
        # We assert that it STILL fell back to the historical consented location (Mangalore),
        # not the latency-triangulated location (Bengaluru).
        assert visit2.city == "Mangalore"
        assert visit2.location_source == "Browser Geolocation API (historical)"
        assert "historical_consented_location_preferred" in visit2.location_source_detail


def test_inline_gps_skips_triangulation(session_factory, monkeypatch):
    """When BrowserSignals includes lat/lng, the visit should be recorded with
    browser geolocation source, NOT latency triangulation."""
    monkeypatch.setattr(
        "app.services.tracking.reverse_geocode",
        lambda _lat, _lon: ReverseGeocodeResult(
            city="Mysuru",
            state="Karnataka",
            country="India",
            raw_city="Mysuru",
            raw_state="Karnataka",
            raw_country="India",
            source_detail="test_reverse_geocode",
        ),
    )
    with session_factory() as db:
        visit = record_visit(
            db,
            visitor_hash="e" * 64,
            agent=ParsedAgent("Chrome 120", "Android", "Mobile"),
            signals=BrowserSignals(
                timezone="Asia/Kolkata",
                language="en-IN",
                # GPS coords included inline (auto-granted on mobile)
                latitude=12.30,
                longitude=76.65,
                accuracy_meters=50,
                # Latency data that would normally trigger triangulation
                latency_bangalore=15.0,
                latency_mumbai=40.0,
                latency_delhi=60.0,
            ),
            geo=geo(city="Mumbai"),  # GeoIP says Mumbai, but GPS says Mysuru
        )
        assert visit.city == "Mysuru"
        assert visit.state == "Karnataka"
        assert visit.location_source == SOURCE_BROWSER
        assert visit.city_confidence_score >= 90
        assert visit.geolocation_accuracy_meters == 50


def test_ranked_resolution_agreement_boost(session_factory, monkeypatch):
    """When ISP parsing and latency triangulation agree on the same city,
    both should get an agreement boost, and the winner should have
    higher confidence than either source alone."""
    from app.config import settings
    monkeypatch.setattr(settings, "disable_latency_triangulation", False)
    with session_factory() as db:
        visit = record_visit(
            db,
            visitor_hash="g" * 64,
            agent=ParsedAgent("Chrome 120", "Windows", "Desktop"),
            signals=BrowserSignals(
                timezone="Asia/Kolkata",
                language="en-IN",
                # Latency closest to Bangalore
                latency_bangalore=15.0,
                latency_mumbai=40.0,
                latency_delhi=60.0,
            ),
            # ISP name contains "bangalore", and GeoIP says Mumbai (mismatch with both)
            geo=GeoResult(
                city="Mumbai",
                state="Maharashtra",
                country="India",
                geo_timezone="Asia/Kolkata",
                asn=123,
                organization="Airtel Bangalore Broadband",
                network_type="Residential Broadband",
                base_confidence=78,
            ),
        )
        # Both ISP and Latency point to Bengaluru — with agreement boost,
        # ISP (base 85 + 8 = 93 city) should beat GeoIP
        assert visit.city == "Bengaluru"
        assert visit.state == "Karnataka"
        # The winner should have the agreement boost applied
        assert visit.city_confidence_score > 85  # base ISP city is 85, boosted to 93
        assert "source_agreement_city_boost" in (visit.location_source_detail or "")  or \
               visit.city_confidence_score >= 90  # either visible in detail or score confirms boost


def test_consented_location_stores_detailed_address(session_factory, monkeypatch):
    monkeypatch.setattr(
        "app.services.tracking.reverse_geocode",
        lambda _lat, _lon: ReverseGeocodeResult(
            city="Bengaluru",
            state="Karnataka",
            country="India",
            raw_city="Bengaluru",
            raw_state="Karnataka",
            raw_country="India",
            source_detail="nominatim_reverse_geocode",
            address="123 MG Road, Bengaluru, Karnataka, 560001",
        ),
    )
    with session_factory() as db:
        visit = record_visit(
            db,
            visitor_hash="e" * 64,
            agent=ParsedAgent("Chrome 120", "Windows", "Desktop"),
            signals=BrowserSignals(timezone="Asia/Kolkata", language="en-IN", latitude=12.97, longitude=77.59, accuracy_meters=10),
            geo=geo(city="Mumbai"),
        )
        assert visit.city == "Bengaluru"
        assert visit.location_source_detail == "123 MG Road, Bengaluru, Karnataka, 560001"


def test_passive_location_appends_postal_code(session_factory):
    with session_factory() as db:
        visit = record_visit(
            db,
            visitor_hash="f" * 64,
            agent=ParsedAgent("Chrome 120", "Windows", "Desktop"),
            signals=BrowserSignals(timezone="Asia/Kolkata", language="en-IN"),
            geo=GeoResult(
                city="Bengaluru",
                state="Karnataka",
                country="India",
                geo_timezone="Asia/Kolkata",
                asn=123,
                organization="Broadband",
                network_type="Residential Broadband",
                base_confidence=78,
                postal_code="560001",
                consensus_verified=True,
            ),
        )
        assert visit.city == "Bengaluru"
        assert "560001" in visit.location_source_detail
        assert "[Postal Code: 560001]" in visit.location_source_detail

