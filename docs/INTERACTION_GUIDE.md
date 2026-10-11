# ASP — Complete Interaction Guide

> How to control the AI Content Agent — dashboard, terminal, CLI, and API.  
> Dashboard: http://localhost:5001  |  Health: http://localhost:5001/api/health  
> Background service (Waitress, 8 threads): `run_background.py:113` — respects `agent.enabled` master switch.

---

## 1) Dashboard Overview (full-glass UI)

All UI settings persist to `config/dashboard_settings.json` via `config/settings_store.py` — no code edits needed. Customize → ⚙.

| View | Route / Card | What you do |
|------|--------------|-------------|
| **Overview** | `view-overview` + `GET /api/status` | `SYSTEM STATUS` (engine online), `AI ENGINE`, `PLATFORM CONNECTIONS`, `MONETIZATION PULSE`, `TAX & INCOME`, `ACTIVITY`, `PUBLISH QUEUE`. Buttons: `◈ Analyze niches` / `⟳ Refresh` / `✎ Generate content` |
| **Content Studio** | `view-content` | Single generate + **Video Upload** (`POST /api/media/upload` → `data/media`, preview `/media/<file>`) + **1-Click Bulk** (see §2). Media render (`POST /api/media/render` → `modules/media_lab.py`) → preview video `9:16` + approval path |
| **Accounts** | `view-platforms` + `GET /api/accounts` | Per-platform: `Enabled in agent`, `Connection`/`Payout`, `＋ Connect`/`－ Disconnect`, `AGENT ASSIGNMENT` toggles: `Agent works`, `Active`, `Auto-post`, `Hold for approval`, `Working niche`, `Content`, `Daily limit`, `YouTube privacy`. `mediaHint` for `tiktok`/`instagram` |
| **Agent** | `view-agent` + `GET /api/accounts` + `GET /api/agent/drafts` | `AUTONOMOUS — MASTER` (`POST /api/agent/enabled`), `AUTONOMOUS LOOP` (`Start`/`Stop`/`Run`), `Talk to ASP`, `NEEDS YOUR APPROVAL` with **filter + bulk Approve/Reject all** (`POST /api/agent/approve/bulk:335`) |
| **Monetization** | `view-money` + `GET /api/agent/path` | `ELIGIBILITY` (per platform), `PATH TO PAYOUT` (YouTube → 1000 subs → days ETA from `AgentController.projection():304`), `PAYOUT READINESS` checklist (`agent.checklist`) |
| **Terminal** | `view-terminal` | No-code cmd/powershell (`POST /api/terminal/exec`) — see `TERMINAL_REFERENCE.md` |
| **Customize (⚙)** | `#panel` + `GET/POST /api/settings` | Theme, Widgets, AI Engine, Agent (`enabled`, `defaultNiche`, `focus`, `voice`, limits), Platforms |
| **Gap Fixes** | New in this release | **Media Library** (`GET/POST /api/media/list`/`delete`, grid in Content Studio with `Use`/`✕`), **Scheduled Queue** (`POST /api/schedule`, `GET /api/schedule`, `POST /api/schedule/due` every 60s daemon `dashboard_app.py:35`, date picker in Content Studio), **Bulk Drafts** (`POST /api/agent/approve/bulk`), **Analytics Charts** (7-day bars `GET /api/analytics/history` under Overview `ACTIVITY`), **Toast + Logs** (`#toasts`, `GET /api/logs`), **Basic Auth** (`DASHBOARD_PASSWORD` in `.env` → `?pw=` or Basic Auth, `dashboard_app.py:72`) |

**Autonomous Master Switch** (`agent.enabled`, `config/settings_store.py:47`, default `False`):
* Dashboard: `Agent → Autonomous: ON/OFF` or `Customize → Agent → Autonomous — master switch` → toggles `POST /api/agent/enabled` (`dashboard_app.py:322`). When `OFF`, `POST /api/agent/start` / `POST /api/agent/run` / bulk `autoPublish` are blocked; `run_background.py:63` stays idle on boot.
* CLI: `python main.py` → `start` only works if enabled via dashboard/terminal first (or set `"agent":{"enabled":true}` in `dashboard_settings.json`).

---

## 2) Content Studio — Video Upload + 1-Click Post to All Chosen Accounts

> **New:** You now see **text only by default because no video was attached**. Upload a real file first — it replaces auto-generated media for YouTube/TikTok.

**Video Upload** (`templates/dashboard.html` ~`#upVideo`, `POST /api/media/upload` `dashboard_app.py:270`):
* Pick ` .mp4 / .mov / .m4v / .webm / .avi / .mkv` (video) or `.jpg/.png/.webp` (image for Instagram) → `⬆ Upload` → saves to `data/media/<uuid>_<name>` (200 MB max) → returns `{media:{video|image, preview_url:/media/...}}`. Preview appears inline (`<video controls>` or `<img>`). Sets `UPLOADED_VIDEO`/`UPLOADED_IMAGE` used by next **1-Click** `POST /api/publish/bulk` (`video_path`/`image_path`). Re-upload to replace. If you skip upload, agent auto-generates narrated video (if `media.enabled+voice` and `text≥60` chars) or falls to draft.

## 2b) Content Studio — 1-Click Post to All Chosen Accounts

**Location:** Dashboard → `Content Studio` (`templates/dashboard.html:462`)

Steps (no code):
1. `Niche` (e.g., `AI & Technology`) — defaults to `agent.defaultNiche`.
2. `Platform` (single generate dropdown) + `Tone` (`professional`/`casual`/`funny`/`motivational`).
3. `✦ Generate with AI` → `POST /api/generate` (`dashboard_app.py:140` → `ContentCreator.generate_ai_content` `modules/content_creator.py:12`). Shows `[AI]` vs `[TEMPLATE]` badge (`main.py:89`). Optionally `▶ Render media` → `POST /api/media/render` (needs ≥60 chars).
4. **1-CLICK — POST TO ALL CHOSEN ACCOUNTS** card (new):
   * Check `YouTube`/`TikTok`/`X`/`Instagram` pills (`#bulkChecks` — chips turn `on` when checked).
   * `Custom text` textarea — leave empty to **AI-generate per platform** (unique hook/hashtags), or type once to reuse everywhere.
   * `Draft only` toggle — when on, stages to `Agent → Needs Your Approval` instead of live publish.
   * Click **`⤴ Post to Selected — 1 Click`** → `POST /api/publish/bulk` (`dashboard_app.py:172`). Per-platform: generates if needed, renders media (if `media.enabled+voice` and `text≥60`), then `AgentController._publish` (`modules/agent_controller.py:202`) → YouTube `upload_video`, TikTok `post_video_file` (`SELF_ONLY`), X `post_thread`, Instagram `post_instagram_image` (auto-hosts via Netlify). Falls back to draft on error (e.g., `tiktok` needs `video`, `instagram` needs `image`).
   * Result toast shows `youtube: ✓ published — preview…` / `✕ not connected` etc. Drafts appear in `Agent`.

**Equivalent CLI/Terminal:**

```bash
# Dashboard Terminal or API:
publish bulk "AI tips" --platforms tiktok,youtube,x --tone casual
publish bulk "crypto news" --platforms youtube --draft
publish "Hello — new video out now!" --platforms x

# Direct API (for assistant):
curl -X POST http://localhost:5001/api/publish/bulk \
  -H "Content-Type: application/json" \
  -d '{"niche":"AI tips","tone":"casual","platforms":["tiktok","youtube"],"autoPublish":true}'
```

---

## 3) Terminal — No-Code CMD (Dashboard + API)

**Location:** Dashboard → `Terminal` (▣) → monospace dark terminal (`templates/dashboard.html:650`).

* Type `help` → full command list. History `↑`/`↓`, `clear` wipes.
* Backend `POST /api/terminal/exec` (`dashboard_app.py:489`) — whitelisted commands, **no shell**. Unknown input → fallback to `AgentController.ask` (LLM with context: accounts, assignments, `projection()`, recent activity).
* Full reference + examples: **`docs/TERMINAL_REFERENCE.md`** (read this!).

**For AI assistant — prefer this (single call, no code):**

```json
POST /api/terminal/exec  {"command": "status"}
POST /api/terminal/exec  {"command": "publish bulk \"AI tips\" --platforms youtube --draft"}
POST /api/terminal/exec  {"command": "ask draft a hook for my tiktok about AI automation"}
```

See `TERMINAL_REFERENCE.md#for-ai-assistant`.

---

## 4) All Other Ways to Interact

### CLI (`main.py:17`)

```bash
pip install -r requirements.txt
python setup_credentials.py           # wizard → writes .env
python main.py                        # interactive
# inside:
analyze   # NicheAnalyzer.get_full_analysis()
create    # ContentCreator.generate_ai_content per platform
connect   # PlatformRegistry.check_all()
monetize  # PlatformRegistry.get_monetization_status()
start     # AutonomousLoop.start() (respects enabled)
status    # agent.get_status() + LLM provider
tax       # TaxTracker.generate_tax_report()
exit
```

### Credentials & Connections

* **Wizard:** `python setup_credentials.py [youtube|tiktok|x|instagram]` → guides portal URLs (`setup_credentials.py:19`) → writes `.env` (`config/settings.py:12` `set_env_vars`).
* **Dashboard:** `Accounts → ＋ Connect` → OAuth (`youtube`/`tiktok` → browser popup `dashboard_app.py:261`) or token modal (`x`/`instagram` → `TOKEN_FIELDS:40`). `POST /api/token/<platform>` verifies via `provider.check_connection()`.
* **Current status:** `yt` connected (`YOUTUBE_API_KEY` `sample=cRp93RxVCjI`), others need tokens (see `/api/status` → `platforms`).

### API Endpoints (for automation / assistant)

| Method | Path | Body | Desc |
|--------|------|------|------|
| GET | `/api/status` | — | AI, platforms, monetization, tax, memory, agent, `autonomousEnabled` |
| GET | `/api/accounts` | — | Accounts + `agent` status + `autonomousEnabled` |
| POST | `/api/connect/<platform>` | — | OAuth or token fields |
| POST | `/api/token/<platform>` | `{values:{...}}` | Save tokens + check |
| POST | `/api/disconnect/<platform>` | — | Unset env vars (`PLATFORM_ENV:33`) |
| POST | `/api/generate` | `{niche,platform,tone}` | Single generate |
| POST | `/api/publish` | `{platform,content}` | Single publish |
| **POST** | `/api/publish/bulk` | `{niche,tone,platforms[],text,autoPublish,video_path,image_path}` | **1-click bulk** — `video_path`/`image_path` from `/api/media/upload` |
| POST | `/api/media/upload` | `multipart file` → `{media:{video|image,preview_url}}` | **Video upload** (YouTube/TikTok) — see §2 |
| POST | `/api/media/render` | `{text}` | Render `modules/media_lab` video+image |
| POST | `/api/analyze` | — | Niche analysis |
| POST | `/api/terminal/exec` | `{command}` | **Terminal no-code** |
| GET/POST | `/api/agent/enabled` | `{enabled}` | Master switch |
| POST | `/api/agent/start` `/stop` `/run` | — | Loop control |
| POST | `/api/agent/assign` | `{platform, assigned, active, autoPost...}` | Assignments |
| POST | `/api/agent/ask` | `{message}` | LLM chat |
| GET | `/api/agent/drafts` | — | Draft queue |
| POST | `/api/agent/approve` | `{index, action, privacy}` | Publish/reject draft |
| GET/POST | `/api/settings` | JSON | Theme/AI/Agent/Platforms |

### Platform Payouts & Requirements (2026)

* **TikTok** `10k followers, 100k likes/28d, 3 posts + 1min+` → PayPal/Hyperwallet $50 on 15th (`api/providers/tiktok_provider.py:265`)
* **YouTube** `1k subs + 4k watch hrs (or 10M Shorts/90d)` → AdSense $100 (`youtube_provider.py:135`, thresholds → 8k/20M Feb 2027)
* **X** `Premium (~$8/mo) + verified + 500 followers + ~5M impressions/3mo` → Stripe $30 biweekly (`x_provider.py:105`)
* **Instagram** `500 fan tips / 1k affiliate / 10k subs+ads` → Bank/Stripe $5 (`meta_provider.py:143`)

### Background Service

* **Dev:** `python dashboard_app.py` → `http://localhost:5001` (single-thread, not for `status` heavy)
* **Prod (recommended):** `python run_background.py` → Waitress `0.0.0.0:5001` `threads=8` + health `GET /api/health` + `auto_start_controller` respects `enabled` (`run_background.py:62`)
* **Win Task Scheduler:** `scripts/install_service.ps1` (admin) + `scripts/stop.ps1` / `scripts/status.ps1`

---

## 5) Typical No-Code Flows

**“Post one idea to all my accounts right now”:**
1. Dashboard → `Accounts` → confirm `● connected` for chosen platforms.
2. `Content Studio` → niche `AI automation` / tone `casual` → check `tiktok,youtube,x` → leave `Custom text` empty → `⤴ Post to Selected — 1 Click`.
3. Or `Terminal` → `publish bulk "AI automation tips" --platforms tiktok,youtube,x --tone casual`

**“Draft for approval, then publish”:**
* `Content Studio` → check `Draft only` → `Post` → `Agent → Needs Your Approval → ✓`.

**“What should I post?” (no code):**
* `Terminal` → `analyze` → picks `top_niche` → `generate "that niche" tiktok casual` → `publish bulk "that niche" --platforms tiktok --draft` → `ask` for hook.

**“Ask without code”:**
* `Agent → Talk to ASP` or `Terminal → ask <question>` — both use `AgentController.ask` with your settings context.
