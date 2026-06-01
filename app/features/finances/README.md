# Finances

Financial analytics: revenue (Orders), expenses (Receipts), PnL.

**Models/tables:** no own model (SQL aggregations over orders and receipts)

**API routes:**
- `GET /api/v1/finances/summary?months=12` — summary (total_revenue, total_expenses, total_pnl, monthly[])

**Web routes:** `/app/{org_id}/finances` — dashboard with Chart.js (metrics, bar chart, table)

**Dependencies:** orders, receipts, orgs
