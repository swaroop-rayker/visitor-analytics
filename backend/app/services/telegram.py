import asyncio
import threading
import logging
import httpx
from app.db import SessionLocal
from app.models import VisitLog
from app.config import settings

logger = logging.getLogger("visitor_analytics.telegram")


def run_async_in_background(coro):
    """
    Run an async coroutine in a background thread or event loop.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        def start_loop(c):
            asyncio.run(c)
        threading.Thread(target=start_loop, args=(coro,), daemon=True).start()


async def send_telegram_message(text: str) -> bool:
    """
    Send an HTML formatted message via Telegram Bot API.
    """
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        logger.warning("[TELEGRAM] Bot token or Chat ID not configured. Skipping alert.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("[TELEGRAM] Alert sent successfully.")
                return True
            else:
                logger.error("[TELEGRAM] Failed to send Telegram alert: %s - %s", resp.status_code, resp.text)
                return False
    except Exception as e:
        logger.error("[TELEGRAM] Exception sending alert: %s", str(e), exc_info=True)
        return False


async def _process_telegram_notification(visit_id: int, is_update: bool):
    """
    Fetch the visit record, run boundary checks, format HTML, and send to Telegram.
    """
    try:
        with SessionLocal() as db:
            visit = db.get(VisitLog, visit_id)
            if not visit:
                logger.warning("[TELEGRAM] VisitLog %s not found. Skipping alert.", visit_id)
                return

            # Skip crawlers and bots to prevent channel spam
            if visit.is_crawler or visit.classification in {
                "Social Media Crawler", "Search Engine Crawler", "Security Scanner", "Monitoring Service", "Known Bot"
            }:
                logger.debug("[TELEGRAM] Visit %s is a crawler/bot. Skipping alert.", visit_id)
                return

            timestamp_str = visit.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            city = visit.city or "Unknown"
            state = visit.state or "Unknown"
            country = visit.country or "Unknown"
            network = visit.isp or visit.network_organization or "Unknown"
            network_type = visit.network_type or "Unknown"

            if is_update:
                title = "📍 <b>Location Consent Shared</b>"
            else:
                title = "👤 <b>New Visit Recorded</b>"

            lines = [
                title,
                "━━━━━━━━━━━━━━━━━━",
                f"<b>Timestamp:</b> {timestamp_str}",
                f"<b>Country:</b> {country}",
                f"<b>State:</b> {state}",
                f"<b>City:</b> {city}",
                f"<b>Network:</b> {network}",
                f"<b>Network Type:</b> {network_type}",
            ]

            matched_boundaries = []
            if visit.latitude is not None and visit.longitude is not None:
                lines.append(f"<b>Location:</b> <code>{visit.latitude:.6f}, {visit.longitude:.6f}</code>")
                maps_url = f"https://www.google.com/maps?q={visit.latitude},{visit.longitude}"
                lines.append(f"🗺️ <a href='{maps_url}'>View on Google Maps</a>")

                # Check geofences
                from app.services.geofence import check_geofences
                matched_boundaries = check_geofences(visit.latitude, visit.longitude, db, city=visit.city)
            else:
                # If coordinates are None, check by city name as fallback
                if visit.city:
                    from app.services.geofence import check_geofences
                    matched_boundaries = check_geofences(0.0, 0.0, db, city=visit.city)

            if matched_boundaries:
                boundary_status = ", ".join(matched_boundaries)
                lines.append(f"📍 <b>Boundary Status:</b> Within boundary ({boundary_status})")
            else:
                if not is_update:
                    lines.append("📍 <b>Boundary Status:</b> Outside boundary")

            message = "\n".join(lines)
            await send_telegram_message(message)
    except Exception as ex:
        logger.error("[TELEGRAM] Error processing Telegram notification: %s", str(ex), exc_info=True)


def trigger_telegram_notification(visit_id: int, is_update: bool = False):
    """
    Triggers Telegram notifications in a non-blocking background runner.
    """
    run_async_in_background(_process_telegram_notification(visit_id, is_update))
