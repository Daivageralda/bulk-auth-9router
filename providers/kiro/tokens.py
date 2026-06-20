"""
Kiro token exchange and refresh logic
"""
import json
import ssl
import aiohttp

from config import (
    KIRO_TOKEN_ENDPOINT,
    KIRO_REFRESH_ENDPOINT,
    KIRO_REDIRECT_URI,
    KIRO_USAGE_ENDPOINT,
    REQUEST_TIMEOUT,
)
from utils.logger import print_info, print_success, print_error

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


async def exchange_code_for_tokens(auth_code, code_verifier):
    """
    Exchange authorization code for access_token + refresh_token
    POST to Kiro token endpoint
    """
    print_info("Exchanging auth code for tokens...")
    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            async with client.post(
                KIRO_TOKEN_ENDPOINT,
                json={
                    "code": auth_code,
                    "code_verifier": code_verifier,
                    "redirect_uri": KIRO_REDIRECT_URI,
                },
                headers={"Content-Type": "application/json"},
                ssl=_SSL_CTX,
            ) as resp:
                if resp.status == 200:
                    payload = await resp.json()
                    access_token = payload.get("accessToken", "")
                    refresh_token = payload.get("refreshToken", "")
                    profile_arn = str(
                        payload.get("profileArn") or payload.get("profile_arn") or ""
                    ).strip()
                    expires_at = payload.get("expiresAt")
                    expires_in = payload.get("expiresIn")

                    if not access_token:
                        print_error("Token response missing accessToken")
                        return None

                    tokens = {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                    }
                    if profile_arn:
                        tokens["profile_arn"] = profile_arn
                    if expires_at is not None:
                        tokens["expires_at"] = str(expires_at)
                    if expires_in is not None:
                        tokens["expires_in"] = str(expires_in)

                    print_success(f"Tokens obtained! refresh_token length: {len(refresh_token)}")
                    return tokens

                if resp.status == 429:
                    print_error("Token endpoint rate limited (429)")
                    return None

                body = await resp.text()
                print_error(f"Token exchange failed ({resp.status}): {body[:120]}")
                return None

    except aiohttp.ServerTimeoutError:
        print_error("Token exchange timeout")
        return None
    except aiohttp.ClientConnectionError:
        print_error("Token exchange connection error")
        return None
    except Exception as exc:
        print_error(f"Token exchange error: {exc}")
        return None


async def refresh_access_token(refresh_token):
    """
    Refresh expired access token using refresh_token
    Returns updated tokens dict or None on failure
    """
    if not refresh_token:
        return None

    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            async with client.post(
                KIRO_REFRESH_ENDPOINT,
                json={"refreshToken": refresh_token},
                headers={"Content-Type": "application/json"},
                ssl=_SSL_CTX,
            ) as resp:
                body = await resp.text()
                if resp.status != 200:
                    print_error(f"Refresh failed: {resp.status} - {body[:100]}")
                    return None

                payload = json.loads(body)

        access_token = str(payload.get("accessToken") or "").strip()
        if not access_token:
            print_error("Refresh response missing accessToken")
            return None

        tokens = {"access_token": access_token}
        next_refresh = str(payload.get("refreshToken") or "").strip()
        if next_refresh:
            tokens["refresh_token"] = next_refresh
        else:
            tokens["refresh_token"] = refresh_token
        if payload.get("expiresIn") is not None:
            tokens["expires_in"] = str(payload.get("expiresIn"))
        if payload.get("expiresAt") is not None:
            tokens["expires_at"] = str(payload.get("expiresAt"))

        print_success("Token refreshed successfully!")
        return tokens

    except Exception as exc:
        print_error(f"Refresh request error: {exc}")
        return None


async def validate_token(refresh_token):
    """Check if a refresh_token is still valid"""
    result = await refresh_access_token(refresh_token)
    return result is not None
