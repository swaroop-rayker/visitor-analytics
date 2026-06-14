import re
from dataclasses import dataclass

from app.services.fingerprint import ParsedAgent, parse_user_agent


@dataclass(frozen=True)
class CrawlerClassification:
    is_crawler: bool
    crawler_type: str | None = None


@dataclass(frozen=True)
class VisitorClassificationResult:
    classification: str
    confidence: float
    reason: str


CRAWLER_SIGNATURES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"facebookexternalhit|facebot", re.I), "Social Media Crawler"),
    (re.compile(r"instagram|meta-externalagent", re.I), "Social Media Crawler"),
    (re.compile(r"twitterbot|xbot", re.I), "Social Media Crawler"),
    (re.compile(r"linkedinbot|slackbot|discordbot|telegrambot|whatsapp", re.I), "Social Media Crawler"),
    (re.compile(r"googlebot|bingbot|duckduckbot|yandexbot|baiduspider", re.I), "Search Engine Crawler"),
    (re.compile(r"ahrefsbot|semrushbot|mj12bot|dotbot|petalbot", re.I), "Known Bot"),
    (re.compile(r"uptimerobot|pingdom|statuscake|better uptime|datadog|newrelic", re.I), "Monitoring Service"),
    (re.compile(r"censysinspect|shodan|zgrab|nmap|masscan|nikto|qualys|nessus", re.I), "Security Scanner"),
    (re.compile(r"headlesschrome|python-requests|curl|wget|go-http-client|http\.client|libwww-perl|scrapy|postman", re.I), "Known Bot"),
)


def classify_visitor(
    user_agent: str,
    ip: str,
    asn: int | None,
    isp: str | None,
    network_type: str,
    parsed_agent: ParsedAgent | None = None,
) -> VisitorClassificationResult:
    ua = user_agent or ""
    org = (isp or "").lower()
    
    # 1. Match User-Agent against crawler/bot regex signatures
    for pattern, crawler_class in CRAWLER_SIGNATURES:
        if pattern.search(ua):
            return VisitorClassificationResult(
                classification=crawler_class,
                confidence=1.0,
                reason=f"User-Agent matched pattern for {crawler_class}"
            )
            
    # 2. Check ISP / Org name signatures
    if "facebook" in org or "meta platforms" in org:
        return VisitorClassificationResult(
            classification="Social Media Crawler",
            confidence=0.95,
            reason="Network owner matches Meta/Facebook hosting"
        )
    if "google" in org:
        # Check if it has a bot UA or parsed agent reports bot
        agent = parsed_agent or parse_user_agent(ua)
        if agent.device_type == "Bot":
            return VisitorClassificationResult(
                classification="Search Engine Crawler",
                confidence=0.95,
                reason="Network owner matches Google and device is Bot"
            )
            
    # 3. Check for parsed Bot device type
    agent = parsed_agent or parse_user_agent(ua)
    if agent.device_type == "Bot":
        return VisitorClassificationResult(
            classification="Known Bot",
            confidence=0.9,
            reason="Device type classified as Bot by User-Agent parser"
        )
        
    # 4. Check Datacenter / Cloud network type
    if network_type in {"Datacenter", "Cloud Provider"}:
        # Browser UA from datacenter/cloud is suspicious
        if agent.device_type in {"Desktop", "Mobile", "Tablet"}:
            return VisitorClassificationResult(
                classification="Likely Bot",
                confidence=0.8,
                reason=f"Standard browser user-agent ({agent.device_type}) originating from a {network_type} network"
            )
        else:
            return VisitorClassificationResult(
                classification="Known Bot",
                confidence=0.95,
                reason=f"Non-standard client originating from a {network_type} network"
            )
            
    # 5. Check VPN / Proxy network type
    if network_type in {"VPN", "Proxy"}:
        return VisitorClassificationResult(
            classification="Likely Human",
            confidence=0.7,
            reason=f"Request from VPN/Proxy network ({network_type}) using browser user-agent"
        )
        
    # 6. Check Residential / Mobile / Corporate Network (Humans)
    if network_type in {"Residential Broadband", "Mobile Carrier", "Corporate Network"}:
        if agent.device_type in {"Desktop", "Mobile", "Tablet"}:
            return VisitorClassificationResult(
                classification="Human",
                confidence=0.95,
                reason=f"Standard browser request from a residential/mobile/corporate network ({network_type})"
            )
        else:
            return VisitorClassificationResult(
                classification="Likely Bot",
                confidence=0.75,
                reason=f"Automated/non-standard client originating from a residential/mobile/corporate network ({network_type})"
            )

    # 6.5. Check Unresolved / Private Network with standard browser
    if not network_type or network_type == "Unknown":
        if agent.device_type in {"Desktop", "Mobile", "Tablet"}:
            return VisitorClassificationResult(
                classification="Human",
                confidence=0.85,
                reason=f"Standard browser user-agent ({agent.device_type}) originating from a private/local or unresolved network"
            )
            
    # 7. Fallback Unknown
    return VisitorClassificationResult(
        classification="Unknown",
        confidence=0.5,
        reason="No matches found for User-Agent, ISP, or network type classification"
    )


def classify_crawler(
    user_agent: str,
    *,
    organization: str | None = None,
    parsed_agent: ParsedAgent | None = None,
) -> CrawlerClassification:
    """Legacy compatibility function for testing or other modules."""
    res = classify_visitor(user_agent, "", None, organization, "Unknown", parsed_agent)
    is_crawler = res.classification in {
        "Social Media Crawler", "Search Engine Crawler", "Security Scanner", "Monitoring Service", "Known Bot"
    }
    return CrawlerClassification(is_crawler=is_crawler, crawler_type=res.classification)
