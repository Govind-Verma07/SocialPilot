"""
app/schemas/team.py
-------------------
Pydantic schemas for Team and Team Member management.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

from app.models.enums import TeamMemberRole


class TeamMemberOut(BaseModel):
    id: str
    team_id: str
    user_id: str
    role: TeamMemberRole
    joined_at: datetime
    email: Optional[str] = None
    full_name: Optional[str] = None

    model_config = {"from_attributes": True}


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, examples=["Growth Marketing"])


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)


class TeamMemberAdd(BaseModel):
    email: EmailStr = Field(..., examples=["colleague@example.com"])
    role: TeamMemberRole = Field(default=TeamMemberRole.member, examples=["member"])


class TeamMemberRoleUpdate(BaseModel):
    role: TeamMemberRole = Field(..., examples=["admin", "member", "viewer"])


class TeamOut(BaseModel):
    id: str
    name: str
    owner_id: str
    created_at: datetime
    updated_at: datetime
    is_owner: bool = False
    member_count: int = 0
    members: List[TeamMemberOut] = []

    model_config = {"from_attributes": True}
