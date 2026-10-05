"""Centralized configuration. Production secrets must come from environment variables."""
from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    ENV: str = "development"
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
        if self.ENV.strip().lower() in {"prod", "production"}:
            if self.JWT_SECRET == "change-me-in-production" or len(self.JWT_SECRET) < 32:
                raise ValueError("Production requires a JWT_SECRET of at least 32 characters.")
            if self.DATABASE_URL == "postgresql://solix:solix@localhost:5432/solix_finance_ai":
                raise ValueError("Production requires an explicitly configured DATABASE_URL.")
        if self.JWT_EXPIRE_MINUTES <= 0:
            raise ValueError("JWT_EXPIRE_MINUTES must be positive.")
        return self

    class Config:
        env_file = ".env"


settings = Settings()
