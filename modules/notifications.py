"""Notifications center - persistent alerts + optional email/push.
Stores to data/notifications.json. Email via SMTP if env vars set.
"""
import json
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from threading import Lock
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FILE = DATA_DIR / "notifications.json"
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
        FILE.write_text(json.dumps(items[-300:], indent=2), encoding="utf-8")


def notify(kind: str, title: str, message: str = "", level: str = "info") -> Dict:
    """kind: publish_fail|approval_needed|threshold|crash|info|digest"""
    items = _load()
    entry = {
        "id": len(items) + 1,
        "ts": datetime.now().isoformat(),
        "kind": kind,
        "title": title,
        "message": message,
        "level": level,  # info|warn|error|success
        "read": False,
    }
    items.append(entry)
    _save(items)
    # best-effort email for important kinds
    if level in ("warn", "error") or kind in ("approval_needed", "digest", "threshold"):
        try:
            _maybe_send_email(f"[ASP {level.upper()}] {title}", f"{title}\n\n{message}\n\n{entry['ts']}")
        except Exception:
            pass
    return entry


def list_notifications(limit: int = 50, unread_only: bool = False) -> List[Dict]:
    items = _load()
    if unread_only:
        items = [n for n in items if not n.get("read")]
    return list(reversed(items[-limit:]))


def unread_count() -> int:
    return sum(1 for n in _load() if not n.get("read"))


def mark_read(nid: int = None, all_read: bool = False):
    items = _load()
    if all_read:
        for n in items:
            n["read"] = True
    elif nid is not None:
        for n in items:
            if n.get("id") == nid:
                n["read"] = True
    _save(items)
    return True


def _maybe_send_email(subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST")
    to = os.getenv("ALERT_EMAIL")
    if not host or not to:
        return False
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    pw = os.getenv("SMTP_PASS", "")
    from_addr = os.getenv("SMTP_FROM", user or "asp@localhost")
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    with smtplib.SMTP(host, port, timeout=15) as s:
        try:
            s.starttls()
        except Exception:
            pass
        if user and pw:
            s.login(user, pw)
        s.sendmail(from_addr, [to], msg.as_string())
    return True
