# GodEye Terminal — No-Code Command Reference

> Dashboard → **Terminal** (▣)  or  `POST /api/terminal/exec` → execute any agent request without writing code.
> Style: `cmd` / `powershell` — type `help` and press Enter. History with ↑ / ↓, `clear` to wipe.

All commands run on the backend (`dashboard_app.py:489` → `api/terminal/exec`). No shell access — only whitelisted agent operations + natural-language fallback via your LLM (`modules/agent_controller.py:337`).

---

## Quick Start

```
help
status
accounts
generate "AI & Technology" tiktok casual
publish bulk "AI tips" --platforms tiktok,youtube --tone motivational
publish "Hello world — follow for daily AI tips!" --platforms x
enable on
run
```

## Command Table

| Command | Syntax | What it does | Example |
|---------|--------|--------------|---------|
| **help** | `help` / `?` | Show all commands | `help` |
| **clear** | `clear` | Clear terminal screen | `clear` |
| **status** | `status` | Health: platforms (connected/payout), autonomous `enabled`/`running`, `last_cycle` | `status` |
| **accounts** | `accounts` / `con` | Detailed `connection_check` per platform | `accounts` |
| **analyze** | `analyze` | Run `NicheAnalyzer` → `top_niche` + 5 recommendations with scores | `analyze` |
| **generate** | `generate "<niche>" [platform] [tone]` | AI content for one platform via `ContentCreator` (`core/llm.py`). Platform `twitter`/`x`/`tiktok`/`youtube`/`instagram`, tone `professional`/`casual`/`funny`/`motivational` | `generate "fitness tips" youtube professional` <br> `generate "AI & Technology" tiktok casual` |
| **publish** (custom) | `publish "<your text>" --platforms p1,p2` | One-click publish custom text to chosen accounts (uses `AgentController._publish`) | `publish "New drop! Link in bio" --platforms instagram` |
| **publish bulk** | `publish bulk "<niche>" --platforms p1,p2 [--tone T] [--draft]` | Generate per-platform with AI then **publish** (omit `--draft` to go live) or `--draft` to stage for approval | `publish bulk "AI tips" --platforms tiktok,youtube,x --tone casual` <br> `publish bulk "crypto news" --platforms youtube --draft` |
| **run** | `run` / `cycle` | Run one `AgentController.run_cycle()` now (respects assignments, daily limits, focus mode) | `run` |
| **start** | `start` | `controller.start()` — start background loop (needs `enable on`) | `start` |
| **stop** | `stop` | `controller.stop()` | `stop` |
| **enable** | `enable on` / `enable off` | Master kill-switch `agent.enabled` (`config/settings_store.py:47`, persisted to `dashboard_settings.json`). When `off`, `run`/`start`/`publish_bulk`+auto are blocked | `enable on` |
| **tax** | `tax` | `TaxTracker.generate_tax_report()` → income/expenses/est. tax | `tax` |
| **monetize** | `monetize` | `PlatformRegistry.get_monetization_status()` per platform (YouTube subs/watch hrs, TikTok 10k/100k, X 500/5M, IG tiers) | `monetize` |
| **ask** | `ask <question>` | Natural language → `AgentController.ask()` (LLM with context: accounts, assignments, recent activity, `projection()`). Also fallback for any unknown command | `ask what niche should I focus on for youtube?` <br> `ask draft a viral hook for my next short` |

### Quoting

Use double quotes for multi-word niches/text (parsed with `shlex.split` like `powershell`):

```
generate "AI & Technology" youtube professional
publish "Hello — new video out now!" --platforms x,youtube
publish bulk "my niche with spaces" --platforms tiktok --tone funny
```

Without quotes, only first word is taken as niche — always quote.

---

## Publish Details

* **Allowed platforms:** `tiktok`, `youtube`, `x` (`twitter` alias), `instagram` (`dashboard_app.py:185`).
* **Connection required:** `X`/`Instagram` via `POST /api/token/<platform>` (Dashboard → Accounts → Connect → paste tokens), `YouTube`/`TikTok` via OAuth (`/api/connect/<platform>`).
* **Media:** For `youtube`/`tiktok`/`instagram`, if `media.enabled + voice` set, `modules/media_lab.py:render` auto-creates narrated video + thumbnail (needs `text ≥60` chars). If no `video` and target is `tiktok`, publish fails → auto-drafted instead (`dashboard_app.py:235`).
* **Video Upload (new):** `POST /api/media/upload` (`multipart file`, 200 MB max, `data/media`) → `POST /api/publish/bulk {video_path: "data/media/<file>"}`. Content Studio → `Upload Video` picker shows `<video>` preview; bulk 1-click then uses **your file** for YouTube/TikTok instead of auto-render. If you skip upload, agent falls back to auto-render/draft. Supported `.mp4/.mov/.m4v/.webm` + images for IG. See `INTERACTION_GUIDE.md §2`.
* **One-click bulk endpoint (also callable directly):**

```bash
curl -X POST http://localhost:5001/api/publish/bulk \
  -H "Content-Type: application/json" \
  -d '{"niche":"AI tips","tone":"casual","platforms":["tiktok","youtube","x"],"text":"","autoPublish":true}'
```

`text` empty → AI-generate per platform; `text` non-empty → reuse same text everywhere. `autoPublish:false` → drafts to `Agent` → `Needs Your Approval`.

---

## Agent Interaction — All Ways (for you & for AI assistant)

| Interface | How | Commands / Docs |
|-----------|-----|-----------------|
| **Dashboard Terminal** | Dashboard → ▣ Terminal → type commands above | This file |
| **Content Studio (1-Click)** | Dashboard → Content Studio → choose niche/tone → check `YouTube/TikTok/X/Instagram` → `⤴ Post to Selected — 1 Click` (calls `POST /api/publish/bulk`) | See `INTERACTION_GUIDE.md#content-studio` |
| **Dashboard UI** | Accounts (connect), Agent (autonomous master, assignments, drafts approve), Monetization, Customize ⚙ | `INTERACTION_GUIDE.md` |
| **CLI** (`main.py`) | `python main.py` interactive: `analyze`/`create`/`connect`/`monetize`/`start`/`status`/`tax`/`exit` | `README.md#commands` |
| **API (for assistant)** | `POST /api/terminal/exec {command}`, `POST /api/publish/bulk`, `POST /api/generate`, `POST /api/agent/*` | `dashboard_app.py` routes |
| **Setup wizard** | `python setup_credentials.py [youtube|tiktok|x|instagram]` → writes `.env` | `setup_credentials.py:19` |

### For AI Assistant (Muse) — Use This

Prefer terminal API — single round-trip, no code:

```
POST /api/terminal/exec  {"command": "status"}
POST /api/terminal/exec  {"command": "publish bulk \"AI tips\" --platforms youtube --draft"}
POST /api/terminal/exec  {"command": "ask <user intent>"}
```

Or bulk direct:

```
POST /api/publish/bulk  {"niche":"...","platforms":["youtube","tiktok"],"autoPublish":true}
```

Check `docs/INTERACTION_GUIDE.md` for full endpoint list + examples.

---

## Tips

* Always run `status` / `accounts` first to verify connections before publishing.
* Use `--draft` during testing — approve in **Agent → Needs Your Approval** (`POST /api/agent/approve`).
* Autonomous must be `enable on` for `run`/`start` to work (see `Agent` → master switch `modules/agent_controller.py:53`).
* All `publish` / `generate` calls log to `data/activity_log.json` via `AgentMemory`.
