"""
app/api/v1/endpoints/recurring_posts.py
---------------------------------------
Endpoints for Phase 4: Recurring Posts.
Provides:
  POST   /recurring-posts       — Create a recurring post schedule and generate scheduled occurrences.
  GET    /recurring-posts       — List user's recurring rules.
  GET    /recurring-posts/{id}  — Retrieve a specific recurring rule and its generated occurrences.
  PUT    /recurring-posts/{id}  — Update or deactivate an existing recurring rule.
  DELETE /recurring-posts/{id}  — Delete a recurring rule and its future scheduled occurrences.
"""

from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import PostStatus, RecurrenceFrequency
from app.models.post import Post, PostSocialAccount
from app.models.recurring_rule import RecurringRule, RecurringRuleSocialAccount
from app.models.social_account import SocialAccount
from app.models.user import User
from app.schemas.post import PostResponse
from app.schemas.recurring_post import (
    RecurringPostCreate,
    RecurringPostUpdate,
    RecurringRuleResponse,
    RecurringRuleListResponse,
)
from app.services.auth_service import get_current_user
from app.services.recurrence_service import compute_occurrences, parse_weekday
from app.api.v1.endpoints.posts import _serialize_post

router = APIRouter()


def _serialize_recurring_rule(rule: RecurringRule, include_occurrences: bool = False, db: Optional[Session] = None) -> dict:
    """Helper to convert a RecurringRule ORM instance into response dict."""
    accounts = []
    for rsa in rule.social_accounts:
        acc = rsa.social_account
        if acc:
            platform_val = acc.platform.value if hasattr(acc.platform, "value") else str(acc.platform)
            status_val = acc.status.value if hasattr(acc.status, "value") else str(acc.status)
            accounts.append({
                "id": acc.id,
                "platform": platform_val,
                "account_name": acc.account_name,
                "account_username": acc.account_username,
                "status": status_val,
            })

    freq_val = rule.frequency.value if hasattr(rule.frequency, "value") else str(rule.frequency)

    occurrences_data = []
    total_posts = len(rule.posts) if rule.posts is not None else 0

    if include_occurrences and rule.posts:
        # Sort occurrences chronologically
        sorted_posts = sorted(rule.posts, key=lambda p: p.scheduled_at or p.created_at)
        occurrences_data = [_serialize_post(p) for p in sorted_posts]

    start_at = rule.start_at
    if start_at and start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=timezone.utc)
    end_at = rule.end_at
    if end_at and end_at.tzinfo is None:
        end_at = end_at.replace(tzinfo=timezone.utc)
    next_run_at = rule.next_run_at
    if next_run_at and next_run_at.tzinfo is None:
        next_run_at = next_run_at.replace(tzinfo=timezone.utc)

    return {
        "id": rule.id,
        "user_id": rule.user_id,
        "content": rule.content,
        "media_urls": rule.media_urls or [],
        "post_type": rule.post_type,
        "frequency": freq_val,
        "interval": rule.interval,
        "by_weekday": rule.by_weekday,
        "by_month_day": rule.by_month_day,
        "start_at": start_at,
        "end_at": end_at,
        "occurrence_limit": rule.occurrence_limit,
        "next_run_at": next_run_at,
        "is_active": rule.is_active,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
        "social_accounts": accounts,
        "generated_count": total_posts,
        "occurrences": occurrences_data,
    }



@router.post("", response_model=RecurringRuleResponse, status_code=status.HTTP_201_CREATED)
def create_recurring_rule(
    payload: RecurringPostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecurringRuleResponse:
    """
    Create a new recurring post schedule:
    1. Authenticates user and validates content, boundaries, and recurrence rules.
    2. Verifies ownership of selected social accounts.
    3. Calculates future occurrence dates safely (handling month-end dates and end bounds).
    4. Creates RecurringRule and links RecurringRuleSocialAccounts.
    5. Generates Post records in 'scheduled' status with PostSocialAccounts.
    6. Returns created recurring rule with all generated occurrences.
    """
    # 1. Ownership check: verify all selected accounts exist and belong to the user
    verified_accounts: List[SocialAccount] = []
    for acc_id in payload.social_account_ids:
        acc = db.query(SocialAccount).filter(SocialAccount.id == acc_id).first()
        if not acc or acc.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected social account is not available.",
            )
        verified_accounts.append(acc)

    # 2. Compute recurrence dates
    weekday_int = parse_weekday(payload.by_weekday) if payload.by_weekday is not None else None
    try:
        occurrences = compute_occurrences(
            start_at=payload.start_at,
            end_at=payload.end_at,
            frequency=payload.frequency,
            interval=payload.interval,
            by_weekday=weekday_int,
            by_month_day=payload.by_month_day,
            occurrence_limit=payload.occurrence_limit,
            max_safety_limit=100,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )

    if not occurrences:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No occurrences could be generated for the specified schedule range.",
        )

    try:
        # 3. Create RecurringRule record
        rule = RecurringRule(
            user_id=current_user.id,
            content=payload.content.strip(),
            media_urls=payload.media_urls or [],
            post_type=payload.post_type or "text",
            frequency=payload.frequency.lower(),
            interval=payload.interval,
            by_weekday=weekday_int,
            by_month_day=payload.by_month_day,
            start_at=payload.start_at,
            end_at=payload.end_at,
            occurrence_limit=payload.occurrence_limit,
            next_run_at=occurrences[0],
            is_active=True,
        )
        db.add(rule)
        db.flush()

        # 4. Attach social accounts to recurring rule
        for acc in verified_accounts:
            link = RecurringRuleSocialAccount(
                recurring_rule_id=rule.id,
                social_account_id=acc.id,
            )
            db.add(link)

        # 5. Generate scheduled Post records
        created_posts = []
        for occ_time in occurrences:
            post = Post(
                user_id=current_user.id,
                content=payload.content.strip(),
                media_urls=payload.media_urls or [],
                post_type=payload.post_type or "text",
                status=PostStatus.scheduled.value,
                scheduled_at=occ_time,
                recurring_rule_id=rule.id,
            )
            db.add(post)
            db.flush()

            for acc in verified_accounts:
                psa = PostSocialAccount(
                    post_id=post.id,
                    social_account_id=acc.id,
                )
                db.add(psa)
            created_posts.append(post)

        db.commit()
        db.refresh(rule)

        return RecurringRuleResponse(**_serialize_recurring_rule(rule, include_occurrences=True, db=db))

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to create recurring schedule: {str(exc)}",
        ) from exc



@router.get("", response_model=RecurringRuleListResponse, status_code=status.HTTP_200_OK)
def list_recurring_rules(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecurringRuleListResponse:
    """Retrieve recurring rules belonging to the authenticated user."""
    query = db.query(RecurringRule).filter(RecurringRule.user_id == current_user.id)

    if is_active is not None:
        query = query.filter(RecurringRule.is_active == is_active)

    total = query.count()
    rules = (
        query.order_by(RecurringRule.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return RecurringRuleListResponse(
        items=[RecurringRuleResponse(**_serialize_recurring_rule(r, include_occurrences=False, db=db)) for r in rules],
        total=total,
    )


@router.get("/{rule_id}", response_model=RecurringRuleResponse, status_code=status.HTTP_200_OK)
def get_recurring_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecurringRuleResponse:
    """Retrieve a single recurring rule with all generated occurrences and ownership check."""
    rule = db.query(RecurringRule).filter(RecurringRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring rule not found.",
        )

    if rule.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this recurring rule.",
        )

    return RecurringRuleResponse(**_serialize_recurring_rule(rule, include_occurrences=True, db=db))


@router.put("/{rule_id}", response_model=RecurringRuleResponse, status_code=status.HTTP_200_OK)
def update_recurring_rule(
    rule_id: str,
    payload: RecurringPostUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecurringRuleResponse:
    """
    Update or deactivate/activate an existing recurring rule.
    If deactivating (is_active=False), updates status.
    If updating content or social accounts, modifies template and future scheduled posts.
    """
    rule = db.query(RecurringRule).filter(RecurringRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring rule not found.",
        )

    if rule.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this recurring rule.",
        )

    if payload.is_active is not None:
        rule.is_active = payload.is_active

    if payload.content is not None and payload.content.strip():
        rule.content = payload.content.strip()
        # Also update future scheduled posts generated by this rule
        now = datetime.now(timezone.utc)
        future_posts = db.query(Post).filter(
            Post.recurring_rule_id == rule.id,
            Post.status == PostStatus.scheduled.value,
            Post.scheduled_at > now,
        ).all()
        for fp in future_posts:
            fp.content = rule.content

    if payload.end_at is not None:
        rule.end_at = payload.end_at

    if payload.post_type is not None:
        rule.post_type = payload.post_type

    if payload.media_urls is not None:
        rule.media_urls = payload.media_urls

    if payload.social_account_ids is not None:
        # Verify accounts
        verified_accounts = []
        for aid in payload.social_account_ids:
            acc = db.query(SocialAccount).filter(SocialAccount.id == aid).first()
            if not acc or acc.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected social account is not available.",
                )
            verified_accounts.append(acc)

        db.query(RecurringRuleSocialAccount).filter(RecurringRuleSocialAccount.recurring_rule_id == rule.id).delete()
        for acc in verified_accounts:
            db.add(RecurringRuleSocialAccount(recurring_rule_id=rule.id, social_account_id=acc.id))

    rule.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rule)

    return RecurringRuleResponse(**_serialize_recurring_rule(rule, include_occurrences=True, db=db))


@router.delete("/{rule_id}", status_code=status.HTTP_200_OK)
def delete_recurring_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Delete a recurring rule and its generated scheduled posts.
    Enforces user ownership isolation.
    """
    rule = db.query(RecurringRule).filter(RecurringRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring rule not found.",
        )

    if rule.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this recurring rule.",
        )

    # Delete scheduled posts created by this recurring rule
    db.query(Post).filter(
        Post.recurring_rule_id == rule.id,
        Post.status == PostStatus.scheduled.value,
    ).delete()

    db.delete(rule)
    db.commit()

    return {"message": "Recurring rule deleted successfully.", "id": rule_id}
