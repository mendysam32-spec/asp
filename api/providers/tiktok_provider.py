"""Real TikTok integration - Content Posting API (2026) + Creator Rewards.

TikTok pays creators via PayPal (through Hyperwallet), $50 min payout on 15th.
This is the #1 priority for a PayPal-linked creator.

IMPORTANT (2026):
- Unaudited apps can ONLY post to private/self-only view until TikTok
  audits the API client. Plan for it: post privately first, or submit
  the app for audit ASAP (demo video + privacy policy required).
- API flow: creator_info/query -> video/init -> video/upload -> status/fetch.
- Tokens: access ~24h, refresh ~365 days. We auto-refresh and persist.

Credentials (set in .env via `python setup_credentials.py tiktok`):
- TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET   (Developer Portal)
- TIKTOK_ACCESS_TOKEN, TIKTOK_REFRESH_TOKEN  (OAuth user tokens)

Setup: https://developers.tiktok.com/
"""
import os
import time
from typing import Dict, List, Optional
from datetime import datetime

import requests

from config.settings import BASE_DIR

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


class TikTokProvider:
    name = "tiktok"
    pays_creators = True
    payout_method = "PayPal (via Hyperwallet), $50 min, 15th of month"

    def __init__(self):
        self.client_key = os.getenv("TIKTOK_CLIENT_KEY")
        self.client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
        self.access_token = os.getenv("TIKTOK_ACCESS_TOKEN")
        self.refresh_token = os.getenv("TIKTOK_REFRESH_TOKEN")

    @property
    def available(self) -> bool:
        return bool(self.client_key and self.client_secret and self.access_token)

    def _headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def _save_env(self, key: str, value: str):
        """Persist updated tokens to .env so the agent stays logged in."""
        env_path = BASE_DIR / ".env"
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
        out, found = [], False
        for line in lines:
            if line.startswith(f"{key}="):
                out.append(f"{key}={value}")
                found = True
            else:
                out.append(line)
        if not found:
            out.append(f"{key}={value}")
        env_path.write_text("\n".join(out), encoding="utf-8")

    async def refresh_access_token(self) -> bool:
        """Refresh the OAuth access token (tokens live ~24h / refresh ~365d)."""
        if not self.refresh_token:
            return False
        resp = requests.post(
            f"{TIKTOK_API_BASE}/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": self.client_key,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            new_access = data.get("access_token")
            new_refresh = data.get("refresh_token")
            if new_access:
                self.access_token = new_access
                self._save_env("TIKTOK_ACCESS_TOKEN", new_access)
            if new_refresh:
                self.refresh_token = new_refresh
                self._save_env("TIKTOK_REFRESH_TOKEN", new_refresh)
            return True
        return False

    def _api(self, path: str, method: str = "GET", params: Dict = None, json_body: Dict = None):
        url = f"{TIKTOK_API_BASE}/{path}"
        resp = requests.request(method, url, headers=self._headers(), params=params, json=json_body)
        if resp.status_code == 401 and method in ("GET", "POST"):
            if self.refresh_access_token():
                resp = requests.request(method, url, headers=self._headers(), params=params, json=json_body)
        if resp.status_code != 200:
            err = resp.json().get("error", {})
            return {"error": err.get("message", f"HTTP {resp.status_code}")}
        return resp.json()

    async def check_connection(self) -> Dict:
        """Verify the app is authorized for user.info.basic."""
        result = await self.get_user_info()
        if "error" in result:
            return {"connected": False, "error": result["error"]}
        return {"connected": True, "open_id": result.get("open_id"), "display_name": result.get("display_name")}

    async def get_user_info(self) -> Dict:
        """Get authenticated user's profile + follower count."""
        data = self._api(
            "user/info/",
            params={"fields": "open_id,avatar_url,display_name,follower_count,following_count"},
        )
        if "error" in data:
            return data
        user = data.get("data", {}).get("user", {})
        return {
            "platform": "tiktok",
            "open_id": user.get("open_id"),
            "display_name": user.get("display_name"),
            "avatar_url": user.get("avatar_url"),
            "followers": int(user.get("follower_count", 0)),
            "following": int(user.get("following_count", 0)),
        }

    async def query_creator_info(self) -> Dict:
        """Get the creator's posting options (privacy levels, interaction toggles).

        REQUIRED before posting: the init call must use one of the returned
        privacy_level_options.
        """
        data = self._api("post/publish/creator_info/query/", method="POST", json_body={})
        if "error" in data:
            return data
        info = data.get("data", {}).get("creator_info", {})
        return {
            "privacy_level_options": info.get("privacy_level_options", []),
            "comment_disabled": info.get("comment_disabled"),
            "duet_disabled": info.get("duet_disabled"),
            "stitch_disabled": info.get("stitch_disabled"),
            "max_video_post_duration_sec": info.get("max_video_post_duration_sec"),
        }

    async def post_video(
        self,
        video_url: str,
        caption: str = "",
        privacy_level: str = "SELF_ONLY",
        disable_duet: bool = False,
        disable_comment: bool = False,
        disable_stitch: bool = False,
    ) -> Dict:
        """Post a video.

        Uses PULL_FROM_URL (TikTok pulls the video file from `video_url`).
        NOTE: unaudited apps are restricted to SELF_ONLY privacy until audit.

        For local files prefer `post_video_file()` (FILE_UPLOAD, no URL verification).
        """
        init = self._api(
            "post/publish/video/init/",
            method="POST",
            json_body={
                "post_info": {
                    "title": caption[:2200],
                    "privacy_level": privacy_level,
                    "disable_duet": disable_duet,
                    "disable_comment": disable_comment,
                    "disable_stitch": disable_stitch,
                },
                "source_info": {
                    "source": "PULL_FROM_URL",
                    "video_url": video_url,
                },
            },
        )
        if "error" in init:
            return init
        publish_id = init.get("data", {}).get("publish_id")
        return {
            "platform": "tiktok",
            "publish_id": publish_id,
            "method": "PULL_FROM_URL",
            "note": "Poll status with get_post_status()",
        }

    async def post_video_file(
        self,
        file_path: str,
        caption: str = "",
        privacy_level: str = "SELF_ONLY",
        disable_duet: bool = False,
        disable_comment: bool = False,
        disable_stitch: bool = False,
    ) -> Dict:
        """Post a local video file via FILE_UPLOAD (no URL ownership needed).

        Flow: init -> get upload_url -> upload file -> poll status.
        """
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}
        file_size = os.path.getsize(file_path)

        init = self._api(
            "post/publish/video/init/",
            method="POST",
            json_body={
                "post_info": {
                    "title": caption[:2200],
                    "privacy_level": privacy_level,
                    "disable_duet": disable_duet,
                    "disable_comment": disable_comment,
                    "disable_stitch": disable_stitch,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": file_size,
                    "total_chunk_count": 1,
                },
            },
        )
        if "error" in init:
            return init

        data = init.get("data", {})
        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")
        if not upload_url:
            return {"error": "No upload_url returned", "data": data}

        # Upload the file (single chunk for simplicity)
        with open(file_path, "rb") as f:
            chunk = f.read()
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "video/mp4",
            "Content-Length": str(len(chunk)),
            "Content-Range": f"bytes 0-{len(chunk) - 1}/{file_size}",
        }
        up_resp = requests.put(upload_url, data=chunk, headers=headers)
        if up_resp.status_code not in (200, 201, 206):
            return {"error": f"Upload failed: HTTP {up_resp.status_code}", "detail": up_resp.text[:200]}

        return {
            "platform": "tiktok",
            "publish_id": publish_id,
            "method": "FILE_UPLOAD",
            "upload_status": up_resp.status_code,
            "note": "Poll status with get_post_status()",
        }

    async def get_post_status(self, publish_id: str) -> Dict:
        """Poll the status of a post."""
        return self._api(
            "post/publish/status/fetch/",
            method="POST",
            json_body={"publish_id": publish_id},
        )

    async def get_creator_reward_status(self) -> Dict:
        """Progress toward TikTok Creator Rewards (10k followers, 100k likes/28d).

        Payout: PayPal/Hyperwallet, $50 min, processed on the 15th monthly.
        """
        user = await self.get_user_info()
        if "error" in user:
            return user

        req_followers = 10000
        req_likes = 100000
        followers = user["followers"]

        tier = "LIVE gifts / subscriptions" if followers >= 1000 else "building audience"
        return {
            "platform": "tiktok",
            "program": "Creator Rewards Program",
            "payout": "PayPal/Hyperwallet, $50 min, 15th monthly",
            "followers": followers,
            "current_tier": tier,
            "likes_28d": "N/A (needs analytics permission)",
            "requirements": {
                "followers": req_followers,
                "likes_in_28_days": req_likes,
                "posts_in_28_days": 3,
                "videos_1min_plus": True,
            },
            "progress": {
                "followers": min(100, round(followers / req_followers * 100)),
            },
            "eligible_creator_rewards": followers >= req_followers,
        }