import os
import smtplib
from email.mime.text import MIMEText
from typing import Dict, Optional

from fastapi import Request
from jinja2 import Environment, FileSystemLoader, select_autoescape

from config.settings import get_settings
from utils.request_utils import get_request_origin


def _get_env() -> Environment:
    settings = get_settings()
    templates_dir = settings.EMAIL_TEMPLATES_DIR
    return Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html", "xml"]),
        enable_async=False,
    )


def render_template(template_name: str, context: Dict[str, object]) -> str:
    """Render HTML email from Jinja2 template"""
    env = _get_env()
    template = env.get_template(template_name)
    return template.render(**context)


def _detect_frontend_origin(request: Optional[Request]) -> Optional[str]:
    """Detect FE origin strictly from the incoming request (no static fallback)."""
    if request is not None:
        try:
            return get_request_origin(request)
        except Exception:
            return None
    return None


def send_mail(
    template_name: str,
    recipient_email: str,
    subject: str,
    context: Dict[str, object],
    request: Optional[Request] = None,
) -> None:
    """
    Send an email using SMTP with HTML body rendered from Jinja2 template.
    - Uses settings for SMTP and sender info
    - Injects `frontend_origin` into context if missing
    """
    settings = get_settings()
    frontend_origin = context.get("frontend_origin") or _detect_frontend_origin(request)
    ctx = {**context, "frontend_origin": frontend_origin}

    html = render_template(template_name, ctx)

    msg = MIMEText(html, "html")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
    msg["To"] = recipient_email

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_TLS:
            server.starttls()
        if settings.SMTP_USER and settings.SMTP_PASS:
            server.login(settings.SMTP_USER, settings.SMTP_PASS)
        server.send_message(msg)


async def send_mail_async(
    template_name: str,
    recipient_email: str,
    subject: str,
    context: Dict[str, object],
    rest_request: Optional[Request] = None,
) -> None:
    """Async friendly wrapper for send_mail"""
    send_mail(template_name, recipient_email, subject, context, request=rest_request) 