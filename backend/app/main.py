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

Milestone 2 — Publishing & Scheduling Engine:
  - Content scheduling (Phase 1)
  - Publishing calendar (Phase 2)
  - Draft post lifecycle (Phase 3)
  - Recurring posts with daily/weekly/monthly rules (Phase 4)
  - Multi-platform publishing adapters — LinkedIn, Facebook, Instagram, X, YouTube, Pinterest (Phase 5)
  - Automated scheduled publishing via Celery Beat (Phase 6)
  - Async Celery publishing workers (Phase 7)
  - Publishing queue with retry & exponential backoff (Phase 8)
  - Publishing logs & audit trail with filtering + pagination (Phase 9)
  - End-to-end integration verified — 105/105 tests passing (Phase 10)
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
    import sys
    import os
    import logging
    logger = logging.getLogger("uvicorn.error")
    is_test = "pytest" in sys.modules or os.environ.get("TESTING") == "1"

    # ── MongoDB: connect client & init indexes ──────────────────────────
    connect_mongodb()
    try:
        from app.db.mongodb import get_mongo_db, init_mongodb_indexes
        mongo_db = get_mongo_db()
        if mongo_db is not None and not is_test:
            import asyncio
            asyncio.create_task(init_mongodb_indexes(mongo_db))
    except Exception as mongo_idx_exc:
        logger.warning("Could not schedule MongoDB index creation: %s", mongo_idx_exc)

    # ── PostgreSQL & background services (non-test only) ─────────────
    if not is_test:
        def _init_db():
            try:
                from app.db.base_all import Base  # noqa: F401 — imports Base + all models
                from app.db.session import engine
                Base.metadata.create_all(bind=engine)
                logger.info("✅ PostgreSQL tables verified / created.")
            except Exception as exc:
                logger.warning(f"⚠️  PostgreSQL connection warning: {exc}")

        import asyncio
        asyncio.create_task(asyncio.to_thread(_init_db))

        # ── Automated Background Scheduler (Managed via Celery Beat & Worker) ──
        if settings.ENABLE_INPROCESS_SCHEDULER:
            try:
                from app.services.publishing.scheduler import start_scheduler, stop_scheduler
                start_scheduler(interval_seconds=15)
                logger.info("✅ Automated Publishing Scheduler active (in-process fallback, 15s interval).")
            except Exception as exc:
                logger.warning(f"⚠️  Could not initialize in-process publishing scheduler: {exc}")
        else:
            logger.info("ℹ️  In-process scheduler disabled. Celery Beat + Celery Worker handle scheduled publishing.")

        # ── IPv6 Localhost Bridge for Windows OpenSSH / Pinggy tunnels ────────
        ipv6_server = None
        try:
            async def _handle_ipv6_client(reader, writer):
                try:
                    target_reader, target_writer = await asyncio.open_connection("127.0.0.1", 8000)
                except Exception:
                    writer.close()
                    return
                async def _pipe(src, dst):
                    try:
                        while True:
                            data = await src.read(4096)
                            if not data:
                                break
                            dst.write(data)
                            await dst.drain()
                    except Exception:
                        pass
                    finally:
                        try:
                            dst.close()
                        except Exception:
                            pass
                asyncio.create_task(_pipe(reader, target_writer))
                asyncio.create_task(_pipe(target_reader, writer))

            ipv6_server = await asyncio.start_server(_handle_ipv6_client, "::1", 8000)
            logger.info("✅ IPv6 localhost bridge active on [::1]:8000 -> 127.0.0.1:8000.")
        except Exception as exc:
            logger.debug("IPv6 bridge not started: %s", exc)

    yield  # ── Application running ──

    # ── Shutdown: stop scheduler if active and close MongoDB client ─────
    if not is_test:
        if ipv6_server is not None:
            try:
                ipv6_server.close()
                await ipv6_server.wait_closed()
            except Exception:
                pass
        if settings.ENABLE_INPROCESS_SCHEDULER:
            try:
                from app.services.publishing.scheduler import stop_scheduler
                stop_scheduler()
            except Exception:
                pass
    disconnect_mongodb()


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "SocialPilot — Social Media Scheduler & Publishing Platform.\n\n"
        "**Milestone 1:** Authentication + Account Management Foundation.\n"
        "**Milestone 2:** Content Scheduling, Calendar, Drafts, Recurring Posts, "
        "Multi-Platform Publishing, Async Queue with Retry, Publishing Logs & End-to-End Integration."
    ),
    version="2.0.0",
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
        "version": "2.0.0",
        "milestone": 2,
        "mongodb_configured": settings.mongodb_configured,
    }
