# Organizations

Organization, settings, and invite management.

**Models/tables:** `Organization` — name, owner_id, timezone; `OrganizationSetting` — org_id, key, value; `UserOrg` — user_id, org_id; `Invite` — org_id, email, token, expires_at

**API routes:**
- `POST /api/v1/orgs` — create organization
- `GET /api/v1/orgs` — list user's organizations
- `GET /api/v1/orgs/{id}` — details
- `GET /api/v1/orgs/{id}/settings` — settings
- `PUT /api/v1/orgs/{id}/settings` — update settings

**Web routes:** `/orgs/select` — organization selector; `/app/{org_id}/dashboard` — dashboard; `/app/{org_id}/settings` — settings

**Dependencies:** users (owner_id FK)
