from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    public_base_url: str = "http://localhost"
    redirect_target_url: str = "https://www.instagram.com/"
    database_url: str = "sqlite:///./data/analytics.db"
    jwt_secret: str = "development-only-change-this-secret"
    fingerprint_secret: str = "development-only-fingerprint-secret"
    admin_username: str = "admin"
    admin_password_hash: str = ""
    admin_password: str = "change-me"
    access_token_minutes: int = 480
    raw_retention_days: int = 45
    backup_retention_count: int = 30
    backup_hour_utc: int = 2
    geoip_city_db: str = "./geoip/GeoLite2-City.mmdb"
    geoip_asn_db: str = "./geoip/GeoLite2-ASN.mmdb"
    disable_maxmind_db: bool = False
    disable_latency_triangulation: bool = False
    maxmind_license_key: str | None = None
    use_external_geoip_api: bool = True
    reverse_geocoding_enabled: bool = True
    reverse_geocoding_url: str = "https://nominatim.openstreetmap.org/reverse"
    reverse_geocoding_user_agent: str = "visitor-analytics-personal/1.0"
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
    forwarded_allow_ips: str = "127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,*"
    login_rate_limit_per_minute: int = 5
    track_rate_limit_per_minute: int = 30

    @field_validator("public_base_url")
    @classmethod
    def validate_public_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("must be an absolute HTTP(S) URL")
        if any(ord(char) < 32 for char in value):
            raise ValueError("URL contains control characters")
        return value.rstrip("/")

    @field_validator("redirect_target_url")
    @classmethod
    def validate_redirect_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("must be an absolute HTTP(S) URL")
        if any(ord(char) < 32 for char in value):
            raise ValueError("URL contains control characters")
        return value

    @property
    def trusted_host_list(self) -> list[str]:
        hosts = [item.strip() for item in self.trusted_hosts.split(",") if item.strip()]
        try:
            parsed = urlparse(self.public_base_url)
            if parsed.hostname and parsed.hostname not in hosts:
                hosts.append(parsed.hostname)
        except Exception:
            pass
        return hosts

    @property
    def forwarded_allow_ip_list(self) -> list[str]:
        return [item.strip() for item in self.forwarded_allow_ips.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def validate_production(self) -> None:
        if not self.is_production:
            return
        if (
            len(self.jwt_secret) < 32
            or len(self.fingerprint_secret) < 32
            or self.jwt_secret == self.fingerprint_secret
            or not self.admin_password_hash.startswith("$argon2")
        ):
            raise RuntimeError("Production requires independent 32+ character secrets and an Argon2 admin hash")

    def ensure_data_directory(self) -> None:
        if self.database_url.startswith("sqlite:///"):
            raw_path = self.database_url.removeprefix("sqlite:///")
            if raw_path != ":memory:":
                Path(raw_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
