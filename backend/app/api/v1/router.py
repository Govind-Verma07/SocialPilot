"""
api/v1/router.py
----------------
Root router for API version 1.
All sub-routers for each feature area are registered here.

Milestone 1 — Authentication Foundation:
  - /auth  → register, login, me, logout
"""

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.teams import router as teams_router
from app.api.v1.endpoints.social import router as social_router
from app.api.v1.endpoints.posts import (
    router as posts_router,
    get_calendar_posts,
    get_draft_posts,
    get_scheduled_posts,
)
from app.api.v1.endpoints.recurring_posts import router as recurring_posts_router
from app.schemas.post import PostListResponse

v1_router = APIRouter()

v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
v1_router.include_router(users_router, prefix="/users", tags=["Users"])
v1_router.include_router(teams_router, prefix="/teams", tags=["Teams"])
v1_router.include_router(social_router, prefix="/social", tags=["Social"])
v1_router.include_router(posts_router, prefix="/posts", tags=["Posts"])
v1_router.include_router(recurring_posts_router, prefix="/recurring-posts", tags=["Recurring Posts"])

# Compatibility aliases
v1_router.include_router(recurring_posts_router, prefix="/recurring", tags=["Recurring Posts Alias"])
v1_router.add_api_route("/calendar", get_calendar_posts, methods=["GET"], response_model=PostListResponse, tags=["Calendar Alias"])
v1_router.add_api_route("/drafts", get_draft_posts, methods=["GET"], response_model=PostListResponse, tags=["Drafts Alias"])
v1_router.add_api_route("/scheduled", get_scheduled_posts, methods=["GET"], response_model=PostListResponse, tags=["Scheduled Alias"])





