"""
Account management utilities
"""
import json
from pathlib import Path

def load_accounts(filepath="accounts.json"):
    """Load accounts from JSON file"""
    with open(filepath, "r") as f:
        data = json.load(f)
    return data.get("accounts", [])

def save_results(results, filepath="results.json"):
    """Save results to JSON file"""
    with open(filepath, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {filepath}")

def create_template(filepath="accounts.json"):
    """Create accounts.json template"""
    template = {
        "accounts": [
            {
                "name": "Account 1",
                "email": "email1@gmail.com",
                "password": "your-password-here"
            },
            {
                "name": "Account 2", 
                "email": "email2@gmail.com",
                "password": "your-password-here"
            }
        ]
    }
    with open(filepath, "w") as f:
        json.dump(template, f, indent=2)
    print(f"Template created: {filepath}")
