"""
core/config.py
--------------
Centralised application settings loaded from the .env file.
Uses pydantic-settings so every value is type-validated at startup.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    # --- Application ---
    APP_ENV: str = "development"
    APP_NAME: str = "SocialPilot API"
    API_V1_PREFIX: str = "/api/v1"

    # --- Database (PostgreSQL via Supabase) ---
    DATABASE_URL: str

    # --- Database (MongoDB Atlas) ---
    MONGODB_URI: str = ""          # Optional — configured when Atlas is ready
    MONGODB_DB_NAME: str = "socialpilot"

    # --- JWT ---
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- CORS ---
    # Stored as a comma-separated string in .env; parsed into a list here.
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # --- Google OAuth (Sign in & Linking) ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # --- Social platform OAuth credentials (filled when approved) ---
    FACEBOOK_CLIENT_ID: str = ""
    FACEBOOK_CLIENT_SECRET: str = ""
    INSTAGRAM_CLIENT_ID: str = ""
    INSTAGRAM_CLIENT_SECRET: str = ""
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    X_CLIENT_ID: str = ""
    X_CLIENT_SECRET: str = ""
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    PINTEREST_CLIENT_ID: str = ""
    PINTEREST_CLIENT_SECRET: str = ""

    @property
    def allowed_origins_list(self) -> List[str]:
        """Return CORS origins as a Python list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def mongodb_configured(self) -> bool:
        """True only when a non-empty MongoDB URI is provided."""
        return bool(self.MONGODB_URI)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",   # silently ignore unknown vars (e.g. VITE_* frontend vars)
    )


# Single global instance — import this everywhere.
settings = Settings()
