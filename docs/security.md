# Security and privacy

## Data boundary

The platform intentionally stores no username, email, password from visitors,
Instagram account identifier, or IP address. The admin password is represented
by an Argon2 hash. GeoIP sees an address only in memory during the request.
Rate-limit keys are secret-key HMACs and live only in process memory.
Nginx and Uvicorn request access logs are disabled so they do not create a
second, accidental store of visitor addresses.

The anonymous fingerprint combines User-Agent, accept headers, language,
timezone, platform, and screen resolution. HMAC prevents an offline observer
from trivially enumerating raw combinations. Changing `FINGERPRINT_SECRET`
breaks continuity, which is useful when intentionally resetting identity
history.

Fingerprinting has unavoidable false positives and false negatives. Browser
updates, privacy settings, and shared devices can change or collide. The UI
therefore calls values anonymous visitor IDs, never people.

## Controls

- Single-admin JWT session, HS256 audience/issuer checks, HttpOnly,
  `SameSite=Strict`, and production-only `Secure` cookies
- Argon2 password hashing via `pwdlib`
- Nginx and application-level rate limits
- Pydantic input limits and SQLAlchemy-bound queries
- Trusted host validation and explicit proxy trust
- CSP on the public redirect page and secure response headers
- Generic external errors with server-side exception logging
- Login/logout audit records without source addresses
- Containers run as non-root with `no-new-privileges` where practical

## Deployment checklist

1. Use independent 32-byte-or-longer JWT and fingerprint secrets.
2. Store only `ADMIN_PASSWORD_HASH`; remove `ADMIN_PASSWORD`. In Docker env
   files, paste the Argon2 value without quotes.
3. Enable HTTPS and set `PUBLIC_BASE_URL` to the exact HTTPS origin.
4. Restrict Google Cloud firewall ingress to TCP 22, 80, and 443.
5. Keep backend/frontend ports unpublished.
6. Protect `.env`, backups, and GeoLite2 license/download credentials.
7. Apply OS and container updates regularly.
8. Test backup restoration quarterly.

ASN organization-name classification cannot reliably prove that traffic is a
VPN, proxy, residential subscriber, or corporation. Labels ending in
“Candidate” are indicators only. No attempt is made to bypass such services.
