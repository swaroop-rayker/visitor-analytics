"""Backfill classification and confidence for historical visits.

Revision ID: 0004_backfill_classifications
Revises: 0003_reliability_and_classification
Create Date: 2026-06-12 19:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import select, update

# Revision identifiers
revision = "0004_backfill_classifications"
down_revision = "0003_reliability_and_classification"
branch_labels = None
depends_on = None


def get_confidence_level(score: int) -> str:
    if score >= 75:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


def classify_row(browser: str | None, device_type: str | None, network_type: str | None, isp: str | None) -> tuple[str, float, str, bool]:
    br = (browser or "").lower()
    dev = (device_type or "").lower()
    net = network_type or "Unknown"
    org = (isp or "").lower()
    
    # Check crawler signatures in browser string
    if any(k in br for k in ["facebookexternalhit", "facebot", "instagram", "meta-externalagent", "twitterbot", "xbot", "linkedinbot", "slackbot", "discordbot", "telegrambot", "whatsapp"]):
        return "Social Media Crawler", 1.0, "Historical browser signature match for Social Media Crawler", True
        
    if any(k in br for k in ["googlebot", "bingbot", "duckduckbot", "yandexbot", "baiduspider"]):
        return "Search Engine Crawler", 1.0, "Historical browser signature match for Search Engine Crawler", True
        
    if any(k in br for k in ["ahrefsbot", "semrushbot", "mj12bot", "dotbot", "petalbot", "headlesschrome", "python-requests", "curl", "wget", "go-http-client", "http.client", "libwww-perl", "scrapy", "postman"]):
        return "Known Bot", 1.0, "Historical browser signature match for Known Bot", True
        
    if any(k in br for k in ["uptimerobot", "pingdom", "statuscake", "better uptime", "datadog", "newrelic"]):
        return "Monitoring Service", 1.0, "Historical browser signature match for Monitoring Service", True
        
    if any(k in br for k in ["censysinspect", "shodan", "zgrab", "nmap", "masscan", "nikto", "qualys", "nessus"]):
        return "Security Scanner", 1.0, "Historical browser signature match for Security Scanner", True

    # Check ISP matching
    if "facebook" in org or "meta platforms" in org:
        return "Social Media Crawler", 0.95, "Historical network owner matches Meta/Facebook", True
        
    if "google" in org and dev == "bot":
        return "Search Engine Crawler", 0.95, "Historical network owner matches Google and device is Bot", True

    if dev == "bot":
        return "Known Bot", 0.90, "Historical device type matches Bot", True

    # Network types
    if net in {"Datacenter", "Cloud Provider"}:
        if dev in {"desktop", "mobile", "tablet"}:
            return "Likely Bot", 0.8, f"Browser ({device_type}) from cloud/datacenter", True
        else:
            return "Known Bot", 0.95, "Non-standard client from cloud/datacenter", True

    if net in {"VPN", "Proxy"}:
        return "Likely Human", 0.7, "Request from VPN/Proxy", False

    if net in {"Residential Broadband", "Mobile Carrier", "Corporate Network"}:
        if dev in {"desktop", "mobile", "tablet"}:
            return "Human", 0.95, f"Browser request from residential/mobile/corporate ({network_type})", False
        else:
            return "Likely Bot", 0.75, "Non-standard client from residential/mobile/corporate", True

    # Fallback for local/private or unresolved networks
    if dev in {"desktop", "mobile", "tablet"}:
        return "Human", 0.85, f"Browser request ({device_type}) from unresolved network", False

    return "Unknown", 0.5, "No historical matches found", False


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    
    # 1. Define temp table references for execution
    visit_logs_table = sa.table(
        "visit_logs",
        sa.column("id", sa.Integer),
        sa.column("visitor_id", sa.Integer),
        sa.column("browser", sa.String),
        sa.column("device_type", sa.String),
        sa.column("network_type", sa.String),
        sa.column("isp", sa.String),
        sa.column("confidence_score", sa.Integer),
        sa.column("country_confidence_score", sa.Integer),
        sa.column("state_confidence_score", sa.Integer),
        sa.column("city_confidence_score", sa.Integer),
        sa.column("classification", sa.String),
        sa.column("classification_confidence", sa.Float),
        sa.column("classification_reason", sa.String),
        sa.column("is_crawler", sa.Boolean),
        sa.column("country_confidence", sa.String),
        sa.column("state_confidence", sa.String),
        sa.column("city_confidence", sa.String),
        sa.column("location_confidence", sa.String),
    )
    
    visitors_table = sa.table(
        "visitors",
        sa.column("id", sa.Integer),
        sa.column("current_isp", sa.String),
        sa.column("current_network_type", sa.String),
        sa.column("confidence_score", sa.Integer),
        sa.column("country_confidence_score", sa.Integer),
        sa.column("state_confidence_score", sa.Integer),
        sa.column("city_confidence_score", sa.Integer),
        sa.column("classification", sa.String),
        sa.column("classification_confidence", sa.Float),
        sa.column("classification_reason", sa.String),
        sa.column("is_crawler", sa.Boolean),
        sa.column("current_country_confidence", sa.String),
        sa.column("current_state_confidence", sa.String),
        sa.column("current_city_confidence", sa.String),
        sa.column("current_location_confidence", sa.String),
    )
    
    # Update VisitLogs
    visits = session.execute(
        select(
            visit_logs_table.c.id,
            visit_logs_table.c.browser,
            visit_logs_table.c.device_type,
            visit_logs_table.c.network_type,
            visit_logs_table.c.isp,
            visit_logs_table.c.confidence_score,
            visit_logs_table.c.country_confidence_score,
            visit_logs_table.c.state_confidence_score,
            visit_logs_table.c.city_confidence_score,
        )
    ).all()
    
    for row in visits:
        cls_name, cls_conf, cls_reason, is_cr = classify_row(row.browser, row.device_type, row.network_type, row.isp)
        country_c = get_confidence_level(row.country_confidence_score)
        state_c = get_confidence_level(row.state_confidence_score)
        city_c = get_confidence_level(row.city_confidence_score)
        loc_c = get_confidence_level(row.confidence_score)
        
        session.execute(
            update(visit_logs_table)
            .where(visit_logs_table.c.id == row.id)
            .values(
                classification=cls_name,
                classification_confidence=cls_conf,
                classification_reason=cls_reason,
                is_crawler=is_cr,
                country_confidence=country_c,
                state_confidence=state_c,
                city_confidence=city_c,
                location_confidence=loc_c,
            )
        )
        
    # Update Visitors
    visitors = session.execute(
        select(
            visitors_table.c.id,
            visitors_table.c.current_isp,
            visitors_table.c.current_network_type,
            visitors_table.c.confidence_score,
            visitors_table.c.country_confidence_score,
            visitors_table.c.state_confidence_score,
            visitors_table.c.city_confidence_score,
        )
    ).all()
    
    for row in visitors:
        last_visit = session.execute(
            select(visit_logs_table.c.browser, visit_logs_table.c.device_type)
            .where(visit_logs_table.c.visitor_id == row.id)
            .order_by(visit_logs_table.c.id.desc())
            .limit(1)
        ).first()
        
        browser = last_visit[0] if last_visit else None
        dev_type = last_visit[1] if last_visit else None
        
        cls_name, cls_conf, cls_reason, is_cr = classify_row(browser, dev_type, row.current_network_type, row.current_isp)
        country_c = get_confidence_level(row.country_confidence_score)
        state_c = get_confidence_level(row.state_confidence_score)
        city_c = get_confidence_level(row.city_confidence_score)
        loc_c = get_confidence_level(row.confidence_score)
        
        session.execute(
            update(visitors_table)
            .where(visitors_table.c.id == row.id)
            .values(
                classification=cls_name,
                classification_confidence=cls_conf,
                classification_reason=cls_reason,
                is_crawler=is_cr,
                current_country_confidence=country_c,
                current_state_confidence=state_c,
                current_city_confidence=city_c,
                current_location_confidence=loc_c,
            )
        )
        
    session.commit()


def downgrade() -> None:
    # Downgrades are not required for simple data backfills
    pass
