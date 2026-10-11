"""Real X (Twitter) API v2 integration.

X pays creators via Creator Ad Revenue Sharing (~$30 min, biweekly via Stripe).
Requirements (2026): X Premium subscription, verified, 500+ followers,
~5M impressions/3mo from verified users.

Credentials (set in .env):
- TWITTER_API_KEY, TWITTER_API_SECRET       (OAuth 1.0a consumer keys)
- TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET (user tokens with read+write)

Get keys: https://developer.x.com/ (Free/Pro tier, v2 API access)
"""
import os
from typing import Dict, List, Optional
from datetime import datetime


class XProvider:
    name = "x"
    pays_creators = True
    payout_method = "Stripe, $30 min, biweekly"


    def __init__(self):
        self.api_key = os.getenv("TWITTER_API_KEY")
        self.api_secret = os.getenv("TWITTER_API_SECRET")
        self.access_token = os.getenv("TWITTER_ACCESS_TOKEN")
        self.access_secret = os.getenv("TWITTER_ACCESS_SECRET")

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.api_secret and self.access_token and self.access_secret)

    def _client(self):
        if not self.available:
            raise RuntimeError(
                "X credentials not configured. Set TWITTER_API_KEY/SECRET and ACCESS_TOKEN/SECRET in .env"
            )
        import tweepy
        client = tweepy.Client(
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            access_token=self.access_token,
            access_token_secret=self.access_secret,
        )
        return client

    async def check_connection(self) -> Dict:
        try:
            client = self._client()
            me = client.get_me(user_auth=True)
            if me and me.data:
                return {"connected": True, "username": me.data.username, "id": me.data.id}
            return {"connected": False, "error": "No user data returned"}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    async def post_tweet(self, text: str, reply_to: str = None) -> Dict:
        """Post a tweet (or reply)."""
        client = self._client()
        if len(text) > 280:
            raise ValueError(f"Tweet too long: {len(text)} chars (max 280)")
        kwargs = {"text": text}
        if reply_to:
            kwargs["in_reply_to_tweet_id"] = reply_to
        resp = client.create_tweet(**kwargs)
        return {
            "platform": "x",
            "tweet_id": resp.data["id"],
            "text": text,
            "posted_at": datetime.now().isoformat(),
        }

    async def post_thread(self, tweets: List[str]) -> List[Dict]:
        """Post a thread by replying to each previous tweet."""
        results = []
        prev_id = None
        for i, text in enumerate(tweets):
            if i == 0:
                result = await self.post_tweet(text)
            else:
                result = await self.post_tweet(text, reply_to=prev_id)
            prev_id = result.get("tweet_id")
            results.append(result)
        return results

    async def get_user(self, username: str = None) -> Dict:
        """Get user info. If no username, gets authenticated user."""
        client = self._client()
        if username:
            user = client.get_user(username=username, user_auth=True)
        else:
            user = client.get_me(user_auth=True)
        if not user.data:
            return {"error": "User not found"}
        return {
            "platform": "x",
            "id": user.data.id,
            "username": user.data.username,
            "name": user.data.name,
            "followers_count": None,  # requires user.follows scope
            "verified": getattr(user.data, "verified", None),
        }

    async def get_creator_metrics(self) -> Dict:
        """Get account metrics to track monetization eligibility.

        X ad revenue share needs: X Premium, verified, 500+ followers,
        ~5M impressions/3mo from verified users. Public API cannot read
        impressions; we surface what we can and note the rest.
        """
        client = self._client()
        me_resp = client.get_me(
            user_auth=True,
            user_fields=["public_metrics", "created_at", "verified"],
        )
        if not me_resp.data:
            return {"error": "Not authorized"}
        me = me_resp.data
        metrics = getattr(me, "public_metrics", {})
        return {
            "platform": "x",
            "username": me.username,
            "followers": metrics.get("followers_count", 0),
            "following": metrics.get("following_count", 0),
            "tweet_count": metrics.get("tweet_count", 0),
            "verified": getattr(me, "verified", False),
            "created_at": str(getattr(me, "created_at", "")),
            "monetization_requirements": {
                "x_premium_subscription": True,  # you pay ~$8/mo before X pays you
                "verified_account": True,
                "followers_min": 500,
                "impressions_3mo": "~5M (from verified users) - not readable via public API",
            },
            "note": "Public API cannot read impression counts. Check the X app dashboard for exact numbers.",
        }