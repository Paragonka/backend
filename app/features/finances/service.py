from collections import OrderedDict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.core.log import get_logger
from app.core.uow import AppUnitOfWork
from app.features.finances.schemas import FinanceSummaryResponse, MonthlyFinance
from app.features.orders.models import Order
from app.features.receipts.models import Receipt
from app.shared.constants import ORDER_STATUS_DONE
from app.shared.exceptions import AppHttpException

logger = get_logger(__name__)


class FinancesService:
    def __init__(self, uow: AppUnitOfWork):
        self.uow = uow

    async def get_summary(
        self,
        org_id: str,
        months: int = 12,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> FinanceSummaryResponse:
        async with self.uow:
            all_months: list[str] = self._build_months(
                months=months, date_from=date_from, date_to=date_to
            )
            from_month = all_months[0]
            to_month = all_months[-1]

            logger.debug(
                "finance_summary",
                org_id=org_id,
                months=months,
                date_from=date_from,
                date_to=date_to,
            )

            monthly_map: dict[str, dict] = OrderedDict()

            for m in all_months:
                monthly_map[m] = {"revenue": Decimal(0), "expenses": Decimal(0)}

            revenue_rows = await self._get_monthly_revenue(org_id, from_month, to_month)

            for row in revenue_rows:
                month_key = str(row[0])

                if month_key in monthly_map:
                    monthly_map[month_key]["revenue"] = row[1] or Decimal(0)

            expense_rows = await self._get_monthly_expenses(
                org_id, from_month, to_month
            )

            for row in expense_rows:
                month_key = str(row[0])

                if month_key in monthly_map:
                    monthly_map[month_key]["expenses"] = row[1] or Decimal(0)

            total_revenue = Decimal(0)
            total_expenses = Decimal(0)
            monthly_list: list[MonthlyFinance] = []

            for month_key, vals in monthly_map.items():
                rev = vals["revenue"]
                exp = vals["expenses"]
                pnl = rev - exp
                total_revenue += rev
                total_expenses += exp
                monthly_list.append(
                    MonthlyFinance(month=month_key, revenue=rev, expenses=exp, pnl=pnl)
                )

            return FinanceSummaryResponse(
                total_revenue=total_revenue,
                total_expenses=total_expenses,
                total_pnl=total_revenue - total_expenses,
                monthly=monthly_list,
                from_month=from_month,
                to_month=to_month,
            )

    @staticmethod
    def _parse_date(value: str, name: str) -> str:
        """Parse a 'YYYY-MM-DD' string and return its 'YYYY-MM' month bucket."""

        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except (TypeError, ValueError) as e:
            raise AppHttpException(
                message=f"Invalid {name}: expected format 'YYYY-MM-DD', got {value!r}",
                status_code=422,
                code="INVALID_DATE",
            ) from e

        return f"{parsed.year:04d}-{parsed.month:02d}"

    def _build_months(
        self, months: int, date_from: str | None, date_to: str | None
    ) -> list[str]:
        if (date_from is None) != (date_to is None):
            missing = "date_to" if date_from is None else "date_from"

            raise AppHttpException(
                message=(
                    "Both 'date_from' and 'date_to' must be provided together when "
                    f"using a date range; missing '{missing}'."
                ),
                status_code=400,
                code="DATE_RANGE_INCOMPLETE",
            )

        if date_from is None and date_to is None:
            now = datetime.now()
            all_months: list[str] = []
            y, m = int(now.year), int(now.month)

            for _ in range(months):
                all_months.append(f"{y:04d}-{m:02d}")
                m -= 1

                if m == 0:
                    m = 12
                    y -= 1

            all_months.reverse()

            return all_months

        assert date_from is not None  # noqa: S101
        assert date_to is not None  # noqa: S101

        from_month = self._parse_date(date_from, "date_from")
        to_month = self._parse_date(date_to, "date_to")

        if from_month > to_month:
            raise AppHttpException(
                message="'date_from' must not be later than 'date_to'.",
                status_code=400,
                code="DATE_RANGE_INVALID",
            )

        from_y, from_m = int(from_month[:4]), int(from_month[5:7])
        to_y, to_m = int(to_month[:4]), int(to_month[5:7])
        all_months = []
        y, m = from_y, from_m

        while (y, m) <= (to_y, to_m):
            all_months.append(f"{y:04d}-{m:02d}")
            m += 1

            if m > 12:
                m = 1
                y += 1

        return all_months

    async def _get_monthly_revenue(
        self, org_id: str, from_month: str, to_month: str
    ) -> list[tuple[str, Decimal]]:
        stmt = (
            select(
                func.substr(Order.execution_date, 1, 7).label("month"),
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
            )
            .where(Order.org_id == org_id)
            .where(Order.status == ORDER_STATUS_DONE)
            .where(Order.execution_date >= from_month)
            .where(Order.execution_date < self._next_month_start(to_month))
            .group_by("month")
            .order_by("month")
        )
        result = await self.uow.session.execute(stmt)
        rows = result.all()

        return [(r[0], Decimal(str(r[1]))) for r in rows]

    async def _get_monthly_expenses(
        self, org_id: str, from_month: str, to_month: str
    ) -> list[tuple[str, Decimal]]:
        stmt = (
            select(
                func.substr(Receipt.receipt_date, 1, 7).label("month"),
                func.coalesce(func.sum(Receipt.total), 0).label("expenses"),
            )
            .where(Receipt.org_id == org_id)
            .where(Receipt.receipt_date >= from_month)
            .where(Receipt.receipt_date < self._next_month_start(to_month))
            .group_by("month")
            .order_by("month")
        )
        result = await self.uow.session.execute(stmt)
        rows = result.all()

        return [(r[0], Decimal(str(r[1]))) for r in rows]

    @staticmethod
    def _next_month_start(ym: str) -> str:
        y, m = int(ym[:4]), int(ym[5:7])

        if m == 12:
            return f"{y + 1:04d}-01-01"

        return f"{y:04d}-{m + 1:02d}-01"
