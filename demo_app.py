"""TheRepublic demo web app - TikTok Content Posting integration.

Screen-record this app for the TikTok app-review demo video.

Run:  python demo_app.py
Visit: http://localhost:5000
"""
import os
import base64
import hashlib
import requests
import secrets
from flask import Flask, session, render_template_string, request, redirect, url_for

from config.settings import BASE_DIR
from api.providers.tiktok_provider import TikTokProvider

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

REDIRECT_URI = "http://localhost:5000/callback"
SCOPES = "user.info.basic,user.info.profile,video.upload,video.publish"

provider = TikTokProvider()

PAGE = """
<!DOCTYPE html><html><head><title>TheRepublic - TikTok</title><style>
body { font-family: system-ui; max-width: 640px; margin: 40px auto; padding: 0 16px; color: #111; }
h1 { color: #5b21b6; }
.card { border: 1px solid #ddd; border-radius: 12px; padding: 20px; margin-top: 16px; }
button, .btn { background: #5b21b6; color: #fff; border: 0; padding: 10px 18px; border-radius: 8px; cursor: pointer; font-size: 15px; text-decoration: none; display: inline-block; }
label { display: block; margin: 10px 0 4px; font-weight: 600; }
input, select, textarea { width: 100%; padding: 8px; border: 1px solid #bbb; border-radius: 6px; box-sizing: border-box; }
.muted { color: #666; font-size: 13px; }
.check { display: flex; align-items: center; gap: 8px; }
.check input { width: auto; }
.ok { color: #16a34a; font-weight: 600; }
</style></head><body>
<h1>TheRepublic</h1>
{{ content|safe }}
</body></html>
"""

def render(body):
    return render_template_string(PAGE, content=body)

@app.route("/")
def home():
    if not provider.available:
        return render("""
            <div class="card">
                <p><strong>Step 1 — Connect your TikTok account</strong></p>
                <p class="muted">We use Login Kit (user.info.basic / profile) to show your stats.
                We never read DMs and you can disconnect anytime.</p>
                <a class="btn" href="/login">Connect with TikTok</a>
            </div>
        """)
    return render(f"""
        <div class="card">
            <p><span class="ok">Connected.</span> Showing user.info.basic data:</p>
            <p><strong>Name:</strong> {session.get('display_name', '?')}<br>
               <strong>Followers:</strong> {session.get('followers', '?')}<br>
               <strong>Open ID:</strong> {session.get('open_id', '?')[:12]}...</p>
        </div>
        <div class="card">
            <p><strong>Step 2 — Publish a video</strong></p>
            <p class="muted">Content Posting API (video.upload / video.publish)</p>
            <a class="btn" href="/post">Create Post</a>
        </div>
    """)

@app.route("/login")
def login():
    state = secrets.token_urlsafe(16)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    session["oauth_state"] = state
    session["code_verifier"] = verifier
    url = (
        "https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={provider.client_key}"
        f"&response_type=code&scope={SCOPES}"
        f"&redirect_uri={REDIRECT_URI}&state={state}"
        f"&code_challenge={challenge}&code_challenge_method=S256"
    )
    return redirect(url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")
    session.pop("oauth_state", None)
    if not code:
        return render(f"<div class='card'>Auth failed: {request.args}</div>")
    token_resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        data={
            "client_key": provider.client_key,
            "client_secret": provider.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": session.pop("code_verifier", ""),
        },
    )
    if token_resp.status_code != 200:
        return render(f"<div class='card'>Token error: {token_resp.text[:300]}</div>")
    data = token_resp.json()
    provider.access_token = data.get("access_token")
    provider.refresh_token = data.get("refresh_token")
    provider._save_env("TIKTOK_ACCESS_TOKEN", provider.access_token)
    if provider.refresh_token:
        provider._save_env("TIKTOK_REFRESH_TOKEN", provider.refresh_token)

    info = requests.get(
        "https://open.tiktokapis.com/v2/user/info/",
        headers={"Authorization": f"Bearer {provider.access_token}"},
        params={"fields": "open_id,display_name,follower_count"},
    )
    user = info.json().get("data", {}).get("user", {})
    session["open_id"] = user.get("open_id")
    session["display_name"] = user.get("display_name")
    session["followers"] = user.get("follower_count")
    session["access_token"] = provider.access_token
    return redirect(url_for("home"))

@app.route("/post", methods=["GET", "POST"])
def post():
    if not provider.available:
        return redirect(url_for("home"))
    # Fetch creator_info to honor the account's real privacy options.
    info = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/creator_info/query/",
        headers={"Authorization": f"Bearer {provider.access_token}",
                 "Content-Type": "application/json; charset=UTF-8"},
        json={},
    )
    privacy_options = []
    if info.status_code == 200:
        privacy_options = info.json().get("data", {}).get("creator_info", {}).get(
            "privacy_level_options", [])

    if request.method == "POST":
        caption = request.form.get("caption", "")
        video_url = request.form.get("video_url", "").strip()
        privacy = request.form.get("privacy", "").strip()
        consent = request.form.get("consent")
        comment = request.form.get("comment") == "on"
        duet = request.form.get("duet") == "on"
        stitch = request.form.get("stitch") == "on"

        if not consent:
            return render("<div class='card'>Consent required: by posting you agree to TikTok's Music Usage Confirmation.</div>")
        if not privacy:
            return render("<div class='card'>Please select a privacy level.</div>")

        init = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers={"Authorization": f"Bearer {provider.access_token}",
                     "Content-Type": "application/json; charset=UTF-8"},
            json={
                "post_info": {
                    "title": caption,
                    "privacy_level": privacy,
                    "disable_comment": not comment,
                    "disable_duet": not duet,
                    "disable_stitch": not stitch,
                },
                "source_info": {"source": "PULL_FROM_URL", "video_url": video_url},
            },
        )
        result = init.json()
        publish_id = result.get("data", {}).get("publish_id")
        return render(f"""
            <div class="card">
                <p><span class="ok">Post initialized!</span></p>
                <p><strong>publish_id:</strong> {publish_id}</p>
                <p><strong>privacy:</strong> {privacy}<br>
                   <strong>comments:</strong> {'on' if comment else 'off'}<br>
                   <strong>duets:</strong> {'on' if duet else 'off'}<br>
                   <strong>stitches:</strong> {'on' if stitch else 'off'}</p>
                <a class="btn" href="/check/{publish_id}">Check status</a>
            </div>
        """)

    options_html = "".join(
        f"<option value='{o}'>{o.replace('_', ' ').title()}</option>" for o in privacy_options
    ) or "<option value=''>No privacy options returned (pre-review/private account)</option>"

    return render(f"""
        <div class="card">
            <p><strong>Create Post</strong></p>
            <form method="post">
                <label>Caption</label>
                <textarea name="caption" rows="2" placeholder="Some caption... #fyp"></textarea>
                <label>Video URL (on your verified domain)</label>
                <input name="video_url" value="https://therepublic.netlify.app/sample.mp4">
                <label>Privacy level (from creator_info/query — no default)</label>
                <select name="privacy" required><option value="">-- choose --</option>{options_html}</select>
                <label>Allow comments</label>
                <div class="check"><input type="checkbox" name="comment"><span>Comments on</span></div>
                <div class="check"><input type="checkbox" name="duet"><span>Duets on</span></div>
                <div class="check"><input type="checkbox" name="stitch"><span>Stitches on</span></div>
                <label>Consent</label>
                <div class="check"><input type="checkbox" name="consent" required>
                    <span>By posting, you agree to TikTok's Music Usage Confirmation.</span></div>
                <br><button type="submit">Publish to TikTok</button>
            </form>
        </div>
    """)

@app.route("/check/<publish_id>")
def check(publish_id):
    resp = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
        headers={"Authorization": f"Bearer {provider.access_token}",
                 "Content-Type": "application/json; charset=UTF-8"},
        json={"publish_id": publish_id},
    )
    return render(f"<div class='card'><p>Status: <pre>{resp.text}</pre></p></div>")

if __name__ == "__main__":
    print("TheRepublic demo app at http://localhost:5000")
    app.run(port=5000, debug=False)