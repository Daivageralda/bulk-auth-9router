"""
Kiro quota/usage fetching
"""
import ssl
from urllib.parse import quote
import aiohttp

from config import KIRO_USAGE_ENDPOINT, KIRO_REGION, REQUEST_TIMEOUT
from providers.kiro.tokens import refresh_access_token
from utils.logger import print_info, print_error, print_success

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _build_usage_url(profile_arn):
    """Build Kiro usage endpoint URL with profile ARN"""
    base = KIRO_USAGE_ENDPOINT
    params = ["origin=AI_EDITOR", "resourceType=AGENTIC_REQUEST"]
    if profile_arn:
        params.append(f"profileArn={quote(profile_arn, safe='')}")
    sep = "&" if "?" in base else "?"
    return base + sep + "&".join(params)


async def fetch_quota(tokens):
    """
    Fetch usage quota for a Kiro account
    Auto-refreshes access_token if expired (401/403)
    Returns dict with limit, remaining, etc.
    """
    access_token = str(tokens.get("access_token") or "").strip()
    if not access_token:
        refreshed = await refresh_access_token(tokens.get("refresh_token", ""))
        if not refreshed:
            return None
        tokens.update(refreshed)
        access_token = tokens.get("access_token", "")

    profile_arn = str(
        tokens.get("profile_arn") or tokens.get("profileArn") or ""
    ).strip()
    usage_url = _build_usage_url(profile_arn)

    for attempt in range(2):
        access_token = str(tokens.get("access_token") or "").strip()
        if not access_token:
            return None

        try:
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as client:
                async with client.get(
                    usage_url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "User-Agent": "enowXGateway/1.0.0",
                    },
                    ssl=_SSL_CTX,
                ) as resp:
                    if resp.status == 200:
                        payload = await resp.json()
                        return _parse_quota(payload)

                    if resp.status in (401, 403) and attempt == 0:
                        refreshed = await refresh_access_token(
                            tokens.get("refresh_token", "")
                        )
                        if refreshed:
                            tokens.update(refreshed)
                            continue
                        return None

                    body = await resp.text()
                    print_error(f"Quota fetch failed ({resp.status}): {body[:100]}")
                    return None

        except Exception as exc:
            print_error(f"Quota fetch error: {exc}")
            return None

    return None


def _parse_quota(payload):
    """Parse Kiro usage API response"""
    usage_list = payload.get("usageBreakdownList") or []
    if not usage_list:
        return {"limit": 0, "remaining": 0}

    usage = usage_list[0] or {}
    sub_type = str(payload.get("subscriptionType") or "").strip()
    sub_title = str(payload.get("subscriptionTitle") or "").strip()

    usage_limit = float(usage.get("usageLimit") or 0)
    current_usage = float(usage.get("currentUsage") or 0)
    total_credits = usage_limit
    total_usage = current_usage

    # Free trial
    free_trial = usage.get("freeTrialInfo") or {}
    if str(free_trial.get("freeTrialStatus") or "").upper() == "ACTIVE":
        ft_limit = float(free_trial.get("usageLimit") or 0)
        ft_usage = float(free_trial.get("currentUsage") or 0)
        total_credits += ft_limit
        total_usage += ft_usage

    # Bonuses
    bonus_credits = 0.0
    for bonus in usage.get("bonuses") or []:
        bonus_credits += float((bonus or {}).get("usageLimit") or 0)
        total_usage += float((bonus or {}).get("currentUsage") or 0)
    total_credits += bonus_credits

    remaining = max(0.0, total_credits - total_usage)

    return {
        "subscription_type": sub_type,
        "subscription_title": sub_title,
        "account_tier": sub_title or sub_type or "free",
        "limit": total_credits,
        "remaining": remaining,
        "current_usage": total_usage,
        "days_until_reset": int(payload.get("daysUntilReset") or 0),
    }
