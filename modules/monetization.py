from typing import Dict, List
from datetime import datetime


class MonetizationManager:
    def __init__(self):
        self.revenue_streams = {}
        self.platform_monetization = self._load_monetization_rules()

    def _load_monetization_rules(self) -> Dict:
        # Requirements as of 2026 (verified against platform programs)
        return {
            "youtube": {
                "requirements": {
                    "subscribers": 1000,
                    "watch_hours": 4000,
                    "short_views": 10000000,
                    "uploads_3mo": 3,
                },
                "payout": "AdSense, $100 min, monthly",
                "revenue_streams": ["ads", "memberships", "super_chat", "shop"],
                "note": "Feb 2027: thresholds double to 8,000h / 20M Shorts",
            },
            "instagram": {
                "requirements": {
                    "followers_fan_tips": 500,
                    "followers_affiliate": 1000,
                    "followers_subscriptions": 10000,
                    "account_type": "business_or_creator",
                },
                "payout": "$5 US min (bank/Stripe), twice monthly",
                "revenue_streams": ["fan_tips", "affiliate", "subscriptions", "bonuses_invite_only"],
                "note": "Bonuses (Meta paid) are invite-only, US/JP/KR",
            },
            "tiktok": {
                "requirements": {
                    "followers": 10000,
                    "likes_28d": 100000,
                    "posts_28d": 3,
                    "videos_1min_plus": True,
                    "age": 18,
                },
                "payout": "PayPal/Hyperwallet, $50 min, 15th monthly",
                "revenue_streams": ["creator_rewards", "live_gifts", "subscriptions", "shop_affiliate", "series"],
                "note": "Only expires: must maintain 100k likes + 3 posts/28d",
            },
            "x": {
                "requirements": {
                    "x_premium": True,
                    "verified": True,
                    "followers": 500,
                    "impressions_3mo": 5000000,
                },
                "payout": "Stripe, $30 min, biweekly",
                "revenue_streams": ["ad_revenue_share", "creator_subscriptions"],
                "note": "You pay for X Premium (~$8/mo) before X pays you",
            },
            "facebook": {
                "requirements": {
                    "followers": 10000,
                    "active_videos": 5,
                    "stream_minutes_60d": 600000,
                },
                "payout": "$5 US min, twice monthly",
                "revenue_streams": ["in_stream_ads", "subscriptions"],
                "note": "Invite-only for some tiers",
            },
        }

    async def check_monetization_eligibility(self, platform: str, metrics: Dict) -> Dict:
        """Check if eligible for monetization"""
        rules = self.platform_monetization.get(platform, {})
        requirements = rules.get("requirements", {})
        
        eligibility = {
            "platform": platform,
            "eligible": True,
            "requirements": requirements,
            "current_metrics": metrics,
            "missing": []
        }
        
        for req, value in requirements.items():
            current = metrics.get(req, 0)
            # bool requirements (e.g. x_premium, videos_1min_plus) must be truthy
            if isinstance(value, bool):
                if not current:
                    eligibility["eligible"] = False
                    eligibility["missing"].append({
                        "requirement": req,
                        "needed": value,
                        "current": current,
                        "gap": "required",
                    })
                continue
            # string requirements (e.g. account_type) must match
            if isinstance(value, str):
                if str(current) != value:
                    eligibility["eligible"] = False
                    eligibility["missing"].append({
                        "requirement": req,
                        "needed": value,
                        "current": current,
                        "gap": "mismatch",
                    })
                continue
            try:
                if current < value:
                    eligibility["eligible"] = False
                    eligibility["missing"].append({
                        "requirement": req,
                        "needed": value,
                        "current": current,
                        "gap": value - current
                    })
            except TypeError:
                eligibility["eligible"] = False
                eligibility["missing"].append({
                    "requirement": req,
                    "needed": value,
                    "current": current,
                    "gap": "mismatch",
                })
        
        return eligibility

    async def calculate_potential_revenue(self, platform: str, metrics: Dict) -> Dict:
        """Estimate potential revenue"""
        # Rough estimates based on industry averages
        estimates = {
            "youtube": {
                "cpm": 5.0,  # Cost per 1000 views
                "rpm": 2.5,  # Revenue per 1000 views
            },
            "instagram": {
                "sponsored_rate_per_1k": 10.0,
                "affiliate_commission": 0.15
            },
            "tiktok": {
                "cpm": 0.50,
                "creator_fund_per_1k": 0.02
            },
            "twitter": {
                "rpm": 0.50
            }
        }
        
        platform_rates = estimates.get(platform, {})
        views = metrics.get("views", 0)
        followers = metrics.get("followers", 0)
        
        return {
            "platform": platform,
            "estimated_monthly": {
                "ad_revenue": (views / 1000) * platform_rates.get("cpm", 0),
                "sponsorships": (followers / 1000) * platform_rates.get("sponsored_rate_per_1k", 0),
                "affiliate": metrics.get("affiliate_clicks", 0) * 0.50
            },
            "breakdown": "Estimates based on industry averages"
        }

    async def generate_monetization_plan(self, platforms: List[str], current_metrics: Dict) -> Dict:
        """Generate a monetization strategy"""
        plan = {
            "created_at": datetime.now().isoformat(),
            "platforms": platforms,
            "strategies": [],
            "timeline": "3-6 months to first revenue"
        }
        
        for platform in platforms:
            eligibility = await self.check_monetization_eligibility(platform, current_metrics.get(platform, {}))
            revenue = await self.calculate_potential_revenue(platform, current_metrics.get(platform, {}))
            
            plan["strategies"].append({
                "platform": platform,
                "eligibility": eligibility,
                "revenue_estimate": revenue,
                "action_items": self._get_action_items(platform, eligibility)
            })
        
        return plan

    def _get_action_items(self, platform: str, eligibility: Dict) -> List[str]:
        """Generate action items based on eligibility"""
        items = []
        if not eligibility["eligible"]:
            for missing in eligibility.get("missing", []):
                items.append(f"Grow {missing['requirement']} from {missing['current']} to {missing['needed']}")
        else:
            items.append("Apply for monetization")
            items.append("Set up payment details")
            items.append("Create monetized content")
        return items
