import secrets
import threading
import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.schemas import BrowserSignals, LocationConsentRequest, LocationConsentResponse, TrackResponse
from app.services.crawlers import classify_visitor
from app.services.fingerprint import ParsedAgent, generate_visitor_hash, parse_user_agent
from app.services.geoip import geoip_service, GeoResult, normalize_location_name
from app.services.security import (
    client_ip,
    create_location_update_token,
    decode_location_update_token,
    enforce_rate_limit,
)
from app.services.tracking import apply_consented_location, record_crawler_visit, record_visit, record_failed_visit

router = APIRouter(tags=["tracking"])
TRACK_WRITE_LOCK = threading.Lock()
logger = logging.getLogger("visitor_analytics.tracker")


def _record(request: Request, signals: BrowserSignals, db: Session) -> TrackResponse:
    ip = client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    path = request.url.path
    
    # 1. Received
    logger.info("[TRACKER_TRACE] STAGE: received | IP: %s | UA: %s | Path: %s", ip, user_agent, path)
    
    try:
        enforce_rate_limit(request, "track", settings.track_rate_limit_per_minute)
    except Exception as e:
        logger.error("[TRACKER_TRACE] STAGE: failed | IP: %s | Step: rate_limit | Error: %s", ip, str(e), exc_info=True)
        try:
            with TRACK_WRITE_LOCK:
                record_failed_visit(
                    db,
                    visitor_hash="rate_limited_fallback_" + secrets.token_hex(8),
                    user_agent=user_agent,
                    ip=ip,
                    failure_reason="rate_limit_exceeded",
                    classification="Unknown",
                )
        except Exception:
            pass
        raise e

    # 2. Fingerprint generation
    logger.info("[TRACKER_TRACE] STAGE: fingerprint_start | IP: %s", ip)
    try:
        signals = signals.model_copy(
            update={"accept_language": signals.accept_language or request.headers.get("accept-language")}
        )
        visitor_hash = generate_visitor_hash(
            secret=settings.fingerprint_secret,
            user_agent=user_agent,
            accept=request.headers.get("accept"),
            accept_language=request.headers.get("accept-language"),
            sec_ch_platform=request.headers.get("sec-ch-ua-platform"),
            signals=signals,
        )
        logger.info("[TRACKER_TRACE] STAGE: fingerprint_done | IP: %s | Hash: %s", ip, visitor_hash)
    except Exception as e:
        logger.error("[TRACKER_TRACE] STAGE: failed | IP: %s | Step: fingerprint | Error: %s", ip, str(e), exc_info=True)
        visitor_hash = "failed_fingerprint_fallback_" + secrets.token_hex(8)

    # 3. Geolocation & Classification
    logger.info("[TRACKER_TRACE] STAGE: geolocation_start | IP: %s", ip)
    try:
        geo = geoip_service.lookup(ip)
        
        # Check Cloudflare geolocation headers (highly accurate for passive routing)
        cf_city = request.headers.get("cf-ipcity")
        cf_region = request.headers.get("cf-region")
        cf_country = request.headers.get("cf-ipcountry")
        
        if cf_city or cf_region or cf_country:
            cf_country_map = {
                "IN": "India", "US": "United States", "GB": "United Kingdom",
                "CA": "Canada", "AU": "Australia", "DE": "Germany", "FR": "France",
                "JP": "Japan", "SG": "Singapore", "AE": "United Arab Emirates",
                "NL": "Netherlands", "IE": "Ireland", "IT": "Italy", "ES": "Spain",
                "MY": "Malaysia", "TH": "Thailand", "VN": "Vietnam", "NZ": "New Zealand",
            }
            cf_country_name = None
            if cf_country:
                cf_country_upper = cf_country.upper()
                cf_country_name = cf_country_map.get(cf_country_upper)
                if not cf_country_name:
                    from app.services.location_intelligence import COUNTRY_BY_LANGUAGE_REGION
                    cf_country_name = COUNTRY_BY_LANGUAGE_REGION.get(cf_country_upper)
                if not cf_country_name:
                    cf_country_name = geo.country or cf_country_upper

            overridden_city = normalize_location_name(cf_city) or geo.city
            overridden_state = normalize_location_name(cf_region) or geo.state
            overridden_country = cf_country_name or geo.country
            
            geo = GeoResult(
                city=overridden_city,
                state=overridden_state,
                country=overridden_country,
                city_raw=cf_city or geo.city_raw,
                state_raw=cf_region or geo.state_raw,
                country_raw=cf_country or geo.country_raw,
                geo_timezone=geo.geo_timezone,
                asn=geo.asn,
                organization=geo.organization,
                network_type=geo.network_type,
                base_confidence=max(geo.base_confidence, 82)
            )
            logger.info("[TRACKER_TRACE] Cloudflare headers override applied | City: %s | State: %s | Country: %s | Conf: %s",
                        geo.city, geo.state, geo.country, geo.base_confidence)

        logger.info("[TRACKER_TRACE] STAGE: geolocation_done | IP: %s | Country: %s | State: %s | City: %s | NetworkType: %s", 
                    ip, geo.country, geo.state, geo.city, geo.network_type)
    except Exception as e:
        logger.error("[TRACKER_TRACE] STAGE: failed | IP: %s | Step: geolocation | Error: %s", ip, str(e), exc_info=True)
        geo = GeoResult(network_type="Unknown")

    agent = parse_user_agent(user_agent)

    # 1. Refine agent information using UA Client Hints if available
    if signals.ua_platform:
        ua_os = signals.ua_platform
        if ua_os.lower() == "windows":
            ua_os = "Windows"
        elif ua_os.lower() in {"macos", "mac os", "mac os x"}:
            ua_os = "Mac OS X"
        elif ua_os.lower() == "android":
            ua_os = "Android"
        elif ua_os.lower() in {"ios", "iphone os"}:
            ua_os = "iOS"
        elif ua_os.lower() == "linux":
            ua_os = "Linux"
        agent = ParsedAgent(browser=agent.browser, os=ua_os, device_type=agent.device_type)

    if signals.ua_mobile is not None:
        if signals.ua_mobile:
            refined_device = "Mobile"
        else:
            refined_device = agent.device_type if agent.device_type in {"Tablet", "Bot"} else "Desktop"
        agent = ParsedAgent(browser=agent.browser, os=agent.os, device_type=refined_device)

    if signals.ua_brands:
        brands_lower = signals.ua_brands.lower()
        import re
        if "edg" in brands_lower or "microsoft edge" in brands_lower:
            version_match = re.search(r'(?:microsoft edge|edge|edg):(\d+)', brands_lower)
            ver = f" {version_match.group(1)}" if version_match else ""
            agent = ParsedAgent(browser=f"Edge{ver}", os=agent.os, device_type=agent.device_type)
        elif "chrome" in brands_lower or "google chrome" in brands_lower:
            version_match = re.search(r'(?:google chrome|chrome):(\d+)', brands_lower)
            ver = f" {version_match.group(1)}" if version_match else ""
            agent = ParsedAgent(browser=f"Chrome{ver}", os=agent.os, device_type=agent.device_type)
        elif "opera" in brands_lower:
            version_match = re.search(r'opera:(\d+)', brands_lower)
            ver = f" {version_match.group(1)}" if version_match else ""
            agent = ParsedAgent(browser=f"Opera{ver}", os=agent.os, device_type=agent.device_type)

    # 2. Refine network type based on client signals
    if geo.network_type in {"Mobile Carrier", "Residential Broadband", "Unknown"}:
        refined_type = geo.network_type
        
        # Heuristic 1: Explicit connection type check (strongest indicator)
        if signals.connection_type:
            if signals.connection_type in {"wifi", "ethernet", "cable", "wimax"}:
                refined_type = "Residential Broadband"
                logger.info("[GEOLOCATION] Network refined to Broadband via client connection_type: %s", signals.connection_type)
            elif signals.connection_type == "cellular":
                refined_type = "Mobile Carrier"
                logger.info("[GEOLOCATION] Network refined to Mobile via client connection_type: %s", signals.connection_type)
        
        else:
            # Heuristic 2: Private IP detection (very strong router NAT indicator)
            if signals.has_private_ip:
                refined_type = "Residential Broadband"
                logger.info("[GEOLOCATION] Network refined to Broadband via private IP detection (NAT/Router present)")
            
            else:
                # Heuristic 3: Browser Data Saver check
                if signals.save_data and agent.device_type == "Mobile":
                    refined_type = "Mobile Carrier"
                    logger.info("[GEOLOCATION] Network refined to Mobile via client save_data preference")
                
                else:
                    # Heuristic 4: Hardware capacity & Device classification check
                    is_desktop_device = agent.device_type == "Desktop"
                    
                    # Check GPU to see if it's desktop class or mobile class
                    has_desktop_gpu = False
                    has_mobile_gpu = False
                    if signals.gpu:
                        gpu_lower = signals.gpu.lower()
                        if any(m in gpu_lower for m in ["nvidia", "geforce", "rtx", "gtx", "amd", "radeon", "intel", "iris", "arc", "apple m"]):
                            has_desktop_gpu = True
                        if any(m in gpu_lower for m in ["adreno", "mali", "powervr", "apple mobile", "apple gpu", "google swiftshader"]):
                            has_mobile_gpu = True
                    
                    is_probably_desktop_or_laptop = False
                    if is_desktop_device or has_desktop_gpu:
                        is_probably_desktop_or_laptop = True
                    elif (signals.cores and signals.cores >= 6) and (signals.memory and signals.memory >= 6) and agent.os not in {"Android", "iOS"}:
                        is_probably_desktop_or_laptop = True
                        
                    if is_probably_desktop_or_laptop and not has_mobile_gpu:
                        refined_type = "Residential Broadband"
                        logger.info("[GEOLOCATION] Network refined to Broadband via desktop/hardware indicators (GPU: %s, Cores: %s, Memory: %s)",
                                    signals.gpu, signals.cores, signals.memory)
                    
                    # Heuristic 5: Latency, RTT & Jitter check
                    else:
                        is_low_latency_rtt = signals.rtt is not None and signals.rtt < 35
                        
                        pings = [
                            signals.latency_mumbai, signals.latency_hyderabad, signals.latency_delhi,
                            signals.latency_bangalore, signals.latency_chennai, signals.latency_kochi,
                            signals.latency_mangalore, signals.latency_kolkata
                        ]
                        valid_pings = [p for p in pings if p is not None and p > 0]
                        is_low_latency_ping = valid_pings and min(valid_pings) < 25
                        
                        # High jitter suggests cellular data variation, low jitter suggests stable fiber/fixed-line
                        is_stable_connection = signals.ping_jitter is not None and signals.ping_jitter < 15
                        is_unstable_connection = signals.ping_jitter is not None and signals.ping_jitter >= 30
                        
                        if (is_low_latency_rtt or is_low_latency_ping) and not is_unstable_connection:
                            refined_type = "Residential Broadband"
                            min_p = min(valid_pings) if valid_pings else "N/A"
                            logger.info("[GEOLOCATION] Network refined to Broadband via latency/jitter (RTT: %sms, Jitter: %sms, Min Ping: %sms)", 
                                        signals.rtt, signals.ping_jitter, min_p)
                        elif is_stable_connection and (signals.rtt is not None and signals.rtt < 55):
                            refined_type = "Residential Broadband"
                            logger.info("[GEOLOCATION] Network refined to Broadband via connection stability (Jitter: %sms, RTT: %sms)", 
                                        signals.ping_jitter, signals.rtt)
                        elif is_unstable_connection and agent.device_type == "Mobile":
                            refined_type = "Mobile Carrier"
                            logger.info("[GEOLOCATION] Network refined to Mobile via high jitter: %sms", signals.ping_jitter)

        if refined_type != geo.network_type:
            geo = GeoResult(
                city=geo.city, state=geo.state, country=geo.country,
                city_raw=geo.city_raw, state_raw=geo.state_raw, country_raw=geo.country_raw,
                geo_timezone=geo.geo_timezone, asn=geo.asn, organization=geo.organization,
                network_type=refined_type, base_confidence=geo.base_confidence
            )

    logger.info("[TRACKER_TRACE] STAGE: classification_start | Hash: %s", visitor_hash)
    try:
        class_res = classify_visitor(
            user_agent=user_agent,
            ip=ip,
            asn=geo.asn,
            isp=geo.organization,
            network_type=geo.network_type,
            parsed_agent=agent,
        )
        classification = class_res.classification
        class_confidence = class_res.confidence
        class_reason = class_res.reason
        logger.info("[TRACKER_TRACE] STAGE: classification_done | Hash: %s | Class: %s | Conf: %s | Reason: %s", 
                    visitor_hash, classification, class_confidence, class_reason)
    except Exception as e:
        logger.error("[TRACKER_TRACE] STAGE: failed | Hash: %s | Step: classification | Error: %s", visitor_hash, str(e), exc_info=True)
        classification = "Unknown"
        class_confidence = 0.5
        class_reason = f"Classification exception: {str(e)}"
        agent = parse_user_agent(user_agent)

    # 4. Database write & Commit
    logger.info("[TRACKER_TRACE] STAGE: db_write_start | Hash: %s", visitor_hash)
    with TRACK_WRITE_LOCK:
        try:
            is_crawler = classification in {
                "Social Media Crawler", "Search Engine Crawler", "Security Scanner", "Monitoring Service", "Known Bot"
            }
            if is_crawler:
                try:
                    record_crawler_visit(
                        db,
                        crawler_type=classification,
                        agent=agent,
                        signals=signals,
                        geo=geo
                    )
                except Exception as ex:
                    logger.error("[TRACKER_TRACE] STAGE: failed | Hash: %s | Step: record_crawler_visit_compat | Error: %s", visitor_hash, str(ex), exc_info=True)
            
            visit = record_visit(
                db,
                visitor_hash=visitor_hash,
                agent=agent,
                signals=signals,
                geo=geo,
                classification=classification,
                class_confidence=class_confidence,
                class_reason=class_reason,
                tracking_status="persisted",
                ip=ip,
            )
            logger.info("[TRACKER_TRACE] STAGE: db_write_done | Hash: %s | VisitID: %s", visitor_hash, visit.id)
            logger.info("[TRACKER_TRACE] STAGE: db_commit_done | Hash: %s | VisitID: %s", visitor_hash, visit.id)
            
            redirect_url = settings.redirect_target_url
            logger.info("[TRACKER_TRACE] STAGE: redirect | VisitID: %s | Target: %s", visit.id, redirect_url)
            
            # If inline GPS was used in /sync, no need for a separate /confirm token
            has_inline_gps = signals.latitude is not None and signals.longitude is not None
            return TrackResponse(
                redirect_url=redirect_url,
                location_update_token=None if has_inline_gps else create_location_update_token(visit.id, visitor_hash),
            )
        except Exception as e:
            logger.error("[TRACKER_TRACE] STAGE: failed | Hash: %s | Step: db_write | Error: %s", visitor_hash, str(e), exc_info=True)
            db.rollback()
            try:
                failed_visit = record_failed_visit(
                    db,
                    visitor_hash=visitor_hash,
                    user_agent=user_agent,
                    ip=ip,
                    failure_reason=f"db_write_failed: {str(e)}",
                    classification=classification,
                    class_confidence=class_confidence,
                    class_reason=class_reason,
                    geo=geo,
                    agent=agent,
                    signals=signals
                )
                if failed_visit:
                    logger.info("[TRACKER_TRACE] STAGE: failed_recorded | VisitID: %s", failed_visit.id)
            except Exception as fe:
                logger.error("[TRACKER_TRACE] STAGE: failed_recording_failed | Error: %s", str(fe), exc_info=True)
            return TrackResponse(redirect_url=settings.redirect_target_url)


@router.get("/api/v1/honeypot", include_in_schema=False)
def honeypot_trigger(
    request: Request,
    v: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Stealth honeypot endpoint to catch automated scrapers and bots.
    If hit, registers the trigger, marks any associated visit anomalous,
    and stealthily redirects to the configured redirect target.
    """
    from app.services.integrity import register_honeypot_trigger
    from app.models import VisitLog
    
    ip = client_ip(request)
    logger.warning("[HONEYPOT] Honeypot link clicked! Query nonce: %s | Client IP: %s", v, ip)
    
    if v:
        visit_id = register_honeypot_trigger(v)
        if visit_id:
            with TRACK_WRITE_LOCK:
                try:
                    visit = db.get(VisitLog, visit_id)
                    if visit:
                        visit.is_anomalous = True
                        reasons = visit.anomaly_reasons or []
                        if "honeypot_triggered" not in reasons:
                            reasons.append("honeypot_triggered")
                            visit.anomaly_reasons = reasons
                            db.commit()
                            logger.warning("[HONEYPOT] Updated existing visit %d to anomalous: honeypot_triggered", visit_id)
                except Exception as e:
                    logger.error("[HONEYPOT] Failed to update existing visit %d: %s", visit_id, str(e), exc_info=True)
                    db.rollback()
                    
    return RedirectResponse(
        url=settings.redirect_target_url,
        status_code=307,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.get("/go", include_in_schema=False)
def tracking_page(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    user_agent = request.headers.get("user-agent", "")
    ua_lower = user_agent.lower()
    
    is_in_app = any(k in ua_lower for k in ["instagram", "fban", "fbav", "fb_iab", "threads"])
    is_bot = any(k in ua_lower for k in ["bot", "crawler", "spider", "facebookexternalhit", "facebot", "meta-externalagent"])
    
    if is_in_app or is_bot:
        logger.info("[TRACKER_TRACE] Immediate redirect triggered for UA: %s | In-app: %s | Bot: %s", user_agent, is_in_app, is_bot)
        try:
            _record(request, BrowserSignals(), db)
        except Exception as e:
            logger.exception("Immediate redirect tracking failed", exc_info=e)
            db.rollback()
        return RedirectResponse(
            url=settings.redirect_target_url,
            status_code=307,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "Referrer-Policy": "no-referrer",
            },
        )

    nonce = secrets.token_urlsafe(18)
    fallback_url = "/api/v1/fallback"
    target_url = settings.redirect_target_url
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <noscript>
    <meta http-equiv="refresh" content="10;url={target_url}">
  </noscript>
  <link rel="dns-prefetch" href="https://dynamodb.ap-south-1.amazonaws.com">
  <link rel="dns-prefetch" href="https://dynamodb.ap-south-2.amazonaws.com">
  <link rel="dns-prefetch" href="https://s3.asia-south2.amazonaws.com">
  <link rel="dns-prefetch" href="https://www.iisc.ac.in">
  <link rel="dns-prefetch" href="https://www.iitm.ac.in">
  <link rel="dns-prefetch" href="https://www.cusat.ac.in">
  <link rel="dns-prefetch" href="https://www.nitk.ac.in">
  <link rel="dns-prefetch" href="https://www.isical.ac.in">
  <title>Redirecting...</title>
  <style nonce="{nonce}">
    html{{color-scheme:dark}}body{{margin:0;display:grid;min-height:100vh;place-items:center;
    background:#09090b;color:#a1a1aa;font:14px system-ui}}main{{width:min(92vw,420px);padding:24px;
    border:1px solid #27272a;border-radius:16px;background:#18181b}}.dot{{color:#fafafa}}
    .actions{{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}}button{{border:1px solid #3f3f46;
    border-radius:10px;background:#27272a;color:#fafafa;padding:10px 12px;font:inherit;cursor:pointer}}
    button.primary{{background:#fafafa;color:#09090b}}button:disabled{{cursor:not-allowed;opacity:.6}}
    small{{display:block;margin-top:12px;line-height:1.5;color:#71717a}}
  </style>
</head>
<body><a href="/api/v1/honeypot?v={nonce}" style="display:none;position:absolute;left:-9999px;top:-9999px;" aria-hidden="true" tabindex="-1" rel="nofollow">Security Verification Link</a><main>
  <p><span class="dot">Redirecting</span> securely...</p>
  <p id="status">Recording an anonymous visit. You can continue now, or optionally share your device location once for more accurate city/state analytics.</p>
  <div class="actions">
    <button id="continue" class="primary" type="button">Continue</button>
    <button id="share" type="button">Share location, then continue</button>
  </div>
  <small>Location sharing is optional, uses the browser permission prompt, and the app still works if you deny or ignore it.</small>
</main>
<script nonce="{nonce}">
function cyrb128(str) {{
  let h1 = 1779033703, h2 = 3024733165, h3 = 3362453659, h4 = 50249339;
  for (let i = 0, k; i < str.length; i++) {{
    k = str.charCodeAt(i);
    h1 = h2 ^ Math.imul(h1 ^ k, 597399067);
    h2 = h3 ^ Math.imul(h2 ^ k, 2869860233);
    h3 = h4 ^ Math.imul(h3 ^ k, 951274213);
    h4 = h1 ^ Math.imul(h4 ^ k, 2716044179);
  }}
  h1 = Math.imul(h3 ^ (h1 >>> 18), 597399067);
  h2 = Math.imul(h4 ^ (h2 >>> 22), 2869860233);
  h3 = Math.imul(h1 ^ (h3 >>> 17), 951274213);
  h4 = Math.imul(h2 ^ (h4 >>> 19), 2716044179);
  return (h1>>>0).toString(16).padStart(8,'0')+(h2>>>0).toString(16).padStart(8,'0')+(h3>>>0).toString(16).padStart(8,'0')+(h4>>>0).toString(16).padStart(8,'0');
}}

let canvasHash = null;
try {{
  let canvas = document.createElement("canvas");
  canvas.width = 200;
  canvas.height = 50;
  let ctx = canvas.getContext("2d");
  if (ctx) {{
    ctx.textBaseline = "top";
    ctx.font = "14px 'Arial'";
    ctx.textBaseline = "alphabetic";
    ctx.fillStyle = "#f60";
    ctx.fillRect(125, 1, 62, 20);
    ctx.fillStyle = "#069";
    ctx.fillText("VisitorAnalytics, 😃", 2, 15);
    ctx.fillStyle = "rgba(102, 204, 0, 0.7)";
    ctx.fillText("VisitorAnalytics, 😃", 4, 17);
    ctx.shadowBlur = 10;
    ctx.shadowColor = "blue";
    ctx.fillRect(20, 20, 10, 10);
    
    let dataUrl = canvas.toDataURL();
    let cHash = cyrb128(dataUrl);
    
    let blankCanvas = document.createElement("canvas");
    blankCanvas.width = 200;
    blankCanvas.height = 50;
    let blankCtx = blankCanvas.getContext("2d");
    let blankHash = blankCtx ? cyrb128(blankCanvas.toDataURL()) : "";
    
    canvasHash = (cHash === blankHash) ? "blank" : cHash;
  }}
}} catch(e) {{
  canvasHash = "blocked";
}}

let webglHash = null;
try {{
  let canvas = document.createElement("canvas");
  let gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
  if (gl) {{
    let webglData = [];
    let extList = gl.getSupportedExtensions() || [];
    webglData.push(extList.join(","));
    
    let params = [
      gl.VERSION,
      gl.SHADING_LANGUAGE_VERSION,
      gl.VENDOR,
      gl.RENDERER,
      gl.MAX_COMBINED_TEXTURE_IMAGE_UNITS,
      gl.MAX_CUBE_MAP_TEXTURE_SIZE,
      gl.MAX_FRAGMENT_UNIFORM_VECTORS,
      gl.MAX_RENDERBUFFER_SIZE,
      gl.MAX_TEXTURE_SIZE,
      gl.MAX_VARYING_VECTORS,
      gl.MAX_VERTEX_ATTRIBS,
      gl.MAX_VERTEX_TEXTURE_IMAGE_UNITS,
      gl.MAX_VERTEX_UNIFORM_VECTORS,
      gl.MAX_VIEWPORT_DIMS ? gl.getParameter(gl.MAX_VIEWPORT_DIMS).join(",") : "",
      gl.RED_BITS,
      gl.GREEN_BITS,
      gl.BLUE_BITS,
      gl.ALPHA_BITS,
      gl.DEPTH_BITS,
      gl.STENCIL_BITS
    ];
    for (let i = 0; i < params.length; i++) {{
      try {{
        let val = gl.getParameter(params[i]);
        webglData.push(params[i] + ":" + (val ? val.toString() : ""));
      }} catch(e) {{}}
    }}
    
    let dbg = gl.getExtension("WEBGL_debug_renderer_info");
    if (dbg) {{
      webglData.push("vendor:" + gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL));
      webglData.push("renderer:" + gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL));
    }}
    
    webglHash = cyrb128(webglData.join("|"));
  }}
}} catch(e) {{
  webglHash = "blocked";
}}

let redirectUrl="{target_url}";
let updateToken=null;
let preciseCoords=null;
let permissionGranted=false;
const statusEl=document.getElementById("status");
const shareButton=document.getElementById("share");
const continueButton=document.getElementById("continue");
function setStatus(value){{statusEl.textContent=value;}}
function goNow(){{location.replace(redirectUrl || "{target_url}");}}
let redirectTimer=setTimeout(goNow,10000);
function scheduleRedirect(delay=8000){{clearTimeout(redirectTimer);redirectTimer=setTimeout(goNow,delay);}}

function submitConsent(token,coords){{
  clearTimeout(redirectTimer);
  setStatus("Optimizing routing...");
  fetch("/api/v1/confirm",{{method:"POST",headers:{{"Content-Type":"application/json"}},
    credentials:"same-origin",body:JSON.stringify({{
      token:token,latitude:coords.latitude,longitude:coords.longitude,
      accuracy_meters:coords.accuracy_meters
    }})}})
    .then(r=>r.ok?r.json():Promise.reject()).then(d=>{{
      console.log("[GEOLOCATION] Confirmed precise location.");
      try {{ localStorage.setItem("va_geo_granted", "1"); }} catch(e) {{}}
      redirectUrl=d.redirect_url||redirectUrl;
      goNow();
    }})
    .catch(()=>{{
      console.error("[GEOLOCATION] Auto-confirm failed. Redirecting.");
      goNow();
    }});
}}

function triggerAutoFetch(){{
  permissionGranted=true;
  shareButton.disabled=true;
  setStatus("Applying location preference...");
  clearTimeout(redirectTimer);
  redirectTimer=setTimeout(goNow,20000);
  
  navigator.geolocation.getCurrentPosition((position)=>{{
    preciseCoords={{
      latitude:position.coords.latitude,
      longitude:position.coords.longitude,
      accuracy_meters:Math.round(position.coords.accuracy||0)
    }};
    data.latitude=preciseCoords.latitude;
    data.longitude=preciseCoords.longitude;
    data.accuracy_meters=preciseCoords.accuracy_meters;
    console.log("[GEOLOCATION] Auto-fetched coordinates (will be sent inline with /sync):",preciseCoords);
    if(updateToken){{
      submitConsent(updateToken,preciseCoords);
    }}
  }},(err)=>{{
    console.warn("[GEOLOCATION] Auto-fetch failed:",err);
    permissionGranted=false;
    shareButton.disabled=false;
    if (err.code === err.PERMISSION_DENIED) {{
      try {{ localStorage.removeItem("va_geo_granted"); }} catch(e) {{}}
    }}
    setStatus("Recording an anonymous visit. You can continue now, or optionally share your device location once for more accurate city/state analytics.");
    scheduleRedirect(8000);
  }},{{enableHighAccuracy:false,maximumAge:600000}});
}}

let checkPermissionPromise = Promise.resolve(false);
try {{
  if (localStorage.getItem("va_geo_granted") === "1") {{
    checkPermissionPromise = Promise.resolve(true);
  }} else if (navigator.permissions && navigator.permissions.query) {{
    checkPermissionPromise = navigator.permissions.query({{name:"geolocation"}})
      .then(result => result.state === "granted")
      .catch(() => false);
  }}
}} catch(e) {{
  console.warn("Permission check error:", e);
}}

checkPermissionPromise.then((isGranted) => {{
  if (isGranted && navigator.geolocation) {{
    triggerAutoFetch();
  }}
}});

const data={{
  canvas_hash: canvasHash,
  webgl_hash: webglHash,
  nonce: "{nonce}",
  timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||null,
  language:navigator.language||null,
  accept_language:Array.isArray(navigator.languages)?navigator.languages.join(","):navigator.language||null,
  platform:navigator.userAgentData?.platform||navigator.platform||null,
  screen_resolution:`${{screen.width}}x${{screen.height}}`,
  connection_type:(navigator.connection||navigator.mozConnection||navigator.webkitConnection)?.type||null,
  effective_type:(navigator.connection||navigator.mozConnection||navigator.webkitConnection)?.effectiveType||null,
  save_data: typeof (navigator.connection||navigator.mozConnection||navigator.webkitConnection)?.saveData === "boolean" ? (navigator.connection||navigator.mozConnection||navigator.webkitConnection).saveData : null,
  has_private_ip: null,
  ping_jitter: null,
  cores:navigator.hardwareConcurrency||null,
  memory:navigator.deviceMemory||null,
  gpu:(function(){{
    try{{
      var canvas=document.createElement("canvas");
      var gl=canvas.getContext("webgl")||canvas.getContext("experimental-webgl");
      if(gl){{
        var dbg=gl.getExtension("WEBGL_debug_renderer_info");
        return dbg?gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
      }}
    }}catch(e){{}}
    return null;
  }})(),
  rtt:(navigator.connection||navigator.mozConnection||navigator.webkitConnection)?.rtt||null,
  downlink:(navigator.connection||navigator.mozConnection||navigator.webkitConnection)?.downlink||null,
  ua_platform:navigator.userAgentData?.platform||null,
  ua_mobile:typeof navigator.userAgentData?.mobile==="boolean"?navigator.userAgentData.mobile:null,
  ua_brands:navigator.userAgentData?.brands?navigator.userAgentData.brands.map(b=>b.brand+":"+b.version).join(","):null,
  latency_mumbai:null,
  latency_hyderabad:null,
  latency_delhi:null,
  latency_bangalore:null,
  latency_chennai:null,
  latency_kochi:null,
  latency_mangalore:null,
  latency_kolkata:null,
  latitude:null,
  longitude:null,
  accuracy_meters:null
}};

function fetchWithTimeout(url,timeoutMs=800){{
  return new Promise((resolve)=>{{
    const timer=setTimeout(()=>resolve(null),timeoutMs);
    fetch(url,{{mode:"no-cors",cache:"no-store"}})
      .then(res=>{{
        clearTimeout(timer);
        resolve(res);
      }})
      .catch(()=>{{
        clearTimeout(timer);
        resolve(null);
      }});
  }});
}}

const pingServers = [
  {{ name: "mumbai", url: "https://dynamodb.ap-south-1.amazonaws.com/" }},
  {{ name: "hyderabad", url: "https://dynamodb.ap-south-2.amazonaws.com/" }},
  {{ name: "delhi", url: "https://s3.asia-south2.amazonaws.com/" }},
  {{ name: "bangalore", url: "https://www.iisc.ac.in/favicon.ico" }},
  {{ name: "chennai", url: "https://www.iitm.ac.in/favicon.ico" }},
  {{ name: "kochi", url: "https://www.cusat.ac.in/favicon.ico" }},
  {{ name: "mangalore", url: "https://www.nitk.ac.in/favicon.ico" }},
  {{ name: "kolkata", url: "https://www.isical.ac.in/favicon.ico" }}
];

function measurePing(url){{
  return fetchWithTimeout(url,800)
    .then((res1)=>{{
      if(!res1)return 800;
      const start2=performance.now();
      return fetchWithTimeout(url,800)
        .then((res2)=>{{
          if(!res2)return 800;
          const time2=performance.now()-start2;
          const start3=performance.now();
          return fetchWithTimeout(url,800)
            .then((res3)=>{{
              if(!res3)return 800;
              const time3=performance.now()-start3;
              return Math.round((time2+time3)/2);
            }});
        }});
    }})
    .catch(()=>800);
}}

function runJitterTest(url) {{
  if (!url) return Promise.resolve(null);
  const pings = [];
  return measurePing(url)
    .then(p1 => {{ pings.push(p1); return measurePing(url); }})
    .then(p2 => {{ pings.push(p2); return measurePing(url); }})
    .then(p3 => {{
      pings.push(p3);
      const valid = pings.filter(p => p < 800);
      if (valid.length < 2) return null;
      const max = Math.max(...valid);
      const min = Math.min(...valid);
      return max - min;
    }})
    .catch(() => null);
}}

function runTriangulation(){{
  console.log("[GEOLOCATION] Running passive edge triangulation...");
  const promises = pingServers.map(s => {{
    return measurePing(s.url).then(t => {{
      data["latency_" + s.name] = t;
      return {{ name: s.name, url: s.url, time: t }};
    }});
  }});
  return Promise.all(promises).then(results => {{
    const valid = results.filter(r => r.time > 0 && r.time < 800);
    if (valid.length > 0) {{
      const fastest = valid.reduce((prev, curr) => prev.time < curr.time ? prev : curr);
      return runJitterTest(fastest.url).then(jitter => {{
        data.ping_jitter = jitter;
        console.log("[GEOLOCATION] Jitter computed for fastest server (" + fastest.name + "):", jitter);
      }});
    }}
  }}).catch(err=>console.warn("Triangulation error:",err));
}}

function detectPrivateIP() {{
  return new Promise((resolve) => {{
    try {{
      var MyPeerConnection = window.RTCPeerConnection || window.mozRTCPeerConnection || window.webkitRTCPeerConnection;
      if (!MyPeerConnection) return resolve(false);
      var pc = new MyPeerConnection({{ iceServers: [] }});
      var noop = function() {{}};
      var resolved = false;
      pc.createDataChannel("");
      pc.createOffer().then(offer => pc.setLocalDescription(offer), noop).catch(noop);
      pc.onicecandidate = function(ice) {{
        if (resolved) return;
        if (!ice || !ice.candidate || !ice.candidate.candidate) return;
        var cand = ice.candidate.candidate;
        var match = /([0-9]{{1,3}}(\.[0-9]{{1,3}}){{3}})/.exec(cand);
        if (match) {{
          var ip = match[1];
          var parts = ip.split(".");
          var isPrivate = parts[0] === "10" ||
            (parts[0] === "172" && (parseInt(parts[1], 10) >= 16 && parseInt(parts[1], 10) <= 31)) ||
            (parts[0] === "192" && parts[1] === "168") ||
            (parts[0] === "169" && parts[1] === "254");
          if (isPrivate) {{
            resolved = true;
            resolve(true);
            try {{ pc.close(); }} catch(e) {{}}
          }}
        }}
      }};
      setTimeout(function() {{
        if (!resolved) {{
          resolved = true;
          resolve(false);
          try {{ pc.close(); }} catch(e) {{}}
        }}
      }}, 300);
    }} catch(e) {{
      resolve(false);
    }}
  }});
}}

detectPrivateIP().then(hasPrivateIP => {{
  data.has_private_ip = hasPrivateIP;
  return runTriangulation();
}}).finally(()=>{{
  console.log("[GEOLOCATION] Dispatching passive track request.");
  fetch("/api/v1/sync",{{method:"POST",headers:{{"Content-Type":"application/json"}},
    credentials:"same-origin",body:JSON.stringify(data)}})
    .then(r=>r.ok?r.json():Promise.reject()).then(d=>{{
      redirectUrl=d.redirect_url||redirectUrl;updateToken=d.location_update_token||null;
      if(!updateToken && data.latitude!==null){{
        console.log("[GEOLOCATION] Inline GPS used in /sync. No /confirm needed.");
        try {{ localStorage.setItem("va_geo_granted", "1"); }} catch(e) {{}}
        goNow();
      }}else if(updateToken && preciseCoords){{
        submitConsent(updateToken,preciseCoords);
      }}else{{
        if(!updateToken||sessionStorage.getItem("va_geo_prompted")==="1"||permissionGranted){{
          shareButton.disabled=true;
        }}
        if(!permissionGranted){{
          setStatus("Anonymous visit recorded. Continue now, or optionally share your location once before continuing.");
          scheduleRedirect();
        }}else{{
          console.log("[GEOLOCATION] Sync complete. Waiting for precise coords...");
        }}
      }}
    }})
    .catch(()=>location.replace("{target_url}"));
}});

continueButton.addEventListener("click",goNow);
shareButton.addEventListener("click",()=>{{
  if(!updateToken||!navigator.geolocation){{
    console.warn("[GEOLOCATION] Geolocation is not supported by this browser or update token is missing.");
    setStatus("Location sharing is unavailable. Continuing.");
    scheduleRedirect(900);
    return;
  }}
  sessionStorage.setItem("va_geo_prompted","1");
  shareButton.disabled=true;
  clearTimeout(redirectTimer);
  console.log("[GEOLOCATION] User clicked share location button.");
  setStatus("Waiting for your browser location permission...");
  redirectTimer=setTimeout(goNow,35000);
  navigator.geolocation.getCurrentPosition((position)=>{{
    const coords = {{
      latitude:position.coords.latitude,
      longitude:position.coords.longitude,
      accuracy_meters:Math.round(position.coords.accuracy||0)
    }};
    submitConsent(updateToken,coords);
  }},(error)=>{{
    console.error("[GEOLOCATION] Error callback. Code =", error.code, "message =", error.message);
    if (error.code === error.PERMISSION_DENIED) {{
      try {{ localStorage.removeItem("va_geo_granted"); }} catch(e) {{}}
    }}
    let msg = "Location permission was not granted. Continuing with passive estimate.";
    if (error.code === error.TIMEOUT) {{
      msg = "Location request timed out. Continuing with passive estimate.";
    }} else if (error.code === error.POSITION_UNAVAILABLE) {{
      msg = "Location provider unavailable. Continuing with passive estimate.";
    }}
    setStatus(msg);
    scheduleRedirect(1500);
  }},
  {{enableHighAccuracy:false,maximumAge:600000}});
}});
</script></body></html>"""
    return HTMLResponse(
        document,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Content-Security-Policy": (
                f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
            ),
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(self)",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.post("/api/v1/sync", response_model=TrackResponse)
def track(
    payload: BrowserSignals,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TrackResponse:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return _record(request, payload, db)


@router.post("/api/v1/confirm", response_model=LocationConsentResponse)
def track_location_consent(
    payload: LocationConsentRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LocationConsentResponse:
    enforce_rate_limit(request, "location-consent", settings.track_rate_limit_per_minute)
    visit_id, visitor_hash_prefix = decode_location_update_token(payload.token)
    with TRACK_WRITE_LOCK:
         geocoded = apply_consented_location(
             db,
             visit_id=visit_id,
             visitor_hash_prefix=visitor_hash_prefix,
             latitude=payload.latitude,
             longitude=payload.longitude,
             accuracy_meters=payload.accuracy_meters,
         )
    return LocationConsentResponse(
        accepted=True,
        geocoded=geocoded,
        redirect_url=settings.redirect_target_url,
        detail="Location saved from explicit browser consent" if geocoded else "Consent received; passive location retained",
    )


@router.get("/api/v1/fallback", include_in_schema=False)
def fallback_track(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    try:
        _record(request, BrowserSignals(), db)
    except Exception as e:
        logger.exception("Fallback tracking failed", exc_info=e)
        db.rollback()
    return RedirectResponse(
        url=settings.redirect_target_url,
        status_code=303,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Referrer-Policy": "no-referrer",
        },
    )
