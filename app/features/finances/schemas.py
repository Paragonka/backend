from decimal import Decimal

from pydantic import BaseModel


class MonthlyFinance(BaseModel):
    month: str
    revenue: Decimal = Decimal(0)
    expenses: Decimal = Decimal(0)
    pnl: Decimal = Decimal(0)


class FinanceSummaryResponse(BaseModel):
    total_revenue: Decimal = Decimal(0)
    total_expenses: Decimal = Decimal(0)
    total_pnl: Decimal = Decimal(0)
    monthly: list[MonthlyFinance]
    from_month: str | None = None
    to_month: str | None = None
