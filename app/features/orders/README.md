# Orders

Order management: creation, items, statuses, material write-offs.

**Models/tables:** `Order` — org_id, client_id, status, total, execution_date, notes, photos (JSONB), local_fields (JSONB); `OrderItem` — order_id, product_id, name, price, qty; `WriteOff` — org_id, order_item_id, product_id, qty, reason

**API routes:**
- `POST /api/v1/orders` — create
- `GET /api/v1/orders` — list with pagination/filtering
- `GET /api/v1/orders/{id}` — details
- `POST /api/v1/orders/{id}/items` — add item
- `GET /api/v1/orders/{id}/items` — list items
- `DELETE /api/v1/orders/{id}/items/{item_id}` — remove item
- `POST /api/v1/orders/{id}/write-offs` — write off materials for an item (`{order_item_id, qty, reason}`; product resolved server-side from item)
- `POST /api/v1/orders/{id}/status` — change status

**Web routes:** `/app/{org_id}/orders` — list; `/app/{org_id}/orders/create` — create; `/app/{org_id}/orders/{id}` — details; `/app/{org_id}/calendar` — calendar

**Dependencies:** clients (client_id FK), products (product_id FK), orgs (org_id FK)
