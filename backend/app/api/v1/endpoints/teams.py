"""
app/api/v1/endpoints/teams.py
------------------------------
Team / Workspace management endpoints for Milestone 1:
  GET    /api/v1/teams                       — list user's workspaces
  POST   /api/v1/teams                       — create a new workspace
  GET    /api/v1/teams/{team_id}             — get workspace details & members
  PATCH  /api/v1/teams/{team_id}             — rename workspace
  POST   /api/v1/teams/{team_id}/members     — add member by email
  PATCH  /api/v1/teams/{team_id}/members/{id} — update member role
  DELETE /api/v1/teams/{team_id}/members/{id} — remove member
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import TeamMemberRole
from app.models.team import Team, TeamMember
from app.models.user import User
from app.schemas.team import (
    TeamCreate,
    TeamMemberAdd,
    TeamMemberOut,
    TeamMemberRoleUpdate,
    TeamOut,
    TeamUpdate,
)
from app.services.auth_service import get_current_user

router = APIRouter()


def _build_member_out(member: TeamMember, db: Session) -> TeamMemberOut:
    user_record = db.query(User).filter(User.id == member.user_id).first()
    return TeamMemberOut(
        id=member.id,
        team_id=member.team_id,
        user_id=member.user_id,
        role=member.role if isinstance(member.role, TeamMemberRole) else TeamMemberRole(member.role),
        joined_at=member.joined_at,
        email=user_record.email if user_record else None,
        full_name=user_record.full_name if user_record else None,
    )


def _build_team_out(team: Team, current_user_id: str, db: Session) -> TeamOut:
    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    members_out = [_build_member_out(m, db) for m in members]
    return TeamOut(
        id=team.id,
        name=team.name,
        owner_id=team.owner_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        is_owner=(team.owner_id == current_user_id),
        member_count=len(members),
        members=members_out,
    )


def _get_user_membership(team_id: str, user_id: str, db: Session) -> TeamMember | None:
    return db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id,
    ).first()


# ---------------------------------------------------------------------------
# Workspace Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[TeamOut], status_code=status.HTTP_200_OK)
def list_teams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TeamOut]:
    """List all teams where the user is an owner or active member."""
    member_team_ids = db.query(TeamMember.team_id).filter(TeamMember.user_id == current_user.id).scalar_subquery()
    teams = db.query(Team).filter(
        (Team.owner_id == current_user.id) | (Team.id.in_(member_team_ids))
    ).distinct().all()

    return [_build_team_out(t, current_user.id, db) for t in teams]


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamOut:
    """Create a new team workspace and assign the creator as owner."""
    team = Team(
        name=payload.name.strip(),
        owner_id=current_user.id,
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    # Add owner as team_member
    owner_member = TeamMember(
        team_id=team.id,
        user_id=current_user.id,
        role=TeamMemberRole.owner.value,
    )
    db.add(owner_member)
    db.commit()

    return _build_team_out(team, current_user.id, db)


@router.get("/{team_id}", response_model=TeamOut, status_code=status.HTTP_200_OK)
def get_team(
    team_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamOut:
    """Retrieve team workspace details and member roster."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team workspace not found.")

    membership = _get_user_membership(team_id, current_user.id, db)
    if team.owner_id != current_user.id and not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this workspace.")

    return _build_team_out(team, current_user.id, db)


@router.patch("/{team_id}", response_model=TeamOut, status_code=status.HTTP_200_OK)
def update_team(
    team_id: str,
    payload: TeamUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamOut:
    """Rename team workspace (owner or admin only)."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team workspace not found.")

    membership = _get_user_membership(team_id, current_user.id, db)
    is_admin = membership and membership.role in [TeamMemberRole.owner.value, TeamMemberRole.admin.value]

    if team.owner_id != current_user.id and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only workspace owner/admin can rename the workspace.")

    if payload.name:
        team.name = payload.name.strip()
        db.commit()
        db.refresh(team)

    return _build_team_out(team, current_user.id, db)


# ---------------------------------------------------------------------------
# Team Members Endpoints
# ---------------------------------------------------------------------------

@router.post("/{team_id}/members", response_model=TeamMemberOut, status_code=status.HTTP_201_CREATED)
def add_team_member(
    team_id: str,
    payload: TeamMemberAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamMemberOut:
    """Add a registered user to the team workspace by email (owner or admin only)."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team workspace not found.")

    membership = _get_user_membership(team_id, current_user.id, db)
    is_admin = membership and membership.role in [TeamMemberRole.owner.value, TeamMemberRole.admin.value]

    if team.owner_id != current_user.id and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only workspace owner or admin can invite members.")

    target_user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No account found with email '{payload.email}'. The user must register first.",
        )

    existing_membership = _get_user_membership(team_id, target_user.id, db)
    if existing_membership:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This user is already a member of the workspace.")

    new_member = TeamMember(
        team_id=team.id,
        user_id=target_user.id,
        role=payload.role.value if hasattr(payload.role, "value") else str(payload.role),
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_member)

    return _build_member_out(new_member, db)


@router.patch("/{team_id}/members/{member_id}", response_model=TeamMemberOut, status_code=status.HTTP_200_OK)
def update_member_role(
    team_id: str,
    member_id: str,
    payload: TeamMemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamMemberOut:
    """Update a team member's role (workspace owner only)."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team workspace not found.")

    if team.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only workspace owner can change member roles.")

    target_member = db.query(TeamMember).filter(TeamMember.id == member_id, TeamMember.team_id == team_id).first()
    if not target_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found.")

    if target_member.user_id == team.owner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change the workspace owner's role.")

    target_member.role = payload.role.value if hasattr(payload.role, "value") else str(payload.role)
    db.commit()
    db.refresh(target_member)

    return _build_member_out(target_member, db)


@router.delete("/{team_id}/members/{member_id}", status_code=status.HTTP_200_OK)
def remove_team_member(
    team_id: str,
    member_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Remove a member from the workspace (owner/admin or self-removal)."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team workspace not found.")

    target_member = db.query(TeamMember).filter(TeamMember.id == member_id, TeamMember.team_id == team_id).first()
    if not target_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found.")

    if target_member.user_id == team.owner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the workspace owner.")

    # Permissions: Workspace owner, Admin, or the user removing themselves
    membership = _get_user_membership(team_id, current_user.id, db)
    is_admin = membership and membership.role in [TeamMemberRole.owner.value, TeamMemberRole.admin.value]
    is_self = target_member.user_id == current_user.id

    if team.owner_id != current_user.id and not is_admin and not is_self:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to remove this member.")

    db.delete(target_member)
    db.commit()

    return {"message": "Team member removed successfully."}
