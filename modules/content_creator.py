from typing import Dict, List
from datetime import datetime
import json


class ContentCreator:
    def __init__(self, llm=None):
        self.content_library = []
        self.llm = llm
        self.platform_specs = self._load_platform_specs()

    async def generate_ai_content(self, niche: str, platform: str, style: str = "educational") -> Dict:
        """Generate real AI content using the LLM provider."""
        if not self.llm or not self.llm.available:
            fallback = {
                "twitter": lambda t: self.generate_twitter_thread(
                    t, ["Why it matters", "How to start", "Tips for success"]
                ),
                "instagram": self.generate_instagram_post,
                "youtube": self.generate_youtube_script,
                "tiktok": self.generate_tiktok_caption,
            }
            func = fallback.get(platform)
            if func:
                result = await func(niche)
                result["ai_generated"] = False
                result.setdefault("niche", niche)
                if "text" not in result:
                    if "content" in result and isinstance(result["content"], list):
                        result["text"] = "\n\n".join(
                            t["text"] for t in result["content"]
                        )
                    else:
                        result["text"] = str(result.get("caption", ""))
                return result
            return {"platform": platform, "niche": niche, "ai_generated": False}

        platform_prompts = {
            "twitter": (
                f"Write an engaging Twitter thread about {niche} ({style} style). "
                "Use the format: [TWEET 1]\n1. point\n2. point\n3. point\n[END]. "
                "Include a strong hook in tweet 1 and a CTA in the last tweet."
            ),
            "instagram": (
                f"Write an Instagram caption about {niche} ({style} style). "
                "Include: strong hook, 3-5 key points, value to audience, "
                "a call to action, and 8-10 relevant hashtags."
            ),
            "youtube": (
                f"Write a YouTube video script about {niche} ({style} style). "
                "Include: title, description with keywords, and a script with "
                "timestamps [0:00], [hook], [main content], [summary], [CTA]."
            ),
            "tiktok": (
                f"Write a TikTok video concept about {niche} ({style} style). "
                "Include: a hook line (first 3 seconds), main point, "
                "trend reference, and hashtags."
            ),
        }

        prompt = platform_prompts.get(platform)
        if not prompt:
            return {"platform": platform, "niche": niche, "ai_generated": False}

        text = await self.llm.complete(
            system_prompt=(
                "You are a professional content creator. Your content must meet "
                "platform monetization standards, be original, engaging, and "
                "designed to grow an audience. Never spam or use filler words."
            ),
            user_prompt=prompt,
            max_tokens=1000
        )

        if not text:
            return {"platform": platform, "niche": niche, "ai_generated": False}

        return {
            "platform": platform,
            "niche": niche,
            "style": style,
            "ai_generated": True,
            "provider": self.llm.provider_name,
            "generated_at": datetime.now().isoformat(),
            "text": text,
            "hashtags": self._extract_hashtags(text),
            "scheduled": False,
        }

    def _extract_hashtags(self, text: str) -> List[str]:
        import re
        return re.findall(r"#\w+", text)

    def _load_platform_specs(self) -> Dict:
        return {
            "twitter": {
                "max_length": 280,
                "thread_limit": 25,
                "best_times": ["09:00", "12:00", "17:00", "20:00"],
                "content_types": ["text", "image", "poll", "thread"]
            },
            "instagram": {
                "caption_limit": 2200,
                "story_limit": 100,
                "best_times": ["11:00", "14:00", "19:00"],
                "content_types": ["post", "story", "reel", "carousel"]
            },
            "youtube": {
                "title_limit": 100,
                "description_limit": 5000,
                "best_times": ["14:00", "18:00", "21:00"],
                "content_types": ["video", "short", "community"]
            },
            "tiktok": {
                "caption_limit": 2200,
                "best_times": ["10:00", "14:00", "21:00"],
                "content_types": ["video", "live"]
            }
        }

    async def generate_twitter_thread(self, topic: str, points: List[str]) -> Dict:
        """Generate a Twitter thread"""
        thread = []
        thread.append({
            "tweet_number": 1,
            "text": f"THREAD | Let's talk about {topic}...\n\nHere's what you need to know:"
        })
        for i, point in enumerate(points, 2):
            thread.append({
                "tweet_number": i,
                "text": f"{i-1}. {point}"
            })
        thread.append({
            "tweet_number": len(points) + 2,
            "text": f"Found this helpful? Follow for more insights on {topic}!\n\n#Thread #{topic.replace(' ', '')}"
        })
        return {"type": "thread", "platform": "twitter", "content": thread}

    async def generate_instagram_post(self, topic: str, style: str = "educational") -> Dict:
        """Generate Instagram post content"""
        captions = {
            "educational": f"LEARN | {topic}\n\nHere's what most people don't know...\n\n[Slide 1] The problem\n[Slide 2] The solution\n[Slide 3] How to implement\n\nSave this for later!\n\n#Learning #Growth #{topic.replace(' ', '')}",
            "lifestyle": f"LIFESTYLE | Living the {topic} life\n\n[Photo description: Modern, clean aesthetic]\n\nCaption: Embracing the journey of {topic}...\n\n#Lifestyle #{topic.replace(' ', '')}",
            "promotional": f"LAUNCH | {topic}\n\nI've been working on something special...\n\n[Product/Service details]\n\nLimited time offer!\n\n#Launch #{topic.replace(' ', '')}"
        }
        return {
            "type": "post",
            "platform": "instagram",
            "caption": captions.get(style, captions["educational"]),
            "style": style
        }

    async def generate_youtube_script(self, topic: str, duration: str = "short") -> Dict:
        """Generate YouTube video script"""
        scripts = {
            "short": {
                "title": f"{topic} in 60 Seconds",
                "description": f"Quick guide to {topic}. Like and subscribe for more!",
                "script": [
                    {"time": "0:00", "action": "Hook", "text": f"Want to master {topic}?"},
                    {"time": "0:05", "action": "Content", "text": "Here are the key points..."},
                    {"time": "0:45", "action": "CTA", "text": "Follow for more!"}
                ]
            },
            "long": {
                "title": f"Complete Guide to {topic} (2024)",
                "description": f"In this video, we cover everything about {topic}...",
                "script": [
                    {"time": "0:00", "action": "Intro", "text": "Welcome back to the channel!"},
                    {"time": "0:30", "action": "Content", "text": "Let's dive into {topic}..."},
                    {"time": "5:00", "action": "Examples", "text": "Here are real examples..."},
                    {"time": "15:00", "action": "Summary", "text": "Let's recap what we learned..."},
                    {"time": "18:00", "action": "CTA", "text": "Smash that like button!"}
                ]
            }
        }
        return {"type": "video", "platform": "youtube", **scripts.get(duration, scripts["short"])}

    async def create_content_calendar(self, niche: str, platforms: List[str], days: int = 7) -> Dict:
        """Create a content calendar"""
        calendar = {
            "niche": niche,
            "platforms": platforms,
            "days": days,
            "schedule": []
        }
        for day in range(days):
            daily_content = {"day": day + 1, "content": []}
            for platform in platforms:
                spec = self.platform_specs.get(platform, {})
                daily_content["content"].append({
                    "platform": platform,
                    "type": spec.get("content_types", ["text"])[0],
                    "best_time": spec.get("best_times", ["12:00"])[0],
                    "topic": f"{niche} tip #{day + 1}"
                })
            calendar["schedule"].append(daily_content)
        return calendar

    async def generate_tiktok_caption(self, topic: str) -> Dict:
        """Fallback TikTok caption generator"""
        return {
            "type": "video",
            "platform": "tiktok",
            "caption": f"POV: you just discovered {topic}...\n\nHere's exactly what to do 👇\n\n[Video: 15-30s, trending audio, text overlay]\n\n#LearnOnTikTok #{topic.replace(' ', '')} #FYP #Trending",
            "hashtags": [f"#{topic.replace(' ', '')}", "#FYP", "#Trending"]
        }
