from typing import Dict, List
from datetime import datetime, timedelta


class AnalyticsAPI:
    def __init__(self):
        self.metrics_history = {}
        self.benchmarks = self._load_benchmarks()

    def _load_benchmarks(self) -> Dict:
        return {
            "engagement_rate": {"excellent": 0.05, "good": 0.03, "average": 0.01},
            "follower_growth": {"excellent": 0.10, "good": 0.05, "average": 0.02},
            "content_frequency": {"excellent": 3, "good": 2, "average": 1}
        }

    async def track_metric(self, platform: str, metric_name: str, value: float) -> None:
        """Track a metric over time"""
        if platform not in self.metrics_history:
            self.metrics_history[platform] = {}
        if metric_name not in self.metrics_history[platform]:
            self.metrics_history[platform][metric_name] = []
        
        self.metrics_history[platform][metric_name].append({
            "value": value,
            "timestamp": datetime.now().isoformat()
        })

    async def get_performance_report(self, platform: str, days: int = 30) -> Dict:
        """Generate performance report"""
        cutoff = datetime.now() - timedelta(days=days)
        
        metrics = self.metrics_history.get(platform, {})
        report = {
            "platform": platform,
            "period_days": days,
            "generated_at": datetime.now().isoformat(),
            "metrics": {},
            "insights": [],
            "recommendations": []
        }

        for metric_name, values in metrics.items():
            recent = [v for v in values if datetime.fromisoformat(v["timestamp"]) > cutoff]
            if recent:
                avg = sum(v["value"] for v in recent) / len(recent)
                report["metrics"][metric_name] = {
                    "average": round(avg, 3),
                    "latest": recent[-1]["value"],
                    "data_points": len(recent)
                }

        # Generate insights
        if "engagement_rate" in report["metrics"]:
            er = report["metrics"]["engagement_rate"]["average"]
            if er > self.benchmarks["engagement_rate"]["excellent"]:
                report["insights"].append("Excellent engagement rate!")
            elif er < self.benchmarks["engagement_rate"]["average"]:
                report["insights"].append("Engagement rate needs improvement")
                report["recommendations"].append("Try more interactive content")

        return report

    async def analyze_content_performance(self, platform: str) -> Dict:
        """Analyze which content types perform best"""
        return {
            "platform": platform,
            "best_content_types": [
                {"type": "how_to", "engagement": 0.045, "reach": "high"},
                {"type": "listicle", "engagement": 0.038, "reach": "medium"},
                {"type": "behind_scenes", "engagement": 0.042, "reach": "medium"}
            ],
            "best_posting_times": ["09:00", "12:00", "19:00"],
            "optimal_hashtag_count": 5,
            "recommendations": [
                "Post more how-to content",
                "Use 5-7 hashtags",
                "Post during lunch hours"
            ]
        }

    async def get_competitor_analysis(self, competitors: List[str]) -> Dict:
        """Analyze competitor performance"""
        analysis = {
            "competitors": [],
            "insights": [],
            "opportunities": []
        }
        
        for competitor in competitors:
            analysis["competitors"].append({
                "name": competitor,
                "estimated_followers": 50000,
                "engagement_rate": 0.035,
                "posting_frequency": "daily",
                "content_style": "educational"
            })
        
        analysis["insights"].append("Competitors post daily educational content")
        analysis["opportunities"].append("Gap in video tutorials")
        
        return analysis
