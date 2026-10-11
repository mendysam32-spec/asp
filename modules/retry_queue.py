"""Retry queue - failed publishes are re-queued with backoff.
Persists to data/retry_queue.json
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FILE = DATA_DIR / "retry_queue.json"
_lock = Lock()
MAX_ATTEMPTS = 5


def _load() -> List[Dict]:
    if not FILE.exists():
        return []
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: List[Dict]):
    DATA_DIR.mkdir(exist_ok=True)
    with _lock:
        FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def push(platform: str, content: Dict, error: str) -> Dict:
    items = _load()
    entry = {
        "platform": platform,
        "content": content,
        "last_error": error[:1000],
        "attempts": 0,
        "next_retry": (datetime.now() + timedelta(minutes=15)).isoformat(),
        "created": datetime.now().isoformat(),
        "status": "queued",
    }
    items.append(entry)
    _save(items)
    return entry


def list_queue() -> List[Dict]:
    return list(reversed(_load()[-100:]))


def due_items() -> List[Dict]:
    now = datetime.now()
    out = []
    for i, e in enumerate(_load()):
        if e.get("status") != "queued":
            continue
        try:
            if datetime.fromisoformat(e["next_retry"]) <= now and e.get("attempts", 0) < MAX_ATTEMPTS:
                out.append((i, e))
        except Exception:
            out.append((i, e))
    return out


def mark_result(index: int, ok: bool, error: str = ""):
    items = _load()
    if not (0 <= index < len(items)):
        return
    e = items[index]
    if ok:
        e["status"] = "done"
    else:
        e["attempts"] = e.get("attempts", 0) + 1
        e["last_error"] = error[:1000]
        if e["attempts"] >= MAX_ATTEMPTS:
            e["status"] = "dead"
        else:
            backoff = 15 * (2 ** e["attempts"])  # 30,60,120...
            e["next_retry"] = (datetime.now() + timedelta(minutes=min(backoff, 720))).isoformat()
    _save(items)
