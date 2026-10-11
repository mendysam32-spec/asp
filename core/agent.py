import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from .brain import AgentBrain
from .memory import AgentMemory


class AIAgent:
    def __init__(self, name: str = "ContentAgent"):
        self.name = name
        self.brain = AgentBrain()
        self.memory = AgentMemory()
        self.status = "idle"
        self.tasks_completed = 0
        self.created_at = datetime.now()

    async def start(self):
        print(f"[{self.name}] Starting agent...")
        self.status = "running"
        await self.memory.initialize()
        print(f"[{self.name}] Agent ready. Status: {self.status}")

    async def analyze_niche(self) -> Dict:
        print(f"[{self.name}] Analyzing trending niches...")
        analysis = await self.brain.analyze_trends()
        await self.memory.log_activity("niche_analysis", analysis)
        return analysis

    async def create_content(self, niche: str, platform: str) -> Dict:
        print(f"[{self.name}] Creating content for {platform} in niche: {niche}")
        content = await self.brain.generate_content(niche, platform)
        await self.memory.log_activity("content_creation", {
            "niche": niche,
            "platform": platform,
            "content_preview": content.get("text", "")[:100]
        })
        return content

    async def schedule_post(self, content: Dict, post_time: datetime) -> bool:
        print(f"[{self.name}] Scheduling post for {post_time}")
        scheduled = await self.memory.schedule_post(content, post_time)
        return scheduled

    async def get_status(self) -> Dict:
        return {
            "name": self.name,
            "status": self.status,
            "tasks_completed": self.tasks_completed,
            "uptime": str(datetime.now() - self.created_at),
            "memory_usage": await self.memory.get_stats()
        }

    async def run_cycle(self):
        print(f"[{self.name}] Running autonomous cycle...")
        self.status = "working"

        # Step 1: Analyze current trends
        analysis = await self.analyze_niche()

        # Step 2: Select best niche
        top_niche = analysis.get("top_niche", "technology")

        # Step 3: Create content for each platform
        platforms = ["twitter", "instagram", "youtube"]
        for platform in platforms:
            content = await self.create_content(top_niche, platform)
            # Schedule for optimal posting time
            await self.schedule_post(content, datetime.now())

        self.tasks_completed += 1
        self.status = "idle"
        print(f"[{self.name}] Cycle complete. Tasks: {self.tasks_completed}")
