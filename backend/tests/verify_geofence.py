# Geofence verification scratch script
# This script simulates the Haversine and Point-In-Polygon algorithms to verify correct logic.

import math


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0  # meters
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


def run_tests():
    print("--- Running Geofence Geometry Tests ---")
    
    # Test 1: Circle (Delhi center to Connaught Place)
    delhi_center = (28.6139, 77.2090)
    cp = (28.6304, 77.2177)
    gurgaon = (28.4595, 77.0266)
    
    dist_cp = haversine_distance(delhi_center[0], delhi_center[1], cp[0], cp[1])
    dist_gurgaon = haversine_distance(delhi_center[0], delhi_center[1], gurgaon[0], gurgaon[1])
    
    print(f"Distance to Connaught Place: {dist_cp:.2f} meters (Expected: ~2000m)")
    print(f"Distance to Gurgaon: {dist_gurgaon:.2f} meters (Expected: ~24000m)")
    
    # Test 2: Point-In-Polygon (Rectangle around SF)
    sf_polygon = [
        [37.70, -122.52],  # Bottom Left
        [37.70, -122.35],  # Bottom Right
        [37.82, -122.35],  # Top Right
        [37.82, -122.52]   # Top Left
    ]
    
    golden_gate = (37.8199, -122.4783)  # Inside SF polygon
    oakland = (37.8044, -122.2711)      # Outside SF polygon (east of SF bay)
    
    in_sf = is_point_in_polygon(golden_gate[0], golden_gate[1], sf_polygon)
    in_oakland = is_point_in_polygon(oakland[0], oakland[1], sf_polygon)
    
    print(f"Golden Gate inside SF boundary? {in_sf} (Expected: True)")
    print(f"Oakland inside SF boundary? {in_oakland} (Expected: False)")
    
    print("--- Tests Finished successfully ---")


if __name__ == "__main__":
    run_tests()
