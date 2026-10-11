# ASP — Agent SP

An AI agent that autonomously creates content, analyzes trends, manages social media accounts, tracks finances, and works toward monetization across platforms.

## What It Does

- **Niche Analysis** - Finds trending niches and growth opportunities
- **Content Creation** - Generates content for X, Instagram, YouTube, TikTok
- **Platform Management** - Real API connections to all major platforms
- **Monetization** - Tracks eligibility using accurate 2026 payout thresholds
- **Tax Tracking** - Logs income/expenses and estimates tax liability
- **Autonomous Operation** - Runs cycles without human intervention

## Platform Priorities (who pays creators)

| Platform | Requirement to get paid | Payout |
|----------|------------------------|--------|
| **TikTok** (priority 1) | 10k followers, 100k likes/28d | **PayPal** (Hyperwallet), $50 min, 15th |
| **YouTube** (priority 2) | 1k subs + 4k watch hrs (or 10M Shorts) | AdSense → bank, $100 min, monthly |
| **X** (priority 3) | 500 followers + ~5M impressions/3mo (needs Premium) | Stripe, $30 min, biweekly |
| **Instagram** (priority 4) | Fan tips from 500 followers; in-stream at 10k | Bank/Stripe, $5 min, 2x monthly |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Get API keys for the platforms you want + choose an AI provider
python setup_credentials.py

# Run dashboard (recommended, Waitress prod) — master switch OFF by default
python run_background.py  # -> http://localhost:5001  (or python dashboard_app.py for dev)

# Or CLI
python main.py
```

The wizard guides you through each platform's developer portal and OAuth flow,
then writes keys to `.env`.

> **Dashboard is the fastest no-code path** — see `docs/INTERACTION_GUIDE.md` + `docs/TERMINAL_REFERENCE.md`.

## AI Engine

The agent uses a real LLM provider for content generation:

- **NVIDIA** (`NVIDIA_API_KEY`, `integrate.api.nvidia.com`, default `meta/muse-glimmer-30b`) — free credits to start
- **OpenRouter** (`OPENROUTER_API_KEY`, `openrouter.ai/api/v1`, default `openai/gpt-4o-mini`) — many free models, e.g. `meta-llama/llama-3.1-8b-instruct:free`
- **OpenAI** (`OPENAI_API_KEY`) - uses `gpt-4o-mini`
- **Anthropic** (`ANTHROPIC_API_KEY`) - uses `claude-3-5-haiku`
- **Fallback** - if no key is set, uses built-in templates

Provider can be `auto` (try every configured key in order), switched anytime in
Customize ⚙ → AI Engine, where keys can also be pasted (saved to `.env`) and
models test-pinged. Reasoning level (`off/low/medium/high`) is sent as
effort/budget to OpenRouter, OpenAI o-series and Anthropic thinking. If a model
errors, the agent auto-fails over to the next provider and reports the switch.
Full chat console lives in Agent → Chat (`POST /api/chat` with per-message
provider/model/reasoning overrides, history, export).

## Dashboard — No-Code Control Center (ASP)

**Start:** `python run_background.py` → http://localhost:5001  (health http://localhost:5001/api/health)

| View | Purpose |
|------|---------|
| **Overview** | System status, AI engine, connections, monetization pulse |
| **Content Studio** | Single generate + **1-Click: Post to All Chosen Accounts** — check `YouTube/TikTok/X/Instagram`, optional custom text, `⤴ Post — 1 Click` calls `POST /api/publish/bulk` (`dashboard_app.py:172`) |
| **Accounts** | Connect/Disconnect + per-account assignment (`Agent works`, `Active`, `Auto-post`, `Hold for approval`, niche, limits) |
| **Agent** | **Autonomous Master** `ON/OFF` (`POST /api/agent/enabled`, `config/settings_store.py:47`), loop `Start/Stop/Run now`, `Talk to ASP` chat, approval queue |
| **Monetization** | Eligibility + `Path to Payout` (`modules/agent_controller.py:304`) |
| **Terminal** (▣) | No-code cmd/powershell — type `help` → executes `POST /api/terminal/exec` (`dashboard_app.py:489`). See `docs/TERMINAL_REFERENCE.md` |

**Autonomous** is `OFF` by default (`agent.enabled:false`). Turn `ON` in `Agent` or `Customize ⚙ → Agent → Autonomous — master switch`.

## All Interaction Paths

See **`docs/INTERACTION_GUIDE.md`** (complete guide) and **`docs/TERMINAL_REFERENCE.md`** (terminal cheat-sheet).

* **Terminal (no-code):** `help`, `status`, `generate "niche" platform tone`, `publish bulk "niche" --platforms t,y,x`, `publish "text" --platforms x`, `ask <question>`, `enable on/off`, `run`, `tax`, `monetize` → `POST /api/terminal/exec`
* **Bulk API:** `POST /api/publish/bulk {niche,tone,platforms[],text,autoPublish}` → generates per-platform + publishes/drafts via `AgentController._publish`
* **CLI:** `python main.py` or `python setup_credentials.py [platform]`

## Commands (CLI `main.py`)

| Command | Description |
|---------|-------------|
| `analyze` | Analyze trending niches |
| `create` | Create content for all platforms |
| `connect` | Verify platform connections (real API checks) |
| `monetize` | Check monetization eligibility per platform |
| `start` | Start autonomous mode (needs `enable on`) |
| `status` | Check agent status |
| `tax` | View tax report |
| `exit` | Stop the agent |

**Terminal adds (Dashboard):** `help`, `generate`, `publish bulk`, `publish`, `ask`, `enable on/off`, `run`, `clear` — full table in `docs/TERMINAL_REFERENCE.md`.

## Docs

* **`docs/INTERACTION_GUIDE.md`** — every way to interact (dashboard, Content Studio 1-Click, Terminal, CLI, API, background service)
* **`docs/TERMINAL_REFERENCE.md`** — terminal command table, quoting rules, examples, and assistant usage

## Project Structure

```
ai-agent/
├── main.py                    # Entry point & CLI
├── setup_credentials.py       # OAuth/API key wizard
├── dashboard_app.py           # ASP dashboard (Flask + Waitress)
├── run_background.py          # Prod runner (Waitress 0.0.0.0:5001, health)
├── config/
│   ├── settings.py            # Configuration (loads .env)
│   ├── settings_store.py      # UI-driven store → dashboard_settings.json
│   └── dashboard_settings.json# Persisted theme/AI/agent/platforms
├── docs/
│   ├── INTERACTION_GUIDE.md   # Complete interaction guide
│   └── TERMINAL_REFERENCE.md  # Terminal cheat-sheet + API
├── core/
│   ├── agent.py               # Main agent
│   ├── brain.py               # Decision making + AI generation
│   ├── llm.py                 # OpenAI/Anthropic/NVIDIA provider
│   └── memory.py              # Data persistence + drafts
├── modules/
│   ├── agent_controller.py    # Assignment, loop, _publish, ask (enabled)
│   ├── niche_analyzer.py      # Trend detection
│   ├── content_creator.py     # Content generation (generate_ai_content)
│   ├── media_lab.py           # Quote cards + TTS video
│   ├── monetization.py        # Revenue tracking (2026 thresholds)
│   └── tax_tracker.py         # Tax management
├── api/
│   ├── registry.py            # Platform priority registry
│   ├── providers/
│   │   ├── tiktok_provider.py # TikTok (pays via PayPal)
│   │   ├── youtube_provider.py# YouTube (largest payouts)
│   │   ├── x_provider.py      # X/Twitter v2
│   │   └── meta_provider.py   # Instagram/Facebook Graph
│   ├── paypal.py              # PayPal integration
│   └── analytics.py           # Performance metrics
├── scheduler/
│   ├── task_scheduler.py      # Timed tasks
│   └── autonomous_loop.py     # Continuous operation
├── templates/dashboard.html   # ASP UI (Overview/Content/Accounts/Agent/Money/Terminal)
├── scripts/
│   ├── install_service.ps1    # Win Task Scheduler (boot)
│   ├── stop.ps1 / status.ps1  # Stop / health check
│   └── start_hidden.vbs       # Hidden background launch
└── data/                      # Stored data (JSON, media, logs)
```

## Important Notes

- **TikTok** auto-posting requires your app be approved for the "Content Posting" permission (developer portal app review)
- **YouTube** uploads + analytics need OAuth (the wizard handles this)
- **X** monetization requires paying for X Premium (~$8/mo) before X pays you
- **Instagram** requires a Business/Creator account linked to a Facebook Page
- Tax tracking is **bookkeeping only** - not tax advice
- Human approval is required for financial decisions