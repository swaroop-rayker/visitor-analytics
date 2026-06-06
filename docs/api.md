# API specification

Development OpenAPI is served at `/api/docs`. Interactive documentation is
disabled when `APP_ENV=production`.

## Public routes

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/go` | Privacy notice-free minimal redirect interstitial |
| `POST` | `/api/v1/track` | Record allowed browser signals and return redirect URL |
| `GET` | `/api/v1/track/fallback` | No-JavaScript tracking and redirect |
| `GET` | `/healthz` | Container liveness only |

`POST /api/v1/track` accepts optional `timezone`, `language`, `platform`, and
`screen_resolution` strings. Each is length-limited and control characters are
removed.

## Authentication

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Set signed JWT in an HttpOnly cookie |
| `POST` | `/api/v1/auth/logout` | Clear session |
| `GET` | `/api/v1/auth/session` | Validate current session |

## Admin analytics

| Method | Route | Key parameters |
|---|---|---|
| `GET` | `/api/v1/analytics/summary` | none |
| `GET` | `/api/v1/analytics/visitors` | page, city, state, returning, dates, confidence, sort |
| `GET` | `/api/v1/analytics/visits` | page, city, state, device, browser, dates, confidence |
| `GET` | `/api/v1/analytics/trends` | period: daily/weekly/monthly, days |
| `GET` | `/api/v1/analytics/locations/{city\|state}` | limit |
| `GET` | `/api/v1/analytics/location-trends` | group_by, days, limit |
| `GET` | `/api/v1/analytics/frequency` | none |
| `GET` | `/api/v1/analytics/retention` | none |
| `GET` | `/api/v1/system/health` | none |

All admin routes require the `access_token` cookie. Pagination is capped at 100
rows. SQLAlchemy parameter binding is used throughout.
