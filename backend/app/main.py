"""
app/main.py
-----------
FastAPI application entry point for SocialPilot.

Milestone 1 — Authentication + Account Management Foundation:
  - FastAPI app created
  - CORS configured from environment variables
  - Versioned API router mounted at /api/v1
  - Health-check root endpoint
  - OpenAPI docs at /docs and /redoc
  - PostgreSQL tables verified on startup (Alembic handles migrations)
  - MongoDB client connected on startup / disconnected on shutdown
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.core.config import settings
from app.api.v1.router import v1_router
from app.db.mongodb import connect_mongodb, disconnect_mongodb


# ---------------------------------------------------------------------------
# Lifespan — replaces deprecated @app.on_event
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    import logging
    logger = logging.getLogger("uvicorn.error")

    # ── PostgreSQL: verify all tables exist ─────────────────────────────
    try:
        from app.db.base_all import Base  # noqa: F401 — imports Base + all models
        from app.db.session import engine
        Base.metadata.create_all(bind=engine)
        logger.info("✅ PostgreSQL tables verified / created.")
    except Exception as exc:
        logger.warning(
            f"⚠️  PostgreSQL connection failed at startup: {exc}\n"
            "    Auth endpoints will fail until the DB is reachable.\n"
            "    Check DATABASE_URL and ensure Supabase is not paused."
        )

    # ── MongoDB: connect client ─────────────────────────────────────────
    connect_mongodb()

    yield  # ── Application running ──

    # ── Shutdown: close MongoDB client ──────────────────────────────────
    disconnect_mongodb()


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "SocialPilot — Social Media Scheduler & Campaign Management Platform.\n\n"
        "**Current scope:** Milestone 1 — Authentication + Account Management Foundation."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Middleware
# Origins are loaded from ALLOWED_ORIGINS in .env — never hard-coded.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_origin_regex=r"https://.*\.run\.pinggy-free\.link|https://.*\.pinggy\.io|https://.*\.loca\.lt",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(v1_router, prefix=settings.API_V1_PREFIX)


# ---------------------------------------------------------------------------
# Root health-check & Public Legal Endpoints
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"])
async def root() -> dict:
    """Health-check endpoint — confirms the API is reachable."""
    return {
        "message": "SocialPilot API is running",
        "version": "0.1.0",
        "milestone": 1,
        "mongodb_configured": settings.mongodb_configured,
    }


_PRIVACY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Privacy Policy - SocialPilot</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      color: #1e293b;
      background-color: #f8fafc;
      margin: 0;
      padding: 40px 20px;
    }
    .container {
      max-width: 760px;
      margin: 0 auto;
      background: #ffffff;
      padding: 40px;
      border-radius: 12px;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
    }
    h1 {
      color: #0f172a;
      margin-top: 0;
      font-size: 28px;
    }
    .updated {
      color: #64748b;
      font-size: 14px;
      margin-bottom: 24px;
      padding-bottom: 12px;
      border-bottom: 1px solid #e2e8f0;
    }
    p {
      margin-bottom: 16px;
    }
    a {
      color: #2563eb;
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Privacy Policy</h1>
    <div class="updated">Last Updated: September 2026</div>

    <p>SocialPilot is a social media management application developed for authorized users.</p>

    <p>SocialPilot uses OAuth authentication to connect users' social media accounts. SocialPilot does not collect or store users' social media passwords.</p>

    <p>When a user connects Pinterest, SocialPilot may access information authorized by the user through Pinterest OAuth, such as account and content information required for the application's functionality.</p>

    <p>OAuth access tokens are securely stored and are not exposed to the frontend.</p>

    <p>Users can disconnect their Pinterest account from SocialPilot at any time.</p>

    <p>For questions regarding this Privacy Policy, please contact: <a href="mailto:govind12022004@gmail.com">govind12022004@gmail.com</a></p>
  </div>
</body>
</html>
"""


@app.get("/privacy", tags=["Legal"], response_class=HTMLResponse)
@app.get("/policy", tags=["Legal"], response_class=HTMLResponse)
@app.get("/api/v1/privacy", tags=["Legal"], response_class=HTMLResponse)
@app.get("/api/v1/policy", tags=["Legal"], response_class=HTMLResponse)
async def privacy_policy():
    """Privacy Policy endpoint for OAuth app verification and legal compliance."""
    return HTMLResponse(content=_PRIVACY_HTML, status_code=200)
