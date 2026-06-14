from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AggregatedDailyStat, CrawlerVisitLog, DailyStatVisitor, VisitLog, Visitor
import logging
from app.schemas import BrowserSignals
from app.services.fingerprint import ParsedAgent
from app.services.geoip import GeoResult
from app.services.location_intelligence import (
    ConfidenceScores,
    SOURCE_BROWSER,
    score_consented_location,
    score_passive_location,
    confidence_level,
    overall_confidence,
)
from app.services.reverse_geocode import reverse_geocode

logger = logging.getLogger("visitor_analytics.tracker")


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def confidence_score(geo: GeoResult, signals: BrowserSignals, visitor: Visitor | None) -> int:
    return score_passive_location(geo, signals, visitor).overall


def detect_anomalies(
    geo: GeoResult, 
    previous: VisitLog | None, 
    now: datetime, 
    confidence: int, 
    agent: ParsedAgent | None = None, 
    signals: BrowserSignals | None = None,
    ip: str | None = None,
) -> list[str]:
    reasons: list[str] = []
    if geo.network_type in {"VPN / Proxy", "VPN Candidate", "VPN", "Proxy"}:
        reasons.append("probable_vpn")
    if geo.network_type in {"Datacenter / Cloud", "Hosting Provider", "Cloud Provider", "Datacenter"}:
        reasons.append("hosting_provider")
    if previous and now - previous.timestamp <= timedelta(hours=6):
        if previous.country and geo.country and previous.country != geo.country:
            reasons.append("rapid_country_change")
        elif previous.city and geo.city and previous.city != geo.city:
            reasons.append("rapid_city_change")
    if previous and previous.country and geo.country and previous.country != geo.country and confidence < 55:
        reasons.append("historical_location_inconsistency")
        
    if agent and signals:
        from app.services.integrity import detect_client_spoofing
        reasons.extend(detect_client_spoofing(agent, signals, ip=ip, ip_country=geo.country, asn=geo.asn))
        
    return reasons


def _location_value(value: str | None) -> str:
    return value or "Unknown"


def _stat_for(db: Session, day, city: str, state: str) -> AggregatedDailyStat | None:
    return db.scalar(
        select(AggregatedDailyStat).where(
            AggregatedDailyStat.date == day,
            AggregatedDailyStat.city == city,
            AggregatedDailyStat.state == state,
        )
    )


def _increment_daily_stat(db: Session, visitor: Visitor, day, city: str, state: str, country: str) -> None:
    stat = _stat_for(db, day, city, state)
    if stat is None:
        stat = AggregatedDailyStat(
            date=day,
            country=country,
            city=city,
            state=state,
            visit_count=0,
            unique_visitors=0,
        )
        db.add(stat)
        db.flush()
    elif stat.country == "Unknown" and country != "Unknown":
        stat.country = country
    stat.visit_count += 1
    seen = db.get(DailyStatVisitor, (stat.id, visitor.id))
    if seen is None:
        db.add(DailyStatVisitor(daily_stat_id=stat.id, visitor_id=visitor.id))
        stat.unique_visitors += 1


def _matches_location(column, value: str):
    if value == "Unknown":
        return column.is_(None)
    return column == value


def _decrement_daily_stat(
    db: Session,
    visit: VisitLog,
    visitor: Visitor,
    city: str,
    state: str,
) -> None:
    stat = _stat_for(db, visit.timestamp.date(), city, state)
    if stat is None:
        return
    stat.visit_count = max(0, stat.visit_count - 1)
    start = datetime.combine(visit.timestamp.date(), datetime.min.time())
    end = start + timedelta(days=1)
    other_visit = db.scalar(
        select(VisitLog.id)
        .where(
            VisitLog.id != visit.id,
            VisitLog.visitor_id == visitor.id,
            VisitLog.timestamp >= start,
            VisitLog.timestamp < end,
            _matches_location(VisitLog.city, city),
            _matches_location(VisitLog.state, state),
        )
        .limit(1)
    )
    if other_visit is None:
        seen = db.get(DailyStatVisitor, (stat.id, visitor.id))
        if seen is not None:
            db.delete(seen)
            stat.unique_visitors = max(0, stat.unique_visitors - 1)


def _update_visitor_location(
    visitor: Visitor,
    *,
    city: str | None,
    state: str | None,
    country: str | None,
    confidence: ConfidenceScores,
    asn: int | None,
    isp: str | None,
    network_type: str,
) -> None:
    visitor.current_city = city
    visitor.current_state = state
    visitor.current_country = country
    visitor.confidence_score = confidence.overall
    visitor.country_confidence_score = confidence.country
    visitor.state_confidence_score = confidence.state
    visitor.city_confidence_score = confidence.city
    visitor.current_asn = asn
    visitor.current_isp = isp
    visitor.current_network_type = network_type
    visitor.current_location_source = confidence.location_source


def resolve_best_location(
    geo: GeoResult,
    signals: BrowserSignals,
    visitor: Visitor | None,
    passive_confidence: ConfidenceScores,
    ip: str | None = None,
) -> tuple[str | None, str | None, str | None, ConfidenceScores]:
    """Resolves true visitor location by scoring independent candidates and
    picking the highest-confidence one.

    Candidate sources:
      1. GeoIP DB / ip-api  (passive_confidence, always present)
      2. ISP Name Parsing   (when ISP org contains a city keyword)
      3. Latency Triangulation (when ping data available)
      4. Reverse DNS Parsing (when client PTR record contains city keyword)

    Agreement between sources boosts confidence; the highest-scoring candidate
    wins.
    """
    from dataclasses import dataclass

    @dataclass
    class LocationCandidate:
        city: str | None
        state: str | None
        country: str | None
        confidence: ConfidenceScores
        source_name: str

    candidates: list[LocationCandidate] = []

    # ── Candidate 1: GeoIP DB / ip-api (always present) ───────────────
    geo_city_conf = passive_confidence.city
    geo_state_conf = passive_confidence.state
    geo_country_conf = passive_confidence.country
    
    is_cellular_carrier = geo.asn in {55836, 64065, 45609, 9498, 55410}
    if is_cellular_carrier:
        # Penalize cellular gateway accuracy as routing is centralized
        geo_city_conf = max(0, geo_city_conf - 20)
        geo_state_conf = max(0, geo_state_conf - 15)
        
    geo_overall = overall_confidence(geo_country_conf, geo_state_conf, geo_city_conf)
    
    candidates.append(LocationCandidate(
        city=geo.city,
        state=geo.state,
        country=geo.country,
        confidence=ConfidenceScores(
            country=geo_country_conf,
            state=geo_state_conf,
            city=geo_city_conf,
            overall=geo_overall,
            location_source=passive_confidence.location_source,
            detail=passive_confidence.detail + " (cellular_carrier_penalty)" if is_cellular_carrier else passive_confidence.detail,
            reasons=list(passive_confidence.reasons) + ["cellular_gateway_penalty"] if is_cellular_carrier else passive_confidence.reasons,
        ),
        source_name="GeoIP DB",
    ))

    # ── Candidate 2: ISP Name Parsing ─────────────────────────────────
    isp_raw = (geo.organization or "").lower()
    isp_candidate: LocationCandidate | None = None
    if geo.country == "India" or not geo.country:
        isp_mappings = {
            "bengaluru": ("Bengaluru", "Karnataka", "India"),
            "bangalore": ("Bengaluru", "Karnataka", "India"),
            "chennai": ("Chennai", "Tamil Nadu", "India"),
            "mumbai": ("Mumbai", "Maharashtra", "India"),
            "delhi": ("Delhi", "Delhi", "India"),
            "new delhi": ("Delhi", "Delhi", "India"),
            "hyderabad": ("Hyderabad", "Telangana", "India"),
            "kolkata": ("Kolkata", "West Bengal", "India"),
            "pune": ("Pune", "Maharashtra", "India"),
            "mangalore": ("Mangalore", "Karnataka", "India"),
            "kochi": ("Kochi", "Kerala", "India"),
        }
        for keyword, (parsed_city, parsed_state, parsed_country) in isp_mappings.items():
            if keyword in isp_raw:
                reasons = list(passive_confidence.reasons) + ["isp_name_keyword_match"]
                isp_candidate = LocationCandidate(
                    city=parsed_city,
                    state=parsed_state,
                    country=parsed_country,
                    confidence=ConfidenceScores(
                        country=90, state=88, city=85,
                        overall=overall_confidence(90, 88, 85),
                        location_source="ISP Name Parsing",
                        detail=f"isp_name_match: {keyword}",
                        reasons=reasons,
                    ),
                    source_name="ISP Name Parsing",
                )
                candidates.append(isp_candidate)
                break

    # ── Candidate 3: Latency Triangulation ────────────────────────────
    # Skip latency candidate if explicit location coordinates are present (user granted permission)
    is_location_granted = signals.latitude is not None and signals.longitude is not None
    
    latency_candidate: LocationCandidate | None = None
    from app.config import settings
    has_pings = (
        not settings.disable_latency_triangulation 
        and not is_location_granted 
        and any(
            getattr(signals, f"latency_{c}") is not None
            for c in ["mumbai", "hyderabad", "delhi", "bangalore", "chennai", "kochi", "mangalore", "kolkata"]
        )
    )
    if has_pings and (geo.country == "India" or not geo.country):
        pings = {
            "mumbai": signals.latency_mumbai,
            "hyderabad": signals.latency_hyderabad,
            "delhi": signals.latency_delhi,
            "bangalore": signals.latency_bangalore,
            "chennai": signals.latency_chennai,
            "kochi": signals.latency_kochi,
            "mangalore": signals.latency_mangalore,
            "kolkata": signals.latency_kolkata,
        }
        valid_pings = {k: v for k, v in pings.items() if v is not None and 0 < v < 1000}
        if valid_pings:
            closest_city_key = min(valid_pings, key=valid_pings.get)
            closest_ping = valid_pings[closest_city_key]

            city_mappings = {
                "bangalore": ("Bengaluru", "Karnataka", "India"),
                "mangalore": ("Mangalore", "Karnataka", "India"),
                "kochi": ("Kochi", "Kerala", "India"),
                "chennai": ("Chennai", "Tamil Nadu", "India"),
                "kolkata": ("Kolkata", "West Bengal", "India"),
                "mumbai": ("Mumbai", "Maharashtra", "India"),
                "delhi": ("Delhi", "Delhi", "India"),
                "hyderabad": ("Hyderabad", "Telangana", "India"),
            }

            mapped_city, mapped_state, mapped_country = city_mappings[closest_city_key]
            reasons = list(passive_confidence.reasons) + ["latency_triangulation_candidate"]
            
            # Scale confidence based on ping time
            if closest_ping < 50:
                l_country, l_state, l_city = 92, 85, 78
            elif closest_ping < 150:
                l_country, l_state, l_city = 90, 80, 72
            elif closest_ping < 300:
                l_country, l_state, l_city = 85, 75, 65
            elif closest_ping < 500:
                l_country, l_state, l_city = 80, 65, 50
            else:
                l_country, l_state, l_city = 70, 50, 30

            latency_candidate = LocationCandidate(
                city=mapped_city,
                state=mapped_state,
                country=mapped_country,
                confidence=ConfidenceScores(
                    country=l_country, state=l_state, city=l_city,
                    overall=overall_confidence(l_country, l_state, l_city),
                    location_source="Latency Triangulation",
                    detail=f"latency_closest_{closest_city_key}_{closest_ping:.0f}ms",
                    reasons=reasons,
                ),
                source_name="Latency Triangulation",
            )
            candidates.append(latency_candidate)

    # ── Candidate 4: Reverse DNS PTR Parsing ────────────────────────────
    from app.services.integrity import resolve_rdns_location
    rdns_city, rdns_state, rdns_country = None, None, None
    if ip:
        rdns_city, rdns_state, rdns_country = resolve_rdns_location(ip)
        if any((rdns_city, rdns_state, rdns_country)):
            reasons = list(passive_confidence.reasons) + ["rdns_ptr_keyword_match"]
            candidates.append(LocationCandidate(
                city=rdns_city,
                state=rdns_state,
                country=rdns_country,
                confidence=ConfidenceScores(
                    country=95 if rdns_country else 0,
                    state=90 if rdns_state else 0,
                    city=85 if rdns_city else 0,
                    overall=overall_confidence(95 if rdns_country else 0, 90 if rdns_state else 0, 85 if rdns_city else 0),
                    location_source="Reverse DNS Parsing",
                    detail=f"rdns_match: {rdns_city or ''}",
                    reasons=reasons,
                ),
                source_name="Reverse DNS Parsing",
            ))

    # ── Agreement / Disagreement Adjustments ──────────────────────────
    if len(candidates) > 1:
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                ci, cj = candidates[i], candidates[j]
                city_agree = (
                    ci.city and cj.city
                    and ci.city.lower() == cj.city.lower()
                )
                state_agree = (
                    ci.state and cj.state
                    and ci.state.lower() == cj.state.lower()
                )

                if city_agree:
                    # Boost both candidates for city agreement
                    for c in (ci, cj):
                        boosted_city = min(100, c.confidence.city + 8)
                        boosted_state = min(100, c.confidence.state + 5)
                        boosted_country = c.confidence.country
                        new_reasons = list(c.confidence.reasons)
                        if "source_agreement_city_boost" not in new_reasons:
                            new_reasons.append("source_agreement_city_boost")
                        c.confidence = ConfidenceScores(
                            country=boosted_country,
                            state=boosted_state,
                            city=boosted_city,
                            overall=overall_confidence(boosted_country, boosted_state, boosted_city),
                            location_source=c.confidence.location_source,
                            detail=c.confidence.detail,
                            reasons=new_reasons,
                        )
                elif state_agree and not city_agree:
                    # State agrees but city disagrees — modest state boost
                    for c in (ci, cj):
                        boosted_state = min(100, c.confidence.state + 3)
                        new_reasons = list(c.confidence.reasons)
                        if "source_agreement_state_boost" not in new_reasons:
                            new_reasons.append("source_agreement_state_boost")
                        c.confidence = ConfidenceScores(
                            country=c.confidence.country,
                            state=boosted_state,
                            city=c.confidence.city,
                            overall=overall_confidence(c.confidence.country, boosted_state, c.confidence.city),
                            location_source=c.confidence.location_source,
                            detail=c.confidence.detail,
                            reasons=new_reasons,
                        )
                else:
                    # Full disagreement — penalize the GeoIP candidate's city score
                    if ci.source_name == "GeoIP DB":
                        penalized_city = max(0, ci.confidence.city - 5)
                        new_reasons = list(ci.confidence.reasons)
                        if "source_disagreement_city_penalty" not in new_reasons:
                            new_reasons.append("source_disagreement_city_penalty")
                        ci.confidence = ConfidenceScores(
                            country=ci.confidence.country,
                            state=ci.confidence.state,
                            city=penalized_city,
                            overall=overall_confidence(ci.confidence.country, ci.confidence.state, penalized_city),
                            location_source=ci.confidence.location_source,
                            detail=ci.confidence.detail,
                            reasons=new_reasons,
                        )

    # ── Pick the best candidate ───────────────────────────────────────
    non_latency_candidates = [c for c in candidates if c.source_name != "Latency Triangulation"]
    latency_candidates = [c for c in candidates if c.source_name == "Latency Triangulation"]

    # Actively prioritize non-latency candidates that successfully resolved a location with >= 50 confidence
    strong_non_latency = [
        c for c in non_latency_candidates
        if c.confidence.overall >= 50 and c.city and c.city != "Unknown"
    ]

    if strong_non_latency:
        best = max(strong_non_latency, key=lambda c: c.confidence.overall)
    elif latency_candidates:
        # If all other methods return low confidence or miss resolved details, use latency as last resort
        best = latency_candidates[0]
    elif non_latency_candidates:
        best = max(non_latency_candidates, key=lambda c: c.confidence.overall)
    else:
        best = candidates[0]

    logger.info(
        "[GEOLOCATION] Ranked Resolution: %d candidates | Winner: %s (%s, %s, %s) conf=%d | %s",
        len(candidates),
        best.source_name,
        best.city,
        best.state,
        best.country,
        best.confidence.overall,
        " | ".join(
            f"{c.source_name}={c.confidence.overall}({c.city})"
            for c in candidates
        ),
    )

    return best.city, best.state, best.country, best.confidence


def record_visit(
    db: Session,
    *,
    visitor_hash: str,
    agent: ParsedAgent,
    signals: BrowserSignals,
    geo: GeoResult,
    classification: str = "Unknown",
    class_confidence: float = 0.0,
    class_reason: str | None = None,
    tracking_status: str = "persisted",
    tracking_failure_reason: str | None = None,
    ip: str | None = None,
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
    confidence = score_passive_location(geo, signals, visitor)
    is_crawler = classification in {
        "Social Media Crawler", "Search Engine Crawler", "Security Scanner", "Monitoring Service", "Known Bot"
    }

    # ── Inline GPS: browser location was sent in /sync payload ─────────
    inline_gps_used = False
    geolocation_accuracy = None
    if signals.latitude is not None and signals.longitude is not None:
        geocoded = reverse_geocode(signals.latitude, signals.longitude)
        geolocation_accuracy = signals.accuracy_meters
        effective_confidence = score_consented_location(geolocation_accuracy)
        effective_city = geocoded.city
        effective_state = geocoded.state
        effective_country = geocoded.country
        inline_gps_used = True
        logger.info(
            "[GEOLOCATION] Inline GPS applied: %s, %s, %s (accuracy=%s)",
            effective_city, effective_state, effective_country, geolocation_accuracy,
        )

    # ── Ranked passive resolution (no GPS available) ──────────────────
    if not inline_gps_used:
        effective_city, effective_state, effective_country, effective_confidence = resolve_best_location(
            geo, signals, visitor, confidence, ip=ip
        )

    if not inline_gps_used and visitor and any((visitor.current_city, visitor.current_state, visitor.current_country)):
        is_unresolved = not any((geo.city, geo.state, geo.country))
        is_same_country = geo.country and geo.country == visitor.current_country
        
        has_historical_consent = visitor.current_location_source and (
            "user-consented" in visitor.current_location_source or
            "Browser Geolocation" in visitor.current_location_source or
            "historical" in visitor.current_location_source.lower()
        )
        
        should_fallback = is_unresolved or (
            is_same_country and (
                has_historical_consent or
                visitor.confidence_score > effective_confidence.overall
            )
        )
        
        if should_fallback:
            effective_city = visitor.current_city
            effective_state = visitor.current_state
            effective_country = visitor.current_country
            fallback_source = visitor.current_location_source or "Unknown"
            if "user-consented" in fallback_source:
                fallback_source = fallback_source.replace("user-consented", "historical")
            elif "historical" not in fallback_source.lower() and fallback_source != "Unknown":
                fallback_source = f"{fallback_source} (Historical)"

            effective_confidence = ConfidenceScores(
                country=visitor.country_confidence_score,
                state=visitor.state_confidence_score,
                city=visitor.city_confidence_score,
                overall=visitor.confidence_score,
                location_source=fallback_source,
                detail="historical_consented_location_preferred" if has_historical_consent else "historical_fallback_higher_confidence",
                reasons=["historical_fallback"],
            )

    if visitor is None:
        visitor = Visitor(
            visitor_hash=visitor_hash,
            first_seen=now,
            last_seen=now,
            total_visits=1,
            is_crawler=is_crawler,
            classification=classification,
            classification_confidence=class_confidence,
            classification_reason=class_reason,
        )
        db.add(visitor)
        db.flush()
    else:
        visitor.last_seen = now
        visitor.total_visits += 1
        visitor.is_crawler = is_crawler
        visitor.classification = classification
        visitor.classification_confidence = class_confidence
        visitor.classification_reason = class_reason

    _update_visitor_location(
        visitor,
        city=effective_city,
        state=effective_state,
        country=effective_country,
        confidence=effective_confidence,
        asn=geo.asn,
        isp=geo.organization,
        network_type=geo.network_type,
    )
    visitor.current_country_confidence = confidence_level(effective_confidence.country)
    visitor.current_state_confidence = confidence_level(effective_confidence.state)
    visitor.current_city_confidence = confidence_level(effective_confidence.city)
    visitor.current_location_confidence = confidence_level(effective_confidence.overall)

    reasons = detect_anomalies(geo, previous, now, confidence.overall, agent, signals, ip=ip)
    visit = VisitLog(
        visitor_id=visitor.id,
        timestamp=now,
        city=effective_city,
        state=effective_state,
        country=effective_country,
        city_raw=geo.city_raw or geo.city,
        state_raw=geo.state_raw or geo.state,
        country_raw=geo.country_raw or geo.country,
        city_normalized=effective_city,
        state_normalized=effective_state,
        country_normalized=effective_country,
        confidence_score=effective_confidence.overall,
        country_confidence_score=effective_confidence.country,
        state_confidence_score=effective_confidence.state,
        city_confidence_score=effective_confidence.city,
        location_source=effective_confidence.location_source,
        location_source_detail=effective_confidence.detail,
        browser=agent.browser,
        os=agent.os,
        device_type=agent.device_type,
        network_type=geo.network_type,
        asn=geo.asn,
        isp=geo.organization,
        network_organization=geo.organization,
        timezone=signals.timezone,
        language=signals.language,
        accept_language=signals.accept_language,
        screen_resolution=signals.screen_resolution,
        geolocation_accuracy_meters=geolocation_accuracy,
        cores=signals.cores,
        memory=signals.memory,
        gpu=signals.gpu,
        rtt=signals.rtt,
        downlink=signals.downlink,
        save_data=signals.save_data,
        has_private_ip=signals.has_private_ip,
        ping_jitter=signals.ping_jitter,
        canvas_hash=signals.canvas_hash,
        webgl_hash=signals.webgl_hash,
        is_anomalous=bool(reasons),
        anomaly_reasons=reasons or None,
        is_crawler=is_crawler,
        crawler_type=classification if is_crawler else None,
        tracking_status=tracking_status,
        tracking_failure_reason=tracking_failure_reason,
        classification=classification,
        classification_confidence=class_confidence,
        classification_reason=class_reason,
        country_confidence=confidence_level(effective_confidence.country),
        state_confidence=confidence_level(effective_confidence.state),
        city_confidence=confidence_level(effective_confidence.city),
        location_confidence=confidence_level(effective_confidence.overall),
    )
    db.add(visit)

    if not is_crawler:
        city = effective_city or "Unknown"
        state = effective_state or "Unknown"
        country = effective_country or "Unknown"
        _increment_daily_stat(db, visitor, now.date(), city, state, country)
        
    db.commit()
    db.refresh(visit)
    if signals.nonce:
        from app.services.integrity import register_visit_nonce
        register_visit_nonce(signals.nonce, visit.id)
    return visit


def record_failed_visit(
    db: Session,
    *,
    visitor_hash: str,
    user_agent: str,
    ip: str,
    failure_reason: str,
    classification: str = "Unknown",
    class_confidence: float = 0.0,
    class_reason: str | None = None,
    geo: GeoResult | None = None,
    agent: ParsedAgent | None = None,
    signals: BrowserSignals | None = None,
) -> VisitLog | None:
    try:
        now = utcnow()
        visitor = db.scalar(select(Visitor).where(Visitor.visitor_hash == visitor_hash))
        is_crawler = classification in {
            "Social Media Crawler", "Search Engine Crawler", "Security Scanner", "Monitoring Service", "Known Bot"
        }
        if visitor is None:
            visitor = Visitor(
                visitor_hash=visitor_hash,
                first_seen=now,
                last_seen=now,
                total_visits=1,
                is_crawler=is_crawler,
                classification=classification,
                classification_confidence=class_confidence,
                classification_reason=class_reason,
            )
            db.add(visitor)
            db.flush()
        visit = VisitLog(
            visitor_id=visitor.id,
            timestamp=now,
            tracking_status="failed",
            tracking_failure_reason=failure_reason[:255],
            classification=classification,
            classification_confidence=class_confidence,
            classification_reason=class_reason,
            country_confidence="Low",
            state_confidence="Low",
            city_confidence="Low",
            location_confidence="Low",
            is_crawler=is_crawler,
            network_type=geo.network_type if geo else "Unknown",
            asn=geo.asn if geo else None,
            isp=geo.organization if geo else None,
            browser=agent.browser if agent else None,
            os=agent.os if agent else None,
            device_type=agent.device_type if agent else None,
            timezone=signals.timezone if signals else None,
            language=signals.language if signals else None,
            screen_resolution=signals.screen_resolution if signals else None,
            cores=signals.cores if signals else None,
            memory=signals.memory if signals else None,
            gpu=signals.gpu if signals else None,
            rtt=signals.rtt if signals else None,
            downlink=signals.downlink if signals else None,
            save_data=signals.save_data if signals else None,
            has_private_ip=signals.has_private_ip if signals else None,
            ping_jitter=signals.ping_jitter if signals else None,
            canvas_hash=signals.canvas_hash if signals else None,
            webgl_hash=signals.webgl_hash if signals else None,
        )
        db.add(visit)
        db.commit()
        db.refresh(visit)
        return visit
    except Exception as e:
        logger.error("Failed to record failed visit: %s", str(e), exc_info=True)
        db.rollback()
        return None


def record_crawler_visit(
    db: Session,
    *,
    crawler_type: str,
    agent: ParsedAgent,
    signals: BrowserSignals,
    geo: GeoResult,
) -> CrawlerVisitLog:
    confidence = score_passive_location(geo, signals, None)
    visit = CrawlerVisitLog(
        timestamp=utcnow(),
        crawler_type=crawler_type,
        user_agent_family=agent.browser,
        city=geo.city,
        state=geo.state,
        country=geo.country,
        confidence_score=confidence.overall,
        asn=geo.asn,
        isp=geo.organization,
        network_type=geo.network_type,
        location_source=confidence.location_source,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


def apply_consented_location(
    db: Session,
    *,
    visit_id: int,
    visitor_hash_prefix: str,
    latitude: float,
    longitude: float,
    accuracy_meters: int | None,
) -> bool:
    visit = db.get(VisitLog, visit_id)
    if visit is None or not visit.visitor.visitor_hash.startswith(visitor_hash_prefix):
        return False

    geocoded = reverse_geocode(latitude, longitude)
    if not any((geocoded.city, geocoded.state, geocoded.country)):
        visit.geolocation_accuracy_meters = accuracy_meters
        visit.location_source = SOURCE_BROWSER
        visit.location_source_detail = (
            f"browser_location_granted; {geocoded.source_detail}; passive_location_retained"
        )[:240]
        db.commit()
        return False

    visitor = visit.visitor
    old_city = _location_value(visit.city)
    old_state = _location_value(visit.state)
    confidence = score_consented_location(accuracy_meters)

    visit.city = geocoded.city
    visit.state = geocoded.state
    visit.country = geocoded.country
    visit.city_raw = geocoded.raw_city or geocoded.city
    visit.state_raw = geocoded.raw_state or geocoded.state
    visit.country_raw = geocoded.raw_country or geocoded.country
    visit.city_normalized = geocoded.city
    visit.state_normalized = geocoded.state
    visit.country_normalized = geocoded.country
    visit.confidence_score = confidence.overall
    visit.country_confidence_score = confidence.country
    visit.state_confidence_score = confidence.state
    visit.city_confidence_score = confidence.city
    visit.location_source = SOURCE_BROWSER
    visit.location_source_detail = geocoded.source_detail
    visit.geolocation_accuracy_meters = accuracy_meters
    visit.country_confidence = confidence_level(confidence.country)
    visit.state_confidence = confidence_level(confidence.state)
    visit.city_confidence = confidence_level(confidence.city)
    visit.location_confidence = confidence_level(confidence.overall)

    _update_visitor_location(
        visitor,
        city=geocoded.city,
        state=geocoded.state,
        country=geocoded.country,
        confidence=confidence,
        asn=visit.asn,
        isp=visit.isp or visit.network_organization,
        network_type=visit.network_type,
    )
    visitor.current_country_confidence = confidence_level(confidence.country)
    visitor.current_state_confidence = confidence_level(confidence.state)
    visitor.current_city_confidence = confidence_level(confidence.city)
    visitor.current_location_confidence = confidence_level(confidence.overall)

    new_city = _location_value(visit.city)
    new_state = _location_value(visit.state)
    new_country = _location_value(visit.country)
    if old_city != new_city or old_state != new_state:
        _decrement_daily_stat(db, visit, visitor, old_city, old_state)
        _increment_daily_stat(db, visitor, visit.timestamp.date(), new_city, new_state, new_country)

    db.commit()
    return True
