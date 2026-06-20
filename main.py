#!/usr/bin/env python3
"""
Bulk Auth 9Router - Unified CLI
Supports both Qoder and Kiro providers

Usage:
  python main.py --provider qoder    # Bulk auth Qoder accounts
  python main.py --provider kiro     # Bulk auth Kiro accounts
  python main.py --template          # Create accounts.json template
"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import DELAY_BETWEEN_ACCOUNTS
from utils.logger import print_header, print_info, print_success, print_error
from core.accounts import load_accounts, create_template, save_results


def print_usage():
    """Print usage information"""
    print_header("🚀 Bulk Auth 9Router - Unified CLI")
    print("\nUsage:")
    print("  python main.py --provider qoder    # Bulk auth Qoder accounts")
    print("  python main.py --provider kiro     # Bulk auth Kiro accounts")
    print("  python main.py --template          # Create accounts.json template")
    print("\nExamples:")
    print("  python main.py --provider qoder")
    print("  python main.py --provider kiro")
    print()


async def run_qoder_bulk_auth(accounts, shared_password):
    """Run Qoder bulk auth"""
    from providers.qoder.auth import authenticate_device_flow
    from providers.qoder.oauth import initiate_device_flow, poll_device_token
    from router.injector import add_to_9router_device
    
    print_header("🔧 Qoder Bulk Auth Started")
    results = []
    
    for i, account in enumerate(accounts):
        name = account["name"]
        email = account["email"]
        password = shared_password or account.get("password", "")
        
        print_info(f"[{i+1}/{len(accounts)}] Processing {name} ({email})")
        
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
            
            # Step 2: Authenticate
            auth_success = await authenticate_device_flow(email, password, auth_url)
            if not auth_success:
                result["error"] = "Authentication failed"
                results.append(result)
                continue
            
            # Step 3: Poll device token
            device_token = await asyncio.to_thread(
                poll_device_token, flow["nonce"], flow["verifier"], 60, 2
            )
            if not device_token:
                result["error"] = "Device token poll timeout"
                results.append(result)
                continue
            
            # Step 4: Inject to 9Router
            injected = add_to_9router_device(email, name, device_token, machine_id)
            result["injected"] = injected
            result["success"] = injected
            
            if injected:
                print_success(f"  ✅ {name} completed!")
            else:
                result["error"] = "9Router injection failed"
                print_error(f"  ❌ Injection failed for {name}")
        
        except Exception as e:
            result["error"] = str(e)
            print_error(f"  ❌ Error: {e}")
        
        results.append(result)
        
        if i < len(accounts) - 1:
            await asyncio.sleep(DELAY_BETWEEN_ACCOUNTS)
    
    return results


async def run_kiro_bulk_auth(accounts, shared_password):
    """Run Kiro bulk auth"""
    from providers.kiro.auth import authenticate
    from providers.kiro.tokens import exchange_code_for_tokens
    from router.injector import add_to_9router_device
    
    print_header("🔧 Kiro Bulk Auth Started")
    results = []
    
    for i, account in enumerate(accounts):
        name = account["name"]
        email = account["email"]
        password = shared_password or account.get("password", "")
        
        print_info(f"[{i+1}/{len(accounts)}] Processing {name} ({email})")
        
        result = {
            "name": name,
            "email": email,
            "provider": "kiro",
            "success": False,
            "injected": False,
            "error": ""
        }
        
        try:
            # Step 1: Authenticate and get auth code
            auth_code = await authenticate(email, password)
            if not auth_code:
                result["error"] = "Authentication failed"
                results.append(result)
                continue
            
            # Step 2: Exchange code for tokens
            tokens = exchange_code_for_tokens(auth_code)
            if not tokens:
                result["error"] = "Token exchange failed"
                results.append(result)
                continue
            
            # Step 3: Inject to 9Router (adapt for Kiro format)
            # TODO: Need to adapt injector for Kiro format
            print_error(f"  ⚠️  Kiro injection not yet implemented")
            result["error"] = "Kiro injection not implemented"
        
        except Exception as e:
            result["error"] = str(e)
            print_error(f"  ❌ Error: {e}")
        
        results.append(result)
        
        if i < len(accounts) - 1:
            await asyncio.sleep(DELAY_BETWEEN_ACCOUNTS)
    
    return results


async def main():
    """Main entry point"""
    if "--template" in sys.argv:
        create_template()
        return
    
    if "--provider" not in sys.argv:
        print_usage()
        sys.exit(1)
    
    provider_idx = sys.argv.index("--provider")
    if provider_idx + 1 >= len(sys.argv):
        print_error("Error: --provider requires an argument (qoder or kiro)")
        print_usage()
        sys.exit(1)
    
    provider = sys.argv[provider_idx + 1].lower()
    if provider not in ["qoder", "kiro"]:
        print_error(f"Error: Invalid provider '{provider}'. Must be 'qoder' or 'kiro'")
        print_usage()
        sys.exit(1)
    
    # Load accounts
    accounts_file = "accounts.json"
    if not os.path.exists(accounts_file):
        print_error(f"Accounts file not found: {accounts_file}")
        create_template(accounts_file)
        print_info("Edit accounts.json with your accounts and run again.")
        return
    
    accounts = load_accounts(accounts_file)
    if not accounts:
        print_error("No valid accounts found!")
        return
    
    shared_password = accounts[0].get("password", "")
    print_info(f"Provider: {provider}")
    print_info(f"Total accounts: {len(accounts)}\n")
    
    # Run provider-specific bulk auth
    if provider == "qoder":
        results = await run_qoder_bulk_auth(accounts, shared_password)
    else:
        results = await run_kiro_bulk_auth(accounts, shared_password)
    
    # Save results
    save_results(results)
    
    # Summary
    print_header("📊 Summary")
    success_count = sum(1 for r in results if r["success"])
    failed_count = len(results) - success_count
    
    print(f"  Total:   {len(results)}")
    print(f"  Success: {success_count}")
    print(f"  Failed:  {failed_count}\n")
    
    if failed_count > 0:
        print("  Failed accounts:")
        for r in results:
            if not r["success"]:
                print(f"    - {r['name']} ({r['email']}): {r['error']}")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_error("\n⚠ Interrupted by user")
        sys.exit(0)
