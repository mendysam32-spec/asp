"""DEPRECATED mock - kept for backwards-compat with test_agent.py only.
Use api.registry.PlatformRegistry (real providers) for all production paths."""
from typing import Dict, List, Optional
from datetime import datetime


class SocialMediaManager:
    def __init__(self):
        self.platforms = {}
        self.connected_accounts = []

    async def connect_twitter(self, api_key: str, api_secret: str, access_token: str, access_secret: str) -> bool:
        """Connect Twitter account"""
        self.platforms["twitter"] = {
            "api_key": api_key,
            "api_secret": api_secret,
            "access_token": access_token,
            "access_secret": access_secret,
            "connected": True
        }
        self.connected_accounts.append("twitter")
        return True

    async def connect_instagram(self, access_token: str) -> bool:
        """Connect Instagram account"""
        self.platforms["instagram"] = {
            "access_token": access_token,
            "connected": True
        }
        self.connected_accounts.append("instagram")
        return True

    async def connect_youtube(self, api_key: str) -> bool:
        """Connect YouTube account"""
        self.platforms["youtube"] = {
            "api_key": api_key,
            "connected": True
        }
        self.connected_accounts.append("youtube")
        return True

    async def connect_tiktok(self, access_token: str) -> bool:
        """Connect TikTok account"""
        self.platforms["tiktok"] = {
            "access_token": access_token,
            "connected": True
        }
        self.connected_accounts.append("tiktok")
        return True

    async def post_tweet(self, text: str, media_urls: List[str] = None) -> Dict:
        """Post a tweet"""
        if "twitter" not in self.platforms:
            return {"error": "Twitter not connected"}
        
        # In production, use tweepy or similar library
        return {
            "platform": "twitter",
            "status": "posted",
            "text": text,
            "media": media_urls,
            "posted_at": datetime.now().isoformat()
        }

    async def post_instagram(self, caption: str, image_url: str, media_type: str = "image") -> Dict:
        """Post to Instagram"""
        if "instagram" not in self.platforms:
            return {"error": "Instagram not connected"}
        
        return {
            "platform": "instagram",
            "status": "posted",
            "caption": caption,
            "media_url": image_url,
            "media_type": media_type,
            "posted_at": datetime.now().isoformat()
        }

    async def post_youtube_video(self, title: str, description: str, video_url: str) -> Dict:
        """Upload video to YouTube"""
        if "youtube" not in self.platforms:
            return {"error": "YouTube not connected"}
        
        return {
            "platform": "youtube",
            "status": "uploaded",
            "title": title,
            "description": description,
            "video_url": video_url,
            "uploaded_at": datetime.now().isoformat()
        }

    async def post_tiktok(self, caption: str, video_url: str) -> Dict:
        """Post to TikTok"""
        if "tiktok" not in self.platforms:
            return {"error": "TikTok not connected"}
        
        return {
            "platform": "tiktok",
            "status": "posted",
            "caption": caption,
            "video_url": video_url,
            "posted_at": datetime.now().isoformat()
        }

    async def get_analytics(self, platform: str, days: int = 30) -> Dict:
        """Get analytics from platform"""
        # Simulated analytics data
        return {
            "platform": platform,
            "period": f"last_{days}_days",
            "followers": 1250,
            "engagement_rate": 0.045,
            "impressions": 45000,
            "reach": 32000,
            "top_content": [],
            "growth_rate": "+12%"
        }

    async def schedule_post(self, platform: str, content: Dict, post_time: datetime) -> Dict:
        """Schedule a post for later"""
        return {
            "platform": platform,
            "content": content,
            "scheduled_time": post_time.isoformat(),
            "status": "scheduled",
            "created_at": datetime.now().isoformat()
        }

    def get_connected_platforms(self) -> List[str]:
        """Get list of connected platforms"""
        return self.connected_accounts
