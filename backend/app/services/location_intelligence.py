from dataclasses import dataclass

from app.models import Visitor
from app.schemas import BrowserSignals
from app.services.geoip import GeoResult, normalize_location_name

SOURCE_BROWSER = "Browser Geolocation API (user-consented)"
SOURCE_HYBRID = "Hybrid Inference"
SOURCE_IP_ASN = "IP/ASN Inference"

COUNTRY_BY_LANGUAGE_REGION = {
    "AU": "Australia",
    "BR": "Brazil",
    "CA": "Canada",
    "DE": "Germany",
    "ES": "Spain",
    "FR": "France",
    "GB": "United Kingdom",
    "IN": "India",
    "JP": "Japan",
    "US": "United States",
}

COUNTRY_BY_TIMEZONE = {
    "Asia/Kolkata": "India",
    "Asia/Calcutta": "India",
    "Europe/London": "United Kingdom",
    "Europe/Berlin": "Germany",
    "Europe/Paris": "France",
    "America/New_York": "United States",
    "America/Chicago": "United States",
    "America/Denver": "United States",
    "America/Los_Angeles": "United States",
}


@dataclass(frozen=True)
class ConfidenceScores:
    country: int
    state: int
    city: int
    overall: int
    location_source: str
    detail: str
    reasons: list[str]


def clamp(value: int) -> int:
    return max(0, min(100, value))


def confidence_level(score: int) -> str:
    if score >= 75:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


def overall_confidence(country: int, state: int, city: int) -> int:
    return clamp(round(country * 0.2 + state * 0.35 + city * 0.45))


def _language_regions(signals: BrowserSignals) -> set[str]:
    value = ",".join(item for item in (signals.language, signals.accept_language) if item)
    regions: set[str] = set()
    for part in value.replace("_", "-").split(","):
        token = part.split(";", 1)[0].strip()
        bits = token.split("-")
        if len(bits) >= 2 and len(bits[-1]) == 2:
            regions.add(bits[-1].upper())
    return regions


def _same(value: str | None, other: str | None) -> bool:
    return bool(value and other and normalize_location_name(value) == normalize_location_name(other))


def score_passive_location(
    geo: GeoResult,
    signals: BrowserSignals,
    visitor: Visitor | None,
) -> ConfidenceScores:
    if getattr(geo, "consensus_verified", False):
        country = 90 if geo.country else 0
        state = 85 if geo.state else 0
        city = 80 if geo.city else 0
        reasons: list[str] = ["geoip_consensus_boost"]
    else:
        country = 78 if geo.country else 0
        state = 66 if geo.state else 0
        city = 58 if geo.city else 0
        reasons = ["geolite2_city" if geo.city or geo.state or geo.country else "geolite2_unavailable"]
    hybrid = False

    if geo.asn:
        country += 4
        state += 3
        city += 2
        reasons.append("asn_available")

    if geo.network_type == "Residential Broadband":
        state += 6
        city += 10
        reasons.append("residential_network")
    elif geo.network_type == "Mobile Carrier":
        country += 4
        state -= 4
        city -= 18
        reasons.append("mobile_gateway_city_reduced")
    elif geo.network_type in {"Datacenter", "Cloud Provider"}:
        country -= 5
        state -= 15
        city -= 25
        reasons.append("datacenter_reduced")
    elif geo.network_type in {"VPN", "Proxy"}:
        country -= 10
        state -= 20
        city -= 30
        reasons.append("vpn_proxy_reduced")
    elif geo.network_type in {"Corporate Network", "Educational Network", "Government Network"}:
        state += 2
        city -= 5
        reasons.append("institutional_network")

    if geo.geo_timezone and signals.timezone:
        hybrid = True
        tz_a = geo.geo_timezone.replace("Calcutta", "Kolkata")
        tz_b = signals.timezone.replace("Calcutta", "Kolkata")
        if tz_a == tz_b:
            country += 6
            state += 5
            city += 4
            reasons.append("timezone_match")
        else:
            country -= 10
            state -= 12
            city -= 14
            reasons.append("timezone_mismatch")

    timezone_country = COUNTRY_BY_TIMEZONE.get(signals.timezone or "")
    if timezone_country and geo.country:
        hybrid = True
        if timezone_country == geo.country:
            country += 4
            reasons.append("timezone_country_match")
        else:
            country -= 8
            reasons.append("timezone_country_mismatch")

    language_countries = {COUNTRY_BY_LANGUAGE_REGION[region] for region in _language_regions(signals) if region in COUNTRY_BY_LANGUAGE_REGION}
    if language_countries and geo.country:
        hybrid = True
        if geo.country in language_countries:
            country += 3
            reasons.append("accept_language_country_match")
        else:
            country -= 2
            reasons.append("accept_language_country_mismatch")

    if visitor:
        hybrid = True
        if _same(visitor.current_country, geo.country):
            country += 6
            reasons.append("historical_country_consistency")
        elif visitor.current_country and geo.country:
            country -= 15
            reasons.append("historical_country_mismatch")
        if _same(visitor.current_state, geo.state):
            state += 7
            reasons.append("historical_state_consistency")
        elif visitor.current_state and geo.state:
            state -= 10
            reasons.append("historical_state_mismatch")
        if _same(visitor.current_city, geo.city):
            city += 5
            reasons.append("historical_city_consistency")
        elif visitor.current_city and geo.city:
            city -= 7
            reasons.append("historical_city_mismatch")

    organization = (geo.organization or "").lower()
    if geo.state and geo.state.lower() in organization:
        hybrid = True
        state += 4
        reasons.append("isp_state_hint")
    if geo.city and geo.city.lower() in organization:
        hybrid = True
        city += 4
        reasons.append("isp_city_hint")

    country = clamp(country)
    state = clamp(state)
    city = clamp(city)
    source = SOURCE_HYBRID if hybrid else SOURCE_IP_ASN
    detail = " + ".join(reasons[:6])
    return ConfidenceScores(
        country=country,
        state=state,
        city=city,
        overall=overall_confidence(country, state, city),
        location_source=source,
        detail=detail,
        reasons=reasons,
    )


def score_consented_location(accuracy_meters: int | None) -> ConfidenceScores:
    accuracy = accuracy_meters or 10_000
    if accuracy <= 1_000:
        country, state, city = 99, 98, 96
    elif accuracy <= 5_000:
        country, state, city = 99, 96, 90
    elif accuracy <= 25_000:
        country, state, city = 96, 88, 72
    else:
        country, state, city = 92, 76, 55
    return ConfidenceScores(
        country=country,
        state=state,
        city=city,
        overall=overall_confidence(country, state, city),
        location_source=SOURCE_BROWSER,
        detail="explicit_browser_geolocation_consent",
        reasons=["user_consented_browser_location"],
    )
