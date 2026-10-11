"""Complete YouTube OAuth and save the refresh token to .env."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def load_env():
    env = {}
    p = BASE_DIR / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

def save_env(env):
    p = BASE_DIR / ".env"
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    out, found = [], set()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in env and k not in found:
                out.append(f"{k}={env[k]}")
                found.add(k)
                continue
        out.append(line)
    for k, v in env.items():
        if k not in found:
            out.append(f"{k}={v}")
    p.write_text("\n".join(out) + "\n", encoding="utf-8")

def main():
    """Run the YouTube OAuth flow and persist the refresh token to .env."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    env = load_env()
    cid = env.get("YOUTUBE_CLIENT_ID")
    csec = env.get("YOUTUBE_CLIENT_SECRET")
    if not cid or not csec:
        raise SystemExit("Missing YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET in .env")

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
    ]
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": cid,
                "client_secret": csec,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        SCOPES,
    )
    print("Opening browser for Google authorization...")
    creds = flow.run_local_server(port=8090, prompt="consent")
    if not creds.refresh_token:
        raise SystemExit("OAuth succeeded but no refresh token was returned (try prompt=consent).")
    env["YOUTUBE_REFRESH_TOKEN"] = creds.refresh_token
    save_env(env)
    print("[OK] Refresh token saved to .env")


if __name__ == "__main__":
    main()