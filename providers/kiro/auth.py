"""
Kiro authentication orchestrator
Runs the full Google OAuth flow and extracts authorization code
"""
import asyncio
import time
from urllib.parse import urlparse

from providers.kiro.browser import (
    bootstrap_browser_session,
    _is_password_step,
    _is_email_step,
    _click_google_next,
)
from providers.kiro.browser_fill import (
    fill_google_email,
    fill_google_password,
    _handle_google_consent,
)
from utils.helpers import extract_code_from_kiro_url
from utils.logger import print_info, print_success, print_error, print_warning


async def authenticate(email, password):
    """
    Full authentication flow:
    1. Open browser to Kiro login
    2. Fill Google email + password
    3. Handle consent screens
    4. Capture authorization code from kiro:// callback
    Returns dict with auth_code and code_verifier, or None on failure
    """
    print_info(f"Opening browser for {email}...")
    session = await bootstrap_browser_session()
    page = session.get("page")

    email_transition_deadline = 0.0
    password_transition_deadline = 0.0
    email_step_started_at = None

    for _ in range(90):
        # Check if auth code captured
        code = session.get("auth_code")
        if code:
            print_success(f"Authorization code captured!")
            return {
                "auth_code": code,
                "code_verifier": session.get("code_verifier", ""),
                "session": session,
            }

        try:
            current_url = page.url
        except Exception:
            print_error("Browser page lost")
            await cleanup_session(session)
            return None

        parsed_url = urlparse(current_url) if current_url else None
        current_host = parsed_url.netloc if parsed_url else ""
        current_path = parsed_url.path if parsed_url else ""
        now = time.monotonic()

        # Skip SetSID redirects
        if "SetSID" in current_url or "/accounts/set" in current_url.lower():
            await asyncio.sleep(0.5)
            continue

        # Handle consent screen
        if await _handle_google_consent(page):
            await asyncio.sleep(0.8)
            continue

        on_google_auth = "accounts.google.com" in current_host
        if on_google_auth:
            at_password = await _is_password_step(page)
            at_email = await _is_email_step(page)

            if at_email and not at_password:
                if email_step_started_at is None:
                    email_step_started_at = now
                elif now - email_step_started_at > 60.0:
                    print_error("Email step stuck > 60s (captcha suspected)")
                    await cleanup_session(session)
                    return None

                if now < email_transition_deadline:
                    await asyncio.sleep(0.4)
                    continue

                if await fill_google_email(page, email):
                    email_transition_deadline = time.monotonic() + 6.0
                    await asyncio.sleep(1.0)
                    continue

            if at_password:
                email_step_started_at = None
                if now < password_transition_deadline:
                    await asyncio.sleep(0.4)
                    continue

                if await fill_google_password(page, password):
                    password_transition_deadline = time.monotonic() + 8.0
                    await asyncio.sleep(1.0)
                    continue

            if at_email or at_password:
                await asyncio.sleep(0.6)
                continue
        else:
            email_step_started_at = None

        # Generic continue button click
        await _click_google_next(page)
        await asyncio.sleep(1.0)

    print_error("Authorization code not received after 90 iterations")
    await cleanup_session(session)
    return None


async def cleanup_session(session):
    """Close browser session"""
    if not isinstance(session, dict):
        return
    manager = session.get("manager")
    if manager is None:
        return
    try:
        await manager.__aexit__(None, None, None)
    except Exception:
        pass
