"""
app/services/publishing/log_generator.py
----------------------------------------
Generates comprehensive, professional publishing audit log files containing
the real content of the post, author metadata, scheduling details, target accounts,
live published URLs, and chronological audit event trails.
Also writes physical .log files to backend/logs/publishing/post_{id}.log.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.user import User
from app.models.publishing_log import PublishingLog

logger = logging.getLogger("socialpilot.log_generator")

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "logs", "publishing")


def write_post_log_file(post_id: str, content: str) -> str:
    """Writes the formatted log string to backend/logs/publishing/post_{post_id}.log"""
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        file_path = os.path.join(LOGS_DIR, f"post_{post_id}.log")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path
    except Exception as exc:
        logger.warning(f"Could not write log file to disk for post #{post_id}: {exc}")
        return ""


def generate_post_audit_log_content(db: Session, post: Post, user: Optional[User] = None) -> str:
    """
    Builds an in-depth, structured audit log string including the full real content
    of the post, media attachments, target accounts, publishing outcomes, and timeline logs.
    """
    if not user and post.user_id:
        user = db.query(User).filter(User.id == post.user_id).first()

    author_name = (user.full_name if user and user.full_name else None) or (user.email if user else "Unknown User")
    author_email = user.email if user else "N/A"
    user_id = user.id if user else post.user_id

    post_status_str = post.status.value if hasattr(post.status, "value") else str(post.status)
    created_at_str = post.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if post.created_at else "N/A"
    updated_at_str = post.updated_at.strftime("%Y-%m-%d %H:%M:%S UTC") if post.updated_at else "N/A"
    scheduled_at_str = post.scheduled_at.strftime("%Y-%m-%d %H:%M:%S UTC") if post.scheduled_at else "Not Scheduled (Immediate / Draft)"
    published_at_str = post.published_at.strftime("%Y-%m-%d %H:%M:%S UTC") if post.published_at else "Pending Publication"

    # Social accounts
    account_lines = []
    if post.social_accounts:
        for psa in post.social_accounts:
            acc = psa.social_account
            if acc:
                plat = acc.platform.value if hasattr(acc.platform, "value") else str(acc.platform)
                acc_name = acc.account_name or "Unknown"
                acc_user = f"@{acc.account_username}" if acc.account_username else "N/A"
                acc_id = acc.platform_account_id or acc.id
                account_lines.append(f"  • Platform: {plat.upper():<10} | Account: {acc_name:<20} | Handle: {acc_user:<18} | ID: {acc_id}")
    if not account_lines:
        account_lines.append("  [No social accounts linked to this post]")

    # Media attachments resolution
    resolved_media_items = []

    # 1. First attempt: Query MongoDB content_posts & media_assets
    try:
        from app.db.mongodb import _mongo_client
        from app.core.config import settings
        if _mongo_client is not None:
            sync_client = _mongo_client.delegate
            mongo_db = sync_client[settings.effective_mongodb_database]
            cp = mongo_db["content_posts"].find_one({"post_id": str(post.id)})
            if cp:
                raw_items = cp.get("media_items") or []
                raw_ids = cp.get("media_ids") or []
                ordered_ids = []
                if raw_items:
                    for idx, it in enumerate(raw_items, start=1):
                        mid = it.get("media_id")
                        if mid:
                            pos = it.get("position", idx)
                            ordered_ids.append((str(mid), int(pos)))
                elif raw_ids:
                    for idx, mid in enumerate(raw_ids, start=1):
                        ordered_ids.append((str(mid), idx))
                ordered_ids.sort(key=lambda x: x[1])

                if ordered_ids:
                    m_ids = [x[0] for x in ordered_ids]
                    assets = list(mongo_db["media_assets"].find({"media_id": {"$in": m_ids}}))
                    asset_map = {a["media_id"]: a for a in assets}
                    for mid, pos in ordered_ids:
                        a = asset_map.get(mid, {})
                        resolved_media_items.append({
                            "media_id": mid,
                            "position": pos,
                            "type": a.get("media_type", "image"),
                            "mime_type": a.get("mime_type", "image/jpeg"),
                            "filename": a.get("original_filename", "media"),
                            "size_bytes": a.get("size_bytes", 0),
                            "public_url": f"/api/v1/media/public/{mid}",
                        })
    except Exception:
        pass

    # 2. Second attempt: Check PostgreSQL post.media_urls
    if not resolved_media_items and post.media_urls and isinstance(post.media_urls, list) and len(post.media_urls) > 0:
        import re
        for idx, m_url in enumerate(post.media_urls, start=1):
            url_str = str(m_url).strip()
            if not url_str:
                continue
            m_match = re.search(r"/api/v1/media/public/([a-f0-9\-]+)", url_str)
            mid = m_match.group(1) if m_match else f"media_{idx}"
            is_vid = any(url_str.lower().endswith(ext) for ext in (".mp4", ".mov", ".avi", ".webm"))
            m_type = "video" if is_vid else "image"
            resolved_media_items.append({
                "media_id": mid,
                "position": idx,
                "type": m_type,
                "mime_type": "video/mp4" if is_vid else "image/jpeg",
                "filename": f"media_{idx}",
                "size_bytes": 0,
                "public_url": url_str,
            })

    # Build formatted media lines
    media_lines = []
    p_format = (post.post_type or "text").lower().strip()
    if resolved_media_items:
        for m in resolved_media_items:
            media_lines.append(f"  • [Position {m['position']}]")
            media_lines.append(f"    media_id:          {m['media_id']}")
            media_lines.append(f"    type:              {m['type']}")
            media_lines.append(f"    mime_type:         {m['mime_type']}")
            media_lines.append(f"    filename:          {m['filename']}")
            if m.get("size_bytes"):
                media_lines.append(f"    size_bytes:        {m['size_bytes']}")
            media_lines.append(f"    public_url:        {m['public_url']}")
    else:
        if p_format in ("image", "video", "carousel", "story", "reel"):
            media_lines.append(f"  [ERROR: No media attachments resolved for {p_format.upper()} post - pipeline error]")
        else:
            media_lines.append("  [No media attachments - Pure text content post]")

    total_media_count = len(resolved_media_items)

    # Publishing Results (outcomes)
    result_lines = []
    if hasattr(post, "publish_results") and post.publish_results:
        for r in post.publish_results:
            p_time = r.published_at.strftime("%Y-%m-%d %H:%M:%S UTC") if r.published_at else "N/A"
            if r.status == "published":
                status_tag = "SUCCESS"
            elif r.status == "skipped":
                status_tag = "SKIPPED"
            else:
                status_tag = "FAILED"
            result_lines.append(f"  • [{r.platform.upper()}] Status: {status_tag} | Time: {p_time}")
            result_lines.append(f"    Platform Post ID: {r.platform_post_id or 'N/A'}")
            result_lines.append(f"    Live URL:         {r.published_url or 'N/A'}")
            if r.error_message:
                result_lines.append(f"    Error Details:    {r.error_message}")
            result_lines.append("")
    if not result_lines:
        result_lines.append("  [No final publishing results recorded yet]")

    # Chronological Audit Logs
    logs = (
        db.query(PublishingLog)
        .filter(PublishingLog.post_id == post.id)
        .order_by(PublishingLog.created_at.asc())
        .all()
    )

    log_event_lines = []
    if logs:
        for idx, log in enumerate(logs, start=1):
            ts = log.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if log.created_at else "N/A"
            log_event_lines.append(
                f"[{idx:02d}] {ts} | Platform: {str(log.platform).upper():<10} | Event: {log.event_type:<14} | Status: {str(log.status).upper()}"
            )
            log_event_lines.append(f"     Attempt Number:   #{log.attempt_number}")
            log_event_lines.append(f"     Platform Post ID: {log.platform_post_id or 'N/A'}")
            log_event_lines.append(f"     Published URL:    {log.published_url or 'N/A'}")
            if log.error_message:
                log_event_lines.append(f"     Failure Reason:   {log.error_message}")
            log_event_lines.append("     " + "-" * 75)
    else:
        log_event_lines.append("  [No publishing log events recorded yet]")

    content_text = post.content or ""
    word_count = len(content_text.split())
    char_count = len(content_text)

    # Assemble complete audit log file
    banner = "=" * 80
    sub_banner = "-" * 80

    lines = [
        banner,
        "                     SOCIALPILOT — POST PUBLISHING AUDIT LOG",
        banner,
        f"Export Timestamp : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "System Version   : SocialPilot Core v2.0 (Milestone 2 - Publishing Engine)",
        "Log Category     : Multi-Platform Publishing Lifecycle & Audit Trail",
        banner,
        "",
        "1. POST IDENTIFICATION & METADATA",
        sub_banner,
        f"Post ID              : {post.id}",
        f"Author Name          : {author_name}",
        f"Author Email         : {author_email}",
        f"Author User ID       : {user_id}",
        f"Post Type / Format   : {post.post_type.upper()}",
        f"Current Post Status  : {post_status_str.upper()}",
        f"Created At           : {created_at_str}",
        f"Last Updated At      : {updated_at_str}",
        f"Recurring Schedule   : {post.recurring_rule_id if post.recurring_rule_id else 'None (One-time post)'}",
        "",
        "2. SCHEDULING & TIMING DETAILS",
        sub_banner,
        f"Scheduled Publish At : {scheduled_at_str}",
        f"Actual Published At  : {published_at_str}",
        f"Auto-Publish Worker  : Active (FastAPI Background Scheduler)",
        "",
        "3. REAL POST CONTENT & PAYLOAD",
        sub_banner,
        f"Character Count      : {char_count} characters",
        f"Word Count           : {word_count} words",
        f"Media Attachments    : {total_media_count} file(s)",
        "",
        "[EXACT POST TEXT / CAPTION]:",
        content_text if content_text else "(Empty Content)",
        "",
        "[ATTACHED MEDIA]:",
        *media_lines,
        "",
        "4. TARGET SOCIAL PLATFORMS & ACCOUNTS",
        sub_banner,
        *account_lines,
        "",
        "5. PLATFORM PUBLISHING OUTCOMES & DIRECT LIVE LINKS",
        sub_banner,
        *result_lines,
        "6. CHRONOLOGICAL EVENT TIMELINE & AUDIT TRAIL",
        sub_banner,
        f"Total Log Events Recorded: {len(logs)}",
        "",
        *log_event_lines,
        banner,
        "                            END OF AUDIT LOG FILE",
        banner,
    ]

    full_log_str = "\n".join(lines)

    # Also automatically write to disk file
    write_post_log_file(post.id, full_log_str)

    return full_log_str
