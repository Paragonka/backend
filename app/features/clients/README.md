# Clients

Client management for small businesses (bakeries, coffee shops, cafes).

**Models/tables:** `Client` — name, surname, phone, notes, custom_fields (JSONB), local_fields (JSONB)

**API routes:**
- `GET /api/v1/clients` — list with cursor-based pagination and filtering (+EAV)
- `POST /api/v1/clients` — create
- `GET /api/v1/clients/{id}` — details
- `PUT /api/v1/clients/{id}` — update
- `DELETE /api/v1/clients/{id}` — archive (soft-delete)
- `POST /api/v1/clients/import` — CSV import

**Web routes:** `/app/{org_id}/clients` — list, create, edit, import (HTMX)

**Dependencies:** orgs (org_id FK), eav (custom_fields validation)
