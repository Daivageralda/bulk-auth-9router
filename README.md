# 🔐 Bulk Auth 9Router

<p align="center">
  <strong>Unified bulk authentication tool for injecting AI provider accounts into <a href="https://github.com/nicepkg/9router">9Router</a>.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey" alt="Platform">
</p>

---

## ✨ Features

- **Multi-Provider** — Supports **Qoder** (device flow) and **Kiro** (OAuth flow) in a single tool
- **CLI & Web UI** — Use the command line or a browser-based dashboard
- **Headless Browser Automation** — Fully automated Google OAuth login via anti-detect browser ([Camoufox](https://github.com/nicepkg/camoufox))
- **Bulk Processing** — Authenticate multiple accounts in one run
- **Duplicate Detection** — Updates existing accounts instead of creating duplicates
- **Direct SQLite Injection** — Writes directly to 9Router's database, no API rate limits
- **Retry & Rate Limiting** — Auto-retry on transient failures with configurable delays
- **Zero Extra Dependencies for Config** — Built-in `.env` loader, no `python-dotenv` needed

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **[9Router](https://github.com/nicepkg/9router)** installed and running locally

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/bulk-auth-9router.git
cd bulk-auth-9router

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download Camoufox browser binary (one-time)
camoufox fetch

# 5. Set up your environment
cp .env.example .env
# Edit .env with your 9Router settings
```

### Usage

#### Option A: CLI

```bash
# Generate accounts template
python main.py --template

# Edit accounts.json with your credentials, then:
python main.py --provider qoder   # Bulk auth Qoder accounts
python main.py --provider kiro    # Bulk auth Kiro accounts
```

#### Option B: Web UI

```bash
python web_ui.py
# Open http://localhost:8485 in your browser
```

The Web UI provides:
- Provider selection (Qoder / Kiro / Both)
- Email list input (one per line) with shared password
- Real-time progress tracking and live logs
- Success/failure statistics

### accounts.json Format

```json
{
  "accounts": [
    {
      "name": "Account 1",
      "email": "u...m",
      "password": "your_password"
    },
    {
      "name": "Account 2",
      "email": "u...m",
      "password": "your_password"
    }
  ]
}
```

> **Tip:** Run `python main.py --template` to generate this file automatically.

## ⚙️ Configuration

All configuration is done via environment variables (or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `NINEROUTER_URL` | `http://localhost:20128` | URL of your 9Router instance |
| `NINEROUTER_PASSWORD` | *(empty)* | 9Router login password |
| `NINEROUTER_DB` | *(auto-detected)* | Custom path to 9Router SQLite database |
| `HEADLESS` | `true` | Run browser in headless mode (`false` to see browser) |
| `BATCHER_PROXY_URL` | *(empty)* | Proxy URL: `http://u...t` |

You can also edit `config.py` directly for advanced settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `DELAY_BETWEEN_ACCOUNTS` | `15` | Seconds between processing accounts |
| `MAX_RETRIES` | `3` | Max retry attempts on failure |
| `RETRY_DELAY` | `5` | Seconds before retrying |
| `LOGIN_TIMEOUT` | `120` | Browser login timeout in seconds |

## 🏗️ Architecture

```
bulk-auth-9router/
├── main.py                  # CLI entry point
├── web_ui.py                # Flask web interface
├── config.py                # Configuration + .env loader
├── core/
│   └── accounts.py          # Account loading/saving
├── router/
│   ├── injector.py          # 9Router SQLite injector (Qoder)
│   └── kiro_injector.py     # 9Router SQLite injector (Kiro)
├── providers/
│   ├── qoder/
│   │   ├── auth.py          # Google OAuth browser automation
│   │   └── oauth.py         # Device flow API (PKCE)
│   └── kiro/
│       ├── auth.py          # Auth orchestrator
│       ├── browser.py       # Browser session management
│       ├── browser_fill.py  # Form filling logic
│       ├── tokens.py        # Token exchange & refresh
│       └── quota.py         # Usage quota checking
├── templates/
│   └── index.html           # Web UI frontend
└── utils/
    ├── helpers.py            # PKCE, URL parsing utilities
    └── logger.py             # Console output formatting
```

### Authentication Flows

**Qoder (Device Flow):**
1. Initiate device flow → get auth URL + machine ID
2. Browser automation → Google OAuth login
3. Poll device token endpoint
4. Inject token into 9Router SQLite DB

**Kiro (OAuth Flow):**
1. Browser automation → Google OAuth login via Kiro auth endpoint
2. Intercept `kiro://` callback → extract authorization code
3. Exchange code for access/refresh tokens
4. Inject token into 9Router SQLite DB

### Duplicate Handling

Both providers check for existing accounts before injection:
- **Existing account** → Update tokens, preserve priority
- **New account** → Insert with auto-incremented priority

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| Camoufox browser issues | Run `camoufox fetch` to download the Firefox binary |
| 9Router DB not found | Verify path: `ls ~/.9router/db/data.sqlite` or set `NINEROUTER_DB` |
| Authentication failures | Set `HEADLESS=false` to watch the browser and debug |
| Rate limiting | Increase `DELAY_BETWEEN_ACCOUNTS` in config |
| Captcha on Google login | Use a proxy via `BATCHER_PROXY_URL` or add longer delays |

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/my-feature`
3. **Make your changes** and test thoroughly
4. **Commit**: `git commit -m "feat: add support for new provider"`
5. **Push**: `git push origin feature/my-feature`
6. **Open a Pull Request**

### Adding a New Provider

1. Create `providers/<name>/` with `auth.py` and any helper modules
2. Add provider URLs to `config.py`
3. Add an injector in `router/<name>_injector.py`
4. Wire it up in `main.py` and `web_ui.py`
5. Update the README

Please use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages.

## ⚠️ Disclaimer

This tool is intended for **legitimate account management** of AI provider services you are authorized to use. Please:

- Comply with the Terms of Service of all providers involved
- Use responsibly and at your own risk
- Do not use for unauthorized access or abuse

The authors are not responsible for any misuse of this tool.

## 📄 License

This project is licensed under the [MIT License](LICENSE).
