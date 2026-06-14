# Private Visitor Analytics

A privacy-preserving, self-hosted visitor analytics platform for custom bio links (e.g. Instagram). It records visits, estimates coarse location, performs bot/spoof analysis, and provides a real-time admin dashboard.

This platform is designed to be **completely free to host indefinitely** on cloud free tiers (like GCP's `e2-micro` in US regions with a 30 GB standard disk).

---

## Key Features & Heuristics

### 1. Multi-Candidate Location Inference
Instead of relying on single IP geolocation lookups, this platform scores and ranks location candidates from multiple independent sources:
* **Passive GeoIP (GeoLite2)**: Local MaxMind databases.
* **ISP Name Parsing**: Matches physical city markers inside the network organization name.
* **Reverse DNS Pointer (rDNS) Parsing**: Runs non-blocking background DNS PTR lookups to parse regional/circle keywords (e.g., `pune`, `kochi`, `delhi`) directly from router hostnames.
* **Latency Triangulation**: Measures round-trip time (RTT) from the browser to 8 Indian regional servers using an optimized Keep-Alive connection (discards first TCP handshake, averages 2nd/3rd pings). *(Can be persistently toggled ON/OFF from the dashboard)*.
* **Browser Geolocation API (Consented)**: Optional, explicit GPS coordinate lookup (the gold standard fallback if passive methods are insufficient).

### 2. Mobile Carrier Gateway Adjustments
Applies a confidence penalty (-20 city, -15 state) to passive GeoIP results for known cellular carriers (Jio, Airtel, Vi) because carrier networks dynamically route IPs through centralized metropolitan packet gateways, making passive databases highly inaccurate.

### 3. Anti-Spoofing & Bot Telemetry
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
