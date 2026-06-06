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
    geo_timezone: str | None = None
    asn: int | None = None
    organization: str | None = None
    network_type: str = "Unknown"
    base_confidence: int = 0


HOSTING_MARKERS = {
    "amazon", "aws", "azure", "cloudflare", "digitalocean", "google cloud",
    "hetzner", "hosting", "linode", "microsoft", "ovh", "vultr", "server",
}
MOBILE_MARKERS = {
    "airtel", "cellular", "jio", "mobile", "telefonica", "t-mobile",
    "verizon wireless", "vodafone",
}
CORPORATE_MARKERS = {"corporation", "corp.", "university", "college", "bank", "government"}
VPN_MARKERS = {"vpn", "proxy", "privacy", "anonymous"}


def classify_network(organization: str | None) -> str:
    value = (organization or "").lower()
    if any(marker in value for marker in VPN_MARKERS):
        return "VPN Candidate"
    if any(marker in value for marker in HOSTING_MARKERS):
        return "Hosting Provider"
    if any(marker in value for marker in MOBILE_MARKERS):
        return "Mobile Carrier"
    if any(marker in value for marker in CORPORATE_MARKERS):
        return "Corporate Network"
    return "Residential ISP" if value else "Unknown"


class GeoIPService:
    def __init__(self, city_path: str | None = None, asn_path: str | None = None) -> None:
        self.city_path = Path(city_path or settings.geoip_city_db)
        self.asn_path = Path(asn_path or settings.geoip_asn_db)

    @property
    def city_available(self) -> bool:
        return self.city_path.is_file()

    @property
    def asn_available(self) -> bool:
        return self.asn_path.is_file()

    def lookup(self, ip_address: str) -> GeoResult:
        city = state = country = timezone = organization = None
        asn = None
        confidence = 0
        try:
            if self.city_available:
                with geoip2.database.Reader(str(self.city_path)) as reader:
                    response = reader.city(ip_address)
                    city = response.city.name
                    state = response.subdivisions.most_specific.name
                    country = response.country.name
                    timezone = response.location.time_zone
                    confidence = 55 + (10 if city else 0) + (8 if state else 0) + (5 if country else 0)
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
        return GeoResult(
            city=city,
            state=state,
            country=country,
            geo_timezone=timezone,
            asn=asn,
            organization=organization,
            network_type=classify_network(organization),
            base_confidence=min(confidence, 85),
        )


geoip_service = GeoIPService()
