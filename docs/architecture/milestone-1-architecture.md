# BrahmaAI Studio — Milestone 1 Architecture

## Runtime boundaries

- `frontend/` is a Next.js browser client. It never stores passwords or authoritative engineering measurements.
- `backend/` is a FastAPI application. It owns authentication, persistence, validation, and future project/domain services.
- PostgreSQL is the selected persistent database. PostGIS is available in the Compose image for later spatial features; the first auth migration does not yet require spatial columns.
- SQLAlchemy models define persistence entities; Alembic owns production schema changes.

## Authentication design

1. Registration normalizes the email and hashes the password with Argon2id.
2. Login creates a high-entropy opaque token and a per-session CSRF token.
3. The browser receives the opaque token only as an HttpOnly cookie. The database stores only its SHA-256 digest.
4. The CSRF token is returned to the authenticated client and must accompany state-changing authenticated requests in `X-CSRF-Token`.
5. Logout revokes the server-side session and clears the browser cookie.
6. Session expiry is checked on every authenticated request.

## Database and migrations

- `DATABASE_URL` configures SQLAlchemy.
- `alembic upgrade head` applies migrations.
- `Base.metadata.create_all()` is exposed only as an explicit app-factory option for isolated tests; production startup relies on migrations.
- SQLite is used only for deterministic unit tests. PostgreSQL remains the intended runtime database.

## Health semantics

`GET /api/v1/health` returns `database=not_configured` when no database URL is provided, `database=connected` after a successful `SELECT 1`, and HTTP 503 when a configured database is unreachable.

## Deferred components

Project/plot CRUD, geometry, Brahma's command interpreter, 2D/3D rendering, billing, collaboration and engineering solvers are not part of this foundation slice. Their interfaces will be introduced in subsequent approved work packages.
