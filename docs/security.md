# Security and Privacy Architecture

This document details the privacy boundaries, threat mitigation strategies, and security controls built into the platform.

---

## 1. Visitor Privacy Boundaries
The platform is designed to respect visitor privacy and comply with GDPR, CCPA, and regional policies:
* **No IP Address Storage**: Visitor IP addresses are processed entirely in-memory to look up GeoIP records, run DNS PTR parsing, or calculate sliding-window device rates. They are **never** written to database disk logs, application standard output, or nginx proxy logs.
* **No Profile/Identity Collection**: The platform does **not** query the Instagram API, scrape account names, or link visits to social media handles.
* **HMAC Anonymous Fingerprinting**: Repeated visits are identified by generating a `sha256` hash of browser parameters (User-Agent, languages, timezone, platform, and screen resolution) salted with a secure server-side `FINGERPRINT_SECRET`.
  * Because the hash is salted, an offline attacker with access to the database cannot reverse-engineer or enumerate visitor parameters.
  * To reset all visitor logs and start fresh, simply change `FINGERPRINT_SECRET` in `.env`.

---

## 2. Advanced Telemetry and Anti-Spoofing Heuristics

### A. Hardware Signature Hashing
The system computes an offline hardware signature using:
* **Offscreen Canvas Hashing**: Draws text and geometric patterns offscreen and hashes the resulting pixel data using a quick 128-bit Cyrb128 hash. If a client attempts to block or return blank canvas renders (common in bot environments), the system flags `"missing_canvas_fingerprint"`.
* **WebGL Signature**: Queries WebGL extension support, device capabilities, and renderer parameters to yield a highly stable signature without triggering GPU resource exhaustion or shader leaks.

### B. Device Fingerprint Collision (Proxy Rotation)
To flag scrapers utilizing rotating IP addresses or VPN proxies, the platform tracks the number of unique IPs associated with a hardware signature in a sliding 15-minute window:
* A **Device Collision 🚨** anomaly is triggered only if a single hardware hash is seen across **$\ge 3$ unique IP addresses** (or $\ge 2$ different ASNs) within 15 minutes.
* This high threshold prevents false-positive alerts when a legitimate user roams from home Wi-Fi to cellular mobile data.

### C. Stealth Honeypot Link Trap
* A hidden link is injected into the `/go` redirect template:
  ```html
  <a href="/api/v1/honeypot?v=NONCE" style="display:none;position:absolute;left:-9999px;top:-9999px;" aria-hidden="true" tabindex="-1" rel="nofollow">Security Verification Link</a>
  ```
* Standard web browsers and screen readers ignore the link because of CSS placement, `aria-hidden="true"`, and `tabindex="-1"`.
* Scraper bots and scrapers parsing raw HTML will read and follow the link. If triggered, the backend marks the visitor's log as anomalous (`"honeypot_triggered"`) and stealthily redirects them to the fallback target using a `307 Temporary Redirect` (keeping the security mechanism invisible).

---

## 3. Platform Security Controls
* **Authentication**: Single-admin console protected by `Argon2` password hashing (using `pwdlib`) and JSON Web Tokens (JWT) signed with `HS256`.
* **Secure Cookies**: HttpOnly, `SameSite=Strict`, and `Secure` (production-only) cookies store the admin session.
* **Rate Limiting**: Sliding-window rate limiters prevent brute-force attacks on `/api/v1/auth/login` and spam on `/api/v1/sync`. Limit keys are hashed locally in memory.
* **Input Validation**: Bounded inputs processed via Pydantic schemas prevent payload injection attacks.
* **Database Optimization**: SQLite parameters ensure that deleted visit logs shrink the database file immediately (`PRAGMA incremental_vacuum`) to prevent storage overflow.
* **Container Isolation**: Multi-container stack where all services run as non-root system users (`USER app` / `USER nextjs`) with `no-new-privileges` constraints enabled.
