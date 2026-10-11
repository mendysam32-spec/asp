"""Projects store - generic multi-project tracking + daily digest.
Persists to data/projects.json
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FILE = DATA_DIR / "projects.json"
_lock = Lock()


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


def list_projects() -> List[Dict]:
    return _load()


def get_project(pid: str) -> Dict:
    for p in _load():
        if p.get("id") == pid:
            return p
    return {}


def upsert_project(data: Dict) -> Dict:
    items = _load()
    pid = data.get("id") or uuid.uuid4().hex[:8]
    now = datetime.now().isoformat()
    existing = next((p for p in items if p.get("id") == pid), None)
    if existing:
        for k in ("name", "description", "niche", "platforms", "status", "notes"):
            if k in data:
                existing[k] = data[k]
        existing["updated"] = now
        _save(items)
        return existing
    proj = {
        "id": pid,
        "name": (data.get("name") or "Untitled project").strip()[:120],
        "description": (data.get("description") or "")[:2000],
        "niche": (data.get("niche") or "")[:120],
        "platforms": data.get("platforms") or [],
        "status": data.get("status") or "active",  # active|paused|done
        "tasks": [],
        "notes": data.get("notes") or "",
        "created": now,
        "updated": now,
    }
    items.append(proj)
    _save(items)
    return proj


def delete_project(pid: str) -> bool:
    items = [p for p in _load() if p.get("id") != pid]
    _save(items)
    return True


def add_task(pid: str, title: str) -> Dict:
    items = _load()
    for p in items:
        if p.get("id") == pid:
            t = {"id": uuid.uuid4().hex[:6], "title": title.strip()[:300],
                 "done": False, "created": datetime.now().isoformat()}
            p.setdefault("tasks", []).append(t)
            p["updated"] = datetime.now().isoformat()
            _save(items)
            return t
    return {}


def toggle_task(pid: str, tid: str) -> bool:
    items = _load()
    for p in items:
        if p.get("id") == pid:
            for t in p.get("tasks", []):
                if t.get("id") == tid:
                    t["done"] = not t.get("done")
                    p["updated"] = datetime.now().isoformat()
                    _save(items)
                    return True
    return False


def build_digest(memory_stats: Dict = None, notifications: List[Dict] = None,
                 scheduled: List[Dict] = None, projection: Dict = None) -> Dict:
    projects = _load()
    open_tasks = sum(1 for p in projects for t in p.get("tasks", []) if not t.get("done"))
    return {
        "ts": datetime.now().isoformat(),
        "projects_total": len(projects),
        "projects_active": sum(1 for p in projects if p.get("status") == "active"),
        "open_tasks": open_tasks,
        "projects": [{"id": p["id"], "name": p["name"], "status": p["status"],
                      "open": sum(1 for t in p.get("tasks", []) if not t.get("done")),
                      "total": len(p.get("tasks", []))} for p in projects],
        "memory": memory_stats or {},
        "scheduled_total": len(scheduled or []),
        "unread_notifications": len([n for n in (notifications or []) if not n.get("read")]),
        "projection": projection or {},
    }
