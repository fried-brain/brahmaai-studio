# Production deployment

This guide describes the first hosted topology for BrahmaAI Studio:

- Frontend: Vercel (Next.js).
- API: Render Docker web service.
- Database: managed PostgreSQL; enable PostGIS if required by the selected provider. Supabase is one option.
- AI: local-model integration remains disabled on the hosted API by default. No cloud AI fallback is configured.

Do not deploy real user data until the production checklist below is complete.

## Database

Create a production PostgreSQL project. Keep it in a region close to the API. Use a direct PostgreSQL connection string for migrations unless the provider documents compatibility with its pooler and the psycopg driver.

DATABASE_URL must use this SQLAlchemy driver prefix:

    postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE

URL-encode special characters in credentials. Never commit this URL. Confirm network reachability, migration privileges, automated backups, and a tested restore procedure before deploying.

## API on Render

The repository root contains render.yaml. It defines the backend Docker service, a pre-deploy Alembic migration, and the readiness health check.

1. Connect fried-brain/brahmaai-studio to Render.
2. Create a Blueprint instance and review the proposed resources and price before applying.
3. Set DATABASE_URL to the production database connection string.
4. Set CORS_ORIGINS to the exact Vercel production origin, e.g. https://your-app.vercel.app.
5. Keep APP_ENV=production, SECURE_COOKIES=true, and LOCAL_LLM_ENABLED=false.
6. Deploy and inspect build, migration, startup, and health-check logs.

The Blueprint selects Render's starter web-service plan so its pre-deploy migration command is available. Review current pricing before approving resource creation. Committing this file does not create a service.

## Frontend on Vercel

1. Import fried-brain/brahmaai-studio into Vercel.
2. Set Root Directory to frontend.
3. Use detected Next.js settings and package-lock-based install.
4. Set NEXT_PUBLIC_API_BASE_URL to the deployed API origin plus /api/v1, e.g. https://YOUR-API.onrender.com/api/v1.
5. Deploy a preview first. Test sign-in, project creation, layout editing, and furniture persistence with a non-production test account.
6. Set Render CORS_ORIGINS to the exact frontend origin and redeploy the API.

Do not use wildcard CORS origins with credentialed session cookies.

## Health endpoints

- GET /api/v1/health/live: process liveness only; independent of PostgreSQL.
- GET /api/v1/health: readiness. Returns HTTP 200 only when the configured database responds to SELECT 1. In production, missing database configuration returns HTTP 503.

Use readiness for Render health checks and liveness for container process checks.

## Migration policy

Schema changes are managed by Alembic. Render's pre-deploy command applies migrations before the new service version starts. A migration failure must fail the deployment.

Manual operations:

    cd backend
    alembic current
    alembic upgrade head

Take a database backup before production migrations that change or remove data. Prefer additive migrations and deploy compatible application code before removing old columns or constraints. Never use Base.metadata.create_all() as a production migration strategy.

## Release verification

After each deployment:

1. GET /api/v1/health/live returns HTTP 200.
2. GET /api/v1/health returns HTTP 200 and database=connected.
3. Register and sign in with a dedicated test account.
4. Create a project and save plot data.
5. Create and edit a room layout; reload and verify persistence.
6. Place, edit, and reload furniture.
7. Verify authenticated write requests reject missing or invalid CSRF tokens.
8. Verify a second account cannot read or mutate the first account's project.
9. Verify browser requests from the configured frontend origin succeed and an unapproved origin is rejected.
10. Confirm backups and restore instructions are available.

Do not describe the application as production-ready until these checks pass on the actual hosted services.

## Rollback

If a release fails health checks, inspect Render build, migration, and runtime logs. Roll back the application to the last healthy deploy. Do not automatically downgrade the database schema; forward-fix migrations are safer for deployed data. Restore from backup only after assessing data loss and obtaining an explicit operator decision.

## Local verification

    cd backend
    python -m pip install -e '.[test]'
    pytest -q

    cd ../frontend
    npm ci
    npm run test:geometry
    npm run lint
    npm run build
