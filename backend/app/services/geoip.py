from dataclasses import dataclass
from pathlib import Path

import geoip2.database
from geoip2.errors import AddressNotFoundError
from maxminddb.errors import InvalidDatabaseError

from app.config import settings


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
        city_raw = state_raw = country_raw = timezone = organization = None
        asn = None
        confidence = 0
        try:
            if self.city_available:
                with geoip2.database.Reader(str(self.city_path)) as reader:
                    response = reader.city(ip_address)
                    city_raw = response.city.name
                    state_raw = response.subdivisions.most_specific.name
                    country_raw = response.country.name
                    timezone = response.location.time_zone
                    confidence = 55 + (10 if city_raw else 0) + (8 if state_raw else 0) + (5 if country_raw else 0)
        except (AddressNotFoundError, InvalidDatabaseError, ValueError, OSError):
            pass
        try:
            if self.asn_available:
                with geoip2.database.Reader(str(self.asn_path)) as reader:
                    response = reader.asn(ip_address)
                    asn = response.autonomous_system_number
                    organization = response.autonomous_system_organization
                    confidence += 5 if asn else 0
        except (AddressNotFoundError, InvalidDatabaseError, ValueError, OSError):
            pass

        # Fallback/Override using ip-api.com for public IPs (high city accuracy in India)
        import ipaddress
        is_public = False
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            is_public = not ip_obj.is_private and not ip_obj.is_loopback
        except ValueError:
            pass

        if settings.use_external_geoip_api and is_public:
            try:
                import httpx
                import logging
                logger = logging.getLogger("visitor_analytics.tracker")
                url = f"http://ip-api.com/json/{ip_address}"
                resp = httpx.get(url, timeout=3.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "success":
                        city_raw = data.get("city")
                        state_raw = data.get("regionName")
                        country_raw = data.get("country")
                        timezone = data.get("timezone")
                        
                        as_field = data.get("as", "")
                        if as_field and not asn:
                            parts = as_field.split(" ", 1)
                            if parts[0].upper().startswith("AS") and parts[0][2:].isdigit():
                                asn = int(parts[0][2:])
                        if data.get("org") and not organization:
                            organization = data.get("org")
                        elif data.get("isp") and not organization:
                            organization = data.get("isp")
                        
                        confidence = 88
                        logger.info("[GEOLOCATION] ip-api.com lookup succeeded for IP %s: %s, %s, %s", 
                                    ip_address, city_raw, state_raw, country_raw)
            except Exception as e:
                import logging
                logger = logging.getLogger("visitor_analytics.tracker")
                logger.error("[GEOLOCATION] ip-api.com lookup failed: %s", str(e), exc_info=True)

        city = normalize_location_name(city_raw)
        state = normalize_location_name(state_raw)
        country = normalize_location_name(country_raw)
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
        )


geoip_service = GeoIPService()
