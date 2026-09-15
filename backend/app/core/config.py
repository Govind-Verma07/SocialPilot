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

    # --- Database (MongoDB Atlas & GridFS) ---
    MONGODB_URI: str = ""          # Optional — configured when Atlas is ready
    MONGODB_URL: str = ""          # Alias for MONGODB_URI
    MONGODB_DB_NAME: str = "socialpilot"
    MONGODB_DATABASE: str = ""     # Alias for MONGODB_DB_NAME

    # --- Media Upload & Public Serving Configuration ---
    MAX_MEDIA_UPLOAD_SIZE_BYTES: int = 250 * 1024 * 1024  # 250MB max file size
    PUBLIC_BASE_URL: str = ""        # Public HTTPS URL of the backend (e.g. Pinggy, Cloudflare, Render)
    BACKEND_PUBLIC_URL: str = ""     # Alias for PUBLIC_BASE_URL
    PUBLIC_MEDIA_BASE_URL: str = ""  # Public base URL for external platforms (Instagram, Pinterest)
    PINGGY_URL: str = ""             # Pinggy tunnel URL
    PINGGY_BASE_URL: str = ""        # Pinggy base URL alias
    RENDER_EXTERNAL_URL: str = ""    # Render deployment URL


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
    FACEBOOK_REDIRECT_URI: str = ""

    INSTAGRAM_CLIENT_ID: str = ""
    INSTAGRAM_CLIENT_SECRET: str = ""
    INSTAGRAM_REDIRECT_URI: str = ""
    INSTAGRAM_SCOPES: str = "instagram_business_basic,instagram_business_content_publish"

    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    LINKEDIN_REDIRECT_URI: str = ""

    X_CLIENT_ID: str = ""
    X_CLIENT_SECRET: str = ""
    X_REDIRECT_URI: str = ""

    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REDIRECT_URI: str = ""

    PINTEREST_CLIENT_ID: str = ""
    PINTEREST_CLIENT_SECRET: str = ""
    PINTEREST_REDIRECT_URI: str = ""

    # --- Redis & Celery Background Worker ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    ENABLE_INPROCESS_SCHEDULER: bool = True  # Enabled: automated publishing loop scans for due posts every 15s (cooperates atomically with Celery)

    # --- Phase 8: Publishing Queue & Retry ---
    MAX_PUBLISH_RETRIES: int = 3
    PUBLISH_RETRY_BACKOFF_SECONDS: str = "60,300,900"

    @property
    def allowed_origins_list(self) -> List[str]:
        """Return CORS origins as a Python list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def effective_mongodb_uri(self) -> str:
        """Return active MongoDB URI from either MONGODB_URL or MONGODB_URI."""
        return (self.MONGODB_URL or self.MONGODB_URI or "").strip()

    @property
    def effective_mongodb_database(self) -> str:
        """Return active MongoDB database name from either MONGODB_DATABASE or MONGODB_DB_NAME."""
        return (self.MONGODB_DATABASE or self.MONGODB_DB_NAME or "socialpilot").strip()

    @property
    def effective_public_media_base_url(self) -> str:
        """
        Return public HTTPS/HTTP base URL for serving media to external platforms (e.g. Instagram/Pinterest/Facebook).
        Prioritizes:
        1. PUBLIC_BASE_URL
        2. BACKEND_PUBLIC_URL
        3. PUBLIC_MEDIA_BASE_URL
        4. PINGGY_URL / PINGGY_BASE_URL
        5. RENDER_EXTERNAL_URL

        Never generates localhost or 127.0.0.1 for external social platforms.
        """
        candidates = [
            self.PUBLIC_BASE_URL,
            self.BACKEND_PUBLIC_URL,
            self.PUBLIC_MEDIA_BASE_URL,
            self.PINGGY_URL,
            self.PINGGY_BASE_URL,
            self.RENDER_EXTERNAL_URL,
        ]
        for cand in candidates:
            if cand and cand.strip():
                clean = cand.strip().rstrip("/")
                from urllib.parse import urlparse
                parsed = urlparse(clean) if "://" in clean else None
                netloc = parsed.netloc if parsed else clean
                host = netloc.split(":")[0].strip().lower()
                if host not in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
                    return clean

        # Safe fallback only for unit testing
        import sys, os
        if "pytest" in sys.modules or os.environ.get("TESTING") == "1" or self.APP_ENV == "testing":
            return "http://localhost:8000"

        return ""

    @property
    def mongodb_configured(self) -> bool:
        """True only when a non-empty MongoDB URI/URL is provided."""
        return bool(self.effective_mongodb_uri)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",   # silently ignore unknown vars (e.g. VITE_* frontend vars)
    )


# Single global instance — import this everywhere.
settings = Settings()
