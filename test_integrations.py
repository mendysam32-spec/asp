"""Verify the real platform integrations import and initialize correctly."""
import asyncio
import sys
import traceback

async def main():
    print("=" * 60)
    print("REAL PLATFORM INTEGRATION TEST")
    print("=" * 60)

    passed = 0
    failed = 0

    print("\n[TEST] Import providers + registry")
    try:
        from api.registry import PlatformRegistry
        registry = PlatformRegistry()
        print("  [OK] PlatformRegistry created")
        print("  Payout priorities:")
        for line in registry.describe():
            print(f"    {line}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()
        failed += 1

    print("\n[TEST] Provider import + connection status (no creds)")
    try:
        from api.providers import YouTubeProvider, TikTokProvider, XProvider, MetaProvider
        providers = [
            ("youtube", YouTubeProvider()),
            ("tiktok", TikTokProvider()),
            ("x", XProvider()),
            ("instagram", MetaProvider()),
        ]
        for name, p in providers:
            avail = p.available
            connected = p.refresh_token if hasattr(p, "refresh_token") else None
            expected = bool(connected or getattr(p, "api_key", None))
            print(f"  [{name}] available={avail} (creds present={expected})")
            assert avail == expected, (
                f"{name} availability mismatch: expected {expected} from configured creds"
            )
        print("  [OK] All providers correctly report connection status")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()
        failed += 1

    print("\n[TEST] Registry check_all (no creds)")
    try:
        from api.registry import PlatformRegistry
        registry = PlatformRegistry()
        statuses = await registry.check_all()
        for s in statuses:
            print(f"  [{s['platform']}] pays={s['pays_creators']}, connected={s['connected']}")
        assert len(statuses) == 4
        print("  [OK] Registry check_all returns all 4 platforms")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()
        failed += 1

    print("\n[TEST] Registry get_monetization_status (no creds)")
    try:
        from api.registry import PlatformRegistry
        registry = PlatformRegistry()
        results = await registry.get_monetization_status()
        for r in results:
            status = "not connected" if r.get("connected") is False else "checked"
            print(f"  [{r.get('platform')}] {status}")
        print("  [OK] Monetization status reconciles gracefully")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()
        failed += 1

    print("\n[TEST] setup_credentials.py exists and parses")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("setup_creds", "setup_credentials.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert len(mod.SETUP_GUIDES) == 4, "4 platforms expected"
        assert mod.SETUP_GUIDES.get("tiktok"), "tiktok guide required"
        print("  [OK] setup_credentials.py loads, 4 platform guides present")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        traceback.print_exc()
        failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    return failed == 0

if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)