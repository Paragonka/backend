# Receipts

Expense receipt tracking (manual entry and JPK_KASA import).

**Models/tables:** `Receipt` — org_id, client_id, order_id, receipt_date, total, source, raw_data (JSONB), notes; `ReceiptItem` — receipt_id, product_id, name, price, qty

**API routes:**
- `POST /api/v1/receipts` — create
- `GET /api/v1/receipts` — list with pagination/filtering
- `GET /api/v1/receipts/{id}` — details
- `GET /api/v1/receipts/{id}/items` — list items
- `DELETE /api/v1/receipts/{id}` — delete

**Web routes:** `/app/{org_id}/receipts` — list; create; details; JPK upload

**Dependencies:** clients (client_id FK), orders (order_id FK), products (product_id FK), orgs (org_id FK)
