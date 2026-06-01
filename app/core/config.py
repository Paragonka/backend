from typing import Any

from dotenv import load_dotenv
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: SecretStr = Field(...)

    # Authentication
    secret_key: SecretStr = Field(...)
    access_token_expire_minutes: int = Field(60)
    refresh_token_expire_days: int = Field(30)
    reset_token_expire_minutes: int = Field(30)

    # Email (SMTP) - optional, for prod
    smtp_host: str = Field("")
    smtp_port: int = Field(587)
    smtp_user: str = Field("")
    smtp_password: SecretStr = Field(SecretStr(""))
    from_email: str = Field("noreply@paragonka.ru")

    # Database Pool
    db_pool_size: int = Field(5)
    db_pool_pre_ping: bool = Field(True)

    # Application
    environment: str = Field("development")
    log_level: str = Field("INFO")

    # Server
    HOST: str = Field("localhost")
    PORT: int = Field(8000)
    FRONTEND_URL: str = Field("http://localhost:8000")

    # Web UI toggle
    web_enabled: bool = Field(True)

    # Deprecated server-rendered HTML/HTMX routers. When False, every route in
    # the legacy web_router modules (and the /app + /lang redirects) returns 410
    # Gone; the SPA frontend and the JSON API remain the supported entry points.
    # Default False: these routes are deprecated and disabled out of the box.
    web_routers_enabled: bool = Field(False)

    # Feature flags
    # TODO: CSV feature - disabled by default (OFF). Enabling via
    # FEATURE_CSV=true activates the CSV import/export routes gated by
    # RequireFeatureCsv in app/shared/feature_flags.py.
    feature_csv: bool = Field(False)

    # Cookies
    cookie_secure: bool = Field(False)

    # CORS - origins allowed to call the API from a browser.
    # Env CORS_ORIGINS - comma-separated, e.g.
    # "http://localhost:5173,https://app.example.com".
    # Never set "*" together with allow_credentials=True.
    cors_origins: list[str] = Field(default=["http://localhost:5173"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]

        return v

    # S3
    s3_endpoint: str | None = Field(None)
    s3_access_key: str | None = Field(None)
    s3_secret_key: SecretStr | None = Field(None)
    s3_bucket: str | None = Field(None)
    s3_region: str | None = Field(None)

    @property
    def s3_enabled(self) -> bool:
        return all(
            [self.s3_endpoint, self.s3_access_key, self.s3_secret_key, self.s3_bucket]
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
        # Disables JSON decoding for complex fields from env: without this
        # CORS_ORIGINS="http://a,http://b" fails with SettingsError before
        # validators (pydantic-settings requires JSON for list types).
        enable_decoding=False,
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


load_dotenv()

settings = Settings()
