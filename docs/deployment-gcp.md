# Google Cloud Compute Engine deployment

## VM

Use a small Ubuntu LTS VM (for example, an e2-small when available) with a
static external IP and at least 15 GB of persistent disk. Point an A/AAAA DNS
record at the static IP. Allow inbound TCP 22 from your administration address
and TCP 80/443 from the internet.

## Install

```bash
sudo bash scripts/setup-ubuntu.sh
sudo usermod -aG docker "$USER"
newgrp docker
cp .env.example .env
chmod 600 .env
```

Configure `.env`, including:

```dotenv
APP_ENV=production
DOMAIN=analytics.example.com
PUBLIC_BASE_URL=https://analytics.example.com
TRUSTED_HOSTS=analytics.example.com
REDIRECT_TARGET_URL=https://www.instagram.com/your_profile/
```

Generate independent secrets with `openssl rand -hex 32`. Generate an Argon2
password hash:

```bash
docker compose run --rm backend python -m app.cli
```

Paste the result without quotes, such as `ADMIN_PASSWORD_HASH=$argon2...`, and
remove `ADMIN_PASSWORD`. Download
GeoLite2 City and ASN from your MaxMind account into `./geoip/`. MaxMind
requires a free account and license acceptance; do not commit the databases.

## TLS and startup

Obtain the initial certificate before starting Nginx:

```bash
sudo certbot certonly --standalone -d analytics.example.com
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Test automatic renewal:

```bash
sudo certbot renew --dry-run
```

Add a root cron entry to reload Nginx after renewal:

```cron
15 3 * * * certbot renew --quiet --deploy-hook "docker compose -f /opt/visitor-analytics/docker-compose.yml -f /opt/visitor-analytics/docker-compose.prod.yml exec -T nginx nginx -s reload"
```

## Operations

```bash
docker compose ps
docker compose logs --tail=100 backend
docker compose pull
bash scripts/deploy.sh
```

Use `https://analytics.example.com/go` as the Instagram bio link. Verify a test
visit, the redirect, dashboard confidence labels, backup creation, and restore
procedure before relying on the installation.

Official references: [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/),
[Compute Engine](https://cloud.google.com/compute/docs/instances),
[Certbot](https://certbot.eff.org/), and
[GeoLite2](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data).
