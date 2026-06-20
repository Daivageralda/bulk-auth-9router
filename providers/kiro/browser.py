"""
Browser automation for Kiro Google OAuth login
Uses Camoufox (anti-detect Firefox) via Playwright API
"""
import asyncio
import os
import time
import uuid
from urllib.parse import urlparse

from config import HEADLESS, DEBUG
from utils.helpers import generate_pkce_pair, extract_code_from_kiro_url, build_auth_url
from utils.logger import print_info, print_error, print_success, print_warning


async def bootstrap_browser_session():
    """Open Camoufox browser and navigate to Kiro login page"""
    try:
        from browserforge.fingerprints import Screen
        from camoufox.async_api import AsyncCamoufox
    except ImportError as exc:
        raise RuntimeError(
            f"Missing browser deps: pip install camoufox browserforge\n{exc}"
        )

    code_verifier, code_challenge = generate_pkce_pair()
    state_uuid = str(uuid.uuid4())
    state = {
        "auth_code": None,
        "code_verifier": code_verifier,
        "stub": False,
    }

    camoufox_kwargs = {
        "headless": HEADLESS,
        "os": "windows",
        "block_webrtc": True,
        "humanize": False,
        "screen": Screen(max_width=1920, max_height=1080),
    }

    proxy_url = os.getenv("BATCHER_PROXY_URL", "")
    if proxy_url:
        parsed = urlparse(proxy_url)
        proxy_cfg = {
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
        }
        if parsed.username:
            proxy_cfg["username"] = parsed.username
        if parsed.password:
            proxy_cfg["password"] = parsed.password
        camoufox_kwargs["proxy"] = proxy_cfg
        camoufox_kwargs["geoip"] = True

    manager = AsyncCamoufox(**camoufox_kwargs)
    browser = await manager.__aenter__()
    page = await browser.new_page()
    page.set_default_timeout(15000)

    # Intercept kiro:// callback to capture auth code
    def on_response(response):
        if state.get("auth_code"):
            return
        try:
            location = response.headers.get("location", "")
            code = extract_code_from_kiro_url(location)
            if code:
                state["auth_code"] = code
        except Exception:
            return

    page.on("response", on_response)

    async def route_handler(route):
        if state.get("auth_code"):
            await route.continue_()
            return
        request_url = route.request.url
        code = extract_code_from_kiro_url(request_url)
        if code:
            state["auth_code"] = code
            await route.abort()
            return
        await route.continue_()

    await page.route("**/*", route_handler)

    auth_url = build_auth_url(code_challenge, state_uuid)
    await page.goto(auth_url, wait_until="domcontentloaded", timeout=20000)

    state.update({
        "manager": manager,
        "browser": browser,
        "page": page,
    })
    return state


async def _is_password_step(page):
    try:
        return bool(await page.evaluate("""() => {
            for (const el of document.querySelectorAll(
                'input[type="password"], input[name="Passwd"]'
            )) {
                if (el.offsetParent !== null) return true;
            }
            return false;
        }"""))
    except Exception:
        return False


async def _is_email_step(page):
    try:
        return bool(await page.evaluate("""() => {
            for (const el of document.querySelectorAll(
                'input[type="email"], input[name="identifier"], #identifierId'
            )) {
                if (el.offsetParent !== null) return true;
            }
            return false;
        }"""))
    except Exception:
        return False


async def _click_google_next(page):
    try:
        return bool(await page.evaluate("""() => {
            const bySubmit = document.querySelector(
                '#identifierNext button, #passwordNext button'
            );
            if (bySubmit && bySubmit.offsetParent !== null) {
                bySubmit.click();
                return true;
            }
            for (const el of document.querySelectorAll(
                'div.VfPpkd-RLmnJb, button, div[role="button"]'
            )) {
                const parentBtn = el.closest('button, div[role="button"]') || el;
                if (parentBtn && parentBtn.offsetParent !== null) {
                    parentBtn.click();
                    return true;
                }
            }
            return false;
        }"""))
    except Exception:
        return False
