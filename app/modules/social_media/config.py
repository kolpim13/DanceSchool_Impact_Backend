from functools import lru_cache
from urllib.parse import urlsplit
from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FACEBOOK_", env_file=".env", extra="ignore")
    page_id: str = Field(pattern=r"^\d+$")
    graph_version: str = Field(pattern=r"^v\d+\.\d+$")
    app_id: str = Field(pattern=r"^\d+$")
    app_secret: SecretStr
    token_encryption_key: SecretStr
    redirect_uri: str
    # Optional Facebook Login for Business configuration ID. Configure its permissions in Meta.
    login_config_id: str | None = Field(default=None, pattern=r"^\d+$")
    max_posts: int = Field(default=30, ge=1, le=500)
    max_scan_pages: int = Field(default=20, ge=1, le=100)
    token_check_seconds: int = Field(default=21600, ge=60)
    renew_before_seconds: int = Field(default=604800, ge=60)
    lock_path: str = "/tmp/impact-facebook-sync.lock"

    @field_validator("redirect_uri")
    @classmethod
    def require_https(cls, value):
        url = urlsplit(value)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment or url.query:
            raise ValueError("Use a fixed HTTPS URL without credentials, query or fragment")
        return value

    @field_validator("token_encryption_key")
    @classmethod
    def valid_key(cls, value):
        try:
            Fernet(value.get_secret_value().encode())
        except Exception:
            raise ValueError("Supply a Fernet key generated once and kept outside the database") from None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
