# Private Visitor Analytics

A privacy-preserving, self-hosted visitor analytics platform for custom bio links (e.g. Instagram). It records visits, estimates coarse location, performs bot/spoof analysis, and provides a real-time admin dashboard.
---

## Key Features & Heuristics

### 1. Multi-Candidate Location Inference
Instead of relying on single IP database queries, this platform generates, scores, and resolves location candidates from multiple independent sources:
* **Passive GeoIP (GeoLite2)**: Uses local MaxMind databases to resolve the client's IP to country, state, and city. It acts as the baseline candidate, initializing confidence scores based on database accuracy.
* **ISP Name Parsing**: Analyzes the organization/ISP string from the IP lookup. Many local broadband and cable providers embed regional names (e.g., "Kochi Cable", "Bengaluru Broadband") directly inside their ISP registration. If matched, it generates a high-confidence candidate.
* **Reverse DNS Pointer (rDNS) Parsing**: Runs a non-blocking DNS PTR lookup in a separate background thread with a strict 1.0-second timeout limit. Many telecom routers embed regional/circle tags (e.g., `pune`, `kochi`, `delhi`, `kar`) directly inside their hostnames. If matched, it generates a location candidate with a city confidence of 85.
* **Latency Triangulation**: Measures round-trip time (RTT) from the visitor's browser to 8 regional Indian endpoints (AWS Mumbai, AWS Hyderabad, AWS Delhi, IISc Bangalore, IIT Madras, CUSAT Kochi, NITK Surathkal, and ISI Kolkata). The client runs three consecutive fetches: the first warms up the TCP/TLS connection, and the 2nd/3rd are averaged (reusing HTTP Keep-Alive) to find the closest server. This is used as a last resort fallback if other passive methods have low confidence ($<50$). *(Can be persistently toggled ON/OFF from the dashboard settings)*.
* **Browser Geolocation API (Consented)**: Request-level browser coordinate capture. Bypasses passive estimation and uses reverse geocoding to resolve exact city, state, and country coordinates with high confidence.

### 2. Classification and Identification System
* **HMAC-Based Visitor Hashing**: To uniquely identify returning browsers without storing PII (like IP addresses), the platform generates a unique signature combining the browser's User-Agent, language, timezone, platform, and screen resolution. This signature is hashed using SHA-256 and salted with a server-side `FINGERPRINT_SECRET`, protecting visitor privacy.
* **Scraper & Bot Classification**: Evaluates incoming requests against user-agent signatures, hosting provider ASN lists, data center IP ranges, and request telemetry. It classifies traffic into categories: `"Social Media Crawler"`, `"Search Engine Crawler"`, `"Security Scanner"`, `"Monitoring Service"`, or `"Known Bot"`, and isolates their logs from primary dashboard analytics.
* **Agreement & Conflict Scoring**: When multiple candidates are generated, the system checks for agreement. If candidates from different sources (e.g., GeoIP and rDNS) agree on the city, they receive confidence boosts (+8 city, +5 state). If they disagree, the passive GeoIP city confidence is penalized (-5 city) to favor the specialized parsed sources. The highest-scoring candidate wins the resolution.

### 3. Mobile Carrier Gateway Adjustments
Applies a confidence penalty (-20 city, -15 state) to passive GeoIP results for known cellular carriers (Jio, Airtel, Vi) because carrier networks dynamically route IPs through centralized metropolitan packet gateways, making passive databases highly inaccurate.

### 4. Anti-Spoofing & Bot Telemetry
* **Headless Browser Detection**: Flags software GPUs (SwiftShader, llvmpipe, Mesa) commonly used by headless scraper scripts.
* **GPU & OS Cross-Checking**: Detects emulators (e.g., an Intel GPU claiming to be an iOS device).
* **iOS Memory Protection**: Identifies emulated Safari browsers by checking if memory details are leaked (iOS devices block memory details to prevent fingerprinting).
* **Stealth Honeypot Trap**: Injects an invisible, keyboard-inaccessible link (`rel="nofollow"`). If a scraper/bot follows the link, the visit is flagged as anomalous and the scraper is stealthily redirected without interrupting the user.
* **Device Fingerprint Collision (Proxy Detection)**: Computes a unique hardware hash (`sha256` of canvas rendering + WebGL limits + screen resolution + cores + memory + language). If the same hardware signature visits from $\ge 3$ unique IPs or $\ge 2$ unique ASNs in 15 minutes, it flags a `"Device Collision 🚨"`.

---

## Quick Start (Local Development)

1. Copy `.env.example` to `.env` and configure your credentials.
2. Put `GeoLite2-City.mmdb` and `GeoLite2-ASN.mmdb` inside the `./geoip/` directory.
3. Start the application:
   ```bash
   docker compose up -d --build
   ```
4. Generate your production admin password hash:
   ```bash
   docker compose run --rm backend python -m app.cli hash-password
   ```
5. Place the generated Argon2 hash under `ADMIN_PASSWORD_HASH` in `.env` (and remove `ADMIN_PASSWORD` for safety).
6. Log in to the Admin Dashboard at `http://localhost`. Use `http://localhost/go` as the bio link.

---

## Documentation

For deep dives into project configuration and details:
* [docs/security.md](docs/security.md) — Security & Privacy Architecture (Visitor boundaries, encryption, HMAC rules).
* [docs/architecture.md](docs/architecture.md) — Multi-container docker stack, database schemas, and background daemons.
* [docs/deployment-gcp.md](docs/deployment-gcp.md) — Step-by-step guide to hosting on Compute Engine (including Duck DNS, SSL setup, and Docker Hub compilation pipelines).
