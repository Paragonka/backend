# EAV

Entity-Attribute-Value: custom fields for clients, products, and orders.

**Models/tables:** `EavAttribute` — org_id, entity_code (client/product/order), code, name, field_type, is_required

**API routes:**
- `POST /api/v1/eav/attributes` — create attribute
- `GET /api/v1/eav/attributes` — list (filter by entity_code)
- `DELETE /api/v1/eav/attributes/{id}` — delete

**Web routes:** `/app/{org_id}/eav` — attribute management (HTMX)

**Dependencies:** orgs (org_id FK)
