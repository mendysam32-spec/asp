"""Content Library - user-created/uploaded content for the agent to use.

Stores text drafts + file references in data/content_library.json.
Agent auto-cycles prefer unconsumed library items matching platform/niche
before generating fresh AI content.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
LIB_FILE = BASE_DIR / "data" / "content_library.json"


def _load() -> List[Dict]:
    if not LIB_FILE.exists():
        return []
    try:
        return json.loads(LIB_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: List[Dict]) -> None:
    LIB_FILE.parent.mkdir(parents=True, exist_ok=True)
    LIB_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def list_items(platform: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
    items = _load()
    if platform:
        items = [i for i in items if (i.get("platform") in (None, "", platform) or platform in (i.get("platforms") or []))]
    if status:
        items = [i for i in items if i.get("status") == status]
    return sorted(items, key=lambda x: x.get("updated_at", ""), reverse=True)


def create_item(title: str = "", text: str = "", niche: str = "",
                platforms: Optional[List[str]] = None, tone: str = "professional",
                media: Optional[Dict] = None, source: str = "created") -> Dict:
    items = _load()
    now = datetime.now().isoformat()
    item = {
        "id": uuid.uuid4().hex[:12],
        "title": (title or text.splitlines()[0][:100] if text else niche or "Untitled")[:100],
        "text": text or "",
        "niche": niche or "",
        "tone": tone or "professional",
        "platforms": platforms or [],
        "platform": (platforms or [""])[0] if platforms else "",
        "media": media or {},
        "status": "ready",  # ready | used | archived
        "source": source,  # created | uploaded | generated
        "created_at": now,
        "updated_at": now,
        "use_count": 0,
    }
    items.append(item)
    _save(items)
    return item


def get_item(item_id: str) -> Optional[Dict]:
    for i in _load():
        if i.get("id") == item_id:
            return i
    return None


def update_item(item_id: str, **fields) -> Optional[Dict]:
    items = _load()
    for i in items:
        if i.get("id") == item_id:
            for k in ("title", "text", "niche", "tone", "platforms", "platform", "media", "status"):
                if k in fields and fields[k] is not None:
                    i[k] = fields[k]
            i["updated_at"] = datetime.now().isoformat()
            _save(items)
            return i
    return None


def delete_item(item_id: str) -> bool:
    items = _load()
    kept = [i for i in items if i.get("id") != item_id]
    if len(kept) == len(items):
        return False
    _save(kept)
    return True


def duplicate_item(item_id: str) -> Optional[Dict]:
    src = get_item(item_id)
    if not src:
        return None
    return create_item(
        title=(src.get("title") or "") + " (copy)",
        text=src.get("text", ""),
        niche=src.get("niche", ""),
        platforms=list(src.get("platforms") or []),
        tone=src.get("tone", "professional"),
        media=dict(src.get("media") or {}),
        source="duplicated",
    )


def mark_used(item_id: str) -> Optional[Dict]:
    items = _load()
    for i in items:
        if i.get("id") == item_id:
            i["use_count"] = int(i.get("use_count", 0)) + 1
            i["status"] = "used"
            i["updated_at"] = datetime.now().isoformat()
            _save(items)
            return i
    return None


def next_for_platform(platform: str) -> Optional[Dict]:
    """Oldest ready item usable for this platform (FIFO)."""
    items = [i for i in _load() if i.get("status") == "ready"]
    cands = [i for i in items
             if not i.get("platforms") or platform in i.get("platforms") or i.get("platform") in ("", platform)]
    if not cands:
        return None
    cands.sort(key=lambda x: x.get("created_at", ""))
    return cands[0]
