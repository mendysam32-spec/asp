"""Real Meta Graph API provider for Instagram and Facebook.

Instagram monetization (2026): fan tips from 500 followers, affiliate/tagging
from 1,000 followers, in-stream ads / subscriptions from 10,000 followers.
Facebook: in-stream ads from 10,000 followers, fifty back to bank/Stripe.

Credentials (set in .env):
- META_USER_ACCESS_TOKEN   (with instagram_basic, instagram_content_publish,
                            pages_show_list, pages_read_engagement, page_manage_posts)
- META_APP_ID, META_APP_SECRET (optional, for token refresh / Page auth)

Setup: https://developers.facebook.com/
"""
import os
import requests
from typing import Dict, List, Optional
from datetime import datetime

GRAPH_BASE = "https://graph.facebook.com/v21.0"


class MetaProvider:
    name = "meta"
    pays_creators = True
    payout_method = "Bank/Stripe, $5 US min, twice monthly"


    def __init__(self):
        self.access_token = os.getenv("META_USER_ACCESS_TOKEN")
        self.app_id = os.getenv("META_APP_ID")
        self.app_secret = os.getenv("META_APP_SECRET")

    @property
    def available(self) -> bool:
        return bool(self.access_token)

    def _headers(self) -> Dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def check_connection(self) -> Dict:
        try:
            resp = requests.get(
                f"{GRAPH_BASE}/me",
                params={"fields": "id,name,instagram_business_account{,id,name,followers_count}",
                        "access_token": self.access_token},
            )
            if resp.status_code != 200:
                return {"connected": False, "error": resp.json().get("error", {}).get("message")}
            data = resp.json()
            return {"connected": True, **data}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    async def get_instagram_user(self) -> Dict:
        """Get linked Instagram business account + follower count."""
        me = await self.check_connection()
        if not me.get("connected"):
            return me
        ig = me.get("instagram_business_account")
        if not ig:
            return {"error": "No Instagram business account linked to this token"}
        return {
            "platform": "instagram",
            "ig_id": ig.get("id"),
            "name": ig.get("name"),
            "followers": ig.get("followers_count", 0),
        }

    async def post_instagram_image(
        self, ig_user_id: str, image_url: str, caption: str
    ) -> Dict:
        """Publish a single image to Instagram (Graph API)."""
        # Step 1: Create a media container
        container_resp = requests.post(
            f"{GRAPH_BASE}/{ig_user_id}/media",
            params={
                "image_url": image_url,
                "caption": caption,
                "access_token": self.access_token,
            },
        )
        if container_resp.status_code != 200:
            return {"error": container_resp.json().get("error", {}).get("message")}
        container_id = container_resp.json().get("id")

        # Step 2: Publish it
        publish_resp = requests.post(
            f"{GRAPH_BASE}/{ig_user_id}/media_publish",
            params={"creation_id": container_id, "access_token": self.access_token},
        )
        if publish_resp.status_code != 200:
            return {"error": publish_resp.json().get("error", {}).get("message")}
        return {
            "platform": "instagram",
            "media_id": publish_resp.json().get("id"),
            "posted_at": datetime.now().isoformat(),
        }

    async def get_instagram_insights(self, ig_user_id: str, period: str = "day") -> Dict:
        """Get account insights (reach, impressions, profile views)."""
        fields = "follower_count,media_count"
        resp = requests.get(
            f"{GRAPH_BASE}/{ig_user_id}",
            params={
                "fields": f"name,{fields},media.limit(5){{comments_count,like_count}}",
                "access_token": self.access_token,
            },
        )
        if resp.status_code != 200:
            return {"error": resp.json().get("error", {}).get("message")}
        data = resp.json()
        return {
            "platform": "instagram",
            "name": data.get("name"),
            "followers": data.get("follower_count", 0),
            "media_count": data.get("media_count", 0),
        }

    async def get_facebook_pages(self) -> List[Dict]:
        """List Facebook pages the user manages."""
        resp = requests.get(
            f"{GRAPH_BASE}/me/accounts",
            params={"access_token": self.access_token},
        )
        if resp.status_code != 200:
            return [{"error": resp.json().get("error", {}).get("message")}]
        pages = resp.json().get("data", [])
        return [
            {"id": p["id"], "name": p["name"]}
            for p in pages
        ]

    async def post_facebook(self, page_id: str, message: str, link: str = None) -> Dict:
        """Post to a Facebook Page."""
        params = {"message": message, "access_token": self.access_token}
        if link:
            params["link"] = link
        resp = requests.post(f"{GRAPH_BASE}/{page_id}/feed", params=params)
        if resp.status_code != 200:
            return {"error": resp.json().get("error", {}).get("message")}
        return {"platform": "facebook", "post_id": resp.json().get("id")}

    async def get_instagram_monetization_status(self, followers: int) -> Dict:
        """Return Instagram monetization eligibility based on current followers."""
        tiers = {
            "fan_tips": {"followers": 500, "feature": "Fan gifts/tips on Reels"},
            "affiliate": {"followers": 1000, "feature": "Tag products / Affiliate"},
            "subscriptions": {"followers": 10000, "feature": "Exclusive content + subscription badge"},
            "in_stream_ads": {"followers": 10000, "feature": "In-stream ads / Reels ads"},
        }
        result = {"platform": "instagram", "followers": followers, "tiers": {}}
        for tier, info in tiers.items():
            result["tiers"][tier] = {
                "requires": info["followers"],
                "feature": info["feature"],
                "unlocked": followers >= info["followers"],
                "gap": max(0, info["followers"] - followers),
            }
        return result