"""
app/services/email_service.py
------------------------------
Real Email Service for the SocialPilot Notification Module (Milestone 4).

Features:
- Real SMTP delivery via standard smtplib & email.mime
- Gmail SMTP & Google App Password compatibility (smtp.gmail.com:587)
- Custom SMTP servers (TLS / SSL / Plain)
- Responsive HTML emails with SocialPilot branding, rich layout, and action CTAs
- Safe error handling & error message sanitization (passwords never exposed)
- Automated test mockability & development safety
"""

import html
import logging
import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Tuple

from app.core.config import settings

logger = logging.getLogger("socialpilot.email")


def sanitize_email_error(error_msg: str) -> str:
    """Sanitize passwords, bearer tokens, or sensitive strings from SMTP error messages."""
    if not error_msg:
        return ""
    # Strip potential passwords or auth credentials
    clean = re.sub(r'(password|pass|secret|key|token)=([^\s,]+)', r'\1=[REDACTED]', error_msg, flags=re.IGNORECASE)
    # Strip base64 auth payload traces
    clean = re.sub(r'AUTH\s+PLAIN\s+[A-Za-z0-9+/=]+', 'AUTH PLAIN [REDACTED]', clean, flags=re.IGNORECASE)
    clean = re.sub(r'AUTH\s+LOGIN\s+[A-Za-z0-9+/=]+', 'AUTH LOGIN [REDACTED]', clean, flags=re.IGNORECASE)
    return clean[:500]


# ---------------------------------------------------------------------------
# Base HTML Email Layout Template
# ---------------------------------------------------------------------------
def _render_base_email_template(
    title: str,
    preheader: str,
    badge_text: str,
    badge_color: str,
    greeting_name: str,
    main_heading: str,
    body_content_html: str,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
) -> str:
    """
    Renders a modern, responsive HTML email matching SocialPilot design aesthetics.
    Works seamlessly in Gmail, Apple Mail, Outlook, and webmail clients.
    """
    safe_title = html.escape(title)
    safe_preheader = html.escape(preheader)
    safe_badge = html.escape(badge_text)
    safe_greeting = html.escape(greeting_name or "there")
    safe_heading = html.escape(main_heading)
    frontend_url = settings.effective_frontend_url

    cta_section_html = ""
    if cta_label and cta_url:
        cta_section_html = f"""
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin: 28px 0 10px 0;">
          <tr>
            <td align="center">
              <a href="{cta_url}" target="_blank" style="display: inline-block; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: #ffffff; text-decoration: none; font-size: 15px; font-weight: 600; padding: 12px 28px; border-radius: 8px; box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);">
                {html.escape(cta_label)} &rarr;
              </a>
            </td>
          </tr>
        </table>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #0d1117;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #e6edf3;
      -webkit-font-smoothing: antialiased;
    }}
    .email-container {{
      max-width: 580px;
      margin: 0 auto;
      padding: 32px 16px;
    }}
    .email-card {{
      background-color: #161b22;
      border: 1px solid #30363d;
      border-radius: 16px;
      padding: 32px 28px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    }}
    .logo-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 18px;
      font-weight: 700;
      color: #ffffff;
      letter-spacing: -0.02em;
    }}
    .badge-pill {{
      display: inline-block;
      padding: 4px 12px;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-radius: 20px;
      background: {badge_color}22;
      color: {badge_color};
      border: 1px solid {badge_color}44;
      margin-bottom: 16px;
    }}
    .email-heading {{
      font-size: 22px;
      font-weight: 700;
      color: #ffffff;
      margin: 0 0 16px 0;
      line-height: 1.3;
    }}
    .email-text {{
      font-size: 15px;
      line-height: 1.6;
      color: #c9d1d9;
      margin: 0 0 16px 0;
    }}
    .info-box {{
      background: #0d1117;
      border: 1px solid #30363d;
      border-radius: 10px;
      padding: 16px 18px;
      margin: 20px 0;
    }}
    .info-label {{
      font-size: 12px;
      text-transform: uppercase;
      font-weight: 600;
      color: #8b949e;
      letter-spacing: 0.04em;
      margin-bottom: 4px;
    }}
    .info-value {{
      font-size: 14px;
      color: #f0f6fc;
      font-weight: 500;
    }}
    .email-footer {{
      margin-top: 28px;
      padding-top: 20px;
      border-top: 1px solid #21262d;
      font-size: 12px;
      color: #8b949e;
      text-align: center;
      line-height: 1.5;
    }}
    .email-footer a {{
      color: #6366f1;
      text-decoration: none;
    }}
  </style>
</head>
<body style="margin: 0; padding: 0; background-color: #0d1117;">
  <!-- Preheader text for email client preview -->
  <div style="display: none; max-height: 0px; overflow: hidden; font-size: 1px; line-height: 1px; color: #0d1117;">
    {safe_preheader}
  </div>

  <div class="email-container">
    <div class="email-card">
      <!-- Header -->
      <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 24px;">
        <tr>
          <td>
            <div class="logo-badge">
              🚀 SocialPilot
            </div>
          </td>
          <td align="right">
            <span class="badge-pill">{safe_badge}</span>
          </td>
        </tr>
      </table>

      <!-- Greeting & Heading -->
      <h1 class="email-heading">{safe_heading}</h1>
      <p class="email-text">Hi {safe_greeting},</p>

      <!-- Main Body -->
      {body_content_html}

      <!-- Action CTA -->
      {cta_section_html}

      <!-- Footer -->
      <div class="email-footer">
        <p style="margin: 0 0 8px 0;">This notification was sent by <a href="{frontend_url}">SocialPilot</a> to your registered email.</p>
        <p style="margin: 0;">You can customize your notification preferences anytime in <a href="{frontend_url}/settings">Settings &rarr; Notifications</a>.</p>
      </div>
    </div>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Template Builders
# ---------------------------------------------------------------------------
class EmailTemplates:
    @staticmethod
    def post_published(
        user_name: str,
        platform: str,
        preview: Optional[str] = None,
        published_url: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """Returns (subject, html_body, text_body)."""
        platform_label = platform.title() if platform else "Social Platform"
        subject = f"SocialPilot — Post Published Successfully on {platform_label}"
        preheader = f"Your scheduled post has been successfully published on {platform_label}."
        preview_text = preview or "Your scheduled content"

        content_html = f"""
        <p class="email-text">
          Great news! Your scheduled post has been successfully published to <strong>{html.escape(platform_label)}</strong>.
        </p>
        <div class="info-box">
          <div class="info-label">Post Preview</div>
          <div class="info-value" style="font-style: italic;">"{html.escape(preview_text)}"</div>
        </div>
        """
        if published_url:
            content_html += f"""
            <p class="email-text" style="font-size: 13px; color: #8b949e;">
              Live Link: <a href="{published_url}" target="_blank" style="color: #6366f1;">{html.escape(published_url)}</a>
            </p>
            """

        cta_url = published_url or f"{settings.effective_frontend_url}/posts"
        cta_label = "View Live Post" if published_url else "Open SocialPilot Posts"

        html_body = _render_base_email_template(
            title=subject,
            preheader=preheader,
            badge_text="Published",
            badge_color="#10b981",
            greeting_name=user_name,
            main_heading="🎉 Post Published Successfully",
            body_content_html=content_html,
            cta_label=cta_label,
            cta_url=cta_url,
        )
        text_body = f"Hi {user_name or 'there'},\n\nYour scheduled post was successfully published on {platform_label}.\n\nContent: {preview_text}\n\nView post: {cta_url}\n\n— The SocialPilot Team"
        return subject, html_body, text_body

    @staticmethod
    def post_failed(
        user_name: str,
        platform: str,
        preview: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """Returns (subject, html_body, text_body)."""
        platform_label = platform.title() if platform else "Social Platform"
        subject = f"SocialPilot — Post Publishing Failed on {platform_label}"
        preheader = f"Your scheduled post could not be published on {platform_label}."
        preview_text = preview or "Your scheduled content"
        safe_err = sanitize_email_error(error_message or "An unexpected issue occurred while publishing.")

        content_html = f"""
        <p class="email-text">
          We encountered an issue while trying to publish your post to <strong>{html.escape(platform_label)}</strong>.
        </p>
        <div class="info-box">
          <div class="info-label">Post Content</div>
          <div class="info-value" style="margin-bottom: 12px;">"{html.escape(preview_text)}"</div>
          <div class="info-label" style="color: #ef4444;">Reason</div>
          <div class="info-value" style="color: #f87171; font-family: monospace; font-size: 13px;">{html.escape(safe_err)}</div>
        </div>
        <p class="email-text">
          Please review your social account permissions and retry publishing from the Post Queue.
        </p>
        """

        html_body = _render_base_email_template(
            title=subject,
            preheader=preheader,
            badge_text="Failed",
            badge_color="#ef4444",
            greeting_name=user_name,
            main_heading="⚠️ Publishing Failed",
            body_content_html=content_html,
            cta_label="Open Post Queue & Retry",
            cta_url=f"{settings.effective_frontend_url}/posts?tab=queue",
        )
        text_body = f"Hi {user_name or 'there'},\n\nYour post could not be published to {platform_label}.\nReason: {safe_err}\n\nManage posts: {settings.effective_frontend_url}/posts\n\n— The SocialPilot Team"
        return subject, html_body, text_body

    @staticmethod
    def post_scheduled(
        user_name: str,
        platform: str,
        preview: Optional[str] = None,
        scheduled_at_str: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """Returns (subject, html_body, text_body)."""
        platform_label = platform.title() if platform else "Social Platform"
        subject = f"SocialPilot — Post Scheduled for {platform_label}"
        preheader = f"Your post has been scheduled on {platform_label}."
        preview_text = preview or "Your scheduled content"
        time_display = scheduled_at_str or "Scheduled Time"

        content_html = f"""
        <p class="email-text">
          Your post has been successfully scheduled for publishing on <strong>{html.escape(platform_label)}</strong>.
        </p>
        <div class="info-box">
          <div class="info-label">Scheduled Time</div>
          <div class="info-value" style="margin-bottom: 12px; color: #6366f1;">📅 {html.escape(time_display)}</div>
          <div class="info-label">Post Preview</div>
          <div class="info-value">"{html.escape(preview_text)}"</div>
        </div>
        """

        html_body = _render_base_email_template(
            title=subject,
            preheader=preheader,
            badge_text="Scheduled",
            badge_color="#6366f1",
            greeting_name=user_name,
            main_heading="📅 Post Scheduled",
            body_content_html=content_html,
            cta_label="View Publishing Calendar",
            cta_url=f"{settings.effective_frontend_url}/posts?tab=calendar",
        )
        text_body = f"Hi {user_name or 'there'},\n\nYour post is scheduled for {platform_label} at {time_display}.\n\nPreview: {preview_text}\n\nCalendar: {settings.effective_frontend_url}/posts?tab=calendar\n\n— The SocialPilot Team"
        return subject, html_body, text_body

    @staticmethod
    def scheduled_reminder(
        user_name: str,
        platform: str,
        preview: Optional[str] = None,
        scheduled_at_str: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """Returns (subject, html_body, text_body)."""
        platform_label = platform.title() if platform else "Social Platform"
        subject = f"SocialPilot Reminder — Post Publishing Soon on {platform_label}"
        preheader = f"Your post is scheduled to publish soon on {platform_label}."
        preview_text = preview or "Your scheduled content"
        time_display = scheduled_at_str or "approx. 30 minutes from now"

        content_html = f"""
        <p class="email-text">
          Friendly reminder: Your scheduled post will be published to <strong>{html.escape(platform_label)}</strong> soon ({html.escape(time_display)}).
        </p>
        <div class="info-box">
          <div class="info-label">Post Preview</div>
          <div class="info-value">"{html.escape(preview_text)}"</div>
        </div>
        """

        html_body = _render_base_email_template(
            title=subject,
            preheader=preheader,
            badge_text="Reminder",
            badge_color="#f59e0b",
            greeting_name=user_name,
            main_heading="⏰ Scheduled Post Reminder",
            body_content_html=content_html,
            cta_label="View / Edit Post",
            cta_url=f"{settings.effective_frontend_url}/posts",
        )
        text_body = f"Hi {user_name or 'there'},\n\nYour post on {platform_label} is scheduled to publish soon ({time_display}).\nPreview: {preview_text}\n\nManage posts: {settings.effective_frontend_url}/posts\n\n— The SocialPilot Team"
        return subject, html_body, text_body

    @staticmethod
    def campaign_event(
        user_name: str,
        campaign_name: str,
        event: str,
    ) -> Tuple[str, str, str]:
        """Returns (subject, html_body, text_body)."""
        event_labels = {
            "created": ("Campaign Created", "#f59e0b", "has been created and is active"),
            "updated": ("Campaign Updated", "#8b5cf6", "has been updated"),
            "completed": ("Campaign Completed", "#10b981", "has successfully completed all scheduled deliverables"),
        }
        title_label, badge_color, desc_suffix = event_labels.get(
            event, ("Campaign Update", "#6366f1", "has a new update")
        )

        subject = f"SocialPilot — {title_label}: {campaign_name}"
        preheader = f"Campaign '{campaign_name}' {desc_suffix}."

        content_html = f"""
        <p class="email-text">
          Campaign <strong>"{html.escape(campaign_name)}"</strong> {desc_suffix}.
        </p>
        <div class="info-box">
          <div class="info-label">Campaign Name</div>
          <div class="info-value">{html.escape(campaign_name)}</div>
        </div>
        """

        html_body = _render_base_email_template(
            title=subject,
            preheader=preheader,
            badge_text="Campaign",
            badge_color=badge_color,
            greeting_name=user_name,
            main_heading=f"🎯 {title_label}",
            body_content_html=content_html,
            cta_label="View Campaign Overview",
            cta_url=f"{settings.effective_frontend_url}/campaigns",
        )
        text_body = f"Hi {user_name or 'there'},\n\nCampaign '{campaign_name}' {desc_suffix}.\n\nView campaigns: {settings.effective_frontend_url}/campaigns\n\n— The SocialPilot Team"
        return subject, html_body, text_body

    @staticmethod
    def account_issue(
        user_name: str,
        platform: str,
        issue_description: str,
    ) -> Tuple[str, str, str]:
        """Returns (subject, html_body, text_body)."""
        platform_label = platform.title() if platform else "Social"
        subject = f"SocialPilot Alert — Action Required: {platform_label} Account Issue"
        preheader = f"Action needed for your {platform_label} account connection."
        clean_issue = sanitize_email_error(issue_description or "Authentication / Token expired")

        content_html = f"""
        <p class="email-text">
          We detected an issue with your connected <strong>{html.escape(platform_label)}</strong> account.
        </p>
        <div class="info-box">
          <div class="info-label" style="color: #f97316;">Issue Details</div>
          <div class="info-value" style="color: #fb923c;">{html.escape(clean_issue)}</div>
        </div>
        <p class="email-text">
          Please reconnect or re-authorize the account to ensure scheduled posts continue publishing without interruption.
        </p>
        """

        html_body = _render_base_email_template(
            title=subject,
            preheader=preheader,
            badge_text="Account Issue",
            badge_color="#f97316",
            greeting_name=user_name,
            main_heading="⚠️ Social Account Action Required",
            body_content_html=content_html,
            cta_label="Reconnect Account",
            cta_url=f"{settings.effective_frontend_url}/accounts",
        )
        text_body = f"Hi {user_name or 'there'},\n\nAction required for your {platform_label} account:\n{clean_issue}\n\nReconnect here: {settings.effective_frontend_url}/accounts\n\n— The SocialPilot Team"
        return subject, html_body, text_body

    @staticmethod
    def system_alert(
        user_name: str,
        title: str,
        message: str,
    ) -> Tuple[str, str, str]:
        """Returns (subject, html_body, text_body)."""
        subject = f"SocialPilot Alert — {title}"
        preheader = message[:100]

        content_html = f"""
        <p class="email-text">{html.escape(message)}</p>
        """

        html_body = _render_base_email_template(
            title=subject,
            preheader=preheader,
            badge_text="System Alert",
            badge_color="#6366f1",
            greeting_name=user_name,
            main_heading=f"ℹ️ {title}",
            body_content_html=content_html,
            cta_label="Open Dashboard",
            cta_url=f"{settings.effective_frontend_url}/dashboard",
        )
        text_body = f"Hi {user_name or 'there'},\n\n{title}\n\n{message}\n\n— The SocialPilot Team"
        return subject, html_body, text_body

    @staticmethod
    def test_email(user_name: str) -> Tuple[str, str, str]:
        """Returns (subject, html_body, text_body)."""
        subject = "SocialPilot — SMTP Email Delivery Verified"
        preheader = "Your SMTP configuration is working perfectly."

        content_html = f"""
        <p class="email-text">
          Congratulations! This is a test email confirming that your SocialPilot SMTP email delivery is configured correctly and operational.
        </p>
        <div class="info-box">
          <div class="info-label">SMTP Host</div>
          <div class="info-value" style="margin-bottom: 8px;">{html.escape(settings.SMTP_HOST or 'Not configured')}</div>
          <div class="info-label">Sender Address</div>
          <div class="info-value">{html.escape(settings.effective_from_email)}</div>
        </div>
        <p class="email-text">
          You will receive real-time updates for post publishing, campaign milestones, and account connectivity.
        </p>
        """

        html_body = _render_base_email_template(
            title=subject,
            preheader=preheader,
            badge_text="Verified",
            badge_color="#10b981",
            greeting_name=user_name,
            main_heading="✅ SMTP Setup Confirmed",
            body_content_html=content_html,
            cta_label="Go to Dashboard",
            cta_url=f"{settings.effective_frontend_url}/dashboard",
        )
        text_body = f"Hi {user_name or 'there'},\n\nYour SocialPilot SMTP configuration is operational!\nSender: {settings.effective_from_email}\n\n— The SocialPilot Team"
        return subject, html_body, text_body


# ---------------------------------------------------------------------------
# Email Service Implementation
# ---------------------------------------------------------------------------
class EmailService:
    """
    Centralized email delivery service using standard smtplib.
    Handles connections, TLS/SSL, authentication, timeouts, and error logging.
    """

    @classmethod
    def send_email(
        cls,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Send an email via configured SMTP settings.

        Returns (success: bool, error_message: Optional[str]).
        Never crashes or exposes credentials on failure.
        """
        if not to_email or "@" not in to_email:
            return False, "Invalid recipient email address."

        if not settings.smtp_configured:
            logger.info(f"SMTP not configured. Skipping email to {to_email} (subject: {subject})")
            return False, "SMTP is not configured on this server."

        # Create MIME message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.effective_from_email}>"
        msg["To"] = to_email

        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        timeout = getattr(settings, "SMTP_TIMEOUT_SECONDS", 15)

        try:
            if settings.SMTP_USE_SSL:
                # Direct SSL (e.g. port 465)
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=timeout) as server:
                    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.sendmail(settings.effective_from_email, [to_email], msg.as_string())
            else:
                # Standard SMTP (e.g. port 587 with STARTTLS)
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout) as server:
                    if settings.SMTP_USE_TLS:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.sendmail(settings.effective_from_email, [to_email], msg.as_string())

            logger.info(f"Successfully delivered email to {to_email} (subject: {subject})")
            return True, None

        except smtplib.SMTPAuthenticationError as auth_err:
            clean_err = sanitize_email_error(str(auth_err))
            logger.error(f"SMTP authentication failed: {clean_err}")
            return False, f"SMTP Authentication Error: {clean_err}"

        except smtplib.SMTPException as smtp_err:
            clean_err = sanitize_email_error(str(smtp_err))
            logger.error(f"SMTP error while sending email to {to_email}: {clean_err}")
            return False, f"SMTP Error: {clean_err}"

        except Exception as exc:
            clean_err = sanitize_email_error(str(exc))
            logger.error(f"Unexpected error sending email to {to_email}: {clean_err}")
            return False, f"Email delivery failed: {clean_err}"
