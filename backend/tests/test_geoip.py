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
