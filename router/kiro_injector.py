"""
Inject Kiro refresh tokens into 9Router
Writes directly to 9Router's SQLite database (providerConnections table)

Schema:
  providerConnections(
    id TEXT PRIMARY KEY,      -- UUID
    provider TEXT,            -- 'kiro'
    authType TEXT,            -- 'oauth'
    name TEXT,                -- display name
    email TEXT,               -- account email (can be empty)
    priority INTEGER,         -- auto-increment per provider
    isActive INTEGER,         -- 1 or 0
    data TEXT,                -- JSON blob (see below)
    createdAt TEXT,           -- ISO timestamp
    updatedAt TEXT            -- ISO timestamp
  )

data JSON structure:
  {
    "accessToken": "...",
    "refreshToken": "...",
    "expiresAt": "2026-06-19T12:23:03.348Z",
    "testStatus": "active",
    "expiresIn": 2592000,
    "providerSpecificData": {
      "authMethod": "imported",
      "provider": "Imported",
      "profileArn": "arn:aws:codewhisperer:..."
    }
  }
"""
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from config import ROUTER_DB_PATH
from utils.logger import print_info, print_success, print_error, print_warning


def _utc_now_iso():
    """Get current UTC time in ISO format"""
    return datetime.now(timezone.utc).isoformat()


def _build_data_json(refresh_token, access_token="", profile_arn="", expires_in=2592000):
    """Build the JSON blob for the data column"""
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).isoformat()

    provider_data = {
        "authMethod": "imported",
        "provider": "Imported",
    }
    if profile_arn:
        provider_data["profileArn"] = profile_arn

    return json.dumps({
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "expiresAt": expires_at,
        "testStatus": "active",
        "expiresIn": expires_in,
        "providerSpecificData": provider_data,
    })


async def inject_via_db(account_name, refresh_token, access_token="", profile_arn="", email=""):
    """
    Insert or update a Kiro connection in 9Router's SQLite database.
    Bypasses REST API (no password needed).

    Args:
        account_name: Display name for the connection
        refresh_token: Kiro refresh token
        access_token: Kiro access token (optional, can be empty)
        profile_arn: Kiro profile ARN (optional)
        email: Account email (for duplicate checking)

    Returns:
        True if successful, False otherwise
    """
    print_info(f"  DB injection for {account_name}...")

    db_path = str(ROUTER_DB_PATH.expanduser())

    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            cursor = conn.cursor()

            # Check if connection with same email exists (if email provided)
            existing = None
            if email:
                cursor.execute(
                    "SELECT id, name, priority FROM providerConnections WHERE provider='kiro' AND email=?",
                    (email,),
                )
                existing = cursor.fetchone()
            
            # If no email match, check by name
            if not existing:
                cursor.execute(
                    "SELECT id, name, priority FROM providerConnections WHERE provider='kiro' AND name=?",
                    (account_name,),
                )
                existing = cursor.fetchone()

            data_json = _build_data_json(refresh_token, access_token, profile_arn)
            now = _utc_now_iso()

            if existing:
                # Update existing connection
                conn_id = existing[0]
                cursor.execute(
                    """UPDATE providerConnections
                       SET data=?, updatedAt=?, isActive=1, email=?
                       WHERE id=?""",
                    (data_json, now, email, conn_id),
                )
                print_success(f"  Updated existing: {account_name} (id={conn_id[:8]}...)")
            else:
                # Get next priority for kiro provider
                cursor.execute(
                    "SELECT COALESCE(MAX(priority),0)+1 FROM providerConnections WHERE provider='kiro'"
                )
                priority = cursor.fetchone()[0]

                conn_id = str(uuid.uuid4())
                cursor.execute(
                    """INSERT INTO providerConnections
                       (id, provider, authType, name, email, priority, isActive, data, createdAt, updatedAt)
                       VALUES (?, 'kiro', 'oauth', ?, ?, ?, 1, ?, ?, ?)""",
                    (conn_id, account_name, email, priority, data_json, now, now),
                )
                print_success(f"  Created new: {account_name} (#{priority}, id={conn_id[:8]}...)")

            conn.commit()
            return True

    except sqlite3.Error as exc:
        print_error(f"  DB injection failed: {exc}")
        return False
    except Exception as exc:
        print_error(f"  DB injection error: {exc}")
        return False


async def inject_via_api(account_name, refresh_token, access_token="", profile_arn="", email=""):
    """Fallback: inject via 9router HTTP API (requires login)"""
    import aiohttp
    from config import ROUTER_API_URL, ROUTER_LOGIN_URL, ROUTER_PASSWORD, REQUEST_TIMEOUT

    print_info(f"  API injection for {account_name}...")

    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            # Login to get session token
            async with client.post(
                ROUTER_LOGIN_URL,
                json={"password": ROUTER_PASSWORD},
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    print_error(f"  9router login failed: {resp.status}")
                    return False
                data = await resp.json()
                session_token = data.get("token", "")

            # Add connection via API
            async with client.post(
                ROUTER_API_URL,
                json={
                    "name": account_name,
                    "refreshToken": refresh_token,
                    "accessToken": access_token,
                    "profileArn": profile_arn,
                    "enabled": True,
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {session_token}",
                },
            ) as resp:
                if resp.status in (200, 201):
                    print_success(f"  API injection OK: {account_name}")
                    return True
                body = await resp.text()
                print_error(f"  API injection failed: {resp.status} - {body[:100]}")
                return False

    except Exception as exc:
        print_error(f"  API injection error: {exc}")
        return False


async def inject_token(account_name, refresh_token, access_token="", profile_arn="", email=""):
    """
    Inject token to 9Router.
    Tries DB injection first (no password needed), falls back to API.
    Returns True on success.
    """
    success = await inject_via_db(account_name, refresh_token, access_token, profile_arn, email)
    if not success:
        print_warning(f"  DB failed, trying API...")
        success = await inject_via_api(account_name, refresh_token, access_token, profile_arn, email)
    return success
