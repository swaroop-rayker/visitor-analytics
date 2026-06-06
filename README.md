# Private Visitor Analytics

A privacy-preserving personal analytics platform for a custom Instagram bio
link. It records visits to the link, estimates coarse location with local
GeoLite2 databases, identifies likely repeat browsers using an HMAC-based
anonymous fingerprint, and exposes a single-admin dashboard.

It does **not** inspect Instagram profile views, collect account identities,
store IP addresses, or attempt to defeat VPNs and anonymity tools.

## Quick start

1. Copy `.env.example` to `.env` and replace every secret/default credential.
2. Put `GeoLite2-City.mmdb` and `GeoLite2-ASN.mmdb` in `./geoip/`.
3. Generate an admin hash with `docker compose run --rm backend python -m app.cli`,
   place it in `.env`, then run `docker compose up -d --build`.
4. Open `http://localhost`, sign in, and use `http://localhost/go` as the link.

GeoIP is optional. Tracking continues with an `Unknown` location and low
confidence if the databases are absent.

See [docs/architecture.md](docs/architecture.md),
[docs/api.md](docs/api.md), [docs/security.md](docs/security.md), and
[docs/deployment-gcp.md](docs/deployment-gcp.md).
