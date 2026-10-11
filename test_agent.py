"""Test script to verify all agent components work"""
import asyncio
import traceback


async def test_all():
    print("=" * 50)
    print("TESTING AI CONTENT AGENT")
    print("=" * 50)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Core Agent
    print("\n[TEST 1] Core Agent")
    try:
        from core.agent import AIAgent
        from core.memory import AgentMemory
        from core.brain import AgentBrain
        
        agent = AIAgent(name="TestAgent")
        await agent.start()
        memory = AgentMemory()
        await memory.initialize()
        brain = AgentBrain()
        
        # Test trend analysis
        analysis = await brain.analyze_trends()
        assert analysis.get("top_niche"), "No top niche found"
        print("  [OK] Agent initialized, niche analysis works")
        tests_passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()
        tests_failed += 1
    
    # Test 2: Niche Analyzer
    print("\n[TEST 2] Niche Analyzer")
    try:
        from modules.niche_analyzer import NicheAnalyzer
        analyzer = NicheAnalyzer()
        analysis = await analyzer.get_full_analysis()
        assert analysis.get("top_niche"), "No top niche"
        assert len(analysis.get("recommendations", [])) > 0, "No recommendations"
        print(f"  [OK] Found top niche: {analysis['top_niche']}")
        print(f"  [OK] {len(analysis['recommendations'])} recommendations generated")
        tests_passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()
        tests_failed += 1
    
    # Test 3: Content Creator
    print("\n[TEST 3] Content Creator")
    try:
        from modules.content_creator import ContentCreator
        creator = ContentCreator()
        
        thread = await creator.generate_twitter_thread("AI Tools", ["Point A", "Point B", "Point C"])
        assert thread["platform"] == "twitter"
        assert len(thread["content"]) == 5  # 1 intro + 3 points + 1 outro
        
        insta = await creator.generate_instagram_post("AI")
        assert insta["platform"] == "instagram"
        
        youtube = await creator.generate_youtube_script("AI")
        assert youtube["platform"] == "youtube"
        
        calendar = await creator.create_content_calendar("AI", ["twitter", "instagram"], 7)
        assert len(calendar["schedule"]) == 7
        
        print("  [OK] Twitter thread, IG post, YT script, calendar all work")
        tests_passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()
        tests_failed += 1
    
    # Test 4: Social Media Manager
    print("\n[TEST 4] Social Media Manager")
    try:
        from api.social_media import SocialMediaManager
        sm = SocialMediaManager()
        result = await sm.post_tweet("Test tweet")
        # Should fail gracefully without connection
        assert "error" in result, "Should error without connection"
        print("  [OK] Graceful error handling works")
        tests_passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()
        tests_failed += 1
    
    # Test 5: Monetization Manager
    print("\n[TEST 5] Monetization")
    try:
        from modules.monetization import MonetizationManager
        monet = MonetizationManager()
        eligibility = await monet.check_monetization_eligibility("youtube", {"subscribers": 500, "watch_hours": 2000})
        assert eligibility["eligible"] == False, "Should not be eligible yet"
        assert len(eligibility["missing"]) > 0, "Should list missing requirements"
        
        plan = await monet.generate_monetization_plan(["youtube"], {"youtube": {"subscribers": 500, "watch_hours": 2000}})
        assert len(plan["strategies"]) == 1
        print("  [OK] Monetization eligibility check works")
        print(f"  [OK] Action items: {plan['strategies'][0]['action_items']}")
        tests_passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()
        tests_failed += 1
    
    # Test 6: Tax Tracker (isolated — restores data/transactions.json afterwards)
    print("\n[TEST 6] Tax Tracker")
    try:
        from pathlib import Path as _P
        import json as _json
        from modules.tax_tracker import TaxTracker
        _tx_file = _P("data/transactions.json")
        _tx_backup = _tx_file.read_text(encoding="utf-8") if _tx_file.exists() else None
        try:
            tracker = TaxTracker()
            _base_income = (await tracker.get_income_summary("monthly"))["total_income"]

            await tracker.log_transaction({
                "type": "income",
                "category": "ad_revenue",
                "amount": 500.00,
                "description": "TEST transaction (auto-removed)",
                "platform": "youtube"
            })
            await tracker.log_transaction({
                "type": "expense",
                "category": "software",
                "amount": 50.00,
                "description": "TEST transaction (auto-removed)",
                "platform": "general",
                "tax_deductible": True
            })

            summary = await tracker.get_income_summary("monthly")
            assert abs(summary["total_income"] - (_base_income + 500.00)) < 0.01, \
                f"expected {_base_income + 500.00}, got {summary['total_income']}"

            taxes = await tracker.estimate_taxes()
            print(f"  [OK] Income logged: ${summary['total_income']}")
            print(f"  [OK] Estimated tax: ${taxes['estimated_tax_liability']:.2f}")
        finally:
            # restore pre-test ledger so tests never pollute real tax data
            try:
                if _tx_backup is None:
                    if _tx_file.exists():
                        _tx_file.unlink()
                else:
                    _tx_file.write_text(_tx_backup, encoding="utf-8")
            except Exception:
                pass
        tests_passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()
        tests_failed += 1
    
    # Test 7: Autonomous Loop
    print("\n[TEST 7] Autonomous Loop")
    try:
        from core.agent import AIAgent
        from scheduler.autonomous_loop import AutonomousLoop
        
        agent = AIAgent(name="LoopTestAgent")
        await agent.start()
        async def _fast_complete(system_prompt, user_prompt, max_tokens=1000):
            return "Fast test content for " + user_prompt[:40]
        agent.brain.llm.complete = _fast_complete
        loop = AutonomousLoop(agent)
        
        result = await loop.run_cycle()
        assert result["status"] == "completed", "Cycle should complete"
        assert len(result["actions"]) >= 4, "Should have multiple actions"
        
        print(f"  [OK] Autonomous cycle completed: {result['status']}")
        print(f"  [OK] Actions executed: {len(result['actions'])}")
        print(f"  [OK] Duration: {result['duration_seconds']:.1f}s")
        tests_passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()
        tests_failed += 1

    # Test 8: AI Content Generation (fast local stub; live LLM tested separately)
    print("\n[TEST 8] AI Content Generation")
    try:
        from core.llm import LLMProvider
        from modules.content_creator import ContentCreator

        llm = LLMProvider()

        async def _fast_complete(system_prompt, user_prompt, max_tokens=1000):
            return "Generated content test text for: " + user_prompt[:50]

        llm.complete = _fast_complete
        creator = ContentCreator(llm=llm)

        content = await creator.generate_ai_content("AI Tools", "twitter", "educational")
        assert content["platform"] == "twitter"
        assert content["niche"] == "AI Tools"
        assert "text" in content
        print(f"  [OK] generate_ai_content works (provider: {llm.provider_name}, ai: {content.get('ai_generated')})")

        # Brain-level generation
        from core.brain import AgentBrain
        brain = AgentBrain()
        brain.llm.complete = _fast_complete
        brain_content = await brain.generate_content("AI Tools", "instagram")
        assert brain_content["platform"] == "instagram"
        assert "text" in brain_content
        print(f"  [OK] Brain generate_content works (provider: {brain.llm.provider_name})")
        tests_passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()
        tests_failed += 1
    
    print("\n" + "=" * 50)
    print(f"RESULTS: {tests_passed} passed, {tests_failed} failed")
    print("=" * 50)
    
    return tests_failed == 0


if __name__ == "__main__":
    success = asyncio.run(test_all())
    exit(0 if success else 1)
