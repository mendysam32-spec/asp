import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"

load_dotenv(BASE_DIR / ".env")


def set_env_vars(pairs: dict) -> None:
    """Persist vars to .env and push into os.environ so running providers see them."""
    path = BASE_DIR / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out, written = [], set()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in pairs and k not in written:
                out.append(f"{k}={pairs[k]}")
                written.add(k)
                continue
        out.append(line)
    for k, v in pairs.items():
        if k not in written:
            out.append(f"{k}={v}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    for k, v in pairs.items():
        os.environ[k] = v


def unset_env_vars(keys: list) -> None:
    """Remove vars from .env and os.environ."""
    path = BASE_DIR / ".env"
    if not path.exists():
        return
    keys = set(keys)
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in keys:
            continue
        out.append(line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    for k in keys:
        os.environ.pop(k, None)

# API Keys (set in environment or .env file)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

# YouTube (Google Cloud OAuth)
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# TikTok (pays via PayPal)
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN")
TIKTOK_REFRESH_TOKEN = os.getenv("TIKTOK_REFRESH_TOKEN")

# X / Twitter
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# Meta (Instagram / Facebook)
META_USER_ACCESS_TOKEN = os.getenv("META_USER_ACCESS_TOKEN")
META_APP_ID = os.getenv("META_APP_ID")
META_APP_SECRET = os.getenv("META_APP_SECRET")
IG_USER_ID = os.getenv("IG_USER_ID")

# PayPal
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")

# Agent Settings (legacy defaults — dashboard config/settings_store.py is the
# source of truth at runtime; these remain for CLI / library imports)
CONTENT_DAILY_LIMIT = 10
ANALYSIS_INTERVAL_HOURS = 6
AUTO_POST = False  # Set True when ready for autonomous posting
HUMAN_APPROVAL_REQUIRED = True

# Niche Analysis
TRENDING_SOURCES = [
    "google_trends",
    "twitter_trending",
    "reddit",
    "youtube_trending"
]

# Content Categories
CONTENT_TYPES = ["text", "image", "video", "carousel", "story"]
POSTING_TIMES = ["09:00", "12:00", "15:00", "18:00", "21:00"]
