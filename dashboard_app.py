"""GodEye - Agent Control Dashboard.

Full-glass modern control center for the AI content agent.
All customization is UI-driven and persisted to config/dashboard_settings.json.
Run:  python dashboard_app.py   -> http://localhost:5001
"""
import asyncio
import json
import os
import secrets
import threading
from datetime import datetime

from flask import Flask, jsonify, render_template, request, send_from_directory as flask_send_from_directory

from config.settings_store import settings_store, get_settings
from config.settings import set_env_vars, unset_env_vars
from core.llm import LLMProvider
from modules.content_creator import ContentCreator
from modules.niche_analyzer import NicheAnalyzer
from modules.tax_tracker import TaxTracker
from modules.monetization import MonetizationManager
from modules.agent_controller import AgentController
from core.memory import AgentMemory
from api.registry import PlatformRegistry

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

controller = AgentController()

# Gap 2 — auto-publish scheduled posts every 60s (daemon, no request needed)
def _schedule_daemon():
    import time as _t
    import asyncio as _a
    while True:
        _t.sleep(60)
        try:
            from core.memory import AgentMemory as _Mem
            from api.registry import PlatformRegistry as _Reg
            mem = _Mem()
            loop = _a.new_event_loop()
            _a.set_event_loop(loop)
            loop.run_until_complete(mem.initialize())
            from datetime import datetime as _dt
            now = _dt.now()
            due = [p for p in mem.scheduled_posts if p.get("status")=="scheduled" and _dt.fromisoformat(p["post_time"]) <= now]
            for item in due:
                plat = item["content"].get("platform")
                prov = _Reg().get_provider(plat)
                if not prov or not prov.available:
                    item["last_error"] = f"{plat} not connected"
                    continue
                res = loop.run_until_complete(controller._publish(plat, {}, item["content"]))
                if res.get("error"):
                    item["last_error"] = res["error"]
                else:
                    item["status"] = "published"
                    loop.run_until_complete(mem.log_activity("schedule_published", {"platform": plat}))
            if due:
                mem._save_data()
            loop.close()
        except Exception:
            pass

try:
    _sched_thread = threading.Thread(target=_schedule_daemon, daemon=True)
    _sched_thread.start()
except Exception:
    pass

# Optional basic auth (Gap 6) — set DASHBOARD_PASSWORD in .env to enable
_DASH_PW = os.getenv("DASHBOARD_PASSWORD") or os.getenv("GOD_EYE_PASSWORD")

@app.before_request
def _basic_auth():
    if not _DASH_PW:
        return
    # allow health without auth for service checks
    if request.path in ("/api/health", "/api/logs"):
        return
    auth = request.authorization
    # also allow ?pw=xxx for simple browser use
    qp = request.args.get("pw") or request.headers.get("X-Dashboard-Pw")
    if qp == _DASH_PW:
        return
    if auth and auth.password == _DASH_PW:
        return
    # if no auth header, allow but warn? enforce for sensitive POST
    if request.method == "POST" and request.path.startswith("/api/") and request.path not in ("/api/health",):
        # require pw for publish/bulk/terminal
        if request.path.startswith(("/api/publish", "/api/terminal", "/api/agent", "/api/media/upload")):
            return jsonify({"ok": False, "error": "Dashboard locked — set ?pw=YOUR_PASSWORD or Basic Auth"}), 401

# env vars that back each platform's credentials
PLATFORM_ENV = {
    "youtube": ["YOUTUBE_REFRESH_TOKEN"],
    "tiktok": ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_ACCESS_TOKEN", "TIKTOK_REFRESH_TOKEN"],
    "x": ["TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"],
    "instagram": ["META_USER_ACCESS_TOKEN", "IG_USER_ID"],
}
# manual token-entry fields per platform (no OAuth portal wiring yet)
TOKEN_FIELDS = {
    "x": [("TWITTER_API_KEY", "API key"), ("TWITTER_API_SECRET", "API secret"),
          ("TWITTER_ACCESS_TOKEN", "Access token"), ("TWITTER_ACCESS_SECRET", "Access secret")],
    "instagram": [("META_USER_ACCESS_TOKEN", "Instagram/Facebook user access token"),
                  ("IG_USER_ID", "Instagram Business account ID (numeric)")],
}
MEDIA_HINT = {"tiktok": "needs video", "instagram": "needs image"}

def _ok(data=None):
    return jsonify({"ok": True, "data": data if data is not None else {}})

def _err(message, code=400):
    return jsonify({"ok": False, "error": message}), code

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/status")
async def status():
    registry = PlatformRegistry()
    statuses = await registry.check_all()
    platforms = [
        {
            "name": s["platform"],
            "connected": s["connected"],
            "pays": s["pays_creators"],
            "payout": s["payout_method"],
            "check": s.get("connection_check"),
        }
        for s in statuses
    ]
    monetization = await registry.get_monetization_status()

    llm = LLMProvider()
    tax = TaxTracker()
    tax_report = await tax.generate_tax_report()
    memory = AgentMemory()
    memory_summary = await memory.get_stats()

    return _ok({
        "time": datetime.now().isoformat(),
        "ai": {
            "provider": llm.provider_name,
            "model": (llm.model or "none"),
            "available": llm.available,
            "active_provider": llm.active_provider,
            "failover": llm.last_failover,
            "last_error": llm.last_error,
            "fallback": llm.fallback_models,
            "reasoning": llm.reasoning,
            "keys": {
                "nvidia": bool(os.getenv("NVIDIA_API_KEY")),
                "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
                "openai": bool(os.getenv("OPENAI_API_KEY")),
                "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            },
        },
        "agent": controller.status(),
        "autonomousEnabled": controller.enabled(),
        "platforms": platforms,
        "monetization": monetization,
        "tax": tax_report,
        "memory": memory_summary,
    })

@app.route("/api/ai/test", methods=["POST"])
async def ai_test():
    body = request.get_json(silent=True) or {}
    models = body.get("models") or []
    provider = body.get("provider") or None
    if not models:
        return _err("Provide at least one model id")
    llm = LLMProvider()
    try:
        results = await asyncio.gather(*[llm.test_model(m, provider=provider) for m in models[:6]])
        return _ok({"results": results})
    except Exception as e:
        return _err(str(e), 500)

@app.route("/api/keys", methods=["GET"])
def keys_status():
    def masked(v):
        if not v:
            return {"set": False, "hint": ""}
        return {"set": True, "hint": f"…{v[-4:]}" if len(v) > 4 else "…"}
    return _ok({"keys": {
        "NVIDIA_API_KEY": masked(os.getenv("NVIDIA_API_KEY", "")),
        "OPENROUTER_API_KEY": masked(os.getenv("OPENROUTER_API_KEY", "")),
        "OPENAI_API_KEY": masked(os.getenv("OPENAI_API_KEY", "")),
        "ANTHROPIC_API_KEY": masked(os.getenv("ANTHROPIC_API_KEY", "")),
        "OPENROUTER_MODEL": os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        "NVIDIA_MODEL": os.getenv("NVIDIA_MODEL", "meta/muse-glimmer-30b"),
    }})

@app.route("/api/keys", methods=["POST"])
def keys_save():
    body = request.get_json(silent=True) or {}
    values = body.get("values") or {}
    allowed = {"NVIDIA_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
               "OPENROUTER_MODEL", "NVIDIA_MODEL", "OPENROUTER_REFERER", "OPENROUTER_TITLE"}
    clean = {k: v.strip() for k, v in values.items() if k in allowed and isinstance(v, str) and v.strip()}
    if not clean:
        return _err("No valid keys provided", 400)
    set_env_vars(clean)
    llm = LLMProvider()
    return _ok({"saved": sorted(clean.keys()), "provider": llm.provider_name, "available": llm.available})

@app.route("/api/chat", methods=["POST"])
async def chat_full():
    """Full-potential chat: per-message provider/model/reasoning/temperature overrides,
    action shortcuts, persistent history, failover metadata."""
    import time as _t
    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    if not message:
        return _err("Provide {message}", 400)
    history = body.get("history") or []  # [{role, text}]
    action = (body.get("action") or "chat").lower()
    provider = body.get("provider") or None
    model = body.get("model") or None
    reasoning = body.get("reasoning") or None
    temperature = body.get("temperature")
    try:
        temperature = float(temperature) if temperature is not None else None
    except Exception:
        temperature = None
    llm = LLMProvider()
    if not llm.available:
        return _err("No AI provider configured — add a key in Customize → AI Engine → API Keys", 400)
    t0 = _t.time()
    # action presets expand the system prompt
    presets = {
        "chat": "You are GodEye, the user's autonomous content assistant. Be helpful, concise, plain.",
        "niche": "You are a niche research analyst. Give data-style reasoning, ranked opportunities, and next actions.",
        "content": "You are a professional content creator. Output platform-ready content with hook, body, CTA, hashtags.",
        "analyst": "You are a performance analyst. Reference the supplied account state and give 3 prioritized fixes.",
        "monetization": "You are a monetization coach. Reference payout thresholds and give a path-to-payout plan.",
    }
    system = presets.get(action, presets["chat"])
    if history:
        tail = history[-6:]
        convo = "\n".join(f"{h.get('role','user')}: {(h.get('text') or '')[:500]}" for h in tail)
        system += f"\nConversation so far:\n{convo}"
    # include live account context for analyst/monetization actions
    if action in ("analyst", "monetization"):
        try:
            system += f"\nLive state: provider={llm.provider_name} model={llm.model}"
        except Exception:
            pass
    text = await llm.complete(system_prompt=system, user_prompt=message,
                              max_tokens=body.get("max_tokens") or llm.max_tokens_default,
                              provider=provider, model=model, reasoning=reasoning,
                              temperature=temperature)
    latency = round(_t.time() - t0, 1)
    if not text:
        try:
            from modules import notifications as _nt
            _nt.notify("publish_fail", "Chat generation failed",
                       f"All providers failed. Tried: {llm.last_failover}", level="error")
        except Exception:
            pass
        return _err(f"All models failed: {llm.last_error or 'unknown'}", 502)
    # persist history server-side (best-effort)
    try:
        from pathlib import Path as _P
        import json as _j
        _cf = _P("data/chat_history.json")
        _h = _j.loads(_cf.read_text(encoding="utf-8")) if _cf.exists() else []
        _h += [{"role": "user", "text": message[:2000]}, {"role": "agent", "text": text[:4000],
                "provider": llm.active_provider, "model": llm.last_model}]
        _cf.write_text(_j.dumps(_h[-100:], indent=2), encoding="utf-8")
    except Exception:
        pass
    est_tokens = round((len(message) + len(text)) / 4)
    return _ok({"text": text, "provider": llm.active_provider, "model": llm.last_model,
                "failover": llm.last_failover, "latency": latency,
                "est_tokens": est_tokens, "reasoning": reasoning or llm.reasoning})

@app.route("/api/chat/history", methods=["GET"])
def chat_history():
    from pathlib import Path as _P
    import json as _j
    try:
        _cf = _P("data/chat_history.json")
        h = _j.loads(_cf.read_text(encoding="utf-8")) if _cf.exists() else []
        return _ok({"history": h[-50:]})
    except Exception as e:
        return _err(str(e), 500)

@app.route("/api/chat/history", methods=["DELETE"])
def chat_clear():
    from pathlib import Path as _P
    try:
        _cf = _P("data/chat_history.json")
        if _cf.exists():
            _cf.unlink()
        return _ok({"cleared": True})
    except Exception as e:
        return _err(str(e), 500)

@app.route("/api/settings", methods=["GET"])
def get_settings_route():
    return _ok({"settings": get_settings()})

@app.route("/api/settings", methods=["POST"])
def update_settings_route():
    body = request.get_json(silent=True) or {}
    if not body:
        return _err("Empty settings payload")
    saved = settings_store.update(body)
    return _ok({"settings": saved})

@app.route("/api/models")
def models():
    provider = (request.args.get("provider") or get_settings().get("ai", {}).get("provider", "nvidia")).lower()
    # OpenRouter catalog (public, no key needed for listing; key needed for generation)
    if provider == "openrouter":
        try:
            import requests
            r = requests.get("https://openrouter.ai/api/v1/models", timeout=15)
            ids = [m.get("id") for m in r.json().get("data", []) if m.get("id")]
            chat = sorted([i for i in ids if "/" in i])[:200]
            if chat:
                return _ok({"models": chat, "provider": "openrouter"})
        except Exception:
            pass
        return _ok({"models": ["openai/gpt-4o-mini", "anthropic/claude-3.5-haiku",
                               "meta-llama/llama-3.1-8b-instruct:free",
                               "meta-llama/llama-3.3-70b-instruct:free",
                               "google/gemini-flash-1.5-8b",
                               "mistralai/mistral-7b-instruct:free"], "provider": "openrouter"})
    key = os.getenv("NVIDIA_API_KEY")
    if not key:
        return _err("NVIDIA_API_KEY not set", 400)
    try:
        import requests
        r = requests.get(
            "https://integrate.api.nvidia.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
        ids = [m["id"] for m in r.json().get("data", [])]
        chat = [i for i in ids if not any(x in i for x in ["embed", "chatqa", "riva", "guard", "recurrent"])]
        chat.sort()
        return _ok({"models": chat})
    except Exception as e:
        return _err(str(e), 502)

@app.route("/api/generate", methods=["POST"])
async def generate():
    body = request.get_json(silent=True) or {}
    niche = body.get("niche") or "AI & Technology"
    platform = (body.get("platform") or "twitter").lower().strip()
    # alias: x and twitter are the same account (registry uses "x", creator uses "twitter")
    if platform == "x":
        platform = "twitter"
    tone = body.get("tone") or "professional"
    if platform not in ("twitter", "instagram", "tiktok", "youtube"):
        return _err(f"Unsupported platform: {platform}")
    try:
        creator = ContentCreator(llm=LLMProvider())
        content = await creator.generate_ai_content(niche, platform, tone)
        return _ok({"content": content, "provider": creator.llm.provider_name})
    except Exception as e:
        return _err(str(e), 500)

@app.route("/api/publish", methods=["POST"])
async def publish():
    body = request.get_json(silent=True) or {}
    platform = (body.get("platform") or "").lower().strip()
    # alias: accept "twitter" for the X account
    if platform == "twitter":
        platform = "x"
    content = body.get("content") or {}
    if platform not in ("tiktok", "youtube", "x", "instagram"):
        return _err(f"Unsupported platform: {platform}")
    registry = PlatformRegistry()
    provider = registry.get_provider(platform)
    if not provider or not provider.available:
        return _err(f"{platform} is not connected", 400)
    try:
        result = await registry.post_content(platform, content)
        return _ok({"result": result})
    except Exception as e:
        return _err(str(e), 500)

@app.route("/api/publish/bulk", methods=["POST"])
async def publish_bulk():
    """One-click publish to all chosen accounts. Generates if no text given.
    Accepts optional media: video_path / image_path from prior /api/media/upload.
    """
    # support both JSON and multipart (for direct file+fields) — JSON is normal
    if request.content_type and "multipart/form-data" in request.content_type:
        # fallback: form fields with file
        body = request.form.to_dict()
        # also check file is already saved via upload flow? not needed
    else:
        body = request.get_json(silent=True) or {}
    niche = (body.get("niche") or get_settings().get("agent", {}).get("defaultNiche", "AI & Technology")).strip()
    tone = (body.get("tone") or "professional").strip()
    platforms = body.get("platforms") or []
    custom_text = (body.get("text") or "").strip()
    auto_publish = body.get("autoPublish", True)
    # booleans may arrive as strings when multipart
    if isinstance(auto_publish, str):
        auto_publish = auto_publish.lower() not in ("0","false","no","off")
    # optional uploaded video/image path from /api/media/upload step
    video_path = (body.get("video_path") or body.get("video") or "").strip()
    image_path = (body.get("image_path") or body.get("image") or "").strip()
    # also accept single 'media_path'
    if not video_path and body.get("media_path"):
        mp = body.get("media_path").strip()
        if mp.lower().endswith((".mp4",".mov",".m4v",".webm",".avi",".mkv")):
            video_path = mp
        else:
            image_path = mp
    # normalize platforms
    if isinstance(platforms, str):
        platforms = [p.strip() for p in platforms.split(",") if p.strip()]
    platforms = [p.lower() for p in platforms]
    allowed = {"tiktok", "youtube", "x", "instagram", "twitter"}
    # map twitter -> x
    norm = []
    for p in platforms:
        if p == "twitter":
            p = "x"
        if p in allowed:
            norm.append(p)
    platforms = norm
    if not platforms:
        return _err("Select at least one platform (tiktok, youtube, x, instagram)", 400)
    # check autonomous master switch for auto publish ? still allow drafts
    results = {}
    creator = ContentCreator(llm=LLMProvider())
    memory = AgentMemory()
    await memory.initialize()
    registry = PlatformRegistry()
    for plat in platforms:
        provider = registry.get_provider(plat)
        if not provider or not provider.available:
            results[plat] = {"ok": False, "error": "not connected — connect in Accounts first"}
            continue
        try:
            # per-platform text
            if custom_text:
                text = custom_text
                ai_generated = False
                content_obj = {"text": text, "platform": plat, "niche": niche}
            else:
                cc_plat = {"x": "twitter"}.get(plat, plat)
                c = await creator.generate_ai_content(niche, cc_plat, tone)
                text = (c.get("text") or c.get("caption") or c.get("title") or "").strip()
                if not text:
                    results[plat] = {"ok": False, "error": "generation produced empty content"}
                    continue
                ai_generated = bool(c.get("ai_generated"))
                content_obj = c
                content_obj["text"] = text
                content_obj["platform"] = plat
            # build draft like agent_controller
            draft = {
                "platform": plat,
                "niche": niche,
                "tone": tone,
                "text": text,
                "title": text.splitlines()[0][:100] if text else niche[:100],
                "generated": datetime.now().isoformat(),
                "ai_generated": ai_generated,
            }
            # attach uploaded video/image if provided, else auto-render
            uploaded_media = {}
            if video_path:
                # validate path is inside data/media
                from pathlib import Path as _P
                vp = _P(video_path)
                # allow absolute or relative
                if not vp.is_absolute():
                    vp = _P("data/media") / vp.name if vp.parent == _P(".") else _P(video_path)
                if vp.exists():
                    uploaded_media["video"] = str(vp)
            if image_path:
                from pathlib import Path as _P2
                ip = _P2(image_path)
                if not ip.is_absolute():
                    ip = _P2("data/media") / ip.name if ip.parent == _P2(".") else _P2(image_path)
                if ip.exists():
                    uploaded_media["image"] = str(ip)
            if uploaded_media:
                draft["media"] = uploaded_media
                # for instagram, if only video supplied, also use it as image fallback where possible
                if plat == "instagram" and "video" in uploaded_media and "image" not in uploaded_media:
                    # will be handled as video Reel fallback if publish supports it; keep as media
                    pass
            elif plat in ("youtube", "tiktok", "instagram"):
                try:
                    cfg = get_settings()
                    voice = (cfg.get("agent", {}) or {}).get("voice")
                    media_enabled = (cfg.get("media", {}) or {}).get("enabled", True) and bool(voice)
                    if media_enabled and len(text) >= 60:
                        from modules.media_lab import render as render_media
                        accent = (cfg.get("theme", {}) or {}).get("accent", "#6c5ce7")
                        media = await render_media(text, accent=accent, voice=voice, slug=niche)
                        draft["media"] = media
                except Exception:
                    pass
            if auto_publish:
                # respect humanApproval per assignment but bulk forces publish if connected
                # we use controller._publish which handles youtube/tiktok/x/instagram specifics
                res = await controller._publish(plat, {}, draft)
                if res.get("error"):
                    # fallback to draft if publish fails (e.g., missing media)
                    draft["status"] = "pending_approval"
                    draft["publish_error"] = res["error"]
                    await memory.stage_draft(draft)
                    results[plat] = {"ok": False, "error": res["error"], "drafted": True, "preview": text[:120]}
                else:
                    await memory.log_activity("bulk_publish", {"platform": plat, "niche": niche})
                    results[plat] = {"ok": True, "result": res, "preview": text[:120]}
            else:
                draft["status"] = "pending_approval"
                await memory.stage_draft(draft)
                results[plat] = {"ok": True, "drafted": True, "preview": text[:120]}
        except Exception as e:
            results[plat] = {"ok": False, "error": str(e)}
    return _ok({"results": results, "niche": niche, "tone": tone})

@app.route("/api/analyze", methods=["POST"])
async def analyze():
    try:
        analyzer = NicheAnalyzer()
        result = await analyzer.get_full_analysis()
        return _ok({"analysis": result})
    except Exception as e:
        return _err(str(e), 500)

@app.route("/api/media/list", methods=["GET"])
def media_list():
    from pathlib import Path as _P
    media_dir = _P("data/media")
    media_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for f in sorted(media_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix.lower() in {".mp4",".mov",".m4v",".webm",".avi",".mkv",".jpg",".jpeg",".png",".webp",".gif",".mp3"}:
            items.append({
                "filename": f.name,
                "size": f.stat().st_size,
                "size_kb": round(f.stat().st_size/1024),
                "mtime": f.stat().st_mtime,
                "preview_url": f"/media/{f.name}",
                "ext": f.suffix.lower(),
                "is_video": f.suffix.lower() in {".mp4",".mov",".m4v",".webm",".avi",".mkv"},
            })
    return _ok({"media": items})

@app.route("/api/media/delete/<path:filename>", methods=["POST","DELETE"])
def media_delete(filename):
    from pathlib import Path as _P
    from werkzeug.utils import secure_filename
    # prevent path traversal
    filename = secure_filename(_P(filename).name)
    media_dir = _P("data/media")
    target = media_dir / filename
    if not target.exists():
        return _err("File not found", 404)
    try:
        target.unlink()
        return _ok({"deleted": filename})
    except Exception as e:
        return _err(str(e), 500)

@app.route("/media/<path:filename>")
def media_file(filename):
    return flask_send_from_directory("data/media", filename)

@app.route("/api/media/upload", methods=["POST"])
def media_upload():
    """Upload a video (or image) to data/media and return preview URL.
    Form: file=<binary>  (field name 'file' or 'video')
    Returns: {media: {video, preview_url, filename, size}}
    """
    from pathlib import Path as _P
    from werkzeug.utils import secure_filename
    import uuid
    f = request.files.get("file") or request.files.get("video") or request.files.get("image")
    if not f or not f.filename:
        return _err("No file uploaded — use form field 'file'", 400)
    # allow mp4, mov, m4v, webm, avi, mkv, jpg, png
    allowed = {".mp4",".mov",".m4v",".webm",".avi",".mkv",".jpg",".jpeg",".png",".webp",".gif"}
    ext = _P(f.filename).suffix.lower()
    if ext not in allowed:
        return _err(f"Unsupported extension {ext} — allowed: {', '.join(sorted(allowed))}", 400)
    # 200 MB max
    media_dir = _P("data/media")
    media_dir.mkdir(parents=True, exist_ok=True)
    safe = secure_filename(f.filename) or f"upload{ext}"
    # avoid collisions: uuid prefix
    name = f"{uuid.uuid4().hex[:8]}_{safe}"
    dest = media_dir / name
    f.save(str(dest))
    size = dest.stat().st_size
    # basic size guard
    if size > 200*1024*1024:
        dest.unlink(missing_ok=True)
        return _err("File too large — 200 MB max", 400)
    preview_url = f"/media/{name}"
    kind = "video" if ext in {".mp4",".mov",".m4v",".webm",".avi",".mkv"} else "image"
    return _ok({"media": {kind: str(dest), "preview_url": preview_url, "filename": name, "size": size, "ext": ext}})

@app.route("/api/media/render", methods=["POST"])
async def media_render():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    if len(text) < 60:
        return _err("Need at least 60 chars of script text to render media", 400)
    try:
        from modules.media_lab import render as render_media
        agent = get_settings().get("agent", {}) or {}
        accent = (get_settings().get("theme", {}) or {}).get("accent", "#6c5ce7")
        result = await render_media(text, accent=accent,
                                    voice=agent.get("voice"),
                                    slug="preview")
        if result.get("error"):
            return _err(f"Render failed: {result['error']}", 500)
        if result.get("video"):
            # validate file is a real video (>50KB), else surface failure instead of silent bad file
            try:
                sz = os.path.getsize(result["video"])
                if sz < 50 * 1024:
                    try:
                        os.remove(result["video"])
                    except Exception:
                        pass
                    return _err(f"Render produced a broken file ({sz} bytes) — try again or upload a real video", 500)
            except Exception:
                pass
            result["preview_url"] = "/media/" + os.path.basename(result["video"])
            # prune old media: keep newest 20 files to stop data/media clutter
            try:
                from pathlib import Path as _P
                _md = _P("data/media")
                files = sorted([f for f in _md.iterdir() if f.is_file()],
                               key=lambda p: p.stat().st_mtime, reverse=True)
                for old in files[20:]:
                    try:
                        old.unlink()
                    except Exception:
                        pass
            except Exception:
                pass
        else:
            return _err("Render produced no video", 500)
        return _ok({"media": result})
    except Exception as e:
        return _err(str(e), 500)

# ------------------------------------------------------------------ #
#  ACCOUNTS (connect / disconnect / tokens)                           #
# ------------------------------------------------------------------ #
@app.route("/api/accounts")
async def accounts():
    registry = PlatformRegistry()
    statuses = await registry.check_all()
    cfg = get_settings()
    platforms = cfg.get("platforms", {})
    agent_cfg = cfg.get("agent", {}) or {}
    assignments = agent_cfg.get("assignments", {}) or {}
    accounts = [
        {
            "name": s["platform"],
            "connected": s["connected"],
            "check": s.get("connection_check"),
            "pays": s["pays_creators"],
            "payout": s["payout_method"],
            "enabled": platforms.get(s["platform"], {}).get("enabled", True),
            "priority": platforms.get(s["platform"], {}).get("priority"),
            "assignment": assignments.get(s["platform"], {}),
            "connectMode": "oauth" if s["platform"] in ("youtube", "tiktok") else "token",
            "mediaHint": MEDIA_HINT.get(s["platform"]),
        }
        for s in statuses
    ]
    return _ok({"accounts": accounts, "agent": controller.status(), "autonomousEnabled": bool(agent_cfg.get("enabled", False))})

def _youtube_oauth_thread():
    try:
        import asyncio as _a
        loop = _a.new_event_loop()
        _a.set_event_loop(loop)
        loop.run_until_complete(_run_youtube_oauth())
        loop.close()
    except Exception as e:
        controller.recent.append({"ts": datetime.now().isoformat(), "summary": f"youtube oauth error: {e}"})

async def _run_youtube_oauth():
    cid = os.getenv("YOUTUBE_CLIENT_ID")
    csec = os.getenv("YOUTUBE_CLIENT_SECRET")
    if not cid or not csec:
        raise RuntimeError("YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET not in .env")
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_config(
        {"installed": {
            "client_id": cid, "client_secret": csec,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"}},
        ["https://www.googleapis.com/auth/youtube.upload",
         "https://www.googleapis.com/auth/youtube",
         "https://www.googleapis.com/auth/yt-analytics.readonly"],
    )
    creds = flow.run_local_server(port=8090, prompt="consent")
    set_env_vars({"YOUTUBE_REFRESH_TOKEN": creds.refresh_token})
    controller.recent.append({"ts": datetime.now().isoformat(), "summary": "YouTube OAuth completed"})

@app.route("/api/connect/<platform>", methods=["POST"])
async def connect_platform(platform):
    if platform == "youtube":
        threading.Thread(target=_youtube_oauth_thread, daemon=True).start()
        return _ok({"mode": "oauth",
                    "note": "A browser popup will open for Google. Approve it, then Refresh."})
    if platform == "tiktok":
        return _ok({"mode": "oauth",
                    "auth_url": "http://localhost:5000/login",
                    "note": "Open the TikTok Login Kit demo app (port 5000), then Refresh."})
    fields = TOKEN_FIELDS.get(platform, [])
    if not fields:
        return _err(f"No connect flow for {platform} yet", 400)
    return _ok({"mode": "token", "fields": [{"var": v, "label": l} for v, l in fields]})

@app.route("/api/token/<platform>", methods=["POST"])
async def save_token(platform):
    body = request.get_json(silent=True) or {}
    values = body.get("values") or {}
    if not values:
        return _err("No token values provided")
    set_env_vars(values)
    registry = PlatformRegistry()
    provider = registry.get_provider(platform)
    check = await provider.check_connection() if provider else None
    return _ok({"check": check})

@app.route("/api/disconnect/<platform>", methods=["POST"])
async def disconnect_platform(platform):
    if platform == "youtube" and os.path.exists("config/youtube_token.json"):
        os.remove("config/youtube_token.json")
    unset_env_vars(PLATFORM_ENV.get(platform, []))
    return _ok({"disconnected": platform})

# ------------------------------------------------------------------ #
#  AGENT (assign / control / ask / drafts)                            #
# ------------------------------------------------------------------ #
@app.route("/api/agent/assign", methods=["POST"])
async def agent_assign():
    body = request.get_json(silent=True) or {}
    platform = body.get("platform")
    if platform not in PLATFORM_ENV:
        return _err(f"Unknown platform: {platform}")
    keys = ("assigned", "active", "autoPost", "humanApproval",
            "dailyPostLimit", "niche", "contentTypes", "youtubePrivacy", "media")
    kw = {k: body[k] for k in keys if k in body}
    try:
        return _ok({"assignment": await controller.assign(platform, **kw)})
    except Exception as e:
        return _err(str(e), 500)

@app.route("/api/agent/unassign", methods=["POST"])
async def agent_unassign():
    body = request.get_json(silent=True) or {}
    await controller.unassign(body.get("platform", ""))
    return _ok({})

@app.route("/api/agent/run", methods=["POST"])
async def agent_run():
    return _ok({"cycle": await controller.run_cycle()})

@app.route("/api/agent/enabled", methods=["GET"])
def agent_enabled_get():
    return _ok({"enabled": controller.enabled(), "running": controller.running})

@app.route("/api/agent/enabled", methods=["POST"])
async def agent_enabled_post():
    body = request.get_json(silent=True) or {}
    # accept {enabled: bool} or {value: bool}
    if "enabled" in body:
        val = body["enabled"]
    elif "value" in body:
        val = body["value"]
    else:
        return _err("Provide {enabled: true/false}", 400)
    # coerce string "true"/"false" too
    if isinstance(val, str):
        val = val.lower() in ("1", "true", "on", "yes")
    result = await controller.set_enabled(bool(val))
    return _ok(result)

@app.route("/api/agent/start", methods=["POST"])
def agent_start():
    if not controller.enabled():
        return _err("Autonomous is disabled — enable it first (Master switch)", 400)
    controller.start()
    return _ok({"enabled": controller.enabled(), "running": controller.running})

@app.route("/api/agent/stop", methods=["POST"])
def agent_stop():
    controller.stop()
    return _ok({"enabled": controller.enabled(), "running": controller.running})

@app.route("/api/agent/ask", methods=["POST"])
async def agent_ask():
    body = request.get_json(silent=True) or {}
    return _ok(await controller.ask(body.get("message", "")))

@app.route("/api/agent/path")
async def agent_path():
    return _ok({"path": await controller.projection()})

@app.route("/api/agent/drafts")
async def agent_drafts():
    memory = AgentMemory()
    drafts = await memory.list_drafts()
    return _ok({"drafts": drafts})

@app.route("/api/agent/approve/bulk", methods=["POST"])
async def agent_approve_bulk():
    body = request.get_json(silent=True) or {}
    action = body.get("action", "approve")  # approve | reject
    platform_filter = body.get("platform")  # optional
    memory = AgentMemory()
    drafts = await memory.list_drafts()
    # filter if requested
    targets = [d for d in drafts if (not platform_filter or d["content"].get("platform")==platform_filter)]
    if not targets:
        return _ok({"processed": 0, "targets": 0})
    results = []
    for d in targets:
        idx = d["index"]
        if action == "reject":
            await memory.resolve_draft(idx, "rejected")
            results.append({"index": idx, "action":"rejected","ok":True})
        else:
            content = d["content"]
            plat = content.get("platform")
            provider = PlatformRegistry().get_provider(plat)
            if not provider or not provider.available:
                results.append({"index": idx, "ok":False, "error": f"{plat} not connected"})
                continue
            res = await controller._publish(plat, {}, content)
            if res.get("error"):
                results.append({"index": idx, "ok":False, "error": res["error"]})
            else:
                await memory.resolve_draft(idx, "published")
                results.append({"index": idx, "ok":True, "result": res})
    return _ok({"processed": len(results), "results": results})

@app.route("/api/schedule", methods=["GET"])
async def schedule_list():
    memory = AgentMemory()
    await memory.initialize()
    # ensure loaded
    items = memory.scheduled_posts
    return _ok({"scheduled": items})

@app.route("/api/schedule", methods=["POST"])
async def schedule_create():
    body = request.get_json(silent=True) or {}
    content = body.get("content") or {}
    post_time_str = body.get("post_time") or body.get("when")
    if not content.get("text") and not content.get("title"):
        return _err("content.text required",400)
    from datetime import datetime as _dt
    try:
        post_time = _dt.fromisoformat(post_time_str) if post_time_str else _dt.now()
    except Exception:
        return _err("Invalid post_time ISO format",400)
    memory = AgentMemory()
    await memory.initialize()
    await memory.schedule_post(content, post_time=post_time, status="scheduled")
    await memory.log_activity("schedule_created", {"platform": content.get("platform"), "post_time": post_time.isoformat()})
    return _ok({"scheduled": True, "post_time": post_time.isoformat()})

@app.route("/api/schedule/due", methods=["POST"])
async def schedule_due():
    """Publish any scheduled posts whose post_time <= now."""
    from datetime import datetime as _dt
    memory = AgentMemory()
    await memory.initialize()
    now = _dt.now()
    due = [p for p in memory.scheduled_posts if p.get("status")=="scheduled" and _dt.fromisoformat(p["post_time"]) <= now]
    published = []
    for item in due:
        idx = memory.scheduled_posts.index(item)
        content = item["content"]
        plat = content.get("platform")
        prov = PlatformRegistry().get_provider(plat)
        if not prov or not prov.available:
            item["last_error"] = f"{plat} not connected"
            continue
        res = await controller._publish(plat, {}, content)
        if res.get("error"):
            item["last_error"] = res["error"]
        else:
            item["status"] = "published"
            await memory.log_activity("schedule_published", {"platform": plat})
            published.append(plat)
    # save
    memory._save_data()
    return _ok({"due": len(due), "published": published})

@app.route("/api/analytics/history", methods=["GET"])
async def analytics_history():
    memory = AgentMemory()
    await memory.initialize()
    # activity_log aggregated
    from collections import Counter
    # posts per day last 14 days, drafts vs published
    history = memory.activity_log
    # scheduled_posts for charts
    return _ok({
        "scheduled_posts": memory.scheduled_posts[-50:],
        "activity_log": history[-100:],
        "stats": await memory.get_stats(),
    })

@app.route("/api/logs", methods=["GET"])
async def logs_api():
    memory = AgentMemory()
    await memory.initialize()
    # combine controller.recent + memory log
    recent = controller.recent[-20:]
    activities = memory.activity_log[-20:]
    return _ok({"recent": recent, "activities": activities, "agent": controller.status()})


@app.route("/api/health", methods=["GET"])
def health():
    """Lightweight health check (also registered by run_background with extra fields)."""
    try:
        s = controller.status()
        settings = get_settings()
        assignments = (settings.get("agent", {}) or {}).get("assignments", {})
        active = sum(1 for a in assignments.values() if a.get("active"))
        return jsonify({
            "ok": True,
            "time": datetime.now().isoformat(),
            "dashboard": "running",
            "agent_running": s["running"],
            "active_assignments": active,
            "last_cycle": s.get("last_cycle"),
            "recent": s.get("recent", [])[-3:],
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/agent/approve", methods=["POST"])
async def agent_approve():
    body = request.get_json(silent=True) or {}
    memory = AgentMemory()
    drafts = await memory.list_drafts()
    index = body.get("index")
    target = next((d for d in drafts if d["index"] == index), None)
    if not target:
        return _err("Draft not found", 404)
    if body.get("action") == "reject":
        await memory.resolve_draft(index, "rejected")
        return _ok({})
    content = target["content"]
    platform = content.get("platform")
    registry = PlatformRegistry()
    provider = registry.get_provider(platform)
    if not provider or not provider.available:
        return _err(f"{platform} not connected", 400)
    result = await controller._publish(platform, {"youtubePrivacy": body.get("privacy", "unlisted")}, content)
    if "error" in result and result["error"]:
        return _err(result["error"], 500)
    await memory.resolve_draft(index, "published")
    return _ok({"result": result})

@app.route("/api/terminal/exec", methods=["POST"])
async def terminal_exec():
    """No-code terminal — executes agent requests without writing code.
    Whitelisted commands + natural-language fallback via LLM.
    Commands (cmd/powershell style):
      help | clear | status | accounts | analyze
      generate <niche> [platform] [tone] | publish bulk ...
      run | start | stop | enable on/off | tax | monetize | ask <prompt>
    """
    body = request.get_json(silent=True) or {}
    raw = (body.get("command") or body.get("cmd") or "").strip()
    if not raw:
        return _err("Provide {command: \"...\"}", 400)
    # split while keeping quoted parts
    import shlex
    try:
        parts = shlex.split(raw)
    except Exception:
        parts = raw.split()
    if not parts:
        return _err("Empty command", 400)
    cmd = parts[0].lower()
    args = parts[1:]
    out_lines = []
    def add(s): out_lines.append(s)
    registry = PlatformRegistry()
    try:
        if cmd in ("help", "?", "h"):
            add("GodEye Terminal — no-code commands:")
            add("  help                          show this help")
            add("  status                        agent + AI + platform health")
            add("  accounts                      list accounts & connection")
            add("  analyze                       run niche analysis")
            add("  generate <niche> [platform] [tone]   generate content (ai)")
            add("  publish bulk <niche> --platforms tiktok,youtube,x,instagram [--draft]")
            add("  publish \"your text\" --platforms x   publish custom text 1-click")
            add("  run | cycle                   run one autonomous cycle now")
            add("  start | stop                  start/stop autonomous loop (master must be on)")
            add("  enable on|off                 toggle autonomous master switch")
            add("  tax                           tax report")
            add("  monetize                      monetization eligibility")
            add("  ask <your question>           chat with GodEye (LLM)")
            add("  clear                         clear terminal")
            add("Examples:")
            add("  generate \"AI & Technology\" tiktok casual")
            add("  publish bulk \"fitness tips\" --platforms tiktok,youtube --tone motivational")
            add("  ask what niche should I focus on for youtube?")
        elif cmd == "clear":
            return _ok({"output": "", "clear": True})
        elif cmd == "status":
            statuses = await registry.check_all()
            for s in statuses:
                add(f"{s['platform']:10} connected={s['connected']}  {s['payout_method']}")
            ag = controller.status()
            add(f"autonomous enabled={ag.get('enabled')} running={ag.get('running')}")
            add(f"last_cycle: {ag.get('last_cycle')}")
        elif cmd in ("accounts", "con", "connections"):
            statuses = await registry.check_all()
            for s in statuses:
                ck = s.get("connection_check", {})
                add(f"[{s['platform']}] connected={s['connected']} check={ck}")
        elif cmd == "analyze":
            analyzer = NicheAnalyzer()
            res = await analyzer.get_full_analysis()
            add(f"top_niche: {res.get('top_niche')}")
            for rec in (res.get("recommendations") or [])[:5]:
                add(f" - {rec.get('niche')} score={rec.get('score')} est={rec.get('monetization', {}).get('estimated_monthly')}")
        elif cmd in ("generate", "gen", "create"):
            # generate <niche> [platform] [tone]
            niche = args[0] if args else "AI & Technology"
            platform = args[1] if len(args) > 1 else "twitter"
            tone = args[2] if len(args) > 2 else "professional"
            # sanitize
            if platform not in ("twitter","instagram","tiktok","youtube","x"):
                # maybe args were quoted, try to detect
                platform = "twitter"
            if platform == "x":
                platform = "twitter"
            creator = ContentCreator(llm=LLMProvider())
            c = await creator.generate_ai_content(niche, platform, tone)
            text = c.get("text") or c.get("caption") or c.get("title") or ""
            add(f"[{platform}] ai_generated={c.get('ai_generated')} provider={c.get('provider')}")
            add(text[:1200] if text else "(empty)")
        elif cmd == "publish":
            # publish bulk <niche> ... or publish "text" --platforms ...
            # detect bulk
            is_bulk = args and args[0].lower() == "bulk"
            # parse --platforms and --tone and --draft
            platforms = []
            tone = "professional"
            niche = None
            text = None
            raw_lower = raw.lower()
            # extract quoted text if present after publish not bulk
            if not is_bulk:
                # publish "my text" --platforms x
                # we already shlex split, so args would contain text as first arg if quoted
                # try to find --platforms index
                p_idx = None
                for i, a in enumerate(args):
                    if a.startswith("--platforms"):
                        p_idx = i
                        break
                if p_idx is not None:
                    # platforms value
                    if "=" in args[p_idx]:
                        platforms = args[p_idx].split("=",1)[1].split(",")
                    elif p_idx+1 < len(args):
                        platforms = args[p_idx+1].split(",")
                    # text is everything before --platforms
                    text_parts = args[:p_idx]
                    text = " ".join(text_parts) if text_parts else None
                else:
                    # no platforms flag -> assume x
                    platforms = ["x"]
                    text = " ".join(args) if args else ""
                if not text:
                    return _err("Usage: publish \"your text\" --platforms x,youtube,tiktok,instagram", 400)
                # reuse bulk logic
                bulk_body = {"text": text, "platforms": platforms, "tone": tone, "autoPublish": True}
                # call internal bulk
                # simulate request by directly calling logic
                from flask import g
                # instead duplicate minimal publish for each
                registry2 = PlatformRegistry()
                mem = AgentMemory(); await mem.initialize()
                for plat in [p.strip().lower() for p in platforms if p.strip()]:
                    if plat == "twitter": plat = "x"
                    prov = registry2.get_provider(plat)
                    if not prov or not prov.available:
                        add(f"[{plat}] error: not connected")
                        continue
                    draft = {"platform": plat, "text": text, "title": text[:100], "generated": datetime.now().isoformat()}
                    res = await controller._publish(plat, {}, draft)
                    if res.get("error"):
                        add(f"[{plat}] publish error: {res['error']} (drafted)")
                        await mem.stage_draft({**draft, "status":"pending_approval"})
                    else:
                        add(f"[{plat}] published: {res}")
            else:
                # publish bulk <niche> --platforms ... --tone ... --draft
                # parse bulk args
                bulk_args = args[1:]  # after bulk
                # niche is first non-flag
                niche_parts = []
                for a in bulk_args:
                    if a.startswith("--"):
                        break
                    niche_parts.append(a)
                niche = " ".join(niche_parts) if niche_parts else "AI & Technology"
                # parse flags
                for i, a in enumerate(bulk_args):
                    if a == "--platforms" and i+1 < len(bulk_args):
                        platforms = bulk_args[i+1].split(",")
                    elif a.startswith("--platforms="):
                        platforms = a.split("=",1)[1].split(",")
                    elif a == "--tone" and i+1 < len(bulk_args):
                        tone = bulk_args[i+1]
                    elif a.startswith("--tone="):
                        tone = a.split("=",1)[1]
                auto_publish = "--draft" not in raw_lower
                if not platforms:
                    platforms = ["x"]
                # call bulk logic inline to avoid HTTP recursion
                creator = ContentCreator(llm=LLMProvider())
                mem = AgentMemory(); await mem.initialize()
                for plat in [p.strip().lower() for p in platforms if p.strip()]:
                    if plat == "twitter": plat = "x"
                    prov = registry.get_provider(plat)
                    if not prov or not prov.available:
                        add(f"[{plat}] error: not connected")
                        continue
                    cc_plat = {"x":"twitter"}.get(plat, plat)
                    c = await creator.generate_ai_content(niche, cc_plat, tone)
                    text2 = (c.get("text") or c.get("caption") or "").strip()
                    if not text2:
                        add(f"[{plat}] generation empty")
                        continue
                    draft = {"platform": plat, "niche": niche, "tone": tone, "text": text2, "title": text2.splitlines()[0][:100]}
                    if auto_publish:
                        res = await controller._publish(plat, {}, draft)
                        if res.get("error"):
                            add(f"[{plat}] error: {res['error']}")
                        else:
                            add(f"[{plat}] published ✓ preview: {text2[:80]}")
                    else:
                        await mem.stage_draft({**draft, "status":"pending_approval"})
                        add(f"[{plat}] drafted ✓ preview: {text2[:80]}")
        elif cmd in ("run","cycle"):
            if not controller.enabled():
                add("Autonomous is OFF — enable first: enable on")
            else:
                cyc = await controller.run_cycle()
                if cyc.get("skipped"):
                    add(f"skipped: {cyc['skipped']}")
                else:
                    add(f"cycle #{cyc.get('cycle')} done platforms: {list(cyc.get('platforms', {}).keys())}")
                    for p, v in cyc.get("platforms", {}).items():
                        add(f"  {p}: {v}")
        elif cmd == "start":
            if not controller.enabled():
                add("Cannot start — autonomous is OFF. Run: enable on")
            else:
                controller.start()
                add(f"started running={controller.running}")
        elif cmd == "stop":
            controller.stop()
            add(f"stopped running={controller.running}")
        elif cmd == "enable":
            val = (args[0].lower() if args else "")
            on = val in ("on","1","true","yes","enable","enabled")
            off = val in ("off","0","false","no","disable","disabled")
            if not (on or off):
                add("Usage: enable on|off")
            else:
                res = await controller.set_enabled(on)
                add(f"autonomous enabled={res['enabled']} running={res['running']}")
        elif cmd == "tax":
            tax = TaxTracker()
            rep = await tax.generate_tax_report()
            add(f"Year {rep['year']} income ${rep['income_summary']['total_income']:.2f} expenses ${rep['expense_summary']['total_expenses']:.2f} est_tax ${rep['tax_estimate']['estimated_tax_liability']:.2f}")
        elif cmd == "monetize":
            results = await registry.get_monetization_status()
            for r in results:
                add(f"{r['platform']}: {r}")
        elif cmd == "ask":
            prompt = " ".join(args) if args else raw[len(cmd):].strip()
            if not prompt:
                add("Usage: ask <your question>")
            else:
                res = await controller.ask(prompt)
                add(res.get("text","(no answer)"))
        else:
            # natural language fallback via LLM
            res = await controller.ask(raw)
            add(res.get("text","(no answer)"))
    except Exception as e:
        add(f"error: {e}")
    return _ok({"output": "\n".join(out_lines)})

# ------------------------------------------------------------------ #
#  NEW: Notifications / Projects / Inbox / Retry / Tax / Digest       #
# ------------------------------------------------------------------ #
@app.route("/api/notifications")
def notif_list():
    from modules import notifications as _nt
    return _ok({"notifications": _nt.list_notifications(limit=100),
                "unread": _nt.unread_count()})

@app.route("/api/notifications/read", methods=["POST"])
def notif_read():
    from modules import notifications as _nt
    body = request.get_json(silent=True) or {}
    if body.get("all"):
        _nt.mark_read(all_read=True)
    else:
        _nt.mark_read(nid=body.get("id"))
    return _ok({"unread": _nt.unread_count()})

@app.route("/api/notifications/test", methods=["POST"])
def notif_test():
    from modules import notifications as _nt
    _nt.notify("info", "Test notification", "Notifications center is working.", level="info")
    return _ok({"sent": True})

@app.route("/api/projects", methods=["GET"])
def proj_list():
    from modules import projects as _p
    return _ok({"projects": _p.list_projects()})

@app.route("/api/projects", methods=["POST"])
def proj_upsert():
    from modules import projects as _p
    body = request.get_json(silent=True) or {}
    return _ok({"project": _p.upsert_project(body)})

@app.route("/api/projects/<pid>", methods=["DELETE"])
def proj_del(pid):
    from modules import projects as _p
    _p.delete_project(pid)
    return _ok({})

@app.route("/api/projects/<pid>/tasks", methods=["POST"])
def proj_task(pid):
    from modules import projects as _p
    body = request.get_json(silent=True) or {}
    if body.get("toggle"):
        return _ok({"toggled": _p.toggle_task(pid, body.get("task_id", ""))})
    return _ok({"task": _p.add_task(pid, body.get("title", ""))})

@app.route("/api/digest")
async def digest():
    from modules import projects as _p
    from modules import notifications as _nt
    memory = AgentMemory()
    await memory.initialize()
    stats = await memory.get_stats()
    try:
        proj = await controller.projection()
    except Exception:
        proj = {}
    d = _p.build_digest(memory_stats=stats,
                        notifications=_nt.list_notifications(limit=100),
                        scheduled=memory.scheduled_posts[-100:],
                        projection=proj)
    # also log a digest notification once per day (best-effort)
    return _ok({"digest": d})

@app.route("/api/inbox")
def inbox_list():
    from modules import inbox as _ib
    status = request.args.get("status", "")
    return _ok({"inbox": _ib.list_inbox(status=status)})

@app.route("/api/inbox/poll", methods=["POST"])
async def inbox_poll():
    from modules import inbox as _ib
    from modules import notifications as _nt
    res = await _ib.poll_all(registry=PlatformRegistry())
    if res.get("added"):
        _nt.notify("info", f"Inbox: {res['added']} new messages",
                   "New comments/mentions arrived.", level="info")
    return _ok(res)

@app.route("/api/inbox/suggest", methods=["POST"])
async def inbox_suggest():
    from modules import inbox as _ib
    body = request.get_json(silent=True) or {}
    txt = await _ib.suggest_reply(body.get("text", ""), body.get("platform", ""))
    return _ok({"reply": txt})

@app.route("/api/inbox/<mid>", methods=["POST"])
def inbox_mark(mid):
    from modules import inbox as _ib
    body = request.get_json(silent=True) or {}
    _ib.mark(mid, body.get("status", "replied"), body.get("reply", ""))
    return _ok({})

@app.route("/api/retry")
def retry_list():
    from modules import retry_queue as _rq
    return _ok({"queue": _rq.list_queue()})

@app.route("/api/retry/run", methods=["POST"])
async def retry_run():
    from modules import retry_queue as _rq
    from modules import notifications as _nt
    mem = AgentMemory()
    await mem.initialize()
    reg = PlatformRegistry()
    due = _rq.due_items()
    done, failed = 0, 0
    for idx, entry in due:
        plat, content = entry["platform"], entry["content"]
        prov = reg.get_provider(plat)
        if not prov or not prov.available:
            _rq.mark_result(idx, False, f"{plat} not connected")
            failed += 1
            continue
        res = await controller._publish(plat, {}, content)
        if res.get("error"):
            _rq.mark_result(idx, False, res["error"])
            failed += 1
        else:
            _rq.mark_result(idx, True)
            done += 1
    if done:
        _nt.notify("info", f"Retry queue: {done} recovered", "", level="success")
    return _ok({"due": len(due), "recovered": done, "failed": failed})

@app.route("/api/tax/log", methods=["POST"])
async def tax_log():
    body = request.get_json(silent=True) or {}
    if not body.get("type") or body.get("amount") is None:
        return _err("Provide {type: income|expense, amount, category}", 400)
    tax = TaxTracker()
    entry = await tax.log_transaction(body)
    return _ok({"entry": entry})

# ------------------------------------------------------------------ #
#  CONTENT LIBRARY + MEDIA EDITING (Studio)                            #
# ------------------------------------------------------------------ #
@app.route("/api/library", methods=["GET"])
def library_list():
    from modules import content_library as _lib
    return _ok({"items": _lib.list_items(
        platform=request.args.get("platform") or None,
        status=request.args.get("status") or None)})


@app.route("/api/library", methods=["POST"])
def library_create():
    from modules import content_library as _lib
    # accept JSON or multipart (text file upload -> library item)
    if request.content_type and "multipart/form-data" in request.content_type:
        title = request.form.get("title", "")
        niche = request.form.get("niche", "")
        tone = request.form.get("tone", "professional")
        plats = [p.strip().lower() for p in (request.form.get("platforms", "") or "").split(",") if p.strip()]
        f = request.files.get("file")
        text = request.form.get("text", "")
        media = {}
        if f and f.filename:
            from pathlib import Path as _P
            from werkzeug.utils import secure_filename as _sf
            ext = _P(f.filename).suffix.lower()
            if ext in {".txt", ".md", ".srt", ".vtt"}:
                text = (f.read().decode("utf-8", errors="ignore") or "")[:20000] or text
            elif ext in {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv",
                         ".jpg", ".jpeg", ".png", ".webp", ".gif"}:
                media_dir = _P("data/media")
                media_dir.mkdir(parents=True, exist_ok=True)
                import uuid as _u
                name = f"{_u.uuid4().hex[:8]}_{_sf(f.filename)}"
                dest = media_dir / name
                f.save(str(dest))
                kind = "video" if ext in {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"} else "image"
                media = {kind: str(dest)}
            else:
                return _err(f"Unsupported upload {ext} — use .txt/.md/.srt or media", 400)
        item = _lib.create_item(title=title, text=text, niche=niche,
                                platforms=plats, tone=tone, media=media, source="uploaded")
        return _ok({"item": item})
    body = request.get_json(silent=True) or {}
    if not (body.get("text") or "").strip() and not (body.get("title") or "").strip():
        return _err("Provide {text} or {title}", 400)
    item = _lib.create_item(title=body.get("title", ""), text=body.get("text", ""),
                            niche=body.get("niche", ""), platforms=body.get("platforms") or [],
                            tone=body.get("tone", "professional"),
                            media=body.get("media") or {}, source="created")
    return _ok({"item": item})


@app.route("/api/library/<item_id>", methods=["PUT"])
def library_update(item_id):
    from modules import content_library as _lib
    body = request.get_json(silent=True) or {}
    item = _lib.update_item(item_id, **{k: body[k] for k in
        ("title", "text", "niche", "tone", "platforms", "platform", "media", "status") if k in body})
    if not item:
        return _err("Item not found", 404)
    return _ok({"item": item})


@app.route("/api/library/<item_id>", methods=["DELETE"])
def library_delete(item_id):
    from modules import content_library as _lib
    if not _lib.delete_item(item_id):
        return _err("Item not found", 404)
    return _ok({"deleted": item_id})


@app.route("/api/library/<item_id>/duplicate", methods=["POST"])
def library_duplicate(item_id):
    from modules import content_library as _lib
    item = _lib.duplicate_item(item_id)
    if not item:
        return _err("Item not found", 404)
    return _ok({"item": item})


@app.route("/api/library/<item_id>/ai-edit", methods=["POST"])
async def library_ai_edit(item_id):
    """AI text tools: rewrite | expand | shorten | hashtags | tone"""
    from modules import content_library as _lib
    body = request.get_json(silent=True) or {}
    mode = (body.get("mode") or "rewrite").lower()
    item = _lib.get_item(item_id)
    if not item:
        return _err("Item not found", 404)
    llm = LLMProvider()
    if not llm.available:
        return _err("No AI provider configured — add a key in Customize → AI Engine", 400)
    prompts = {
        "rewrite": "Rewrite this post to be sharper and more engaging, same length. Keep meaning.",
        "expand": "Expand this post with one concrete example and a stronger CTA. Keep platform-ready.",
        "shorten": "Shorten this post to under 280 chars, punchy, keep the hook.",
        "hashtags": "Keep the post as-is but append 5-8 relevant hashtags at the end.",
        "tone": f"Rewrite this post in a {body.get('tone') or 'casual'} tone.",
    }
    system = "You are a professional social media editor. Output ONLY the edited post, no commentary."
    out = await llm.complete(system_prompt=system,
                             user_prompt=f"{prompts.get(mode, prompts['rewrite'])}\n\nPOST:\n{item.get('text','')}",
                             max_tokens=800)
    if not out:
        return _err(f"AI edit failed: {llm.last_error or 'unknown'}", 502)
    updated = _lib.update_item(item_id, text=out.strip())
    return _ok({"item": updated, "mode": mode})


@app.route("/api/library/<item_id>/use", methods=["POST"])
async def library_use(item_id):
    """Stage library item as draft (default) or schedule it."""
    from modules import content_library as _lib
    body = request.get_json(silent=True) or {}
    item = _lib.get_item(item_id)
    if not item:
        return _err("Item not found", 404)
    platforms = body.get("platforms") or item.get("platforms") or ([item.get("platform")] if item.get("platform") else [])
    if not platforms:
        return _err("No platform — set platforms on the item or pass {platforms:[...]}", 400)
    memory = AgentMemory()
    await memory.initialize()
    staged = []
    for plat in platforms:
        draft = {"platform": plat, "niche": item.get("niche", ""), "tone": item.get("tone", "professional"),
                 "text": item.get("text", ""), "title": (item.get("title") or "")[:100],
                 "library_id": item.get("id"), "generated": datetime.now().isoformat(),
                 "ai_generated": False, "media": item.get("media") or {}}
        if body.get("post_time"):
            from datetime import datetime as _dt
            try:
                pt = _dt.fromisoformat(body["post_time"])
            except Exception:
                return _err("Invalid post_time ISO format", 400)
            await memory.schedule_post(draft, post_time=pt, status="scheduled")
        else:
            draft["status"] = "pending_approval"
            await memory.stage_draft(draft)
        staged.append(plat)
    _lib.mark_used(item_id)
    return _ok({"staged": staged})


@app.route("/api/media/edit", methods=["POST"])
def media_edit():
    from modules import media_edit as _me
    body = request.get_json(silent=True) or {}
    if not body.get("file"):
        return _err("Provide {file, operation}", 400)
    try:
        params = {k: v for k, v in body.items() if k not in ("file", "operation")}
        res = _me.edit_image(body["file"], body.get("operation", ""), **params)
        return _ok({"media": res})
    except FileNotFoundError as e:
        return _err(str(e), 404)
    except (ValueError, RuntimeError) as e:
        return _err(str(e), 400)
    except Exception as e:
        return _err(str(e), 500)


@app.route("/api/media/trim", methods=["POST"])
def media_trim():
    from modules import media_edit as _me
    body = request.get_json(silent=True) or {}
    if not body.get("file"):
        return _err("Provide {file, start, end|duration}", 400)
    try:
        res = _me.trim_video(body["file"], start=body.get("start", 0),
                             end=body.get("end"), duration=body.get("duration"))
        return _ok({"media": res})
    except FileNotFoundError as e:
        return _err(str(e), 404)
    except (ValueError, RuntimeError) as e:
        return _err(str(e), 400)
    except Exception as e:
        return _err(str(e), 500)


@app.route("/api/media/thumbnail", methods=["POST"])
def media_thumb():
    from modules import media_edit as _me
    body = request.get_json(silent=True) or {}
    if not body.get("file"):
        return _err("Provide {file, at}", 400)
    try:
        res = _me.video_thumbnail(body["file"], at=body.get("at", 1.0))
        return _ok({"media": res})
    except FileNotFoundError as e:
        return _err(str(e), 404)
    except (ValueError, RuntimeError) as e:
        return _err(str(e), 400)
    except Exception as e:
        return _err(str(e), 500)

if __name__ == "__main__":
    print("GodEye dashboard -> http://localhost:5001")
    app.run(port=5001, debug=False)