"""Agent Controller - assignment, autonomous loop, chat with the agent.

Bridges the dashboard to the agent core:
  - assign the agent to social accounts (with or without restrictions)
  - focus mode: pour all cycles into ONE priority account
  - generate real media (quote cards + narrated Shorts) so TikTok/Shorts ship files
  - pull performance analytics every cycle and project the path to payout
  - human approval queue gates everything before it publishes
"""
import asyncio
import os
import re
import shutil
import subprocess
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config.settings_store import settings_store, get_settings
from config.settings import BASE_DIR
from core.llm import LLMProvider
from core.memory import AgentMemory
from modules.content_creator import ContentCreator
from modules.niche_analyzer import NicheAnalyzer
from modules.media_lab import render as render_media
from api.registry import PlatformRegistry

CC_PLATFORM = {"x": "twitter"}
MEDIA_SITE_DIR = BASE_DIR / "dashboard" / "site" / "media"
SITE_BASE = "https://therepublic.netlify.app/media"
FALLBACK_VIDEO = str(BASE_DIR / "dashboard" / "site" / "sample.mp4")


class AgentController:
    def __init__(self):
        self.registry = PlatformRegistry()
        self.llm = LLMProvider()
        self.memory = AgentMemory()
        self.creator = ContentCreator(llm=self.llm)
        self.analyzer = NicheAnalyzer()
        self.running = False
        self.thread = None
        self.last_cycle = None
        self.recent: List[Dict] = []
        self.chat: List[Dict] = []

    # ------------------------------------------------------------------ #
    #  assignments                                                        #
    # ------------------------------------------------------------------ #
    def enabled(self) -> bool:
        return bool((get_settings().get("agent", {}) or {}).get("enabled", False))

    async def set_enabled(self, enabled: bool) -> Dict:
        data = settings_store.update({"agent": {"enabled": bool(enabled)}})
        if bool(enabled) and not self.running:
            # start loop so cycles can run; assignments still gate work
            self.start()
        elif not bool(enabled) and self.running:
            self.stop()
        return {"enabled": bool(enabled), "running": self.running}

    def assignments(self) -> Dict:
        return (get_settings().get("agent", {}) or {}).get("assignments", {}) or {}

    async def assign(self, platform: str, **kw) -> Dict:
        cfg = get_settings()
        assignments = cfg.get("agent", {}).get("assignments", {}) or {}
        a = dict(assignments.get(platform, {}))
        for k in ("assigned", "active", "autoPost", "humanApproval",
                  "dailyPostLimit", "niche", "contentTypes", "youtubePrivacy", "media"):
            if kw.get(k, None) is not None:
                a[k] = kw[k]
        if "assigned" in kw and not kw["assigned"]:
            a["active"] = False
        a["assigned"] = bool(a.get("assigned", True))
        a.setdefault("active", False)
        a.setdefault("media", True)
        a["updated"] = datetime.now().isoformat()
        if a["assigned"]:
            a.setdefault("since", datetime.now().isoformat())
        assignments[platform] = a
        settings_store.update({"agent": {"assignments": assignments}})
        if a.get("active") and not self.running and cfg.get("agent", {}).get("enabled", False):
            self.start()
        return a

    async def unassign(self, platform: str) -> None:
        cfg = get_settings()
        assignments = cfg.get("agent", {}).get("assignments", {}) or {}
        assignments.pop(platform, None)
        settings_store.update({"agent": {"assignments": assignments}})

    # ------------------------------------------------------------------ #
    #  cycle                                                             #
    # ------------------------------------------------------------------ #
    async def run_cycle(self) -> Dict:
        cfg = get_settings()
        agent = cfg.get("agent", {})
        if not agent.get("enabled", False):
            return {"skipped": "autonomous disabled", "enabled": False, "cycle": (self.last_cycle or {}).get("cycle", 0)}
        media_cfg = cfg.get("media", {}) or {}
        default_niche = agent.get("defaultNiche", "AI & Technology")
        default_limit = agent.get("dailyPostLimit", 10)
        focus = agent.get("focus")
        voice = agent.get("voice")
        media_enabled = media_cfg.get("enabled", True) and bool(voice)
        enabled = cfg.get("platforms", {})
        assignments = self.assignments()
        memory = AgentMemory()

        cycle = {
            "cycle": (self.last_cycle or {}).get("cycle", 0) + 1,
            "start": datetime.now().isoformat(),
            "platforms": {},
            "analytics": None,
        }

        try:
            cycle["analytics"] = await self._pull_analytics()
        except Exception as e:
            cycle["analytics"] = {"error": str(e)}

        for platform, a in assignments.items():
            if not a.get("assigned") or not a.get("active"):
                continue
            if focus and platform != focus:
                cycle["platforms"][platform] = {"skipped": f"focus mode → {focus}"}
                continue
            if not enabled.get(platform, {}).get("enabled", True):
                cycle["platforms"][platform] = {"skipped": "platform disabled in settings"}
                continue
            provider = self.registry.get_provider(platform)
            if not provider or not provider.available:
                cycle["platforms"][platform] = {"error": "not connected"}
                continue

            used = await memory.post_count_today(platform)
            limit = int(a.get("dailyPostLimit") or default_limit)
            if used >= limit:
                cycle["platforms"][platform] = {"skipped": f"daily limit reached ({used}/{limit})"}
                continue

            niche = a.get("niche") or default_niche
            ctype = (a.get("contentTypes") or ["text"])[0]
            need_media = platform in ("youtube", "tiktok", "instagram")
            a.setdefault("media", True)
            tone = a.get("tone") or ("casual" if ctype == "short" else "professional")
            cc_platform = CC_PLATFORM.get(platform, platform)

            cycle["platforms"][platform] = {"niche": niche, "type": ctype}
            try:
                # Prefer user library content (Studio → Library) over fresh generation
                lib_item = None
                try:
                    from modules import content_library as _lib
                    lib_item = _lib.next_for_platform(platform)
                except Exception:
                    lib_item = None
                if lib_item and (lib_item.get("text") or "").strip():
                    content = {"text": lib_item["text"], "title": lib_item.get("title", ""),
                               "ai_generated": False, "provider": "library",
                               "library_id": lib_item.get("id")}
                    try:
                        from modules import content_library as _lib2
                        _lib2.mark_used(lib_item["id"])
                    except Exception:
                        pass
                    cycle["platforms"][platform]["library"] = lib_item.get("id")
                else:
                    content = await self.creator.generate_ai_content(niche, cc_platform, tone)
            except Exception:
                traceback.print_exc()
                cycle["platforms"][platform]["error"] = "generate failed"
                continue
            text = (content.get("text") or content.get("caption") or content.get("title") or "").strip()
            if not text:
                cycle["platforms"][platform]["error"] = "content generation produced nothing"
                continue
            template_mode = not content.get("ai_generated")

            draft = {"platform": platform, "niche": niche,
                     "type": ctype, "tone": tone,
                     "title": self._extract_title(text, niche),
                     "text": text,
                     "ai_generated": bool(content.get("ai_generated")),
                     "provider": content.get("provider", "template"),
                     "generated": datetime.now().isoformat()}
            if content.get("library_id"):
                draft["library_id"] = content["library_id"]
                # library media (user upload) wins over auto-render
                try:
                    from modules import content_library as _lib3
                    _li = _lib3.get_item(content["library_id"])
                    if _li and _li.get("media"):
                        draft["media"] = _li["media"]
                        cycle["platforms"][platform]["media"] = "library attached"
                except Exception:
                    pass
            if template_mode and not content.get("library_id"):
                draft["template_mode"] = True
                cycle["platforms"][platform]["template"] = True

            if need_media and a.get("media") and media_enabled and not draft.get("media"):
                media = await render_media(text, accent=self._accent(), voice=voice, slug=niche)
                draft["media"] = media
                if media.get("video"):
                    cycle["platforms"][platform]["media"] = "mp4 ready"
                elif media.get("error"):
                    cycle["platforms"][platform]["media_error"] = media["error"]

            auto = a.get("autoPost", agent.get("autoPost", False))
            # Never auto-publish template fallback content — always hold for approval.
            if auto and not draft.get("template_mode"):
                result = await self._publish(platform, a, draft)
                cycle["platforms"][platform]["published"] = result
            else:
                draft["status"] = "pending_approval"
                await memory.stage_draft(draft)
                await memory.log_activity("content_drafted", {"platform": platform, "niche": niche, "media": bool(draft.get("media", {}).get("video"))})
                note = "awaiting approval" + (" (+media)" if draft.get("media", {}).get("video") else "")
                if draft.get("template_mode"):
                    note += " [template — add an AI key for full generation]"
                cycle["platforms"][platform]["drafted"] = note

        cycle["end"] = datetime.now().isoformat()
        self.memory = memory
        self.last_cycle = cycle
        self.recent.append({
            "ts": datetime.now().isoformat(),
            "cycle": cycle["cycle"],
            "platforms": list(cycle["platforms"].keys()),
            "summary": ", ".join(
                f"{p}: {list(v.keys())[0]}" for p, v in cycle["platforms"].items()) or "nothing assigned",
        })
        self.recent = self.recent[-50:]
        return cycle

    async def _publish(self, platform: str, a: Dict, draft: Dict) -> Dict:
        text = draft.get("text", "")
        media = draft.get("media") or {}
        video = media.get("video") if isinstance(media, dict) else None
        image = media.get("image") if isinstance(media, dict) else None
        try:
            if platform == "youtube":
                file_path = video or FALLBACK_VIDEO
                result = await self.registry.post_content("youtube", {
                    "title": draft.get("title", "TheRepublic post"),
                    "description": (text or "")[:5000],
                    "file_path": file_path,
                    "privacy_status": a.get("youtubePrivacy", "unlisted"),
                })
            elif platform == "tiktok":
                if not video:
                    return {"error": "no video file for TikTok", "media": media if isinstance(media, dict) else None}
                provider = self.registry.get_provider("tiktok")
                result = await provider.post_video_file(
                    file_path=video,
                    caption=(draft.get("title") or "TheRepublic")[:2200],
                    privacy_level="SELF_ONLY",
                )
            elif platform == "x":
                post_result = await self.registry.post_content("x", {"text": text})
                result = {"posted": post_result}
            elif platform == "instagram":
                if not image:
                    return {"error": "media upload requires an image (generated cards available)"}
                ig_user_id = os.getenv("IG_USER_ID", "")
                if not ig_user_id:
                    return {"error": "IG_USER_ID not set — add your numeric Instagram Business ID in Accounts → instagram → token, or .env (see .env.example)"}
                url = await self._host_image(image)
                if not url:
                    return {"error": "could not host image for Instagram"}
                provider = self.registry.get_provider("instagram")
                result = await provider.post_instagram_image(
                    ig_user_id=ig_user_id,
                    image_url=url,
                    caption=(draft.get("title") or text or "")[:2200],
                )
            else:
                return {"error": f"no publisher for {platform}"}
            await self.memory.schedule_post(draft, status="published")
            await self.memory.log_activity("post_published", {"platform": platform, **result})
            return result
        except Exception as e:
            try:
                from modules import notifications as _nt
                from modules import retry_queue as _rq
                _nt.notify("publish_fail", f"Publish failed: {platform}",
                           f"{e}\nDraft: {(draft.get('title') or draft.get('text',''))[:200]}", level="error")
                _rq.push(platform, draft, str(e))
            except Exception:
                pass
            return {"error": str(e)}

    async def _host_image(self, image_path: str) -> Optional[str]:
        """Copy a generated card into the Netlify site folder and deploy so IG can fetch it."""
        site = MEDIA_SITE_DIR
        site.mkdir(parents=True, exist_ok=True)
        name = Path(image_path).name
        dst = site / name
        try:
            shutil.copyfile(image_path, dst)
        except Exception:
            return None
        try:
            r = subprocess.run(
                ["netlify", "deploy", "--dir", str(BASE_DIR / "dashboard" / "site"), "--prod"],
                capture_output=True, text=True, timeout=300, cwd=str(BASE_DIR),
            )
            if r.returncode != 0:
                print("[Agent] netlify deploy failed:", (r.stderr or "")[-300:])
                return None
        except Exception as e:
            print("[Agent] netlify deploy error:", e)
            return None
        return f"{SITE_BASE}/{name}"

    # ------------------------------------------------------------------ #
    #  analytics + payout projections                                     #
    # ------------------------------------------------------------------ #
    async def _pull_analytics(self) -> Dict:
        """Pull real stats for connected platforms and persist a snapshot."""
        crawler = {"date": datetime.now().strftime("%Y-%m-%d"), "time": datetime.now().isoformat()}
        youtube = self.registry.get_provider("youtube")
        if youtube and youtube.available and youtube._oauth_service_available():
            try:
                _ = youtube._get_auth_service()
                playlists = youtube._service.playlists().list(part="contentDetails", mine=True).execute()
                uploads = next((p["contentDetails"]["relatedPlaylists"]["uploads"] for p in playlists.get("items", []) if "contentDetails" in p), None)
                items = []
                if uploads:
                    pl = youtube._service.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=10).execute()
                    items = [i["contentDetails"]["videoId"] for i in pl.get("items", [])]
                stats = await youtube.get_channel_stats()
                crawler["youtube"] = {"subs": stats.get("subscribers", 0), "views": stats.get("total_views", 0), "videos": stats.get("videos", 0)}
                if items:
                    video_ids = ",".join(items)
                    vids = youtube._service.videos().list(part="statistics", id=video_ids).execute()
                    recent = [{"id": v["id"], "views": int(v["statistics"].get("viewCount", 0)),
                               "likes": int(v["statistics"].get("likeCount", 0))} for v in vids.get("items", [])]
                    crawler["youtube"]["recent_views"] = sum(v["views"] for v in recent)
                    crawler["youtube"]["last_video_views"] = recent[0]["views"] if recent else 0
                    crawler["youtube"]["last_video_likes"] = recent[0]["likes"] if recent else 0
            except Exception as e:
                crawler["youtube_error"] = str(e)

        memory = AgentMemory()
        await memory.log_activity("analytics_pull", crawler)
        return crawler

    async def projection(self) -> Dict:
        """Path-to-payout: current metrics + weekly delta + days to each target."""
        memory = AgentMemory()
        await memory.initialize()
        pulls = [e.get("data", {}) for e in memory.activity_log if e.get("type") == "analytics_pull"]
        pulls = [p for p in pulls if p.get("youtube")]
        days = [p["date"] for p in pulls]
        fresh = max(days) if days else None
        cur = pulls[-1]["youtube"] if pulls else {}
        prev = pulls[0]["youtube"] if len(pulls) > 2 else {}
        subs_now = cur.get("subs", 0)
        views_now = cur.get("views", 0)
        subs_prev = prev.get("subs", subs_now)
        weekly_delta = (subs_now - subs_prev) / max(1, len(pulls)) * 7.0
        out = {
            "updated": fresh,
            "platforms": {
                "youtube": {
                    "subs": subs_now,
                    "views": views_now,
                    "subs_this_week": round(weekly_delta, 1),
                    "target_subs": 1000,
                    "days_to_1000_subs": int(round((1000 - subs_now) / weekly_delta)) if weekly_delta > 0 else None,
                    "last_video_views": cur.get("last_video_views", 0),
                    "pulls": len(pulls),
                }
            },
        }
        return out

    # ------------------------------------------------------------------ #
    #  ask the agent                                                      #
    # ------------------------------------------------------------------ #
    async def ask(self, message: str) -> Dict:
        msg = (message or "").strip()
        if not self.llm.available:
            return {"type": "error", "text": "No AI provider configured."}
        low = msg.lower()
        analysis = None

        if any(k in low for k in ("niche", "research", "trend", "market", "find me", "what to post")):
            analysis = await self.analyzer.get_full_analysis()
            top = (analysis or {}).get("top_niche", "unknown")
            answer = (
                f"Niche analysis complete. Top niche right now: **{top}**. "
                f"{len(analysis.get('recommendations', []))} recommendations found. "
                "Open the Overview -> Analyze to apply it, or assign it to an account."
            )
            self.chat.append({"role": "user", "text": msg})
            self.chat.append({"role": "agent", "text": answer, "kind": "analysis"})
            return {"type": "niche_analysis", "text": answer, "analysis": analysis}

        await self.memory.initialize()
        acts = getattr(self.memory, "activity_log", [])[-5:]
        context = {
            "accounts": [
                {"name": p.name, "connected": p.available}
                for p in self.registry.providers.values()
            ],
            "assignments": self.assignments(),
            "recent_activity": acts,
            "projection": await self.projection(),
        }
        import json as _json
        system = (
            "You are TheRepublic, the user's autonomous content agent. "
            "Respond helpfully, plainly, and short. You can analyze niches, generate "
            "content (and media), and post to connected accounts within the user's "
            "restrictions. "
            f"Current state: {_json.dumps(context, default=str)[:1800]}"
        )
        answer = await self.llm.complete(system_prompt=system, user_prompt=msg, max_tokens=400)
        self.chat.append({"role": "user", "text": msg})
        self.chat.append({"role": "agent", "text": answer, "kind": "chat"})
        return {"type": "answer", "text": answer}

    # ------------------------------------------------------------------ #
    #  persistent loop                                                    #
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        if self.running:
            return
        if not self.enabled():
            return
        self.running = True
        self.thread = threading.Thread(target=self._thread_target, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False

    def _thread_target(self) -> None:
        while self.running:
            # respect enabled toggle - pause without burning cycles
            if not self.enabled():
                # stay alive but idle until re-enabled
                time.sleep(5)
                continue
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.run_cycle())
                loop.close()
            except Exception:
                self.recent.append({"ts": datetime.now().isoformat(), "cycle": None,
                                    "platforms": [], "summary": "cycle crashed",
                                    "error": traceback.format_exc()[-600:]})
                self.recent = self.recent[-50:]
                try:
                    from modules import notifications as _nt2
                    _nt2.notify("crash", "Agent cycle crashed",
                                traceback.format_exc()[-800:], level="error")
                except Exception:
                    pass
            hours = (get_settings().get("agent", {}) or {}).get("analysisIntervalHours", 6)
            deadline = time.time() + hours * 3600
            while self.running and time.time() < deadline:
                if not self.enabled():
                    break
                time.sleep(5)

    def status(self) -> Dict:
        return {
            "enabled": self.enabled(),
            "running": self.running,
            "last_cycle": self.last_cycle,
            "recent": self.recent,
            "chat_len": len(self.chat),
        }

    # ------------------------------------------------------------------ #
    #  helpers                                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _accent() -> str:
        try:
            return (get_settings().get("theme", {}) or {}).get("accent", "#6c5ce7")
        except Exception:
            return "#6c5ce7"

    @staticmethod
    def _extract_title(text: str, fallback: str) -> str:
        import re as _re
        if not text:
            return fallback[:100]
        m = _re.search(r"\*\*TITLE:\*\*\s*\n?\s*(.+)", text)
        if m:
            return m.group(1).strip(" *#*").strip("**").strip()[:100]
        first = text.splitlines()[0]
        first = _re.sub(r"^#+\s*", "", first).strip(" *")
        return (first[:100] if first and len(first) > 3 else fallback[:100])