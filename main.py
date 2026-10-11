"""AI Content Agent - Main Entry Point"""
import asyncio
import os
from core.agent import AIAgent
from core.llm import LLMProvider
from core.memory import AgentMemory
from modules.niche_analyzer import NicheAnalyzer
from modules.content_creator import ContentCreator
from modules.monetization import MonetizationManager
from modules.tax_tracker import TaxTracker
from api.registry import PlatformRegistry
from api.paypal import PayPalIntegration
from scheduler.autonomous_loop import AutonomousLoop


class ContentAgent:
    def __init__(self):
        self.agent = AIAgent(name="ContentAgent")
        self.llm = LLMProvider()
        self.memory = AgentMemory()
        self.niche_analyzer = NicheAnalyzer()
        self.content_creator = ContentCreator(llm=self.llm)
        self.monetization = MonetizationManager()
        self.tax_tracker = TaxTracker()
        self.paypal = PayPalIntegration()
        self.registry = PlatformRegistry()
        self.autonomous_loop = AutonomousLoop(self.agent)
        
    async def initialize(self):
        """Initialize all components"""
        print("=" * 50)
        print("AI Content Agent - Initializing...")
        print("=" * 50)
        
        await self.agent.start()
        await self.memory.initialize()
        
        ai_status = f"Ready ({self.llm.provider_name.upper()})" if self.llm.available else "NOT CONFIGURED (using fallback templates)"
        
        print("\n[Components]")
        print(f"- AI Engine: {ai_status}")
        print("- Niche Analyzer: Ready")
        print("- Content Creator: Ready")
        print("- Social Media Manager: Ready")
        print("- PayPal Integration: Ready")
        print("- Tax Tracker: Ready")
        print("- Autonomous Loop: Ready")
        
        print("\n" + "=" * 50)
        print("Agent Ready! Commands:")
        print("  1. analyze   - Analyze trending niches")
        print("  2. create    - Create content (AI generated)")
        print("  3. connect   - Check platform connections")
        print("  4. monetize  - Check monetization eligibility")
        print("  5. start     - Start autonomous mode")
        print("  6. status    - Check agent status")
        print("  7. tax       - View tax report")
        print("  8. exit      - Stop agent")
        print("=" * 50)
    
    async def analyze_niche(self):
        """Analyze trending niches"""
        print("\n[Analyzing niches...]")
        analysis = await self.niche_analyzer.get_full_analysis()
        
        print("\n[TOP NICHES]")
        for i, rec in enumerate(analysis.get("recommendations", [])[:5], 1):
            print(f"  {i}. {rec['niche']} (Score: {rec['score']})")
            print(f"     Monetization: {rec['monetization'].get('estimated_monthly', 'N/A')}")
        
        print(f"\n[RECOMMENDED Niche]: {analysis.get('top_niche')}")
        return analysis
    
    async def create_content(self, niche: str = "AI & Technology"):
        """Create content for all platforms using AI"""
        print(f"\n[Creating AI content for {niche}...]")
        
        content_plan = {
            "twitter": await self.content_creator.generate_ai_content(niche, "twitter"),
            "instagram": await self.content_creator.generate_ai_content(niche, "instagram"),
            "youtube": await self.content_creator.generate_ai_content(niche, "youtube"),
            "tiktok": await self.content_creator.generate_ai_content(niche, "tiktok"),
        }
        
        print("\n[CONTENT CREATED]")
        for platform, content in content_plan.items():
            generated = "[AI]" if content.get("ai_generated") else "[TEMPLATE]"
            print(f"\n  {platform.upper()} {generated}:")
            text = content.get("text") or content.get("caption") or content.get("title") or ""
            print(f"     {text[:120]}")
        
        return content_plan
    
    async def connect_platforms(self):
        """Connect social media accounts and show status"""
        print("\n[PLATFORM CONNECTIONS]")
        print("Prioritized by creator payouts:\n")
        for line in self.registry.describe():
            print(f"  {line}")
        
        statuses = await self.registry.check_all()
        print("\n[CONNECTION STATUS]")
        for status in statuses:
            if status["connected"]:
                check = status.get("connection_check", {})
                detail = check.get("connected", False)
                print(f"  [OK] {status['platform']}: connected (verified={detail})")
            else:
                print(f"  [X]  {status['platform']}: NOT connected")
        
        if not self.registry.connected():
            print("\n[HELP] Run this to set up credentials:")
            print("  python setup_credentials.py")
            print("  # or for one platform:")
            print("  python setup_credentials.py tiktok   # pays via PayPal")
    
    async def show_monetization(self):
        """Show monetization eligibility across connected platforms"""
        print("\n[MONETIZATION STATUS]")
        results = await self.registry.get_monetization_status()
        for r in results:
            if r.get("connected") is False:
                print(f"\n  {r['platform']}: not connected")
                continue
            print(f"\n  {r.get('platform', '?').upper()}:")
            for k, v in r.items():
                if k != "platform":
                    print(f"    {k}: {v}")
    
    async def start_autonomous(self):
        """Start autonomous mode"""
        print("\n[STARTING] Autonomous Mode...")
        print("Agent will now work independently to:")
        print("  - Analyze trends")
        print("  - Create content")
        print("  - Schedule posts")
        print("  - Track finances")
        print("\nPress Ctrl+C to stop")
        
        await self.autonomous_loop.start()
    
    async def get_status(self):
        """Get agent status"""
        print("\n[Agent Status]")
        status = await self.agent.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
        print(f"  ai_provider: {self.llm.provider_name}")
        print(f"  ai_available: {self.llm.available}")
        return status
    
    async def get_tax_report(self):
        """Get tax report"""
        print("\n[Tax Report]")
        report = await self.tax_tracker.generate_tax_report()
        
        print(f"\n  Year: {report['year']}")
        print(f"  Total Income: ${report['income_summary']['total_income']:.2f}")
        print(f"  Total Expenses: ${report['expense_summary']['total_expenses']:.2f}")
        print(f"  Estimated Tax: ${report['tax_estimate']['estimated_tax_liability']:.2f}")
        
        return report


async def main():
    """Main entry point"""
    agent = ContentAgent()
    await agent.initialize()
    
    while True:
        try:
            command = input("\n[Agent] > ").strip().lower()
            
            if command == "analyze":
                await agent.analyze_niche()
            elif command == "create":
                niche = input("Enter niche (or press Enter for default): ").strip()
                await agent.create_content(niche if niche else "AI & Technology")
            elif command == "connect":
                await agent.connect_platforms()
            elif command == "monetize":
                await agent.show_monetization()
            elif command == "start":
                await agent.start_autonomous()
            elif command == "status":
                await agent.get_status()
            elif command == "tax":
                await agent.get_tax_report()
            elif command == "exit":
                print("\n[SHUTDOWN] Stopping agent...")
                break
            else:
                print("Unknown command. Try: analyze, create, connect, monetize, start, status, tax, exit")
                
        except KeyboardInterrupt:
            print("\n\n[INTERRUPTED] Shutting down...")
            break
        except Exception as e:
            print(f"\n[ERROR]: {e}")


if __name__ == "__main__":
    asyncio.run(main())
