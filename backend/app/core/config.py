"""
Centralized configuration. All secrets come from environment variables —
never hardcode API keys. See ../.env.example for the full list.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # --- Core ---
    ENV: str = "development"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # --- Database ---
    DATABASE_URL: str = "postgresql://solix:solix@localhost:5432/solix_finance_ai"
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- AI ---
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    VOYAGE_API_KEY: str = ""  # optional — enables real semantic embeddings for RAG; falls back to TF-IDF if unset

    # --- Billing (Razorpay) ---
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # --- Auth ---
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    class Config:
        env_file = ".env"


settings = Settings()
