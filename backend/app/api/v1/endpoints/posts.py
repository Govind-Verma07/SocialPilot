"""
app/api/v1/endpoints/posts.py
-----------------------------
Endpoints for Phase 1: Content Scheduling Foundation.
Provides:
  POST /posts       — Create and schedule a new post with associated social accounts.
  GET  /posts       — List user's scheduled and published posts.
  GET  /posts/{id}  — Retrieve a specific post by ID with ownership verification.
  DELETE /posts/{id}— Delete a scheduled post.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import PostStatus
from app.models.post import Post, PostSocialAccount
from app.models.publishing_log import PublishingLog
from app.models.social_account import SocialAccount
from app.models.user import User
from app.schemas.post import (
    PostCreate,
    PostUpdate,
    PostResponse,
    PostListResponse,
    AttachedSocialAccount,
    PublishingLogResponse,
    PublishingLogListResponse,
)
from app.services.auth_service import get_current_user

router = APIRouter()


def _serialize_post(post: Post) -> dict:
    """Helper to convert a Post ORM instance into response dict."""
    accounts = []
    for psa in post.social_accounts:
        acc = psa.social_account
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

    post_status_val = post.status.value if hasattr(post.status, "value") else str(post.status)

    sched_at = post.scheduled_at
    if sched_at and sched_at.tzinfo is None:
        sched_at = sched_at.replace(tzinfo=timezone.utc)

    pub_at = post.published_at
    if pub_at and pub_at.tzinfo is None:
        pub_at = pub_at.replace(tzinfo=timezone.utc)

    results = []
    if hasattr(post, "publish_results") and post.publish_results:
        for pr in post.publish_results:
            p_at = pr.published_at
            if p_at and p_at.tzinfo is None:
                p_at = p_at.replace(tzinfo=timezone.utc)
            c_at = pr.created_at
            if c_at and c_at.tzinfo is None:
                c_at = c_at.replace(tzinfo=timezone.utc)
            results.append({
                "id": pr.id,
                "post_id": pr.post_id,
                "social_account_id": pr.social_account_id,
                "platform": pr.platform,
                "status": pr.status,
                "platform_post_id": pr.platform_post_id,
                "published_url": pr.published_url,
                "error_message": pr.error_message,
                "published_at": p_at,
                "created_at": c_at,
            })

    jobs = []
    if hasattr(post, "publishing_jobs") and post.publishing_jobs:
        for pj in post.publishing_jobs:
            nr_at = pj.next_retry_at
            if nr_at and nr_at.tzinfo is None:
                nr_at = nr_at.replace(tzinfo=timezone.utc)
            cr_at = pj.created_at
            if cr_at and cr_at.tzinfo is None:
                cr_at = cr_at.replace(tzinfo=timezone.utc)
            up_at = pj.updated_at
            if up_at and up_at.tzinfo is None:
                up_at = up_at.replace(tzinfo=timezone.utc)
            plat = None
            if pj.social_account:
                plat = pj.social_account.platform.value if hasattr(pj.social_account.platform, "value") else str(pj.social_account.platform)
            jobs.append({
                "id": pj.id,
                "post_id": pj.post_id,
                "social_account_id": pj.social_account_id,
                "platform": plat,
                "status": pj.status,
                "attempt_count": pj.attempt_count,
                "max_attempts": pj.max_attempts,
                "next_retry_at": nr_at,
                "last_error": pj.last_error,
                "created_at": cr_at,
                "updated_at": up_at,
            })

    return {
        "id": post.id,
        "user_id": post.user_id,
        "team_id": post.team_id,
        "content": post.content,
        "media_urls": post.media_urls or [],
        "post_type": post.post_type,
        "status": post_status_val,
        "scheduled_at": sched_at,
        "published_at": pub_at,
        "recurring_rule_id": getattr(post, "recurring_rule_id", None),
        "created_at": post.created_at,
        "updated_at": post.updated_at,
        "social_accounts": accounts,
        "publish_results": results,
        "publishing_jobs": jobs,
    }




@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_scheduled_post(
    payload: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostResponse:
    """
    Create a post (either SCHEDULED or DRAFT) for one or more connected social accounts.
    Enforces JWT authentication, content validation, account ownership verification,
    and future scheduling timestamp validation when scheduling.
    """
    target_status = (payload.status or "scheduled").lower()

    if target_status == "scheduled":
        # 1. Content validation for scheduled posts
        if not payload.content or not payload.content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Post content is required.",
            )

        # 2. Social accounts validation: at least one account required
        if not payload.social_account_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please select at least one social account.",
            )

        # 3. Scheduled time required and in future
        if not payload.scheduled_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scheduled time is required for scheduled posts.",
            )
        now = datetime.now(timezone.utc)
        target_sched = payload.scheduled_at if payload.scheduled_at.tzinfo is not None else payload.scheduled_at.replace(tzinfo=timezone.utc)
        if target_sched <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scheduled time must be in the future.",
            )

    # 4. Ownership check: all selected accounts must exist and belong to the user
    verified_accounts = []
    if payload.social_account_ids:
        for acc_id in payload.social_account_ids:
            account = db.query(SocialAccount).filter(SocialAccount.id == acc_id).first()
            if not account or account.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected social account is not available.",
                )
            verified_accounts.append(account)

    try:
        post = Post(
            user_id=current_user.id,
            content=(payload.content or "").strip(),
            media_urls=payload.media_urls or [],
            post_type=payload.post_type or "text",
            status=PostStatus.scheduled.value if target_status == "scheduled" else PostStatus.draft.value,
            scheduled_at=payload.scheduled_at if target_status == "scheduled" else payload.scheduled_at,
        )
        db.add(post)
        db.flush()

        for acc in verified_accounts:
            link = PostSocialAccount(
                post_id=post.id,
                social_account_id=acc.id,
            )
            db.add(link)

        db.commit()
        db.refresh(post)

        return PostResponse(**_serialize_post(post))

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to schedule the post. Please try again." if target_status == "scheduled" else "Unable to save draft. Please try again.",
        ) from exc



def _parse_datetime(dt_str: str, is_end: bool = False) -> datetime:
    """Parse date or ISO datetime string into UTC datetime."""
    clean_str = dt_str.strip().replace(" ", "+").replace("Z", "+00:00")
    if len(clean_str) == 10 and clean_str.count("-") == 2:
        d = datetime.strptime(clean_str, "%Y-%m-%d")
        if is_end:
            return d.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
        return d.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    
    dt = datetime.fromisoformat(clean_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("", response_model=PostListResponse, status_code=status.HTTP_200_OK)
def list_posts(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (scheduled, draft, published)"),
    start_date: Optional[str] = Query(None, description="Start date/time for range filter (YYYY-MM-DD or ISO 8601)"),
    end_date: Optional[str] = Query(None, description="End date/time for range filter (YYYY-MM-DD or ISO 8601)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostListResponse:
    """Retrieve posts belonging to the authenticated user, optionally filtered by status and scheduled date range."""
    query = db.query(Post).filter(Post.user_id == current_user.id)

    if status_filter:
        query = query.filter(Post.status == status_filter.lower())

    if start_date:
        try:
            parsed_start = _parse_datetime(start_date, is_end=False)
            query = query.filter(Post.scheduled_at >= parsed_start)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use YYYY-MM-DD or ISO 8601.",
            )

    if end_date:
        try:
            parsed_end = _parse_datetime(end_date, is_end=True)
            query = query.filter(Post.scheduled_at <= parsed_end)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use YYYY-MM-DD or ISO 8601.",
            )

    total = query.count()
    posts = (
        query.order_by(Post.scheduled_at.asc().nullslast(), Post.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return PostListResponse(
        items=[PostResponse(**_serialize_post(p)) for p in posts],
        total=total,
    )


@router.get("/calendar", response_model=PostListResponse, status_code=status.HTTP_200_OK)
def get_calendar_posts(
    start_date: Optional[str] = Query(None, description="Start date/time for range filter"),
    end_date: Optional[str] = Query(None, description="End date/time for range filter"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostListResponse:
    """Convenience alias endpoint for calendar posts."""
    return list_posts(
        status_filter="scheduled",
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
        current_user=current_user,
        db=db,
    )


@router.get("/drafts", response_model=PostListResponse, status_code=status.HTTP_200_OK)
def get_draft_posts(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostListResponse:
    """Convenience alias endpoint for draft posts."""
    return list_posts(
        status_filter="draft",
        start_date=None,
        end_date=None,
        limit=limit,
        offset=offset,
        current_user=current_user,
        db=db,
    )


@router.get("/scheduled", response_model=PostListResponse, status_code=status.HTTP_200_OK)
def get_scheduled_posts(
    start_date: Optional[str] = Query(None, description="Start date/time for range filter"),
    end_date: Optional[str] = Query(None, description="End date/time for range filter"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostListResponse:
    """Convenience alias endpoint for scheduled posts."""
    return list_posts(
        status_filter="scheduled",
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
        current_user=current_user,
        db=db,
    )


@router.get("/{post_id}", response_model=PostResponse, status_code=status.HTTP_200_OK)
def get_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostResponse:
    """Retrieve a single post by ID with ownership verification."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )

    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this post.",
        )

    return PostResponse(**_serialize_post(post))


@router.put("/{post_id}", response_model=PostResponse, status_code=status.HTTP_200_OK)
def update_post(
    post_id: str,
    payload: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostResponse:
    """
    Update an existing draft or post. Supports modifying content, target accounts,
    format, and converting DRAFT -> SCHEDULED.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )

    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this post.",
        )

    target_status = (payload.status or post.status).lower()

    if target_status == "scheduled":
        # Validating conversion to or update of scheduled post
        final_content = payload.content if payload.content is not None else post.content
        if not final_content or not final_content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Post content is required.",
            )

        if payload.social_account_ids is not None:
            target_account_ids = payload.social_account_ids
        else:
            target_account_ids = [psa.social_account_id for psa in post.social_accounts]

        if not target_account_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please select at least one social account.",
            )

        final_sched = payload.scheduled_at if payload.scheduled_at is not None else post.scheduled_at
        if not final_sched:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scheduled time is required for scheduled posts.",
            )
        now = datetime.now(timezone.utc)
        target_dt = final_sched if final_sched.tzinfo is not None else final_sched.replace(tzinfo=timezone.utc)
        if target_dt <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scheduled time must be in the future.",
            )

        verified_accounts = []
        for aid in target_account_ids:
            acc = db.query(SocialAccount).filter(SocialAccount.id == aid).first()
            if not acc or acc.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected social account is not available.",
                )
            verified_accounts.append(acc)

        post.content = final_content.strip()
        post.status = PostStatus.scheduled.value
        post.scheduled_at = target_dt

        if payload.social_account_ids is not None:
            db.query(PostSocialAccount).filter(PostSocialAccount.post_id == post.id).delete()
            for acc in verified_accounts:
                db.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))

    elif target_status == "draft":
        if payload.content is not None:
            post.content = payload.content
        if payload.scheduled_at is not None:
            post.scheduled_at = payload.scheduled_at
        post.status = PostStatus.draft.value

        if payload.social_account_ids is not None:
            verified_accounts = []
            for aid in payload.social_account_ids:
                acc = db.query(SocialAccount).filter(SocialAccount.id == aid).first()
                if not acc or acc.user_id != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Selected social account is not available.",
                    )
                verified_accounts.append(acc)
            db.query(PostSocialAccount).filter(PostSocialAccount.post_id == post.id).delete()
            for acc in verified_accounts:
                db.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))

    if payload.post_type is not None:
        post.post_type = payload.post_type
    if payload.media_urls is not None:
        post.media_urls = payload.media_urls

    post.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(post)

    return PostResponse(**_serialize_post(post))


@router.delete("/{post_id}", status_code=status.HTTP_200_OK)

def delete_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Delete a post owned by the current user."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )

    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this post.",
        )

    db.delete(post)
    db.commit()
    return {"message": "Post deleted successfully.", "id": post_id}


@router.post("/{post_id}/publish", response_model=PostResponse, status_code=status.HTTP_200_OK)
async def publish_post_now(
    post_id: str,
    async_publish: bool = Query(False, description="Whether to queue publication asynchronously via Celery worker"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostResponse:
    """
    Phase 5 & 7: Social Media Publishing.
    Publishes the post immediately or queues it for asynchronous worker execution.
    Enforces user authentication, post ownership verification, and social account ownership.
    """
    from app.services.publishing.service import PublishingService
    from app.worker.tasks import claim_post_for_publishing, publish_post_task

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )

    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to publish this post.",
        )

    if not post.content or not post.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Post content cannot be empty for publishing.",
        )

    if not post.social_accounts or len(post.social_accounts) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Post has no attached social accounts to publish to.",
        )

    # Verify that all attached social accounts belong to the user
    for psa in post.social_accounts:
        acc = psa.social_account
        if not acc or acc.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="One or more selected social accounts do not belong to you.",
            )

    from app.services.publishing.service import PublishingService
    from app.services.publishing.queue_service import enqueue_publishing_jobs
    from app.worker.tasks import claim_post_for_publishing, publish_post_task, process_publishing_job

    # Phase 8: Enqueue per-platform publishing jobs
    jobs = enqueue_publishing_jobs(db, post.id)

    if async_publish:
        # Phase 7 & 8: Asynchronous Publishing
        for j in jobs:
            process_publishing_job.delay(j.id)
        publish_post_task.delay(post.id)
        db.refresh(post)
        return PostResponse(**_serialize_post(post))

    # Synchronous direct publish (Phase 5 compatibility)
    updated_post, results = await PublishingService.publish_post(db, post)
    for res in results:
        for j in jobs:
            if j.social_account_id == res.social_account_id:
                j.status = "published" if res.status == "published" else "failed"
                j.attempt_count = 1
                j.last_error = res.error_message
                j.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(updated_post)
    return PostResponse(**_serialize_post(updated_post))


@router.get("/{post_id}/publishing-logs", response_model=PublishingLogListResponse, status_code=status.HTTP_200_OK)
def get_post_publishing_logs(
    post_id: str,
    platform: Optional[str] = Query(None, description="Filter by platform (e.g. linkedin, facebook)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. queued, processing, published, retrying, failed)"),
    start_date: Optional[datetime] = Query(None, description="Filter logs on or after this timestamp"),
    end_date: Optional[datetime] = Query(None, description="Filter logs on or before this timestamp"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublishingLogListResponse:
    """
    Phase 9: Publishing Logs & Tracking.
    Returns chronological audit logs and event timeline for a post across all platforms.
    Enforces user authentication and post ownership.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )

    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view publishing logs for this post.",
        )

    query = db.query(PublishingLog).filter(PublishingLog.post_id == post.id)

    if platform:
        query = query.filter(PublishingLog.platform == platform.lower())
    if status_filter:
        query = query.filter(PublishingLog.status == status_filter.lower())
    if start_date:
        query = query.filter(PublishingLog.created_at >= start_date)
    if end_date:
        query = query.filter(PublishingLog.created_at <= end_date)

    total = query.count()
    logs = (
        query.order_by(PublishingLog.created_at.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = [
        PublishingLogResponse(
            id=log.id,
            post_id=log.post_id,
            publishing_job_id=log.publishing_job_id,
            social_account_id=log.social_account_id,
            platform=log.platform,
            event_type=log.event_type,
            status=log.status,
            attempt_number=log.attempt_number,
            platform_post_id=log.platform_post_id,
            published_url=log.published_url,
            error_message=log.error_message,
            created_at=log.created_at,
        )
        for log in logs
    ]

    return PublishingLogListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{post_id}/publishing-logs/export", summary="Download publishing audit logs as a file")
def export_post_publishing_logs(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Export post publishing logs as a downloadable .log audit file.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    if post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    from app.services.publishing.log_generator import generate_post_audit_log_content

    log_content = generate_post_audit_log_content(db, post, current_user)
    return Response(
        content=log_content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=publishing_logs_{post_id[:8]}.log"
        }
    )



