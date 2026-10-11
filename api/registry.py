"""Platform registry - prioritizes platforms that pay creators."""
from typing import Dict, List
from api.providers import YouTubeProvider, TikTokProvider, XProvider, MetaProvider


class PlatformRegistry:
    """Central registry of all connected platforms, prioritized by payout."""

    def __init__(self):
        self.providers = {
            "youtube": YouTubeProvider(),
            "tiktok": TikTokProvider(),
            "x": XProvider(),
            "instagram": MetaProvider(),
        }
        # Priority order: platforms that pay creators first, best payout first.
        self.priority_order = ["tiktok", "youtube", "x", "instagram"]

    def get_provider(self, platform: str):
        return self.providers.get(platform)

    def connected(self) -> List[str]:
        return [p for p in self.priority_order if self.providers[p].available]

    def not_connected(self) -> List[str]:
        return [p for p in self.priority_order if not self.providers[p].available]

    async def check_all(self) -> List[Dict]:
        results = []
        for name in self.priority_order:
            provider = self.providers[name]
            status = {
                "platform": name,
                "pays_creators": provider.pays_creators,
                "payout_method": provider.payout_method,
                "connected": provider.available,
            }
            if provider.available:
                try:
                    check = await provider.check_connection()
                    if name == "x":
                        check = await provider.check_connection()
                    status["connection_check"] = check
                except Exception as e:
                    status["connection_check"] = {"connected": False, "error": str(e)}
            results.append(status)
        return results

    async def get_monetization_status(self) -> List[Dict]:
        """Get monetization eligibility across all connected platforms."""
        results = []
        for name in self.priority_order:
            provider = self.providers[name]
            if not provider.available:
                results.append({"platform": name, "connected": False})
                continue
            try:
                if name == "tiktok":
                    status = await provider.get_creator_reward_status()
                elif name == "youtube":
                    status = await provider.get_monetization_status()
                elif name == "x":
                    status = await provider.get_creator_metrics()
                elif name == "instagram":
                    ig = await provider.get_instagram_user()
                    if "error" in ig:
                        status = ig
                    else:
                        status = await provider.get_instagram_monetization_status(ig["followers"])
                results.append(status)
            except Exception as e:
                results.append({"platform": name, "error": str(e)})
        return results

    async def post_content(self, platform: str, content: Dict) -> Dict:
        """Post content to a specific platform."""
        provider = self.providers.get(platform)
        if not provider:
            return {"error": f"Unknown platform: {platform}"}
        if not provider.available:
            return {"error": f"Platform {platform} not connected"}

        if platform == "youtube":
            return await provider.upload_video(
                title=content.get("title", "Untitled"),
                description=content.get("description", ""),
                file_path=content.get("file_path"),
                privacy_status=content.get("privacy_status", "public"),
            )
        if platform == "tiktok":
            return await provider.post_video(
                video_url=content.get("video_url"),
                caption=content.get("caption", ""),
            )
        if platform == "x":
            tweets = content.get("thread", [content.get("text", "")])
            return await provider.post_thread(tweets)
        if platform == "instagram":
            return await provider.post_instagram_image(
                ig_user_id=content.get("ig_user_id"),
                image_url=content.get("image_url"),
                caption=content.get("caption", ""),
            )
        return {"error": f"No post handler for {platform}"}

    def describe(self) -> List[str]:
        """Human-readable summary of platform payout priorities."""
        lines = []
        for name in self.priority_order:
            p = self.providers[name]
            lines.append(f"- {name}: pays={p.pays_creators}, payout={p.payout_method}, connected={p.available}")
        return lines