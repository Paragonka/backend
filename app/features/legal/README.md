# Legal

Legal pages and user consent management.

**Models/tables:** `UserConsent` — user_id, consent_type, ip_address, user_agent, agreed_at

**API routes:**
- `POST /api/v1/consent/cookie` — record cookie consent

**Web routes:** `/privacy`, `/terms`, `/cookie` — static legal pages (i18n)

**Dependencies:** none
