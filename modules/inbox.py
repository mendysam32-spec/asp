"""Inbox - comment/mention polling + LLM-suggested replies.
Persists to data/inbox.json. Providers have limited inbox APIs, so this
does best-effort real pulls and always keeps a unified queue.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FILE = DATA_DIR / "inbox.json"
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


def list_inbox(status: str = "") -> List[Dict]:
    items = _load()
    if status:
        items = [m for m in items if m.get("status") == status]
    return list(reversed(items[-100:]))


def add_message(platform: str, author: str, text: str, external_id: str = "") -> Dict:
    items = _load()
    # dedupe on external_id
    if external_id and any(m.get("external_id") == external_id for m in items):
        return {}
    msg = {
        "id": uuid.uuid4().hex[:8],
        "external_id": external_id,
        "platform": platform,
        "author": author[:80],
        "text": text[:2000],
        "suggested_reply": "",
        "status": "new",  # new|replied|dismissed
        "ts": datetime.now().isoformat(),
    }
    items.append(msg)
    _save(items)
    return msg


async def poll_all(registry=None) -> Dict:
    """Best-effort pull from each connected provider. Never raises."""
    added = []
    if registry is None:
        return {"added": 0, "note": "no registry"}
    # YouTube: try commentThreads on recent uploads (if OAuth available)
    try:
        yt = registry.get_provider("youtube")
        if yt and getattr(yt, "available", False) and hasattr(yt, "_get_auth_service"):
            try:
                svc = yt._get_auth_service()
                # list recent comment threads on channel (mine) - may fail without scope
                res = svc.commentThreads().list(part="snippet", mine=True, maxResults=10,
                                                textFormat="plainText").execute()
                for it in res.get("items", []):
                    sn = it.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                    txt = sn.get("textDisplay", "")[:500]
                    author = sn.get("authorDisplayName", "youtube")
                    cid = it.get("id", "")
                    if txt and add_message("youtube", author, txt, external_id=cid):
                        added.append(cid)
            except Exception:
                pass
    except Exception:
        pass
    # X: tweepy mentions timeline (if available)
    try:
        x = registry.get_provider("x")
        if x and getattr(x, "available", False) and hasattr(x, "client"):
            try:
                me = x.client.get_me()
                my_id = me.data.id if me and me.data else None
                if my_id:
                    ments = x.client.get_users_mentions(id=my_id, max_results=10)
                    for t in (ments.data or []):
                        if add_message("x", f"@{t.author_id}", t.text, external_id=str(t.id)):
                            added.append(str(t.id))
            except Exception:
                pass
    except Exception:
        pass
    return {"added": len(added)}


async def suggest_reply(text: str, platform: str = "", llm=None) -> str:
    if llm is None:
        try:
            from core.llm import LLMProvider
            llm = LLMProvider()
        except Exception:
            llm = None
    if llm is None or not getattr(llm, "available", False):
        return "Thanks for reaching out! We'll get back to you shortly."
    try:
        out = await llm.complete(
            system_prompt="You are a friendly social media assistant. Draft a short, warm, professional reply (max 280 chars). No hashtags unless needed.",
            user_prompt=f"Platform: {platform}\nComment: {text}\nDraft reply:",
            max_tokens=150,
        )
        return (out or "").strip()[:600] or "Thanks for your comment!"
    except Exception:
        return "Thanks for your comment!"


def mark(pid: str, status: str, reply: str = "") -> bool:
    items = _load()
    for m in items:
        if m.get("id") == pid:
            m["status"] = status
            if reply:
                m["suggested_reply"] = reply
                m["replied_at"] = datetime.now().isoformat()
            _save(items)
            return True
    return False
