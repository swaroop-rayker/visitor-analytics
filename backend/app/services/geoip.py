import logging
from dataclasses import dataclass
from pathlib import Path

import geoip2.database
from geoip2.errors import AddressNotFoundError
from maxminddb.errors import InvalidDatabaseError

from app.config import settings

logger = logging.getLogger("visitor_analytics.tracker")


@dataclass(frozen=True)
class GeoResult:
    city: str | None = None
    state: str | None = None
    country: str | None = None
    city_raw: str | None = None
    state_raw: str | None = None
    country_raw: str | None = None
    geo_timezone: str | None = None
    asn: int | None = None
    organization: str | None = None
    network_type: str = "Unknown"
    base_confidence: int = 0
    postal_code: str | None = None
    consensus_verified: bool = False
    latitude: float | None = None
    longitude: float | None = None


VPN_MARKERS = {
    "vpn", "nordvpn", "expressvpn", "surfshark", "protonvpn", "private internet access",
    "mullvad", "ipvanish", "cyberghost", "windscribe", "vyprvpn", "anonymous", "ip-vpn"
}
PROXY_MARKERS = {
    "proxy", "tor exit", "tor relay", "socks", "shadowsocks", "squid", "proxy-net",
    "smartproxy", "crawl", "scrap", "residential proxy"
}
CLOUD_MARKERS = {
    "aws", "amazon", "google cloud", "gcp", "azure", "microsoft", "digitalocean",
    "linode", "vultr", "oracle cloud", "alibaba", "ovh", "scaleway", "hetzner",
    "heroku", "fastly", "cloudflare", "akamai", "hosting", "provider"
}
DATACENTER_MARKERS = {
    "datacenter", "data center", "colocation", "server", "bandwidth", "telehouse",
    "equinix", "cogent", "hurricane electric", "host", "dedicated", "leaseweb",
    "interxion", "co-location"
}
MOBILE_MARKERS = {
    "airtel", "cellular", "jio", "mobile", "reliance jio", "telefonica",
    "t-mobile", "verizon wireless", "vodafone", "sprint", "orange", "att",
    "telefónica", "docomo", "singtel", "optus", "telstra"
}
EDUCATION_MARKERS = {"college", "edu", "institute", "school", "university", "academy"}
GOVERNMENT_MARKERS = {"gov", "government", "military", "ministry"}
CORPORATE_MARKERS = {"bank", "business", "corp", "corporation", "enterprise", "limited", "ltd", "co.", "inc.", "inc"}
RESIDENTIAL_MARKERS = {"broadband", "cable", "fiber", "fibre", "home", "residential", "telecom", "isp", "adsl", "dsl"}


def normalize_location_name(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.replace("_", " ").strip().split())
    if not cleaned:
        return None
    lowered = cleaned.lower()
    for prefix in ("state of ", "province of ", "region of "):
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    if cleaned.isupper() or cleaned.islower():
        return cleaned.title()
    return cleaned


def classify_network(organization: str | None, asn: int | None = None) -> str:
    value = (organization or "").lower()
    if not value:
        return "Unknown"
    if any(marker in value for marker in VPN_MARKERS):
        return "VPN"
    if any(marker in value for marker in PROXY_MARKERS):
        return "Proxy"
    if any(marker in value for marker in CLOUD_MARKERS):
        return "Cloud Provider"
    if any(marker in value for marker in DATACENTER_MARKERS):
        return "Datacenter"

    # Fixed-line overrides for dual-play mobile/broadband ISPs (like JioFiber and Airtel Xstream)
    fixed_line_indicators = {"fiber", "fibre", "broadband", "dsl", "ftth", "gpon", "cable", "fixed", "line", "xstream", "gigafiber"}
    is_fixed_line = (
        asn in {9498, 64044} or
        any(indicator in value for indicator in fixed_line_indicators)
    )
    if is_fixed_line:
        return "Residential Broadband"

    if any(marker in value for marker in MOBILE_MARKERS):
        return "Mobile Carrier"
    if any(marker in value for marker in RESIDENTIAL_MARKERS):
        return "Residential Broadband"
    if any(marker in value for marker in EDUCATION_MARKERS) or \
       any(marker in value for marker in GOVERNMENT_MARKERS) or \
       any(marker in value for marker in CORPORATE_MARKERS):
        return "Corporate Network"
    return "Residential Broadband"


class GeoIPService:
    def __init__(self, city_path: str | None = None, asn_path: str | None = None) -> None:
        self.city_path = Path(city_path or settings.geoip_city_db)
        self.asn_path = Path(asn_path or settings.geoip_asn_db)

    @property
    def city_available(self) -> bool:
        if getattr(settings, "disable_maxmind_db", False):
            return False
        return self.city_path.is_file()

    @property
    def asn_available(self) -> bool:
        if getattr(settings, "disable_maxmind_db", False):
            return False
        return self.asn_path.is_file()

    def lookup(self, ip_address: str) -> GeoResult:
        maxmind_city = maxmind_state = maxmind_country = maxmind_timezone = maxmind_postal = None
        maxmind_latitude = maxmind_longitude = None
        asn = None
        organization = None
        maxmind_confidence = 0

        try:
            if self.city_available:
                with geoip2.database.Reader(str(self.city_path)) as reader:
                    response = reader.city(ip_address)
                    maxmind_city = response.city.name
                    maxmind_state = response.subdivisions.most_specific.name
                    maxmind_country = response.country.name
                    maxmind_timezone = response.location.time_zone
                    maxmind_postal = response.postal.code
                    maxmind_latitude = response.location.latitude
                    maxmind_longitude = response.location.longitude
                    maxmind_confidence = 55 + (10 if maxmind_city else 0) + (8 if maxmind_state else 0) + (5 if maxmind_country else 0)
        except (AddressNotFoundError, InvalidDatabaseError, ValueError, OSError):
            pass

        try:
            if self.asn_available:
                with geoip2.database.Reader(str(self.asn_path)) as reader:
                    response = reader.asn(ip_address)
                    asn = response.autonomous_system_number
                    organization = response.autonomous_system_organization
                    maxmind_confidence += 5 if asn else 0
        except (AddressNotFoundError, InvalidDatabaseError, ValueError, OSError):
            pass

        import ipaddress
        is_public = False
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            is_public = not ip_obj.is_private and not ip_obj.is_loopback
        except ValueError:
            pass

        maxmind_candidate = {
            "city": normalize_location_name(maxmind_city),
            "state": normalize_location_name(maxmind_state),
            "country": normalize_location_name(maxmind_country),
            "city_raw": maxmind_city,
            "state_raw": maxmind_state,
            "country_raw": maxmind_country,
            "timezone": maxmind_timezone,
            "postal_code": maxmind_postal,
            "latitude": maxmind_latitude,
            "longitude": maxmind_longitude,
        }

        ip_api_candidate = None
        ipwhois_candidate = None

        if settings.use_external_geoip_api and is_public:
            import httpx
            import concurrent.futures

            def fetch_ip_api():
                try:
                    url = f"http://ip-api.com/json/{ip_address}"
                    resp = httpx.get(url, timeout=3.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("status") == "success":
                            return data
                except Exception as e:
                    logger.warning("[GEOLOCATION] ip-api lookup failed: %s", str(e))
                return None

            def fetch_ipwhois():
                try:
                    url = f"http://ipwho.is/{ip_address}"
                    resp = httpx.get(url, timeout=3.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("success") is True:
                            return data
                except Exception as e:
                    logger.warning("[GEOLOCATION] ipwho.is lookup failed: %s", str(e))
                return None

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future_ip_api = executor.submit(fetch_ip_api)
                future_ipwhois = executor.submit(fetch_ipwhois)

                concurrent.futures.wait([future_ip_api, future_ipwhois], timeout=3.5)

                try:
                    ip_api_data = future_ip_api.result(timeout=0)
                except Exception:
                    ip_api_data = None

                try:
                    ipwhois_data = future_ipwhois.result(timeout=0)
                except Exception:
                    ipwhois_data = None

            if ip_api_data:
                # Extract ASN and ISP if not already resolved
                as_field = ip_api_data.get("as", "")
                if as_field and not asn:
                    parts = as_field.split(" ", 1)
                    if parts[0].upper().startswith("AS") and parts[0][2:].isdigit():
                        asn = int(parts[0][2:])
                if ip_api_data.get("org") and not organization:
                    organization = ip_api_data.get("org")
                elif ip_api_data.get("isp") and not organization:
                    organization = ip_api_data.get("isp")

                ip_api_candidate = {
                    "city": normalize_location_name(ip_api_data.get("city")),
                    "state": normalize_location_name(ip_api_data.get("regionName")),
                    "country": normalize_location_name(ip_api_data.get("country")),
                    "city_raw": ip_api_data.get("city"),
                    "state_raw": ip_api_data.get("regionName"),
                    "country_raw": ip_api_data.get("country"),
                    "timezone": ip_api_data.get("timezone"),
                    "postal_code": ip_api_data.get("zip"),
                    "latitude": ip_api_data.get("lat"),
                    "longitude": ip_api_data.get("lon"),
                }

            if ipwhois_data:
                connection = ipwhois_data.get("connection") or {}
                if connection.get("asn") and not asn:
                    asn = connection.get("asn")
                if connection.get("org") and not organization:
                    organization = connection.get("org")
                elif connection.get("isp") and not organization:
                    organization = connection.get("isp")

                tz_data = ipwhois_data.get("timezone") or {}
                tz_id = tz_data.get("id")

                ipwhois_candidate = {
                    "city": normalize_location_name(ipwhois_data.get("city")),
                    "state": normalize_location_name(ipwhois_data.get("region")),
                    "country": normalize_location_name(ipwhois_data.get("country")),
                    "city_raw": ipwhois_data.get("city"),
                    "state_raw": ipwhois_data.get("region"),
                    "country_raw": ipwhois_data.get("country"),
                    "timezone": tz_id,
                    "postal_code": ipwhois_data.get("postal"),
                    "latitude": ipwhois_data.get("latitude"),
                    "longitude": ipwhois_data.get("longitude"),
                }

        # Determine best location and consensus
        candidates = []
        if maxmind_candidate.get("city"):
            candidates.append(("maxmind", maxmind_candidate))
        if ip_api_candidate and ip_api_candidate.get("city"):
            candidates.append(("ip-api", ip_api_candidate))
        if ipwhois_candidate and ipwhois_candidate.get("city"):
            candidates.append(("ipwhois", ipwhois_candidate))

        from collections import Counter
        city_counts = Counter(c["city"].lower() for _, c in candidates)

        consensus_city_lower = None
        for city_lower, count in city_counts.items():
            if count >= 2:
                consensus_city_lower = city_lower
                break

        winner = None
        consensus_verified = False

        if consensus_city_lower:
            consensus_verified = True
            agreed_candidates = [c for _, c in candidates if c["city"].lower() == consensus_city_lower]
            for source in ["ip-api", "maxmind", "ipwhois"]:
                for name, c in candidates:
                    if name == source and c in agreed_candidates:
                        winner = c
                        break
                if winner:
                    break
        else:
            # No consensus, select highest-priority provider that has city
            for source in ["ip-api", "maxmind", "ipwhois"]:
                for name, c in candidates:
                    if name == source:
                        winner = c
                        break
                if winner:
                    break

            # If still no winner, try any candidate with country/state
            if not winner:
                all_candidates = []
                if maxmind_candidate.get("country") or maxmind_candidate.get("state"):
                    all_candidates.append(("maxmind", maxmind_candidate))
                if ip_api_candidate and (ip_api_candidate.get("country") or ip_api_candidate.get("state")):
                    all_candidates.append(("ip-api", ip_api_candidate))
                if ipwhois_candidate and (ipwhois_candidate.get("country") or ipwhois_candidate.get("state")):
                    all_candidates.append(("ipwhois", ipwhois_candidate))

                for source in ["ip-api", "maxmind", "ipwhois"]:
                    for name, c in all_candidates:
                        if name == source:
                            winner = c
                            break
                    if winner:
                        break

        if not winner:
            winner = maxmind_candidate

        # Determine confidence
        if consensus_verified:
            confidence = 90
        elif winner == ip_api_candidate:
            confidence = 88
        elif winner == ipwhois_candidate:
            confidence = 80
        else:
            confidence = maxmind_confidence

        city = winner.get("city")
        state = winner.get("state")
        country = winner.get("country")
        city_raw = winner.get("city_raw")
        state_raw = winner.get("state_raw")
        country_raw = winner.get("country_raw")
        timezone = winner.get("timezone")
        postal_code = winner.get("postal_code")
        latitude = winner.get("latitude")
        longitude = winner.get("longitude")

        logger.info(
            "[GEOLOCATION] GeoIP consensus: verified=%s, winner_source=%s, city=%s, postal_code=%s, lat=%s, lon=%s",
            consensus_verified,
            "ip-api" if winner == ip_api_candidate else ("ipwhois" if winner == ipwhois_candidate else "maxmind"),
            city,
            postal_code,
            latitude,
            longitude
        )

        return GeoResult(
            city=city,
            state=state,
            country=country,
            city_raw=city_raw,
            state_raw=state_raw,
            country_raw=country_raw,
            geo_timezone=timezone,
            asn=asn,
            organization=organization,
            network_type=classify_network(organization, asn),
            base_confidence=min(confidence, 90),
            postal_code=postal_code,
            consensus_verified=consensus_verified,
            latitude=latitude,
            longitude=longitude,
        )


geoip_service = GeoIPService()
