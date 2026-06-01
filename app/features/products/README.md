# Products

Unified product model (good/service/material).

**Models/tables:** `Product` — org_id, name, category, unit, product_type (good/service/material), price, cost_price, stock_qty, track_inventory, is_sellable, is_active, custom_fields (JSONB), photos (JSONB), local_fields (JSONB)

**API routes:**
- `GET /api/v1/products` — list with cursor-based pagination and filtering (+EAV)
- `POST /api/v1/products` — create
- `GET /api/v1/products/{id}` — details
- `PUT /api/v1/products/{id}` — update
- `DELETE /api/v1/products/{id}` — delete
- `POST /api/v1/products/import` — CSV import

**Web routes:** `/app/{org_id}/products` — list, create, edit, import (HTMX)

**Dependencies:** orgs (org_id FK), eav (custom_fields validation)
