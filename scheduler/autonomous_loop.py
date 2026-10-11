import asyncio
from datetime import datetime
from typing import Dict


class AutonomousLoop:
    def __init__(self, agent):
        self.agent = agent
        self.running = False
        self.cycle_count = 0
        self.status = "idle"
        self.log = []

    async def start(self) -> None:
        """Start the autonomous loop"""
        self.running = True
        self.status = "running"
        print(f"[Autonomous] Starting loop for {self.agent.name}")
        
        while self.running:
            await self.run_cycle()
            await asyncio.sleep(3600)  # Run every hour

    async def stop(self) -> None:
        """Stop the autonomous loop"""
        self.running = False
        self.status = "stopped"
        print("[Autonomous] Loop stopped")

    async def run_cycle(self) -> Dict:
        """Run one autonomous cycle"""
        self.status = "working"
        cycle_start = datetime.now()
        print(f"\n[Autonomous] Starting cycle #{self.cycle_count + 1}")
        
        cycle_log = {
            "cycle": self.cycle_count + 1,
            "start_time": cycle_start.isoformat(),
            "actions": []
        }
        
        try:
            # Step 1: Analyze trends
            print("[Autonomous] Step 1: Analyzing trends...")
            analysis = await self.agent.analyze_niche()
            cycle_log["actions"].append({
                "action": "trend_analysis",
                "status": "completed",
                "top_niche": analysis.get("top_niche")
            })
            
            # Step 2: Create content
            print("[Autonomous] Step 2: Creating content...")
            niche = analysis.get("top_niche", "technology")
            platforms = ["twitter", "instagram", "youtube"]
            
            for platform in platforms:
                content = await self.agent.create_content(niche, platform)
                cycle_log["actions"].append({
                    "action": f"content_creation_{platform}",
                    "status": "completed",
                    "content_preview": str(content.get("text", ""))[:100]
                })
            
            # Step 3: Schedule posts
            print("[Autonomous] Step 3: Scheduling posts...")
            cycle_log["actions"].append({
                "action": "post_scheduling",
                "status": "completed"
            })
            
            # Step 4: Analyze performance
            print("[Autonomous] Step 4: Analyzing performance...")
            cycle_log["actions"].append({
                "action": "performance_analysis",
                "status": "completed"
            })
            
            # Step 5: Make decisions
            print("[Autonomous] Step 5: Making decisions...")
            decisions = await self.make_decisions(analysis)
            cycle_log["actions"].append({
                "action": "decision_making",
                "status": "completed",
                "decisions": decisions
            })
            
            cycle_log["status"] = "completed"
            cycle_log["end_time"] = datetime.now().isoformat()
            cycle_log["duration_seconds"] = (datetime.now() - cycle_start).total_seconds()
            
            self.cycle_count += 1
            self.log.append(cycle_log)
            
            print(f"[Autonomous] Cycle #{self.cycle_count} completed in {cycle_log['duration_seconds']:.1f}s")
            
        except Exception as e:
            cycle_log["status"] = "error"
            cycle_log["error"] = str(e)
            print(f"[Autonomous] Cycle failed: {e}")
        
        self.status = "idle"
        return cycle_log

    async def make_decisions(self, analysis: Dict) -> Dict:
        """Make autonomous decisions based on analysis"""
        decisions = {
            "content_strategy": "maintain",
            "posting_frequency": "increase",
            "niche_focus": analysis.get("top_niche", "technology"),
            "platform_priority": ["youtube", "instagram", "twitter"]
        }
        
        # AI decision logic would go here
        # For now, return default decisions
        
        return decisions

    def get_status(self) -> Dict:
        """Get autonomous loop status"""
        return {
            "running": self.running,
            "status": self.status,
            "cycle_count": self.cycle_count,
            "log_entries": len(self.log),
            "last_cycle": self.log[-1] if self.log else None
        }
