from typing import Dict, List
from datetime import datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
from threading import Lock

_TAX_FILE = Path(__file__).resolve().parent.parent / "data" / "transactions.json"
_tax_lock = Lock()


class TaxTracker:
    def __init__(self):
        self.transactions = self._load()
        self.categories = self._load_tax_categories()

    def _load(self) -> List[Dict]:
        if _TAX_FILE.exists():
            try:
                return json.loads(_TAX_FILE.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _persist(self):
        _TAX_FILE.parent.mkdir(exist_ok=True)
        with _tax_lock:
            _TAX_FILE.write_text(json.dumps(self.transactions, indent=2), encoding="utf-8")

    def _load_tax_categories(self) -> Dict:
        return {
            "income": {
                "ad_revenue": {"description": "Ad revenue from platforms", "tax_rate": 0.22},
                "sponsorships": {"description": "Brand deals and sponsorships", "tax_rate": 0.22},
                "affiliate": {"description": "Affiliate commissions", "tax_rate": 0.22},
                "products": {"description": "Digital product sales", "tax_rate": 0.22},
                "services": {"description": "Freelance/services income", "tax_rate": 0.22}
            },
            "expenses": {
                "equipment": {"description": "Camera, mic, computer", "deductible": True},
                "software": {"description": "Editing software, tools", "deductible": True},
                "internet": {"description": "Internet bill (business %)", "deductible": True},
                "education": {"description": "Courses, books", "deductible": True},
                "marketing": {"description": "Ads, promotions", "deductible": True},
                "home_office": {"description": "Home office space", "deductible": True}
            }
        }

    async def log_transaction(self, transaction: Dict) -> Dict:
        """Log a financial transaction"""
        entry = {
            "id": len(self.transactions) + 1,
            "type": transaction.get("type"),  # income or expense
            "category": transaction.get("category"),
            "amount": float(transaction.get("amount", 0)),
            "description": transaction.get("description"),
            "platform": transaction.get("platform"),
            "date": transaction.get("date", datetime.now().isoformat()),
            "tax_deductible": transaction.get("tax_deductible", False),
            "receipt_url": transaction.get("receipt_url"),
            "created_at": datetime.now().isoformat()
        }
        self.transactions.append(entry)
        try:
            self._persist()
        except Exception:
            pass
        return entry

    async def get_income_summary(self, period: str = "monthly") -> Dict:
        """Get income summary"""
        now = datetime.now()
        if period == "monthly":
            start = now.replace(day=1)
        elif period == "quarterly":
            quarter = (now.month - 1) // 3
            start = now.replace(month=quarter * 3 + 1, day=1)
        else:
            start = now.replace(month=1, day=1)

        income_transactions = [
            t for t in self.transactions
            if t["type"] == "income" and datetime.fromisoformat(t["date"]) >= start
        ]

        summary = {
            "period": period,
            "start_date": start.isoformat(),
            "total_income": sum(t["amount"] for t in income_transactions),
            "by_category": {},
            "by_platform": {},
            "transaction_count": len(income_transactions)
        }

        for t in income_transactions:
            cat = t["category"]
            platform = t["platform"]
            summary["by_category"][cat] = summary["by_category"].get(cat, 0) + t["amount"]
            summary["by_platform"][platform] = summary["by_platform"].get(platform, 0) + t["amount"]

        return summary

    async def get_expense_summary(self, period: str = "monthly") -> Dict:
        """Get expense summary"""
        now = datetime.now()
        if period == "monthly":
            start = now.replace(day=1)
        elif period == "quarterly":
            quarter = (now.month - 1) // 3
            start = now.replace(month=quarter * 3 + 1, day=1)
        else:
            start = now.replace(month=1, day=1)

        expense_transactions = [
            t for t in self.transactions
            if t["type"] == "expense" and datetime.fromisoformat(t["date"]) >= start
        ]

        summary = {
            "period": period,
            "start_date": start.isoformat(),
            "total_expenses": sum(t["amount"] for t in expense_transactions),
            "deductible_expenses": sum(t["amount"] for t in expense_transactions if t["tax_deductible"]),
            "by_category": {},
            "transaction_count": len(expense_transactions)
        }

        for t in expense_transactions:
            cat = t["category"]
            summary["by_category"][cat] = summary["by_category"].get(cat, 0) + t["amount"]

        return summary

    async def estimate_taxes(self, year: int = None) -> Dict:
        """Estimate tax liability"""
        if year is None:
            year = datetime.now().year

        year_transactions = [
            t for t in self.transactions
            if datetime.fromisoformat(t["date"]).year == year
        ]

        total_income = sum(t["amount"] for t in year_transactions if t["type"] == "income")
        total_deductible = sum(t["amount"] for t in year_transactions if t["type"] == "expense" and t["tax_deductible"])
        
        taxable_income = total_income - total_deductible
        estimated_tax = taxable_income * 0.22  # 22% bracket

        return {
            "year": year,
            "total_income": total_income,
            "total_deductible_expenses": total_deductible,
            "taxable_income": taxable_income,
            "estimated_tax_liability": estimated_tax,
            "effective_tax_rate": (estimated_tax / total_income * 100) if total_income > 0 else 0,
            "recommendations": [
                "Keep all receipts for deductions",
                "Track mileage for business travel",
                "Consider quarterly estimated payments",
                "Consult a tax professional"
            ]
        }

    async def generate_tax_report(self, year: int = None) -> Dict:
        """Generate comprehensive tax report"""
        income = await self.get_income_summary("yearly")
        expenses = await self.get_expense_summary("yearly")
        tax_estimate = await self.estimate_taxes(year)

        return {
            "report_date": datetime.now().isoformat(),
            "year": year or datetime.now().year,
            "income_summary": income,
            "expense_summary": expenses,
            "tax_estimate": tax_estimate,
            "documents_needed": [
                "1099 forms from platforms",
                "Receipts for business expenses",
                "Bank statements",
                "PayPal transaction history"
            ]
        }
