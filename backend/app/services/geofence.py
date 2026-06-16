import math
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Geofence


CITY_ALIASES = {
    "hubli": {"hubballi", "hubli-dharwad", "hubli dharwad"},
    "hubballi": {"hubli", "hubli-dharwad", "hubli dharwad"},
    "bangalore": {"bengaluru"},
    "bengaluru": {"bangalore"},
    "mumbai": {"bombay"},
    "bombay": {"mumbai"},
    "chennai": {"madras"},
    "madras": {"chennai"},
    "kolkata": {"calcutta"},
    "calcutta": {"kolkata"},
    "pune": {"poona"},
    "poona": {"pune"},
    "kochi": {"cochin"},
    "cochin": {"kochi"},
    "mysore": {"mysuru"},
    "mysuru": {"mysore"},
    "belgaum": {"belagavi"},
    "belagavi": {"belgaum"},
    "mangalore": {"mangaluru"},
    "mangaluru": {"mangalore"},
    "gurgaon": {"gurugram"},
    "gurugram": {"gurgaon"},
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees) in meters.
    """
    R = 6371000.0  # Radius of earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def is_point_in_polygon(lat: float, lon: float, vertices: list[list[float]]) -> bool:
    """
    Point-in-Polygon (PIP) ray casting algorithm.
    vertices is a list of [latitude, longitude] pairs.
    """
    n = len(vertices)
    if n < 3:
        return False

    inside = False
    p1lat, p1lon = vertices[0]
    for i in range(1, n + 1):
        p2lat, p2lon = vertices[i % n]
        if lat > min(p1lat, p2lat):
            if lat <= max(p1lat, p2lat):
                if lon <= max(p1lon, p2lon):
                    if p1lat != p2lat:
                        xints = (lat - p1lat) * (p2lon - p1lon) / (p2lat - p1lat) + p1lon
                    if p1lon == p2lon or lon <= xints:
                        inside = not inside
        p1lat, p1lon = p2lat, p2lon

    return inside


def check_geofences(latitude: float, longitude: float, db: Session, city: str | None = None) -> list[str]:
    """
    Check all active geofences in the database.
    Returns a list of names of the matched geofences.
    """
    matched_names = []
    try:
        stmt = select(Geofence).where(Geofence.is_active == True)
        geofences = db.scalars(stmt).all()

        for gf in geofences:
            # 1. Match by city name if available (case-insensitive fallback with aliases)
            if city and gf.name:
                c_clean = city.strip().lower()
                g_clean = gf.name.strip().lower()
                
                c_aliases = {c_clean}
                if c_clean in CITY_ALIASES:
                    c_aliases.update(CITY_ALIASES[c_clean])
                g_aliases = {g_clean}
                if g_clean in CITY_ALIASES:
                    g_aliases.update(CITY_ALIASES[g_clean])
                
                is_match = False
                for ca in c_aliases:
                    for ga in g_aliases:
                        if ca == ga or ca in ga or ga in ca:
                            is_match = True
                            break
                    if is_match:
                        break
                        
                if is_match:
                    matched_names.append(gf.name)
                    continue

            # 2. Match by coordinates
            if gf.type == "circle":
                if gf.center_latitude is not None and gf.center_longitude is not None and gf.radius_meters is not None:
                    dist = haversine_distance(latitude, longitude, gf.center_latitude, gf.center_longitude)
                    if dist <= gf.radius_meters:
                        matched_names.append(gf.name)
            elif gf.type == "polygon":
                if gf.coordinates:
                    # coordinates is a list of [lat, lon] pairs
                    if is_point_in_polygon(latitude, longitude, gf.coordinates):
                        matched_names.append(gf.name)
    except Exception as e:
        import logging
        logger = logging.getLogger("visitor_analytics.geofence")
        logger.error("[GEOFENCE] Error evaluating geofences: %s", str(e), exc_info=True)

    return matched_names
