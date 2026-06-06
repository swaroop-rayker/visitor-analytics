from app.services.geoip import GeoResult


def test_authentication_lifecycle(client):
    assert client.get("/api/v1/auth/session").status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct-horse-battery"},
    ).status_code == 200
    assert client.get("/api/v1/auth/session").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/auth/session").status_code == 401


def test_tracking_and_analytics_flow(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.tracking.geoip_service.lookup",
        lambda _ip: GeoResult(
            city="Bengaluru",
            state="Karnataka",
            country="India",
            geo_timezone="Asia/Kolkata",
            asn=123,
            organization="Example Broadband",
            network_type="Residential ISP",
            base_confidence=78,
        ),
    )
    headers = {"user-agent": "Mozilla/5.0 Chrome/120.0", "accept-language": "en-IN"}
    payload = {
        "timezone": "Asia/Kolkata",
        "language": "en-IN",
        "platform": "Android",
        "screen_resolution": "1080x2400",
    }
    first = client.post("/api/v1/track", json=payload, headers=headers)
    second = client.post("/api/v1/track", json=payload, headers=headers)
    assert first.status_code == 200
    assert first.json()["redirect_url"].startswith("https://")
    assert second.status_code == 200

    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct-horse-battery"},
    )
    summary = client.get("/api/v1/analytics/summary")
    assert summary.status_code == 200
    assert summary.json()["total_visits"] == 2
    assert summary.json()["unique_visitors"] == 1
    assert summary.json()["returning_visitors"] == 1
    visitors = client.get("/api/v1/analytics/visitors?returning=true&sort=most_visits")
    assert visitors.json()["meta"]["total"] == 1
    assert visitors.json()["items"][0]["confidence_score"] >= 75
    timeline = client.get("/api/v1/analytics/visits")
    assert len(timeline.json()["items"]) == 2
    locations = client.get("/api/v1/analytics/locations/city")
    assert locations.json()[0]["name"] == "Bengaluru"
    assert client.get("/api/v1/analytics/locations/state").status_code == 200
    for period in ("daily", "weekly", "monthly"):
        trend = client.get(f"/api/v1/analytics/trends?period={period}&days=30")
        assert trend.status_code == 200
        assert trend.json()[0]["visits"] == 2
    retention = client.get("/api/v1/analytics/retention")
    assert retention.status_code == 200
    assert retention.json()[0]["retention_rate"] == 100
    assert client.get("/api/v1/analytics/frequency").json()[1]["visitors"] == 1
    location_trends = client.get("/api/v1/analytics/location-trends")
    assert location_trends.status_code == 200
    assert location_trends.json()[0]["location"] == "Bengaluru"
    assert client.get("/api/v1/analytics/visitors?city=Nowhere").json()["meta"]["total"] == 0
    assert client.get("/api/v1/analytics/visits?device_type=Mobile&min_confidence=50").status_code == 200
    health = client.get("/api/v1/system/health")
    assert health.status_code == 200
    assert health.json()["database_status"] == "available"
    fallback = client.get("/api/v1/track/fallback", headers=headers, follow_redirects=False)
    assert fallback.status_code == 303
    assert fallback.headers["location"].startswith("https://")


def test_tracking_page_has_strict_privacy_headers(client):
    response = client.get("/go")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "geolocation=()" in response.headers["permissions-policy"]


def test_validation_is_bounded(client):
    response = client.post("/api/v1/track", json={"timezone": "x" * 81})
    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid request"


def test_admin_endpoints_require_auth(client):
    assert client.get("/api/v1/analytics/summary").status_code == 401
    assert client.get("/api/v1/system/health").status_code == 401
