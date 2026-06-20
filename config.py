"""
Bulk Auth 9Router - Unified Configuration
Supports both Qoder and Kiro providers
"""
import os
from pathlib import Path


def _load_dotenv():
    """Lightweight .env loader (no external dependency needed)."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()

# Directories
BASE_DIR = Path(__file__).parent
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

# 9Router Configuration
NINEROUTER_URL = os.getenv("NINEROUTER_URL", "http://localhost:20128")
NINEROUTER_PASSWORD = os.getenv("NINEROUTER_PASSWORD", "")
ROUTER_API_URL = f"{NINEROUTER_URL}/api/connections"
ROUTER_LOGIN_URL = f"{NINEROUTER_URL}/api/login"
ROUTER_PASSWORD = NINEROUTER_PASSWORD

# Default 9Router DB path (OS-aware)
def get_default_ninerouter_db():
    import platform
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return os.path.join(appdata, "9router", "db", "data.sqlite")
        return os.path.join(str(Path.home()), "AppData", "Roaming", "9router", "db", "data.sqlite")
    return str(Path.home() / ".9router" / "db" / "data.sqlite")

NINEROUTER_DB = os.getenv("NINEROUTER_DB", get_default_ninerouter_db())
ROUTER_DB_PATH = Path(NINEROUTER_DB)

# Qoder Configuration
QODER_SIGNIN_URL = "https://qoder.com/users/sign-in"
QODER_LOGIN_URL = "https://qoder.com/device/selectAccounts"
QODER_DEVICE_TOKEN_URL = "https://openapi.qoder.sh/api/v1/deviceToken/poll"
QODER_USERINFO_URL = "https://openapi.qoder.sh/api/v1/userinfo"

# Kiro Configuration
KIRO_AUTH_BASE = "https://prod.us-east-1.auth.desktop.kiro.dev"
KIRO_LOGIN_ENDPOINT = f"{KIRO_AUTH_BASE}/login"
KIRO_TOKEN_ENDPOINT = f"{KIRO_AUTH_BASE}/oauth/token"
KIRO_REFRESH_ENDPOINT = f"{KIRO_AUTH_BASE}/refreshToken"
KIRO_USAGE_ENDPOINT = "https://q.us-east-1.amazonaws.com/getUsageLimits"
KIRO_REDIRECT_URI = "kiro://kiro.kiroAgent/authenticate-success"
KIRO_REGION = "us-east-1"

# Browser Automation
HEADLESS = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")  # Headless mode for both providers
LOGIN_TIMEOUT = 120  # seconds
DEBUG = False
TIMEOUT = 30

# Rate Limiting & Retry
DELAY_BETWEEN_ACCOUNTS = 15  # seconds between accounts
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3  # Max retry attempts for failed auth
RETRY_DELAY = 5  # Delay before retry in seconds
