"""
Logger utilities
"""

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def print_step(current, total, text):
    print(f"\n[{current}/{total}] {text}")

def print_info(text):
    print(f"ℹ️  {text}")

def print_success(text):
    print(f"✅ {text}")

def print_error(text):
    print(f"❌ {text}")

def print_warning(text):
    print(f"⚠️  {text}")
