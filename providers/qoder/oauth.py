"""
Qoder OAuth Device Flow
Implements PKCE device authorization flow (copied from qoder-autopilot)
"""
import base64
import hashlib
import os
import time
import uuid
from urllib.parse import quote as url_quote
from urllib.parse import urlencode

import requests

from config import (
    QODER_SIGNIN_URL,
    QODER_LOGIN_URL,
    QODER_DEVICE_TOKEN_URL
)


def base64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE verifier + S256 challenge (32 random bytes).
    
    Returns:
        Tuple of (verifier, challenge).
    """
    verifier = base64url_encode(os.urandom(32))
    challenge = base64url_encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def initiate_device_flow() -> dict:
    """Generate the full device auth URL and parameters.
    
    Returns:
        dict with keys: auth_url, verifier, challenge, nonce, machine_id
    """
    verifier, challenge = generate_pkce_pair()
    nonce = str(uuid.uuid4())
    machine_id = str(uuid.uuid4())

    # Build direct device auth URL (same as 9Router "Add" button)
    params = urlencode(
        {
            "challenge": challenge,
            "challenge_method": "S256",
            "machine_id": machine_id,
            "nonce": nonce,
        }
    )
    auth_url = f"{QODER_LOGIN_URL}?{params}"

    return {
        "auth_url": auth_url,
        "verifier": verifier,
        "challenge": challenge,
        "nonce": nonce,
        "machine_id": machine_id,
    }


def poll_device_token(
    nonce: str,
    verifier: str,
    max_attempts: int = 60,
    interval: int = 2,
) -> dict | None:
    """Poll Qoder deviceToken endpoint until user authorizes.
    
    Args:
        nonce: The nonce from initiate_device_flow().
        verifier: The PKCE verifier from initiate_device_flow().
        max_attempts: Maximum number of polling attempts.
        interval: Seconds between polls.
    
    Returns:
        dict with {token, refresh_token, user_id, expires_at} or None on timeout.
    """
    url = (
        f"{QODER_DEVICE_TOKEN_URL}"
        f"?nonce={url_quote(nonce)}"
        f"&verifier={url_quote(verifier)}"
        f"&challenge_method=S256"
    )
    headers = {"Accept": "application/json", "User-Agent": "Go-http-client/2.0"}

    print(f"  Polling device token (max {max_attempts * interval}s)...")
    for i in range(max_attempts):
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code in (202, 404):
                # Still pending
                if i % 10 == 0 and i > 0:
                    print(f"  ⏳ Poll #{i} — still waiting...")
                time.sleep(interval)
                continue
            if r.status_code == 200:
                body = r.json()
                if body.get("token"):
                    print(f"  ✅ Device token received! user_id={body.get('user_id', '?')}")
                    return body
                else:
                    print(f"  ⚠️  200 but no token: {body}")
            else:
                print(f"  ⚠️  Poll #{i} unexpected status: {r.status_code}")
            time.sleep(interval)
        except requests.RequestException as e:
            print(f"  ⚠️  Poll error: {e}")
            time.sleep(interval)

    print("  ❌ Device token poll timed out")
    return None
