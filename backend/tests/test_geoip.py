from app.services.geoip import GeoIPService, classify_network


def test_network_classification_heuristics():
    assert classify_network("Amazon.com Inc.") == "Cloud Provider"
    assert classify_network("Example VPN Services") == "VPN"
    assert classify_network("Airtel Mobile") == "Mobile Carrier"
    assert classify_network("Example University") == "Corporate Network"
    assert classify_network("Neighborhood Broadband") == "Residential Broadband"
    assert classify_network("Bharti Airtel Ltd. (AS9498)", 9498) == "Residential Broadband"
    assert classify_network("Airtel Xstream Fiber") == "Residential Broadband"
    assert classify_network("Reliance Jio Infocomm Limited", 64044) == "Residential Broadband"
    assert classify_network(None) == "Unknown"


def test_missing_databases_degrade_gracefully(tmp_path):
    service = GeoIPService(str(tmp_path / "city.mmdb"), str(tmp_path / "asn.mmdb"))
    result = service.lookup("203.0.113.1")
    assert result.city is None
    assert result.base_confidence == 0
    assert result.network_type == "Unknown"


def test_geoip_consensus_and_postcode_resolution(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "use_external_geoip_api", True)
    monkeypatch.setattr(settings, "disable_maxmind_db", True)
    
    import httpx
    
    class MockResponse:
        def __init__(self, url, json_data, status_code=200):
            self.url = url
            self._json_data = json_data
            self.status_code = status_code
            
        def json(self):
            return self._json_data
            
        def raise_for_status(self):
            pass

    def mock_get(url, *args, **kwargs):
        if "ip-api.com" in url:
            return MockResponse(
                url,
                {
                    "status": "success",
                    "city": "Bengaluru",
                    "regionName": "Karnataka",
                    "country": "India",
                    "timezone": "Asia/Kolkata",
                    "zip": "560001",
                    "as": "AS9498 Bharti Airtel Ltd.",
                    "isp": "Airtel",
                }
            )
        elif "ipwho.is" in url:
            return MockResponse(
                url,
                {
                    "success": True,
                    "city": "Bengaluru",
                    "region": "Karnataka",
                    "country": "India",
                    "timezone": {"id": "Asia/Kolkata"},
                    "postal": "560001",
                    "connection": {
                        "asn": 9498,
                        "org": "Bharti Airtel Ltd.",
                        "isp": "Airtel"
                    }
                }
            )
        return MockResponse(url, {}, 404)

    monkeypatch.setattr(httpx, "get", mock_get)
    
    service = GeoIPService()
    result = service.lookup("8.8.8.8")
    
    assert result.city == "Bengaluru"
    assert result.postal_code == "560001"
    assert result.consensus_verified is True
    assert result.base_confidence == 90
    assert result.network_type == "Residential Broadband"


def test_geoip_no_consensus_resolution(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "use_external_geoip_api", True)
    monkeypatch.setattr(settings, "disable_maxmind_db", True)
    
    import httpx
    
    class MockResponse:
        def __init__(self, url, json_data, status_code=200):
            self.url = url
            self._json_data = json_data
            self.status_code = status_code
            
        def json(self):
            return self._json_data

    def mock_get(url, *args, **kwargs):
        if "ip-api.com" in url:
            return MockResponse(
                url,
                {
                    "status": "success",
                    "city": "Bengaluru",
                    "regionName": "Karnataka",
                    "country": "India",
                    "timezone": "Asia/Kolkata",
                    "zip": "560001",
                }
            )
        elif "ipwho.is" in url:
            return MockResponse(
                url,
                {
                    "success": True,
                    "city": "Mumbai",
                    "region": "Maharashtra",
                    "country": "India",
                    "timezone": {"id": "Asia/Kolkata"},
                    "postal": "400001",
                }
            )
        return MockResponse(url, {}, 404)

    monkeypatch.setattr(httpx, "get", mock_get)
    
    service = GeoIPService()
    result = service.lookup("8.8.8.8")
    
    assert result.city == "Bengaluru"
    assert result.postal_code == "560001"
    assert result.consensus_verified is False
    assert result.base_confidence == 88


def test_geoip_ipv6_lookup(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "use_external_geoip_api", True)
    monkeypatch.setattr(settings, "disable_maxmind_db", True)
    
    import httpx
    
    class MockResponse:
        def __init__(self, url, json_data, status_code=200):
            self.url = url
            self._json_data = json_data
            self.status_code = status_code
            
        def json(self):
            return self._json_data

    def mock_get(url, *args, **kwargs):
        if "ip-api.com" in url:
            return MockResponse(
                url,
                {
                    "status": "success",
                    "city": "Bengaluru",
                    "regionName": "Karnataka",
                    "country": "India",
                    "timezone": "Asia/Kolkata",
                    "zip": "560001",
                    "as": "AS9498 Bharti Airtel Ltd.",
                    "isp": "Airtel",
                }
            )
        elif "ipwho.is" in url:
            return MockResponse(
                url,
                {
                    "success": True,
                    "city": "Bengaluru",
                    "region": "Karnataka",
                    "country": "India",
                    "timezone": {"id": "Asia/Kolkata"},
                    "postal": "560001",
                }
            )
        return MockResponse(url, {}, 404)

    monkeypatch.setattr(httpx, "get", mock_get)
    
    service = GeoIPService()
    result = service.lookup("2409:4060:1e:a95e::")
    
    assert result.city == "Bengaluru"
    assert result.postal_code == "560001"
    assert result.consensus_verified is True
    assert result.base_confidence == 90
