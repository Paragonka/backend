# Media

Photo upload and serving via S3 (MinIO).

**Models/tables:** none (keys stored in JSONB `photos` fields on entities)

**API routes:**
- `POST /api/v1/media/upload/{entity_type}/{entity_id}` — upload photo (products/orders/clients)
- `GET /api/v1/media/{key}` — redirect to presigned URL

**Web routes:** none

**Dependencies:** orgs (org_id in S3 key)
