from app.schemas import BrowserSignals
from app.services.fingerprint import generate_visitor_hash, parse_user_agent


def test_fingerprint_is_deterministic_and_signal_sensitive():
    arguments = {
        "secret": "secret",
        "user_agent": "Mozilla/5.0 Test",
        "accept": "text/html",
        "accept_language": "en-US",
        "sec_ch_platform": "Windows",
        "signals": BrowserSignals(timezone="Asia/Kolkata", screen_resolution="1920x1080"),
    }
    first = generate_visitor_hash(**arguments)
    second = generate_visitor_hash(**arguments)
    changed = generate_visitor_hash(**{**arguments, "accept_language": "fr-FR"})
    assert first == second
    assert first != changed
    assert len(first) == 64


def test_fingerprint_normalizes_case_and_whitespace():
    base = BrowserSignals(timezone="Asia/Kolkata", language="EN-US")
    altered = BrowserSignals(timezone="  asia/kolkata ", language="en-us")
    common = {
        "secret": "secret",
        "user_agent": "UA",
        "accept": None,
        "accept_language": None,
        "sec_ch_platform": None,
    }
    assert generate_visitor_hash(**common, signals=base) == generate_visitor_hash(**common, signals=altered)


def test_user_agent_is_reduced_to_coarse_fields():
    parsed = parse_user_agent(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
    )
    assert parsed.device_type == "Mobile"
    assert "Mobile Safari" in parsed.browser
    assert parsed.os == "iOS"

