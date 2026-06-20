#!/usr/bin/env python3
"""
Bulk Auth 9Router - Unified Web UI
Flask web interface for both Qoder and Kiro providers
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from threading import Thread

from flask import Flask, render_template, request, jsonify, send_from_directory

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import DELAY_BETWEEN_ACCOUNTS
from utils.logger import print_header, print_info, print_success, print_error
from core.accounts import save_results

app = Flask(__name__)

# Global state
processing_state = {
    "is_running": False,
    "current_index": 0,
    "total_accounts": 0,
    "results": [],
    "provider": None,
    "logs": [],
}


def add_log(message, level="info"):
    """Add log message to processing state"""
    processing_state["logs"].append({"message": message, "level": level})
    # Keep last 100 logs only
    if len(processing_state["logs"]) > 100:
        processing_state["logs"] = processing_state["logs"][-100:]


@app.route("/")
def index():
    """Main page"""
    return render_template("index.html")


@app.route("/api/status")
def get_status():
    """Get current processing status"""
    return jsonify({
        **processing_state,
        "logs": processing_state["logs"]
    })


@app.route("/api/start", methods=["POST"])
def start_processing():
    """Start bulk auth processing"""
    global processing_state
    
    if processing_state["is_running"]:
        return jsonify({"error": "Already running"}), 400
    
    data = request.json
    provider = data.get("provider", "").lower()
    accounts = data.get("accounts", [])
    
    if provider not in ["qoder", "kiro", "both"]:
        return jsonify({"error": "Invalid provider. Must be 'qoder', 'kiro', or 'both'"}), 400
    
    if not accounts:
        return jsonify({"error": "No accounts provided"}), 400
    
    # Reset state
    processing_state["is_running"] = True
    processing_state["current_index"] = 0
    processing_state["total_accounts"] = len(accounts)
    processing_state["results"] = []
    processing_state["provider"] = provider
    processing_state["logs"] = []
    
    add_log(f"🚀 Starting bulk auth with {provider} provider", "info")
    add_log(f"📊 Total accounts: {len(accounts)}", "info")
    
    # Start processing in background thread
    thread = Thread(
        target=run_bulk_auth_sync,
        args=(provider, accounts),
        daemon=True
    )
    thread.start()
    
    return jsonify({"status": "started", "provider": provider, "total": len(accounts)})


def run_bulk_auth_sync(provider, accounts):
    """Run bulk auth in new event loop (for background thread)"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        if provider == "qoder":
            loop.run_until_complete(process_qoder_accounts(accounts))
        elif provider == "kiro":
            loop.run_until_complete(process_kiro_accounts(accounts))
        elif provider == "both":
            loop.run_until_complete(process_both_providers(accounts))
    finally:
        loop.close()
        processing_state["is_running"] = False


async def process_qoder_accounts(accounts):
    """Process Qoder accounts"""
    from providers.qoder.auth import authenticate_device_flow
    from providers.qoder.oauth import initiate_device_flow, poll_device_token
    from router.injector import add_to_9router_device
    
    shared_password = accounts[0].get("password", "") if accounts else ""
    
    add_log(f"🔧 Starting Qoder bulk auth for {len(accounts)} accounts", "info")
    
    for i, account in enumerate(accounts):
        processing_state["current_index"] = i + 1
        
        name = account["name"]
        email = account["email"]
        password = shared_password or account.get("password", "")
        
        add_log(f"📧 [{i+1}/{len(accounts)}] Processing {email} (Qoder)", "info")
        
        result = {
            "name": name,
            "email": email,
            "provider": "qoder",
            "success": False,
            "injected": False,
            "error": ""
        }
        
        try:
            # Step 1: Initiate device flow
            flow = initiate_device_flow()
            auth_url = flow["auth_url"]
            machine_id = flow["machine_id"]
            
            add_log(f"  🔗 Device flow initiated", "info")
            
            # Step 2: Authenticate
            auth_success = await authenticate_device_flow(email, password, auth_url)
            if not auth_success:
                result["error"] = "Authentication failed"
                add_log(f"  ❌ Authentication failed", "error")
                processing_state["results"].append(result)
                continue
            
            add_log(f"  ✅ Authentication successful", "success")
            
            # Step 3: Poll device token
            add_log(f"  🔄 Polling for device token...", "info")
            device_token = await asyncio.to_thread(
                poll_device_token, flow["nonce"], flow["verifier"], 60, 2
            )
            if not device_token:
                result["error"] = "Device token poll timeout"
                add_log(f"  ❌ Device token timeout for {email}", "error")
                processing_state["results"].append(result)
                continue
            
            add_log(f"  ✅ Device token obtained for {email}", "success")
            
            # Step 4: Inject to 9Router
            injected = add_to_9router_device(email, name, device_token, machine_id)
            result["injected"] = injected
            result["success"] = injected
            
            if injected:
                add_log(f"  ✅ Injected to 9Router", "success")
            else:
                result["error"] = "9Router injection failed"
                add_log(f"  ❌ 9Router injection failed", "error")
        
        except Exception as e:
            result["error"] = str(e)
        
        processing_state["results"].append(result)
        
        if i < len(accounts) - 1:
            await asyncio.sleep(DELAY_BETWEEN_ACCOUNTS)
    
    # Save final results
    save_results(processing_state["results"])


async def process_kiro_accounts(accounts):
    """Process Kiro accounts"""
    from providers.kiro.auth import authenticate
    from providers.kiro.tokens import exchange_code_for_tokens
    from router.kiro_injector import inject_token
    
    shared_password = accounts[0].get("password", "") if accounts else ""
    add_log(f"🎯 Starting Kiro bulk auth for {len(accounts)} accounts", "info")
    
    for i, account in enumerate(accounts):
        processing_state["current_index"] = i + 1
        
        name = account["name"]
        email = account["email"]
        password = shared_password or account.get("password", "")
        
        add_log(f"📧 [{i+1}/{len(accounts)}] Processing {email} (Kiro)", "info")
        
        result = {
            "name": name,
            "email": email,
            "provider": "kiro",
            "success": False,
            "injected": False,
            "error": ""
        }
        
        try:
            # Step 1: Authenticate and get auth code + verifier
            auth_result = await authenticate(email, password)
            if not auth_result:
                result["error"] = "Authentication failed"
                add_log(f"  ❌ Authentication failed for {email}", "error")
                processing_state["results"].append(result)
                continue
            
            auth_code = auth_result["auth_code"]
            code_verifier = auth_result["code_verifier"]
            add_log(f"  ✅ Auth code obtained for {email}", "success")
            
            # Step 2: Exchange code for tokens
            add_log(f"  🔄 Exchanging code for tokens...", "info")
            tokens = await exchange_code_for_tokens(auth_code, code_verifier)
            if not tokens:
                result["error"] = "Token exchange failed"
                add_log(f"  ❌ Token exchange failed for {email}", "error")
                processing_state["results"].append(result)
                continue
            
            add_log(f"  ✅ Tokens obtained (refresh_token: {len(tokens['refresh_token'])} chars)", "success")
            
            # Step 3: Inject to 9Router
            add_log(f"  💾 Injecting to 9Router...", "info")
            injected = await inject_token(
                account_name=name,
                refresh_token=tokens["refresh_token"],
                access_token=tokens.get("access_token", ""),
                profile_arn=tokens.get("profile_arn", ""),
                email=email
            )
            result["injected"] = injected
            result["success"] = injected
            
            if injected:
                add_log(f"  ✅ {email} injected to 9Router successfully!", "success")
            else:
                result["error"] = "9Router injection failed"
                add_log(f"  ❌ 9Router injection failed for {email}", "error")
        
        except Exception as e:
            result["error"] = str(e)
            add_log(f"  ❌ Exception for {email}: {str(e)}", "error")
        
        processing_state["results"].append(result)
        
        if i < len(accounts) - 1:
            await asyncio.sleep(DELAY_BETWEEN_ACCOUNTS)
    
    # Save final results
    save_results(processing_state["results"])


async def process_both_providers(accounts):
    """Process accounts with both Kiro and Qoder providers sequentially"""
    add_log(f"🚀 Running BOTH providers for {len(accounts)} accounts", "info")
    add_log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "info")
    
    # Run Kiro first
    add_log(f"🎯 PHASE 1: Kiro Authentication", "warning")
    processing_state["provider"] = "kiro"
    await process_kiro_accounts(accounts)
    
    add_log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "info")
    
    # Small delay between providers
    add_log(f"⏳ Waiting 5s before switching to Qoder...", "warning")
    await asyncio.sleep(5)
    
    # Then run Qoder
    add_log(f"🔧 PHASE 2: Qoder Authentication", "warning")
    processing_state["provider"] = "qoder"
    processing_state["current_index"] = 0
    await process_qoder_accounts(accounts)
    
    add_log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "info")
    
    # Save combined results
    save_results(processing_state["results"])
    
    success_count = sum(1 for r in processing_state["results"] if r["success"])
    add_log(f"🏁 ALL DONE! {success_count}/{len(processing_state['results'])} successful", "success")


@app.route("/api/results")
def get_results():
    """Get processing results"""
    return jsonify({
        "results": processing_state["results"],
        "total": processing_state["total_accounts"],
        "completed": len(processing_state["results"]),
        "is_running": processing_state["is_running"]
    })


@app.route("/api/stop", methods=["POST"])
def stop_processing():
    """Stop processing (graceful)"""
    # Note: Can't force stop async tasks, just mark as not running
    processing_state["is_running"] = False
    return jsonify({"status": "stopping"})


if __name__ == "__main__":
    print_header("🚀 Bulk Auth 9Router - Web UI")
    print_info("Starting Flask server on http://localhost:8485")
    print_info("Press Ctrl+C to stop\n")
    app.run(host="0.0.0.0", port=8485, debug=False)
