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
            network_type="Residential Broadband",
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
    first = client.post("/api/v1/sync", json=payload, headers=headers)
    second = client.post("/api/v1/sync", json=payload, headers=headers)
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
    assert summary.json()["top_country"] == "India"
    visitors = client.get("/api/v1/analytics/visitors?returning=true&sort=most_visits")
    assert visitors.json()["meta"]["total"] == 1
    assert visitors.json()["items"][0]["confidence_score"] >= 75
    assert visitors.json()["items"][0]["current_isp"] == "Example Broadband"
    timeline = client.get("/api/v1/analytics/visits")
    assert len(timeline.json()["items"]) == 2
    assert timeline.json()["items"][0]["location_source"] == "Hybrid Inference"
    assert timeline.json()["items"][0]["network_type"] == "Residential Broadband"
    assert timeline.json()["items"][0]["asn"] == 123
    assert client.get("/api/v1/analytics/locations/country").json()[0]["name"] == "India"
    assert client.get("/api/v1/analytics/locations/isp").json()[0]["name"] == "Example Broadband"
    assert client.get("/api/v1/analytics/locations/asn").json()[0]["name"] == "123"
    assert client.get("/api/v1/analytics/locations/network_type").json()[0]["name"] == "Residential Broadband"
    assert client.get("/api/v1/analytics/locations/location_source").json()[0]["name"] == "Hybrid Inference"
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
    assert client.get("/api/v1/analytics/visits?device_type=Mobile&min_confidence=50&country=India").status_code == 200
    health = client.get("/api/v1/system/health")
    assert health.status_code == 200
    assert health.json()["database_status"] == "available"
    fallback = client.get("/api/v1/fallback", headers=headers, follow_redirects=False)
    assert fallback.status_code == 303
    assert fallback.headers["location"].startswith("https://")


def test_known_crawler_is_separated_from_primary_analytics(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.tracking.geoip_service.lookup",
        lambda _ip: GeoResult(city="Menlo Park", state="California", country="United States"),
    )
    response = client.post("/api/v1/sync", json={}, headers={"user-agent": "facebookexternalhit/1.1"})
    assert response.status_code == 200
    assert response.json()["location_update_token"] is None

    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct-horse-battery"},
    )
    summary = client.get("/api/v1/analytics/summary").json()
    assert summary["total_visits"] == 0
    assert summary["crawler_visits"] == 1
    assert client.get("/api/v1/analytics/visits").json()["meta"]["total"] == 0
    crawlers = client.get("/api/v1/analytics/crawlers").json()
    assert crawlers[0]["crawler_type"] == "Social Media Crawler"
    assert crawlers[0]["visits"] == 1


def test_tracking_page_has_strict_privacy_headers(client):
    response = client.get("/go")
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "geolocation=(self)" in response.headers["permissions-policy"]
    assert "Share location, then continue" in response.text


def test_instagram_webview_is_not_redirected_and_not_crawler(client, monkeypatch):
    from app.services.geoip import GeoResult
    # 1. Instagram WebView User-Agent should NOT be immediately redirected on /go
    insta_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 172.0.0.22.121"
    response = client.get("/go", headers={"user-agent": insta_ua})
    assert response.status_code == 200
    assert "Share location, then continue" in response.text

    # 2. Instagram WebView User-Agent sync should be classified as a standard visitor, not a crawler
    monkeypatch.setattr(
        "app.api.tracking.geoip_service.lookup",
        lambda _ip: GeoResult(
            city="Bengaluru", 
            state="Karnataka", 
            country="India",
            geo_timezone="Asia/Kolkata",
            asn=55836,
            organization="Reliance Jio",
            network_type="Mobile Carrier",
            base_confidence=80
        ),
    )
    
    sync_res = client.post(
        "/api/v1/sync",
        json={
            "timezone": "Asia/Kolkata",
            "canvas_hash": "insta_canvas",
            "webgl_hash": "insta_webgl",
            "nonce": "some_nonce_for_insta",
        },
        headers={"user-agent": insta_ua}
    )
    assert sync_res.status_code == 200
    
    # Authenticate to check analytics
    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct-horse-battery"},
    )
    
    summary = client.get("/api/v1/analytics/summary").json()
    assert summary["total_visits"] == 1
    assert summary["crawler_visits"] == 0
    
    visits = client.get("/api/v1/analytics/visits").json()
    assert visits["meta"]["total"] == 1


def test_known_crawler_is_immediately_redirected_on_go(client):
    response = client.get(
        "/go", 
        headers={"user-agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_patched.html)"}, 
        follow_redirects=False
    )
    assert response.status_code == 307
    assert response.headers["location"].startswith("https://")


def test_validation_is_bounded(client):
    response = client.post("/api/v1/sync", json={"timezone": "x" * 81})
    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid request"


def test_admin_endpoints_require_auth(client):
    assert client.get("/api/v1/analytics/summary").status_code == 401
    assert client.get("/api/v1/system/health").status_code == 401


def test_system_config_and_geoip_endpoints(client):
    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct-horse-battery"},
    )
    
    health = client.get("/api/v1/system/health")
    assert health.status_code == 200
    assert "redirect_target_url" in health.json()
    original_url = health.json()["redirect_target_url"]
    
    new_url = "https://news.ycombinator.com/news"
    update_res = client.post(
        "/api/v1/system/config/redirect",
        json={"redirect_target_url": new_url}
    )
    assert update_res.status_code == 200
    assert update_res.json()["redirect_target_url"] == new_url
    
    health2 = client.get("/api/v1/system/health")
    assert health2.json()["redirect_target_url"] == new_url
    
    restore_res = client.post(
        "/api/v1/system/config/redirect",
        json={"redirect_target_url": original_url}
    )
    assert restore_res.status_code == 200
    
    geoip_res = client.post("/api/v1/system/geoip/update")
    assert geoip_res.status_code == 200
    assert geoip_res.json()["success"] is True


def test_ua_ch_and_hardware_classification_overrides(client, monkeypatch):
    # Mock lookup to return "Unknown" so heuristics determine classification
    monkeypatch.setattr(
        "app.api.tracking.geoip_service.lookup",
        lambda _ip: GeoResult(
            city="Mumbai",
            state="Maharashtra",
            country="India",
            geo_timezone="Asia/Kolkata",
            asn=55836,
            organization="Reliance Jio",
            network_type="Unknown",
            base_confidence=70,
        ),
    )

    # Login first so we can read back analytics easily
    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct-horse-battery"},
    )

    headers_mobile = {"user-agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"}

    # 1. Private IP present -> Residential Broadband
    payload_private_ip = {
        "timezone": "Asia/Kolkata",
        "ua_platform": "Android",
        "ua_mobile": True,
        "has_private_ip": True,
    }
    res1 = client.post("/api/v1/sync", json=payload_private_ip, headers=headers_mobile)
    assert res1.status_code == 200

    # 2. Data saver enabled on Mobile -> Mobile Carrier
    payload_data_saver = {
        "timezone": "Asia/Kolkata",
        "ua_platform": "Android",
        "ua_mobile": True,
        "save_data": True,
    }
    res2 = client.post("/api/v1/sync", json=payload_data_saver, headers=headers_mobile)
    assert res2.status_code == 200

    # 3. Stable low jitter and low RTT -> Residential Broadband
    payload_low_jitter = {
        "timezone": "Asia/Kolkata",
        "ua_platform": "Android",
        "ua_mobile": True,
        "ping_jitter": 5.0,
        "rtt": 40,
    }
    res3 = client.post("/api/v1/sync", json=payload_low_jitter, headers=headers_mobile)
    assert res3.status_code == 200

    # 4. High jitter on mobile -> Mobile Carrier
    payload_high_jitter = {
        "timezone": "Asia/Kolkata",
        "ua_platform": "Android",
        "ua_mobile": True,
        "ping_jitter": 50.0,
    }
    res4 = client.post("/api/v1/sync", json=payload_high_jitter, headers=headers_mobile)
    assert res4.status_code == 200

    # Retrieve visits and assert the overrides
    visits = client.get("/api/v1/analytics/visits").json()["items"]
    
    # Chronology is newest first: [high_jitter, low_jitter, data_saver, private_ip]
    assert visits[0]["network_type"] == "Mobile Carrier"       # High jitter
    assert visits[1]["network_type"] == "Residential Broadband" # Low jitter/RTT
    assert visits[2]["network_type"] == "Mobile Carrier"       # Data saver
    assert visits[3]["network_type"] == "Residential Broadband" # Private IP


def test_integrity_and_spoof_detection(client, monkeypatch):
    # Mock lookup
    monkeypatch.setattr(
        "app.api.tracking.geoip_service.lookup",
        lambda _ip: GeoResult(
            city="Mumbai",
            state="Maharashtra",
            country="India",
            geo_timezone="Asia/Kolkata",
            asn=55836,
            organization="Reliance Jio",
            network_type="Residential Broadband",
            base_confidence=70,
        ),
    )

    # Login to retrieve visits
    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct-horse-battery"},
    )

    # 1. Test Headless software GPU
    res1 = client.post(
        "/api/v1/sync",
        json={
            "timezone": "Asia/Kolkata",
            "gpu": "Google SwiftShader (Google)",
        },
        headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    assert res1.status_code == 200

    # 2. Test GPU OS Mismatch (Intel GPU on iOS - reports as Apple OS but non-Apple GPU in emulator)
    res2 = client.post(
        "/api/v1/sync",
        json={
            "timezone": "Asia/Kolkata",
            "gpu": "Intel(R) Iris(TM) Plus Graphics",
            "ua_platform": "iOS",
            "ua_mobile": True,
        },
        headers={"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15"}
    )
    assert res2.status_code == 200

    # 3. Test iOS Memory Leak
    res3 = client.post(
        "/api/v1/sync",
        json={
            "timezone": "Asia/Kolkata",
            "ua_platform": "iOS",
            "ua_mobile": True,
            "memory": 4, # iOS Safari does not expose memory
        },
        headers={"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15"}
    )
    assert res3.status_code == 200

    # 4. Test Suspicious hardware capacity (mobile with 16 cores)
    res4 = client.post(
        "/api/v1/sync",
        json={
            "timezone": "Asia/Kolkata",
            "ua_platform": "Android",
            "ua_mobile": True,
            "cores": 16, # Mobile shouldn't have 16 cores
        },
        headers={"user-agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"}
    )
    assert res4.status_code == 200

    visits = client.get("/api/v1/analytics/visits").json()["items"]
    # Chronology is newest first: [suspicious_hardware, ios_memory_leak, gpu_os_mismatch, headless_software_gpu]
    
    # 4. Mobile 16 cores
    assert visits[0]["is_anomalous"] is True
    assert "suspicious_hardware_capacity" in visits[0]["anomaly_reasons"]

    # 3. iOS memory leak
    assert visits[1]["is_anomalous"] is True
    assert "ios_memory_leak" in visits[1]["anomaly_reasons"]

    # 2. GPU OS Mismatch (Intel GPU on iOS)
    assert visits[2]["is_anomalous"] is True
    assert "gpu_os_mismatch" in visits[2]["anomaly_reasons"]

    # 1. Headless software GPU
    assert visits[3]["is_anomalous"] is True
    assert "headless_software_gpu" in visits[3]["anomaly_reasons"]


def test_canvas_webgl_fingerprint_and_honeypot(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.tracking.geoip_service.lookup",
        lambda _ip: GeoResult(
            city="Mumbai",
            state="Maharashtra",
            country="India",
            geo_timezone="Asia/Kolkata",
            asn=55836,
            organization="Reliance Jio",
            network_type="Residential Broadband",
            base_confidence=70,
        ),
    )

    # 1. Login to retrieve visits later
    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct-horse-battery"},
    )

    # 2. Trigger Honeypot BEFORE sync
    test_nonce_1 = "test_nonce_1"
    honeypot_res = client.get(f"/api/v1/honeypot?v={test_nonce_1}", follow_redirects=False)
    assert honeypot_res.status_code == 307
    assert honeypot_res.headers["location"].startswith("https://")

    # 3. POST sync with test_nonce_1 and canvas/webgl hashes
    sync_res_1 = client.post(
        "/api/v1/sync",
        json={
            "timezone": "Asia/Kolkata",
            "canvas_hash": "a1b2c3d4e5f6g7h8",
            "webgl_hash": "h8g7f6e5d4c3b2a1",
            "nonce": test_nonce_1,
        },
        headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    assert sync_res_1.status_code == 200

    # 4. POST sync for a second visit (test_nonce_2) without honeypot yet
    test_nonce_2 = "test_nonce_2"
    sync_res_2 = client.post(
        "/api/v1/sync",
        json={
            "timezone": "Asia/Kolkata",
            "canvas_hash": "canvas_ok",
            "webgl_hash": "webgl_ok",
            "nonce": test_nonce_2,
        },
        headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    assert sync_res_2.status_code == 200

    # 5. Trigger Honeypot AFTER sync for test_nonce_2
    honeypot_res_2 = client.get(f"/api/v1/honeypot?v={test_nonce_2}", follow_redirects=False)
    assert honeypot_res_2.status_code == 307

    # 6. Retrieve visits and assert fingerprints and honeypot triggers
    visits = client.get("/api/v1/analytics/visits").json()["items"]
    # Chronology is newest first: [test_nonce_2, test_nonce_1]
    
    # Check test_nonce_2 (honeypot triggered after sync)
    assert visits[0]["canvas_hash"] == "canvas_ok"
    assert visits[0]["webgl_hash"] == "webgl_ok"
    assert visits[0]["is_anomalous"] is True
    assert "honeypot_triggered" in visits[0]["anomaly_reasons"]

    # Check test_nonce_1 (honeypot triggered before sync)
    assert visits[1]["canvas_hash"] == "a1b2c3d4e5f6g7h8"
    assert visits[1]["webgl_hash"] == "h8g7f6e5d4c3b2a1"
    assert visits[1]["is_anomalous"] is True
    assert "honeypot_triggered" in visits[1]["anomaly_reasons"]

    # 7. Check anomaly trigger for missing/blank canvas/webgl hashes on desktop
    res_missing = client.post(
        "/api/v1/sync",
        json={
            "timezone": "Asia/Kolkata",
            "canvas_hash": "blank",
            "webgl_hash": "blocked",
        },
        headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    assert res_missing.status_code == 200
    
    visits_updated = client.get("/api/v1/analytics/visits").json()["items"]
    assert visits_updated[0]["is_anomalous"] is True
    assert "missing_canvas_fingerprint" in visits_updated[0]["anomaly_reasons"]
    assert "missing_webgl_fingerprint" in visits_updated[0]["anomaly_reasons"]


def test_new_heuristics(client, monkeypatch):
    # Mock GeoIP lookup
    monkeypatch.setattr(
        "app.api.tracking.geoip_service.lookup",
        lambda _ip: GeoResult(
            city="Mumbai",
            state="Maharashtra",
            country="India",
            geo_timezone="Asia/Kolkata",
            asn=55836,
            organization="Reliance Jio",
            network_type="Residential Broadband",
            base_confidence=70,
        ),
    )

    # 1. Test rDNS parsing: Mock get_rdns_hostname to return a name containing "bengaluru"
    monkeypatch.setattr(
        "app.services.integrity.get_rdns_hostname",
        lambda ip, timeout=1.0: "node-bengaluru-isp.net"
    )

    # Login to read visits
    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct-horse-battery"},
    )

    # Trigger a sync with Bengaluru rDNS match
    res_rdns = client.post(
        "/api/v1/sync",
        json={
            "timezone": "Asia/Kolkata",
            "canvas_hash": "canvas_rdns",
            "webgl_hash": "webgl_rdns",
        },
        headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    assert res_rdns.status_code == 200

    visits = client.get("/api/v1/analytics/visits").json()["items"]
    # The winner should be Bengaluru from Reverse DNS Parsing rather than Mumbai (due to cellular carrier penalty on Mumbai)
    assert visits[0]["city"] == "Bengaluru"
    assert "Reverse DNS Parsing" in visits[0]["location_source"]

    # 2. Test Timezone & Locale Cross-Checking
    # Case A: Timezone mismatch (client in Europe/Berlin, IP is in India)
    res_tz = client.post(
        "/api/v1/sync",
        json={
            "timezone": "Europe/Berlin",
            "canvas_hash": "canvas_tz",
            "webgl_hash": "webgl_tz",
        },
        headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    assert res_tz.status_code == 200

    # Case B: Locale mismatch (client language is German/de-DE, IP is in India)
    res_locale = client.post(
        "/api/v1/sync",
        json={
            "timezone": "Asia/Kolkata",
            "language": "de-DE",
            "accept_language": "de-DE,de;q=0.9",
            "canvas_hash": "canvas_locale",
            "webgl_hash": "webgl_locale",
        },
        headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    assert res_locale.status_code == 200

    visits = client.get("/api/v1/analytics/visits").json()["items"]
    # visits[0] is locale mismatch (newest first)
    assert "locale_mismatch" in visits[0]["anomaly_reasons"]
    # visits[1] is timezone mismatch
    assert "timezone_mismatch" in visits[1]["anomaly_reasons"]

    # 3. Test Device Fingerprint Collision (Proxy Detection)
    # Perform 3 sync requests from 3 different IPs with the same fingerprint
    payload_fingerprint = {
        "timezone": "Asia/Kolkata",
        "canvas_hash": "collision_canvas",
        "webgl_hash": "collision_webgl",
        "screen_resolution": "1080x2400",
        "cores": 8,
        "memory": 8,
        "language": "en-IN",
    }
    
    # Request 1: IP 1.1.1.1
    res_coll1 = client.post(
        "/api/v1/sync",
        json=payload_fingerprint,
        headers={
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "cf-connecting-ip": "1.1.1.1"
        }
    )
    assert res_coll1.status_code == 200

    # Request 2: IP 2.2.2.2
    res_coll2 = client.post(
        "/api/v1/sync",
        json=payload_fingerprint,
        headers={
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "cf-connecting-ip": "2.2.2.2"
        }
    )
    assert res_coll2.status_code == 200

    # Request 3: IP 3.3.3.3
    res_coll3 = client.post(
        "/api/v1/sync",
        json=payload_fingerprint,
        headers={
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "cf-connecting-ip": "3.3.3.3"
        }
    )
    assert res_coll3.status_code == 200

    visits = client.get("/api/v1/analytics/visits").json()["items"]
    # visits[0] is the 3rd request (newest first)
    assert "device_collision_detected" in visits[0]["anomaly_reasons"]
    # visits[1] (2nd request) and visits[2] (1st request) should not have the collision flag
    if visits[1]["anomaly_reasons"]:
        assert "device_collision_detected" not in visits[1]["anomaly_reasons"]
    if visits[2]["anomaly_reasons"]:
        assert "device_collision_detected" not in visits[2]["anomaly_reasons"]


def test_latency_fallback_as_last_resort(client, monkeypatch):
    # Mock GeoIP lookup to return a Jio mobile carrier in Mumbai
    # Because of cellular gateway penalty (and mobile carrier type), this will drop confidence under 50.
    monkeypatch.setattr(
        "app.api.tracking.geoip_service.lookup",
        lambda _ip: GeoResult(
            city="Mumbai",
            state="Maharashtra",
            country="India",
            geo_timezone="Asia/Kolkata",
            asn=55836,
            organization="Reliance Jio",
            network_type="Mobile Carrier", # triggers mobile carrier reductions
            base_confidence=68,
        ),
    )

    # Mock get_rdns_hostname to return a hostname without any location keywords
    monkeypatch.setattr(
        "app.services.integrity.get_rdns_hostname",
        lambda ip, timeout=1.0: "adsl-static-pool.jio.com"
    )

    # Login first
    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct-horse-battery"},
    )

    # 1. Trigger a sync with latency bangalore ping (default state: enabled)
    res = client.post(
        "/api/v1/sync",
        json={
            "timezone": "Asia/Kolkata",
            "canvas_hash": "canvas_last_resort_enabled",
            "webgl_hash": "webgl_last_resort_enabled",
            "latency_bangalore": 12, # Bengaluru ping
        },
        headers={"user-agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"}
    )
    assert res.status_code == 200

    visits = client.get("/api/v1/analytics/visits").json()["items"]
    # The winner should be Bengaluru from Latency Triangulation
    assert visits[0]["city"] == "Bengaluru"
    assert visits[0]["location_source"] == "Latency Triangulation"

    # 2. Toggle latency triangulation to disabled
    res_toggle = client.post(
        "/api/v1/system/latency/toggle",
        json={"disabled": True}
    )
    assert res_toggle.status_code == 200
    assert res_toggle.json()["disabled"] is True

    # 3. Trigger a sync with latency bangalore ping (state: disabled)
    res_disabled = client.post(
        "/api/v1/sync",
        json={
            "timezone": "Asia/Kolkata",
            "canvas_hash": "canvas_last_resort_disabled",
            "webgl_hash": "webgl_last_resort_disabled",
            "latency_bangalore": 12, # Bengaluru ping (should be ignored)
        },
        headers={"user-agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"}
    )
    assert res_disabled.status_code == 200

    visits_disabled = client.get("/api/v1/analytics/visits").json()["items"]
    # The winner should remain Mumbai (since latency is disabled)
    assert visits_disabled[0]["city"] == "Mumbai"
    assert visits_disabled[0]["location_source"] == "GeoIP DB"

    # 4. Toggle latency triangulation back to enabled
    res_restore = client.post(
        "/api/v1/system/latency/toggle",
        json={"disabled": False}
    )
    assert res_restore.status_code == 200
    assert res_restore.json()["disabled"] is False





