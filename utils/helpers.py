"""
Helper utilities for Kiro auth flow
"""
import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse


def generate_pkce_pair():
    """Generate PKCE code_verifier and code_challenge (S256)"""
    code_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def extract_code_from_kiro_url(url):
    """Extract authorization code from kiro:// callback URL"""
    if not url or not url.startswith("kiro://"):
        return None
    params = parse_qs(urlparse(url).query)
    values = params.get("code")
    if not values:
        return None
    return values[0]


def build_auth_url(code_challenge, state):
    """Build Kiro OAuth login URL with Google IDP"""
    from urllib.parse import urlencode
    from config import KIRO_LOGIN_ENDPOINT, KIRO_REDIRECT_URI
    return f"{KIRO_LOGIN_ENDPOINT}?" + urlencode({
        "idp": "Google",
        "redirect_uri": KIRO_REDIRECT_URI,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    })
