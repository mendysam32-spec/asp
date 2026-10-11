"""Background runner - runs dashboard + autonomous agent 24/7.

- Uses waitress (production WSGI) not Flask dev server
- Auto-starts AgentController if any assignment is active
- File logging to data/agent.log (survives reboots)
- Health check at /api/health
- Graceful shutdown on SIGTERM

Run manually:  python run_background.py
As service:   Task Scheduler points here (see scripts/install_service.ps1)
"""
import logging
import os
import sys
import signal
import threading
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_FILE = DATA_DIR / "agent.log"

DATA_DIR.mkdir(exist_ok=True)

# Setup file logging + console
handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
console = logging.StreamHandler(sys.stdout)
console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[handler, console])
log = logging.getLogger("agent.background")

# Import after logging setup
from dashboard_app import app, controller
from config.settings_store import get_settings

# Health endpoint lives in dashboard_app; only add the extended
# (log_file) variant here if it is somehow missing.
try:
    _rules = [str(r) for r in app.url_map.iter_rules()]
    if "/api/health" not in _rules:
        from flask import jsonify
        @app.route("/api/health")
        def health():
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
                "log_file": str(LOG_FILE),
            })
        log.info("Health endpoint registered at /api/health")
    else:
        log.info("Health endpoint already provided by dashboard_app")
except Exception as e:
    log.warning(f"Could not register health endpoint: {e}")


def auto_start_controller():
    """If dashboard_settings.json has active assignments AND agent.enabled, start loop automatically on boot."""
    try:
        settings = get_settings()
        agent = settings.get("agent", {}) or {}
        if not agent.get("enabled", False):
            log.info("Autonomous disabled (agent.enabled=false) - agent idle until enabled in dashboard -> Agent -> Master switch")
            return
        assignments = agent.get("assignments", {})
        has_active = any(a.get("active") for a in assignments.values())
        if has_active and not controller.running:
            controller.start()
            log.info(f"Auto-started agent loop (active assignments: {[k for k,v in assignments.items() if v.get('active')]})")
        elif has_active:
            log.info("Agent loop already running")
        else:
            log.info("No active assignments - agent idle (activate one in dashboard -> Accounts)")
            # Still start so dashboard /api/agent/start works, but don't loop cycles until assigned
            # Controller.start() is idempotent, we skip to save cycles
    except Exception as e:
        log.error(f"auto_start_controller failed: {e}", exc_info=True)


def signal_handler(sig, frame):
    log.info(f"Received signal {sig}, shutting down...")
    try:
        controller.stop()
    except Exception:
        pass
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    log.info("="*50)
    log.info("ASP Agent - Background Service Starting")
    log.info(f"BASE_DIR: {BASE_DIR}")
    log.info(f"LOG_FILE: {LOG_FILE}")
    log.info("="*50)

    auto_start_controller()

    # Log startup info
    settings = get_settings()
    log.info(f"AI provider: {(settings.get('ai',{}) or {}).get('provider')} / {(settings.get('ai',{}) or {}).get('model')}")
    log.info(f"Interval: {(settings.get('agent',{}) or {}).get('analysisIntervalHours',6)}h")
    log.info(f"Assignments: {list((settings.get('agent',{}) or {}).get('assignments',{}).keys())}")

    port = int(os.getenv("PORT", "5001"))
    log.info(f"Starting waitress on http://0.0.0.0:{port} -> http://localhost:{port}")
    log.info("Dashboard: http://localhost:5001  |  Health: http://localhost:5001/api/health")
    log.info("Logs: data/agent.log  |  Stop with: scripts/stop.ps1 or Task Scheduler")

    # Warm check
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=port, threads=8, channel_timeout=120, cleanup_interval=30)
    except ImportError:
        log.warning("waitress not installed, falling back to Flask dev server (not recommended for prod)")
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
