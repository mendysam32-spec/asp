"""UI-driven settings store. All values editable from the dashboard - no code changes needed.

Read via:  settings_store.get()
Write via: settings_store.update({...}) or settings_store.set(path, value)
"""
import json
from copy import deepcopy
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORE_FILE = Path(__file__).resolve().parent / "dashboard_settings.json"

DEFAULTS = {
    "theme": {
        "accent": "#6c5ce7",
        "accent2": "#00d2ff",
        "glassBlur": "6px",
        "glassOpacity": 0.88,
        "radius": "18px",
        "borderOpacity": 0.28,
        "font": "Inter",
        "bg": "aurora",
        "glow": True,
        "density": "comfortable",
        "powerAvatar": True,
    },
    "widgets": {
        "order": ["status", "platforms", "monetization", "ai", "tax", "posts", "activity"],
        "visible": {
            "status": True,
            "platforms": True,
            "monetization": True,
            "ai": True,
            "tax": True,
            "posts": True,
            "activity": True,
        },
    },
    "ai": {
        "provider": "nvidia",
        "model": "meta/muse-glimmer-30b",
        "fallbackModels": [],
        "temperature": 0.8,
        "maxTokens": 1000,
        "reasoning": "low",
    },
    "agent": {
        "enabled": False,
        "dailyPostLimit": 10,
        "autoPost": False,
        "humanApproval": True,
        "defaultNiche": "AI & Technology",
        "analysisIntervalHours": 6,
        "postingTimes": ["09:00", "12:00", "15:00", "18:00", "21:00"],
        "assignments": {},
        "focus": None,
        "voice": "en-US-JennyNeural",
        "checklist": {},
    },
    "media": {
        "enabled": True,
        "hostImagesDir": "",
    },
    "platforms": {
        "tiktok": {"enabled": True, "priority": 1},
        "youtube": {"enabled": True, "priority": 2},
        "x": {"enabled": True, "priority": 3},
        "instagram": {"enabled": True, "priority": 4},
    },
}

class SettingsStore:
    def __init__(self):
        self.path = STORE_FILE

    def _read(self) -> dict:
        if not self.path.exists():
            return deepcopy(DEFAULTS)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return deepcopy(DEFAULTS)
        return self._merge(deepcopy(DEFAULTS), data)

    @staticmethod
    def _merge(base: dict, override: dict) -> dict:
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                SettingsStore._merge(base[k], v)
            else:
                base[k] = v
        return base

    def _write(self, data: dict):
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self) -> dict:
        return self._read()

    def update(self, patch: dict) -> dict:
        data = self._read()
        self._merge(data, patch)
        self._write(data)
        return data

    def get_section(self, section: str) -> dict:
        return self._read().get(section, {})

    def set(self, dotted_path: str, value):
        data = self._read()
        parts = dotted_path.split(".")
        node = data
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = value
        self._write(data)
        return data


settings_store = SettingsStore()

def get_settings() -> dict:
    return settings_store.get()