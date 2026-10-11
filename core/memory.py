import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

_lock = threading.Lock()


class AgentMemory:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.activity_log = []
        self.scheduled_posts = []
        self.performance_metrics = {}
        self._loaded = False

    async def initialize(self):
        """Initialize memory storage"""
        self.data_dir.mkdir(exist_ok=True)
        self._load_data()
        self._loaded = True
        print(f"[Memory] Initialized. Loaded {len(self.activity_log)} activities")

    def _ensure_loaded(self):
        if not self._loaded:
            self.data_dir.mkdir(exist_ok=True)
            self._load_data()
            self._loaded = True

    def _load_data(self):
        """Load existing data from files"""
        activity_file = self.data_dir / "activity_log.json"
        if activity_file.exists():
            with open(activity_file, "r") as f:
                self.activity_log = json.load(f)

        schedule_file = self.data_dir / "scheduled_posts.json"
        if schedule_file.exists():
            with open(schedule_file, "r") as f:
                self.scheduled_posts = json.load(f)

    def _save_data(self):
        """Persist data to files (thread-safe)"""
        with _lock:
            activity_file = self.data_dir / "activity_log.json"
            with open(activity_file, "w") as f:
                json.dump(self.activity_log[-1000:], f, indent=2)

            schedule_file = self.data_dir / "scheduled_posts.json"
            with open(schedule_file, "w") as f:
                json.dump(self.scheduled_posts[-500:], f, indent=2)

    async def log_activity(self, activity_type: str, data: Dict):
        """Log agent activity"""
        self._ensure_loaded()
        entry = {
            "type": activity_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        self.activity_log.append(entry)
        self._save_data()
        print(f"[Memory] Logged: {activity_type}")

    async def schedule_post(self, content: Dict, post_time: datetime = None, status: str = "pending") -> bool:
        """Schedule a post (or stage a draft when status != pending)."""
        self._ensure_loaded()
        scheduled = {
            "content": content,
            "post_time": (post_time or datetime.now()).isoformat(),
            "status": status,
            "created_at": datetime.now().isoformat()
        }
        self.scheduled_posts.append(scheduled)
        self._save_data()
        return True

    async def stage_draft(self, content: Dict) -> Dict:
        """Queue content for human approval. Publishes only after approval."""
        await self.schedule_post(content, status="pending_approval")
        return {"drafted": True, "index": len(self.scheduled_posts) - 1}

    async def list_drafts(self) -> List[Dict]:
        self._ensure_loaded()
        drafts = [
            {**p, "index": i}
            for i, p in enumerate(self.scheduled_posts)
            if p["status"] == "pending_approval"
        ]
        return drafts

    async def resolve_draft(self, index: int, status: str) -> bool:
        """status: published | rejected"""
        self._ensure_loaded()
        if not (0 <= index < len(self.scheduled_posts)):
            return False
        self.scheduled_posts[index]["status"] = status
        self._save_data()
        return True

    async def post_count_today(self, platform: str) -> int:
        self._ensure_loaded()
        today = datetime.now().strftime("%Y-%m-%d")
        return sum(
            1 for p in self.scheduled_posts
            if p.get("content", {}).get("platform") == platform
            and p["created_at"][:10] == today
            and p["status"] in ("published", "pending", "pending_approval")
        )

    async def get_stats(self) -> Dict:
        """Get memory statistics"""
        self._ensure_loaded()
        return {
            "total_activities": len(self.activity_log),
            "scheduled_posts": len(self.scheduled_posts),
            "pending_posts": len([p for p in self.scheduled_posts if p["status"] == "pending"]),
            "posted_today": len([p for p in self.scheduled_posts if p.get("status") == "published" and str(p.get("created_at", ""))[:10] == datetime.now().strftime("%Y-%m-%d")]),
            "drafts": len([p for p in self.scheduled_posts if p["status"] == "pending_approval"]),
        }

    async def get_performance_data(self, days: int = 7) -> List[Dict]:
        """Get performance metrics for analysis"""
        self._ensure_loaded()
        cutoff = datetime.now().timestamp() - (days * 86400)
        recent = [
            entry for entry in self.activity_log
            if datetime.fromisoformat(entry["timestamp"]).timestamp() > cutoff
        ]
        return recent
