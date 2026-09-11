"""
core/config.py
--------------
Centralised application settings loaded from the .env file.
Uses pydantic-settings so every value is type-validated at startup.
"""

from pydantic import model_validator
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
    FRONTEND_URL: str = ""

    # --- Google OAuth (Sign in & Linking) ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # --- Social platform OAuth credentials (filled when approved) ---
    FACEBOOK_CLIENT_ID: str = ""
    FACEBOOK_CLIENT_SECRET: str = ""
    FACEBOOK_APP_ID: str = ""
    FACEBOOK_APP_SECRET: str = ""
    FACEBOOK_REDIRECT_URI: str = "http://localhost:8000/api/v1/social/oauth/facebook/callback"
    INSTAGRAM_CLIENT_ID: str = ""
    INSTAGRAM_CLIENT_SECRET: str = ""
    INSTAGRAM_APP_ID: str = ""
    INSTAGRAM_APP_SECRET: str = ""
    INSTAGRAM_REDIRECT_URI: str = "http://localhost:8000/api/v1/social/oauth/instagram/callback"
    INSTAGRAM_SCOPES: str = "instagram_business_basic,instagram_business_content_publish"
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    LINKEDIN_REDIRECT_URI: str = "http://localhost:8000/api/v1/social/oauth/linkedin/callback"
    LINKEDIN_SCOPES: str = "openid profile email w_member_social"
    X_CLIENT_ID: str = ""
    X_CLIENT_SECRET: str = ""
    X_REDIRECT_URI: str = "http://localhost:8000/api/v1/social/oauth/x/callback"
    X_SCOPES: str = "tweet.read tweet.write users.read offline.access"
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REDIRECT_URI: str = "http://localhost:8000/api/v1/social/oauth/youtube/callback"
    YOUTUBE_SCOPES: str = "https://www.googleapis.com/auth/youtube"
    PINTEREST_CLIENT_ID: str = ""
    PINTEREST_CLIENT_SECRET: str = ""

    @model_validator(mode="after")
    def sync_social_credentials(self) -> "Settings":
        if not self.FACEBOOK_CLIENT_ID and self.FACEBOOK_APP_ID:
            self.FACEBOOK_CLIENT_ID = self.FACEBOOK_APP_ID
        if not self.FACEBOOK_CLIENT_SECRET and self.FACEBOOK_APP_SECRET:
            self.FACEBOOK_CLIENT_SECRET = self.FACEBOOK_APP_SECRET
        if not self.INSTAGRAM_CLIENT_ID and self.INSTAGRAM_APP_ID:
            self.INSTAGRAM_CLIENT_ID = self.INSTAGRAM_APP_ID
        if not self.INSTAGRAM_CLIENT_SECRET and self.INSTAGRAM_APP_SECRET:
            self.INSTAGRAM_CLIENT_SECRET = self.INSTAGRAM_APP_SECRET
        if not self.YOUTUBE_CLIENT_ID and self.GOOGLE_CLIENT_ID:
            self.YOUTUBE_CLIENT_ID = self.GOOGLE_CLIENT_ID
        if not self.YOUTUBE_CLIENT_SECRET and self.GOOGLE_CLIENT_SECRET:
            self.YOUTUBE_CLIENT_SECRET = self.GOOGLE_CLIENT_SECRET
        return self

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


import os

_last_env_mtime: float = 0.0

# Single global instance — import this everywhere.
settings = Settings()
try:
    if os.path.exists(".env"):
        _last_env_mtime = os.path.getmtime(".env")
except Exception:
    pass


def get_settings() -> Settings:
    """
    Return settings instance, automatically refreshing if .env has been modified on disk.
    """
    global settings, _last_env_mtime
    try:
        env_file = ".env"
        if os.path.exists(env_file):
            current_mtime = os.path.getmtime(env_file)
            if current_mtime > _last_env_mtime:
                _last_env_mtime = current_mtime
                settings = Settings()
    except Exception:
        pass
    return settings


