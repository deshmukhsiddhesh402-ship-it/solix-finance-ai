"""Centralized configuration. Production secrets must come from environment variables."""
from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import List
from urllib.parse import urlparse


class Settings(BaseSettings):
    # Require an explicit environment so an unset deployment cannot silently run as development.
    ENV: str
    # Returning a development OTP is opt-in; never enable this in a deployed environment.
    DEV_OTP_ENABLED: bool = False
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    DATABASE_URL: str = "postgresql://solix:solix@localhost:5432/solix_finance_ai"
    REDIS_URL: str = "redis://localhost:6379/0"
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    VOYAGE_API_KEY: str = ""
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7

    @model_validator(mode="after")
    def require_production_secrets(self):
        environment = self.ENV.strip().lower()
        if environment not in {"dev", "development", "test", "staging", "prod", "production"}:
            raise ValueError("ENV must be one of dev, development, test, staging, prod, or production.")
        if environment in {"staging", "prod", "production"}:
            # Staging must exercise the same deployment-secret and CORS safeguards as production.
            if self.DEV_OTP_ENABLED:
                raise ValueError("DEV_OTP_ENABLED must be false in staging and production.")
            normalized_secret = self.JWT_SECRET.strip()
            if normalized_secret.lower() in {"", "change-me-in-production", "secret", "changeme", "your_secret_key"} or len(normalized_secret) < 32:
                raise ValueError("Staging and production require a non-placeholder JWT_SECRET of at least 32 characters.")
            if self.DATABASE_URL.strip() == "postgresql://solix:solix@localhost:5432/solix_finance_ai":
                raise ValueError("Staging and production require an explicitly configured DATABASE_URL.")
            if not self.ALLOWED_ORIGINS or any(not origin.strip() or origin.strip() == "*" for origin in self.ALLOWED_ORIGINS):
                raise ValueError("Staging and production require explicit ALLOWED_ORIGINS.")
            seen_origins = set()
            for origin in self.ALLOWED_ORIGINS:
                normalized_origin = origin.strip()
                parsed = urlparse(normalized_origin)
                if (
                    parsed.scheme not in {"http", "https"}
                    or not parsed.hostname
                    or parsed.username is not None
                    or parsed.password is not None
                    or parsed.path not in {"", "/"}
                    or parsed.params
                    or parsed.query
                    or parsed.fragment
                    or parsed.port == 0
                ):
                    raise ValueError("Staging and production ALLOWED_ORIGINS must be valid HTTP(S) origins without credentials, paths, queries, or fragments.")
                if parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
                    raise ValueError("Staging and production ALLOWED_ORIGINS cannot use localhost.")
                if normalized_origin.rstrip("/").lower() in seen_origins:
                    raise ValueError("Staging and production ALLOWED_ORIGINS must not contain duplicates.")
                seen_origins.add(normalized_origin.rstrip("/").lower())
        if self.JWT_ALGORITHM not in {"HS256", "HS384", "HS512"}:
            raise ValueError("JWT_ALGORITHM must be one of HS256, HS384, or HS512.")
        if self.JWT_EXPIRE_MINUTES <= 0 or self.JWT_EXPIRE_MINUTES > 60 * 24 * 7:
            raise ValueError("JWT_EXPIRE_MINUTES must be between 1 minute and 7 days.")
        return self

    class Config:
        env_file = ".env"


settings = Settings()
