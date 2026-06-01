# Auth

JWT authentication: registration, login, refresh, logout, password change.

**Models/tables:** no own model (uses `users.User`)

**API routes:**
- `POST /api/v1/auth/register` — registration (returns access + refresh tokens)
- `POST /api/v1/auth/login` — login
- `POST /api/v1/auth/refresh` — refresh access token
- `POST /api/v1/auth/logout` — clear cookie
- `POST /api/v1/auth/change-password` — change password (requires auth)

**Web routes:** `/auth/login`, `/auth/register` — login and registration pages; `/auth/logout` — logout

**Dependencies:** users
