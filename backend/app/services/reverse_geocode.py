import logging
from dataclasses import dataclass

import httpx

from app.config import settings
from app.services.geoip import normalize_location_name

logger = logging.getLogger("visitor_analytics.tracker")


@dataclass(frozen=True)
class ReverseGeocodeResult:
    city: str | None = None
    state: str | None = None
    country: str | None = None
    raw_city: str | None = None
    raw_state: str | None = None
    raw_country: str | None = None
    source_detail: str = "reverse_geocoder_unavailable"


def reverse_geocode(latitude: float, longitude: float) -> ReverseGeocodeResult:
    if not settings.reverse_geocoding_enabled:
        return ReverseGeocodeResult(source_detail="reverse_geocoding_disabled")
    try:
        response = httpx.get(
            settings.reverse_geocoding_url,
            params={
                "format": "jsonv2",
                "lat": f"{latitude:.6f}",
                "lon": f"{longitude:.6f}",
                "zoom": "10",
                "addressdetails": "1",
            },
            headers={"User-Agent": settings.reverse_geocoding_user_agent},
            timeout=4.0,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.warning("[GEOLOCATION] Nominatim geocoding failed: %s. Trying BigDataCloud fallback...", str(e))
        try:
            fallback_response = httpx.get(
                "https://api.bigdatacloud.net/data/reverse-geocode-client",
                params={
                    "latitude": f"{latitude:.6f}",
                    "longitude": f"{longitude:.6f}",
                    "localityLanguage": "en",
                },
                timeout=4.0,
            )
            fallback_response.raise_for_status()
            data = fallback_response.json()
            
            raw_city = data.get("city") or data.get("locality") or data.get("principalSubdivisionWithoutSuffix")
            raw_state = data.get("principalSubdivision")
            raw_country = data.get("countryName")
            
            if raw_city or raw_state or raw_country:
                logger.info("[GEOLOCATION] BigDataCloud fallback reverse geocode succeeded.")
                return ReverseGeocodeResult(
                    city=normalize_location_name(raw_city),
                    state=normalize_location_name(raw_state),
                    country=normalize_location_name(raw_country),
                    raw_city=raw_city,
                    raw_state=raw_state,
                    raw_country=raw_country,
                    source_detail="bigdatacloud_fallback_reverse_geocode",
                )
        except Exception as fe:
            logger.error("[GEOLOCATION] BigDataCloud fallback also failed: %s", str(fe), exc_info=True)
        return ReverseGeocodeResult()

    address = data.get("address") if isinstance(data, dict) else None
    if not isinstance(address, dict):
        return ReverseGeocodeResult(source_detail="reverse_geocoder_missing_address")

    raw_city = (
        address.get("city")
        or address.get("town")
        or address.get("municipality")
        or address.get("village")
        or address.get("county")
    )
    raw_state = address.get("state") or address.get("region") or address.get("state_district")
    raw_country = address.get("country")
    return ReverseGeocodeResult(
        city=normalize_location_name(raw_city),
        state=normalize_location_name(raw_state),
        country=normalize_location_name(raw_country),
        raw_city=raw_city,
        raw_state=raw_state,
        raw_country=raw_country,
        source_detail="nominatim_reverse_geocode",
    )
