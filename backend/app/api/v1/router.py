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

v1_router = APIRouter()

v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
v1_router.include_router(users_router, prefix="/users", tags=["Users"])
v1_router.include_router(teams_router, prefix="/teams", tags=["Teams"])
v1_router.include_router(social_router, prefix="/social", tags=["Social"])



