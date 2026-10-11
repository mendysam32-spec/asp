"""Interactive credential setup wizard.

Guides you through getting API keys + OAuth tokens for each platform
and writes them to your .env file.

Usage:
    python setup_credentials.py            # all platforms
    python setup_credentials.py youtube    # one platform
    python setup_credentials.py tiktok x instagram
"""
import os
import sys
import re
from pathlib import Path
from config.settings import BASE_DIR

ENV_PATH = BASE_DIR / ".env"

SETUP_GUIDES = {
    "youtube": {
        "description": "YouTube Partner Program (1,000 subs / 4,000 watch hrs)",
        "steps": [
            "1. Go to https://console.cloud.google.com/apis/credentials",
            "   -> Create Credentials -> OAuth client ID -> Desktop app",
            "   -> Copy YOUR_CLIENT_ID and YOUR_CLIENT_SECRET",
            "2. Enable the 'YouTube Data API v3'",
            "   -> https://console.cloud.google.com/apis/library/youtube.googleapis.com",
            "   (The wizard will run OAuth flow to get your refresh token automatically)",
        ],
        "env_keys": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_API_KEY"],
    },
    "tiktok": {
        "description": "TikTok Creator Rewards (10k followers, PayPal payout)",
        "steps": [
            "1. Go to https://developers.tiktok.com -> Sign up (use a BUSINESS email)",
            "2. Create/join an organization, then click 'Connect an app'",
            "3. App platform: Web/Desktop. Set a Redirect URI (for OAuth login)",
            "   - If you don't have a website yet, use https://www.tiktok.com/auth/",
            "4. Add the 'Content Posting API' product + 'Login Kit' (user.info.basic)",
            "5. Copy Client Key and Client Secret from the Credentials section",
            "6. SCOPE NOTE: 'video.publish' requires app review + a demo video.",
            "   Without it you can still read account data (followers, etc.)",
        ],
        "env_keys": ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_ACCESS_TOKEN", "TIKTOK_REFRESH_TOKEN"],
    },
    "x": {
        "description": "X/Twitter revenue share (requires Premium, ~$30/2wk via Stripe)",
        "steps": [
            "1. Go to https://developer.x.com -> Dashboard -> Keys and tokens",
            "2. Create a project/app to get API Key (consumer) + API Secret",
            "3. Under 'User Access Tokens', generate Access Token + Secret",
            "   (requires OAuth 1.0a with READ + WRITE permissions)",
        ],
        "env_keys": ["TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"],
    },
    "instagram": {
        "description": "Instagram/Facebook monetization (fan tips 500+ followers)",
        "steps": [
            "1. Go to https://developers.facebook.com -> Create app (Business type)",
            "2. Add the 'Instagram Graph API' and 'Facebook Login for Business' products",
            "3. Generate a long-lived User Access Token with scopes:",
            "   instagram_basic, instagram_content_publish, pages_show_list",
            "4. Link an Instagram Business (or Creator) account to your Page",
            "5. Get your numeric Instagram Business ID (IG_USER_ID):",
            "   GET https://graph.facebook.com/v21.0/me?fields=instagram_business_account{id,name}",
            "   -> copy instagram_business_account.id into IG_USER_ID",
        ],
        "env_keys": ["META_USER_ACCESS_TOKEN", "META_APP_ID", "META_APP_SECRET", "IG_USER_ID"],
    },
}


def _load_env() -> dict:
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _save_env(env: dict):
    lines = []
    for k, v in env.items():
        lines.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n[OK] Saved credentials to {ENV_PATH}")


def _set_echo_off_password(var_name: str) -> str:
    import getpass
    return getpass.getpass(f"  {var_name} (hidden): ")


def _input(key: str, env: dict, secret: bool = False, optional: bool = False):
    current = env.get(key, "")
    if current:
        print(f"  {key}: [already set: {current[:8]}...] (Enter to keep)")
        val = input(f"  -> new value {'(hidden) ' if secret else ''}: ").strip()
        return val or current
    prompt = f"  {key}:"
    if secret:
        val = _set_echo_off_password(key)
        if val == "" and not optional:
            print("  [WARN] Empty value - skipping")
            return None
        return val
    val = input(f"{prompt} ").strip()
    return val


def tiktok_oauth_url(client_key: str, redirect_uri: str) -> str:
    return (
        f"https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={client_key}"
        f"&response_type=code&scope=user.info.basic,video.upload,video.publish"
        f"&redirect_uri={redirect_uri}"
    )


def setup_one(name: str, env: dict) -> dict:
    guide = SETUP_GUIDES.get(name)
    if not guide:
        print(f"Unknown platform: {name}")
        return env

    print("\n" + "=" * 60)
    print(f"[{name.upper()}] {guide['description']}")
    print("=" * 60)
    for step in guide["steps"]:
        print(step)

    if name == "tiktok":
        print(f"\n  OAuth URL (after setting client key): {tiktok_oauth_url('YOUR_CLIENT_KEY', 'https://www.tiktok.com/auth/')}")

    print("\n  Enter your credentials (blank = skip a key):")
    for key in guide["env_keys"]:
        secret = "SECRET" in key or "TOKEN" in key or "KEY" in key
        val = _input(key, env, secret=secret)
        if val:
            env[key] = val

    if name == "youtube" and env.get("YOUTUBE_CLIENT_ID") and env.get("YOUTUBE_CLIENT_SECRET"):
        print("\n  Running YouTube OAuth flow to get refresh token...")
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            SCOPES = [
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube",
                "https://www.googleapis.com/auth/yt-analytics.readonly",
            ]
            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": env["YOUTUBE_CLIENT_ID"],
                        "client_secret": env["YOUTUBE_CLIENT_SECRET"],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
                    }
                },
                SCOPES,
            )
            creds = flow.run_local_server(port=0, prompt="consent")
            env["YOUTUBE_REFRESH_TOKEN"] = creds.refresh_token
            print("  [OK] Refresh token obtained")
        except Exception as e:
            print(f"  [WARN] OAuth flow failed: {e}")
            print("  Set YOUTUBE_REFRESH_TOKEN manually from Google console if needed")

    return env


def main():
    env = _load_env()
    targets = sys.argv[1:] or list(SETUP_GUIDES.keys())
    for name in targets:
        env = setup_one(name, env)
    _save_env(env)
    print("\nDone. Run `python main.py` then use the 'connect' command to verify.")


if __name__ == "__main__":
    main()