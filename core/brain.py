from typing import Dict, List
import json
from datetime import datetime
from .llm import LLMProvider


class AgentBrain:
    def __init__(self):
        self.niche_cache = {}
        self.llm = LLMProvider()
        self.content_templates = self._load_templates()

    def _load_templates(self) -> Dict:
        return {
            "twitter": {
                "text": "Thread style, engaging hooks, hashtags",
                "max_length": 280
            },
            "instagram": {
                "text": "Visual captions, stories, reels ideas",
                "max_length": 2200
            },
            "youtube": {
                "text": "Video scripts, titles, descriptions",
                "max_length": 5000
            }
        }

    async def analyze_trends(self) -> Dict:
        """Analyze current trending niches across platforms"""
        # This would integrate with real APIs
        # For now, return simulated analysis
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "niches": [
                {
                    "name": "AI & Technology",
                    "score": 95,
                    "growth": "+45%",
                    "monetization_potential": "high",
                    "competition": "medium"
                },
                {
                    "name": "Personal Finance",
                    "score": 88,
                    "growth": "+32%",
                    "monetization_potential": "high",
                    "competition": "high"
                },
                {
                    "name": "Health & Wellness",
                    "score": 82,
                    "growth": "+28%",
                    "monetization_potential": "medium",
                    "competition": "high"
                },
                {
                    "name": "Remote Work",
                    "score": 79,
                    "growth": "+55%",
                    "monetization_potential": "medium",
                    "competition": "medium"
                }
            ],
            "top_niche": "AI & Technology",
            "recommendation": "Focus on AI tutorials and tools - high demand, good monetization"
        }
        self.niche_cache = analysis
        return analysis

    async def generate_content(self, niche: str, platform: str) -> Dict:
        """Generate content based on niche and platform"""
        template = self.content_templates.get(platform, {})

        content = {
            "platform": platform,
            "niche": niche,
            "generated_at": datetime.now().isoformat(),
            "text": f"[AI Generated] Exploring {niche} - here's what you need to know...",
            "hashtags": [f"#{niche.replace(' ', '')}", "#trending", "#learning"],
            "cta": "Follow for more insights!",
            "scheduled": False,
            "ai_generated": False,
            "provider": "fallback",
            "model": "template"
        }

        if self.llm.available:
            platform_instructions = {
                "twitter": (
                    f"Write an engaging, original Twitter thread about {niche}. "
                    "Start with a scroll-stopping hook, give 3-5 value-packed points, "
                    "end with a call to action. Label each tweet '[TWEET n]'."
                ),
                "instagram": (
                    f"Write an original Instagram caption about {niche}. "
                    "Start with a strong hook, share 3-5 insights, add value to the audience, "
                    "include a call to action and 8-10 relevant hashtags."
                ),
                "youtube": (
                    f"Write a YouTube video title, description, and short script outline about {niche}. "
                    "Title must be under 100 chars and click-worthy. Include timestamps and a CTA."
                ),
                "tiktok": (
                    f"Write a TikTok video concept about {niche}: a 3-second hook, "
                    "the main message, a trending-angle reference, and hashtags."
                ),
            }
            instructions = platform_instructions.get(platform)
            if instructions:
                result = await self.llm.complete(
                    system_prompt=(
                        "You are a professional social media content creator. "
                        "Create original, high-engagement content that meets platform "
                        "monetization standards. Never use spammy language or filler."
                    ),
                    user_prompt=instructions,
                    max_tokens=900,
                )
                if result:
                    content.update({
                        "text": result,
                        "ai_generated": True,
                        "provider": self.llm.provider_name,
                        "model": getattr(self.llm, "last_model", None) or getattr(self.llm, "model", "unknown"),
                        "hashtags": self._extract_hashtags(result),
                    })

        return content

    def _extract_hashtags(self, text: str) -> List[str]:
        import re
        return re.findall(r"#\w+", text)

    async def decide_action(self, context: Dict) -> str:
        """AI decision making based on context"""
        metrics = context.get("metrics", {})

        if metrics.get("engagement_rate", 0) < 0.02:
            return "increase_posting_frequency"
        elif metrics.get("follower_growth", 0) > 100:
            return "maintain_strategy"
        else:
            return "experiment_with_content"
