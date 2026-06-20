"""
9Router Database Injector for Qoder (copied from qoder-autopilot)
Insert Qoder device tokens directly into 9Router SQLite DB
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from config import NINEROUTER_DB

def add_to_9router_device(
    email: str,
    display_name: str,
    device_token_body: dict,
    machine_id: str,
    db_path: str | None = None,
) -> bool:
    """Add a Qoder connection to 9Router DB using device token response.
    
    Args:
        email: The Qoder account email.
        display_name: Display name for the connection.
        device_token_body: Response from poll_device_token() containing
            token, refresh_token, user_id, expires_at, expires_in.
        machine_id: The machine_id from initiate_device_flow().
        db_path: Override path to 9Router SQLite DB.
    
    Returns:
        True if successfully inserted, False otherwise.
    """
    db = db_path or NINEROUTER_DB
    db = os.path.expanduser(db)
    
    print("💾 Adding to 9Router DB (device token flow)...")
    
    if not os.path.exists(db):
        print(f"❌ 9Router DB not found: {db}")
        return False
    
    try:
        at = device_token_body["token"]
        rt = device_token_body.get("refresh_token", "")
        user_id = device_token_body.get("user_id", "")
        expires_at = device_token_body.get("expires_at")
        expires_in = device_token_body.get("expires_in", 2592000)
        
        # Cap at 30 days (API sometimes returns unreasonable values)
        if expires_in > 2592000:
            expires_in = 2592000
        if not expires_at:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        
        with sqlite3.connect(db, timeout=10) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            c = conn.cursor()
            
            # Check for duplicate
            c.execute(
                "SELECT id, priority FROM providerConnections WHERE provider='qoder' AND email=?",
                (email,)
            )
            existing = c.fetchone()
            
            data = json.dumps(
                {
                    "displayName": display_name,
                    "accessToken": at,
                    "refreshToken": rt,
                    "expiresAt": expires_at,
                    "testStatus": "active",
                    "expiresIn": expires_in,
                    "providerSpecificData": {
                        "authMethod": "device",
                        "userId": user_id,
                        "machineId": machine_id,
                        "organizationId": "",
                    },
                }
            )
            
            now = datetime.now(timezone.utc).isoformat()
            
            if existing:
                # Update existing connection
                existing_id, existing_prio = existing
                c.execute(
                    """UPDATE providerConnections
                    SET name=?, data=?, updatedAt=?, isActive=1
                    WHERE id=?""",
                    (display_name, data, now, existing_id),
                )
                conn.commit()
                print(f"✅ Updated existing 9Router connection #{existing_prio} (device token)")
            else:
                # Insert new connection
                c.execute(
                    "SELECT COALESCE(MAX(priority),0)+1 FROM providerConnections WHERE provider='qoder'"
                )
                prio = c.fetchone()[0]
                
                c.execute(
                    """INSERT INTO providerConnections
                    (id, provider, authType, name, email, priority, isActive, data,
                     createdAt, updatedAt)
                    VALUES (?, 'qoder', 'oauth', ?, ?, ?, 1, ?, ?, ?)""",
                    (str(uuid.uuid4()), display_name, email, prio, data, now, now),
                )
                conn.commit()
                print(f"✅ Added to 9Router as #{prio} (device token)")
        
        return True
        
    except (sqlite3.Error, KeyError) as e:
        print(f"❌ DB injection failed: {e}")
        return False
