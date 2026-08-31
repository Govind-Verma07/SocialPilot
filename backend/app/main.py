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
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(v1_router, prefix=settings.API_V1_PREFIX)


# ---------------------------------------------------------------------------
# Root health-check
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
