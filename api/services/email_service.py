"""AYUR-INTEL — Email Notification Service.

Handles administrative email alerts for new access approval and reactivation requests.
Supports both SMTP and Resend providers, loaded securely from environment variables.
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any, Callable, Dict, Optional, Tuple

import httpx

from api.core.config import settings

logger = logging.getLogger("ayur_intel.email")

# Default Production Targets
DEFAULT_ADMIN_EMAIL = "india.deepanshaggarwal@gmail.com"
DEFAULT_PRODUCTION_URL = "https://ayur-intel.onrender.com/"

# Test hook for automated testing: when set, intercepts outgoing emails
# Callback signature: hook(message_dict) -> bool (True = success, False = simulate failure)
_TEST_EMAIL_HOOK: Optional[Callable[[Dict[str, Any]], bool]] = None
_OUTBOX_FOR_TESTS: list[Dict[str, Any]] = []


def set_test_email_hook(hook: Optional[Callable[[Dict[str, Any]], bool]]) -> None:
    """Set or clear the test interceptor hook for automated testing."""
    global _TEST_EMAIL_HOOK
    _TEST_EMAIL_HOOK = hook


def get_test_outbox() -> list[Dict[str, Any]]:
    """Return a copy of captured emails for test assertions."""
    return list(_OUTBOX_FOR_TESTS)


def clear_test_outbox() -> None:
    """Clear captured test emails."""
    global _OUTBOX_FOR_TESTS
    _OUTBOX_FOR_TESTS.clear()


def format_datetime_ist(dt: Optional[datetime]) -> str:
    """Format UTC datetime into human-readable Indian Standard Time (IST, UTC+05:30)."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    ist_tz = timezone(timedelta(hours=5, minutes=30), name="IST")
    ist_time = dt.astimezone(ist_tz)
    return ist_time.strftime("%d %b %Y, %I:%M %p IST")


def get_effective_admin_recipient() -> str:
    """Return the recipient administrator email from environment or default."""
    configured = (
        os.getenv("ADMIN_NOTIFICATION_EMAIL")
        or getattr(settings, "ADMIN_NOTIFICATION_EMAIL", None)
        or os.getenv("AYURINTEL_ADMIN_EMAIL")
        or getattr(settings, "AYURINTEL_ADMIN_EMAIL", None)
        or DEFAULT_ADMIN_EMAIL
    )
    return str(configured).strip()


def get_effective_production_url() -> str:
    """Return the base production URL from environment or default."""
    url = (
        os.getenv("AYURINTEL_PRODUCTION_URL")
        or getattr(settings, "AYURINTEL_PRODUCTION_URL", None)
        or os.getenv("PRODUCTION_URL")
        or DEFAULT_PRODUCTION_URL
    )
    return str(url).strip().rstrip("/")


def build_access_request_email(
    applicant_name: str,
    applicant_email: str,
    request_type: str,
    created_at: Optional[datetime] = None,
    device_info: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, str]:
    """Build subject, plain text body, and HTML body for access approval request notification."""
    prod_url = get_effective_production_url()
    admin_url = f"{prod_url}/#admin"
    created_ist = format_datetime_ist(created_at)

    type_label = "New User" if str(request_type).upper() in ("NEW_USER", "NEW USER") else "Reactivation"
    dev_str = (device_info or "").strip() or "Not recorded"
    reason_str = (reason or "").strip() or ("New user registration" if type_label == "New User" else "Deactivated user sign-in attempt")

    subject = "[AYUR-INTEL] New Access Approval Request"

    plain_text = f"""[AYUR-INTEL] Access Approval Request
==========================================

A new access approval request has been submitted and requires administrator review.

Applicant Details:
------------------
* Name: {applicant_name}
* Registered Email: {applicant_email}
* Request Type: {type_label}
* Request Date & Time: {created_ist}
* Device / Client: {dev_str}
* Stated Reason: {reason_str}

Notice:
Until approved, this applicant cannot access protected application features, APIs, data, dashboards, or other authenticated resources.

To review and Approve or Reject this request, open the Admin Console:
Admin Console: {admin_url}
Application: {prod_url}

--
AYUR-INTEL Security & Institutional Access Oversight
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>AYUR-INTEL Access Approval Request</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b1a13; color: #e2e8f0; margin: 0; padding: 24px;">
  <div style="max-width: 600px; margin: 0 auto; background: #11261c; border: 1px solid rgba(46, 125, 90, 0.4); border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.4);">
    <div style="background: linear-gradient(135deg, #1b4d36 0%, #0e291d 100%); padding: 24px 28px; border-bottom: 1px solid rgba(74, 222, 128, 0.2);">
      <h2 style="margin: 0; color: #4ade80; font-size: 20px; font-weight: 700; letter-spacing: 0.5px;">AYUR-INTEL</h2>
      <p style="margin: 4px 0 0 0; color: #94a39b; font-size: 13px;">Evidence · Intelligence · Institutional Access Oversight</p>
    </div>
    <div style="padding: 28px;">
      <h3 style="margin-top: 0; color: #f2f7f4; font-size: 17px; font-weight: 600;">New Access Approval Request</h3>
      <p style="color: #cbd5e1; font-size: 14px; line-height: 1.5; margin-bottom: 20px;">
        A new access request has been recorded and is awaiting your review. Until approved, the user remains strictly blocked from protected application resources.
      </p>

      <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 13.5px;">
        <tr>
          <td style="padding: 9px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #94a39b; width: 35%;">Applicant Name</td>
          <td style="padding: 9px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #f2f7f4; font-weight: 600;">{applicant_name}</td>
        </tr>
        <tr>
          <td style="padding: 9px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #94a39b;">Registered Email</td>
          <td style="padding: 9px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #4ade80;">{applicant_email}</td>
        </tr>
        <tr>
          <td style="padding: 9px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #94a39b;">Request Type</td>
          <td style="padding: 9px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #f2f7f4;">
            <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; background: {'rgba(56, 189, 248, 0.15)' if type_label == 'New User' else 'rgba(245, 158, 11, 0.15)'}; color: {'#38bdf8' if type_label == 'New User' else '#f59e0b'};">
              {type_label}
            </span>
          </td>
        </tr>
        <tr>
          <td style="padding: 9px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #94a39b;">Submission Time</td>
          <td style="padding: 9px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #f2f7f4;">{created_ist}</td>
        </tr>
        <tr>
          <td style="padding: 9px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #94a39b;">Device / Browser</td>
          <td style="padding: 9px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #cbd5e1;">{dev_str}</td>
        </tr>
        <tr>
          <td style="padding: 9px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #94a39b;">Reason / Notes</td>
          <td style="padding: 9px 12px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #cbd5e1;">{reason_str}</td>
        </tr>
      </table>

      <div style="text-align: center; margin: 30px 0 20px 0;">
        <a href="{admin_url}" style="display: inline-block; background: #22c55e; color: #042111; font-weight: 700; font-size: 14px; text-decoration: none; padding: 12px 28px; border-radius: 6px; box-shadow: 0 4px 14px rgba(34, 197, 94, 0.35);">
          Open Admin Console
        </a>
      </div>
    </div>
    <div style="background: #091710; padding: 16px 28px; border-top: 1px solid rgba(255,255,255,0.05); text-align: center; font-size: 12px; color: #64748b;">
      AYUR-INTEL · Automated Security Notification · Do not reply directly to this email
    </div>
  </div>
</body>
</html>"""

    return {
        "subject": subject,
        "text": plain_text,
        "html": html_content,
        "type_label": type_label,
        "created_ist": created_ist,
    }


def send_email_via_smtp(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: str,
) -> Tuple[bool, Optional[str]]:
    """Send email via standard SMTP (e.g. Gmail, SendGrid, Amazon SES, or custom relay)."""
    host = os.getenv("SMTP_HOST") or getattr(settings, "SMTP_HOST", None)
    if not host:
        return False, "SMTP_HOST not configured"

    raw_port = os.getenv("SMTP_PORT") or getattr(settings, "SMTP_PORT", 587)
    try:
        port = int(raw_port)
    except (ValueError, TypeError):
        port = 587

    user = os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME") or getattr(settings, "SMTP_USER", None)
    password = os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS") or getattr(settings, "SMTP_PASSWORD", None)

    sender_email = (
        os.getenv("SMTP_FROM_EMAIL")
        or os.getenv("EMAIL_FROM")
        or getattr(settings, "SMTP_FROM_EMAIL", None)
        or user
        or "noreply@ayur-intel.onrender.com"
    )
    sender_name = os.getenv("SMTP_FROM_NAME") or getattr(settings, "SMTP_FROM_NAME", "AYUR-INTEL Notifications")
    from_header = f"{sender_name} <{sender_email}>" if sender_name else sender_email

    use_ssl = (
        str(os.getenv("SMTP_USE_SSL", "")).lower() in ("true", "1")
        or bool(getattr(settings, "SMTP_USE_SSL", False))
        or port == 465
    )
    use_tls = (
        str(os.getenv("SMTP_USE_TLS", "true")).lower() in ("true", "1")
        and not use_ssl
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = to_email
    msg.set_content(text_content)
    msg.add_alternative(html_content, subtype="html")

    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as server:
                if user and password:
                    server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                if use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                if user and password:
                    server.login(user, password)
                server.send_message(msg)

        logger.info("Admin notification successfully delivered via SMTP to %s", to_email)
        return True, None
    except Exception as e:
        safe_msg = f"{type(e).__name__}: {str(e)}"
        logger.warning("SMTP delivery failed to %s: %s", to_email, safe_msg)
        return False, safe_msg


def send_email_via_resend(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: str,
) -> Tuple[bool, Optional[str]]:
    """Send email via Resend API."""
    api_key = os.getenv("RESEND_API_KEY") or getattr(settings, "RESEND_API_KEY", None)
    if not api_key or not str(api_key).strip():
        return False, "RESEND_API_KEY not configured"

    from_email = (
        os.getenv("RESEND_FROM_EMAIL")
        or os.getenv("EMAIL_FROM")
        or getattr(settings, "RESEND_FROM_EMAIL", None)
        or "AYUR-INTEL <notifications@ayur-intel.com>"
    )

    headers = {
        "Authorization": f"Bearer {str(api_key).strip()}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": text_content,
        "html": html_content,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post("https://api.resend.com/emails", json=payload, headers=headers)
            if 200 <= resp.status_code < 300:
                logger.info("Admin notification delivered via Resend to %s", to_email)
                return True, None
            else:
                err_detail = resp.text[:200]
                logger.warning("Resend delivery failed (HTTP %s): %s", resp.status_code, err_detail)
                return False, f"Resend API HTTP {resp.status_code}: {err_detail}"
    except Exception as e:
        safe_msg = f"{type(e).__name__}: {str(e)}"
        logger.warning("Resend request exception: %s", safe_msg)
        return False, safe_msg


def dispatch_admin_notification(
    applicant_name: str,
    applicant_email: str,
    request_type: str,
    created_at: Optional[datetime] = None,
    device_info: Optional[str] = None,
    reason: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Dispatch admin notification email using configured provider (or test hook)."""
    admin_recipient = get_effective_admin_recipient()
    content = build_access_request_email(
        applicant_name=applicant_name,
        applicant_email=applicant_email,
        request_type=request_type,
        created_at=created_at,
        device_info=device_info,
        reason=reason,
    )

    # 1. Test Interceptor Hook (Automated tests: never send real external emails)
    if _TEST_EMAIL_HOOK is not None:
        email_record = {
            "recipient": admin_recipient,
            "subject": content["subject"],
            "text": content["text"],
            "html": content["html"],
            "applicant_name": applicant_name,
            "applicant_email": applicant_email,
            "request_type": content["type_label"],
            "created_ist": content["created_ist"],
        }
        _OUTBOX_FOR_TESTS.append(email_record)
        success = _TEST_EMAIL_HOOK(email_record)
        if success:
            return True, None
        return False, "Simulated test email failure"

    # 2. Resend Provider (if configured)
    resend_key = os.getenv("RESEND_API_KEY") or getattr(settings, "RESEND_API_KEY", None)
    if resend_key and str(resend_key).strip():
        ok, err = send_email_via_resend(
            to_email=admin_recipient,
            subject=content["subject"],
            text_content=content["text"],
            html_content=content["html"],
        )
        if ok:
            return True, None
        return False, err

    # 3. SMTP Provider (if configured)
    smtp_host = os.getenv("SMTP_HOST") or getattr(settings, "SMTP_HOST", None)
    if smtp_host and str(smtp_host).strip():
        ok, err = send_email_via_smtp(
            to_email=admin_recipient,
            subject=content["subject"],
            text_content=content["text"],
            html_content=content["html"],
        )
        if ok:
            return True, None
        return False, err

    # 4. No email provider configured
    logger.info(
        "Admin email notification not dispatched: Neither SMTP nor Resend is configured. "
        "Access request for %s recorded in database.",
        applicant_email,
    )
    return False, "No email provider configured (configure SMTP_* or RESEND_API_KEY)"
