# BrahmaAI Studio

**Imagine Beyond Boundaries. Build Within Possibilities.**

BrahmaAI Studio is an independently developed, web-first architectural planning platform. It combines a FastAPI service, PostgreSQL persistence, secure account sessions, an interactive 2D floor-plan editor, a local-first design assistant, deterministic floor-plan optimization, and an editable furniture-planning studio. The current release focuses on validated 2D geometry and approval-gated planning workflows. 3D editing and Brahma command execution remain future work and are not represented as complete.

## Repository layout

```text
backend/       FastAPI service, SQLAlchemy models, Alembic migrations, tests
frontend/      Next.js web client
infrastructure/ deployment and operations assets
```

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- Docker with Compose (recommended for PostgreSQL/PostGIS)

## Local development with Docker

1. Copy `backend/.env.example` to `backend/.env` for direct backend development, or set `POSTGRES_PASSWORD` in your shell for Compose.
2. Start the database and API:

   ```bash
   docker compose up --build
   ```

3. In a second terminal, start the web client:

   ```bash
   cd frontend
   cp .env.example .env.local
   npm install
   npm run dev
   ```

4. Open `http://localhost:3000`. API documentation is available at `http://localhost:8000/docs` and health at `http://localhost:8000/api/v1/health`.

The Compose API service applies Alembic migrations before starting. For production, set a strong `POSTGRES_PASSWORD`, set `SECURE_COOKIES=true`, configure the exact frontend origin, terminate TLS at the ingress, and use a managed secret store. Do not deploy with the example password.

## Backend without Docker

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
cp .env.example .env
# Ensure PostgreSQL is running and DATABASE_URL points to it.
alembic upgrade head
uvicorn app.main:app --reload
```

## Tests

```bash
cd backend
pip install -e '.[test]'
pytest -q
```

Tests use isolated in-memory SQLite databases for deterministic behavior. PostgreSQL is the selected production database; SQLite in tests is not a change to that decision.

## Authentication behavior

- Registration normalizes email addresses to lowercase.
- Passwords are hashed with Argon2id through `argon2-cffi`; plaintext passwords are never stored.
- Login issues a high-entropy opaque session token in an HttpOnly, SameSite=Lax cookie.
- Only a SHA-256 hash of the session token is persisted.
- Mutating authenticated requests require the per-session `X-CSRF-Token` header.
- Sessions expire after the configured `SESSION_TTL_HOURS` and are revocable at logout.
- Set `SECURE_COOKIES=true` behind HTTPS in production.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `APP_ENV` | Runtime environment label | `development` |
| `DATABASE_URL` | SQLAlchemy database URL | unset; database endpoints return `not_configured` |
| `SESSION_COOKIE_NAME` | Session cookie name | `bas_session` |
| `SESSION_TTL_HOURS` | Session lifetime | `24` |
| `SECURE_COOKIES` | Require HTTPS cookie transport | `false` |
| `CORS_ORIGINS` | Comma-separated allowed browser origins | `http://localhost:3000` |
| `NEXT_PUBLIC_API_BASE_URL` | Browser-visible API base URL | `http://localhost:8000/api/v1` |

## Project and plot API

- `POST /api/v1/projects` (authenticated, CSRF-protected)
- `GET /api/v1/projects` (authenticated)
- `GET /api/v1/projects/{project_id}` (owner only)
- `PATCH /api/v1/projects/{project_id}` (owner only, CSRF-protected)
- `PUT /api/v1/projects/{project_id}/plot` (owner only, CSRF-protected)
- `DELETE /api/v1/projects/{project_id}` (recoverable archive, owner only, CSRF-protected)

Rectangular plot dimensions accept `mm`, `cm`, `m`, `in`, or `ft`. Stored dimensions are normalized to millimetres. Polygon plots are supported through the authenticated API; the current dashboard form remains rectangular-only. Floor layouts accept room polygons in millimetres, validate plot containment and room overlap, and return deduplicated wall segments derived from room boundaries.

## Initial API

- `GET /api/v1/health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout` (requires `X-CSRF-Token`)

## Current status

| Capability | Status |
|---|---|
| FastAPI application factory and health endpoint | Implemented |
| SQLAlchemy database connection and models | Implemented |
| PostgreSQL/PostGIS Compose service | Configured; not live-tested in this environment |
| Alembic migrations through `0008_room_furniture` | Implemented; SQLite upgrade/downgrade/re-upgrade verified |
| Registration/login/logout | Implemented and unit-tested |
| Project CRUD and recoverable archive | Implemented and API-tested |
| Rectangular plot configuration and unit normalization | Implemented and API-tested |
| Browser project dashboard and create-project workflow | Implemented; production build verification pending |
| Next.js authentication shell | Implemented; browser build verification pending |
| Project management and rectangular plot configuration | Implemented and API-tested; live PostgreSQL verification pending |
| Rectangular plot unit normalization and area calculation | Implemented and tested |
| Polygon plot geometry and validation | Implemented and API-tested |
| Room geometry, floor layouts, derived walls, wall classification, room adjacency and door-connected circulation | Implemented and API-tested |
| BrahmaAI local LLM gateway, persistent conversations, structured proposals and approval-gated application | Implemented; live local model runtime and browser production verification pending |
| WP5D bounded spatial-search floor-plan optimization, room proportion preferences, circulation/utilization analysis, diverse candidate comparison and approval-gated application (extends WP5C) | Implemented; see current verification notes below |
| Interactive 2D room editor (draw, move, resize, reshape, openings, staircase planner, adjacency/circulation inspector, undo/redo, autosave, SVG export) | Implemented; browser production verification pending |
| WP5E furniture persistence, catalog, geometry validation, deterministic arrangements, opening suggestions, usability review and approval-gated optimization | Implemented; 166 backend tests and 20 frontend tests pass; browser production build and live PostgreSQL/Ollama verification pending |
| 3D editor | Planned |

## Engineering and safety boundary

This foundation does not perform structural engineering calculations, certify code compliance, or produce construction-ready documentation. Those capabilities require separate validated engineering implementations and qualified professional review.

### Work Package 3 — Plot geometry engine

The API accepts rectangular plots and validated polygon boundaries. Polygon geometry is stored in millimetres and returns deterministic area and perimeter calculations.

### Work Package 3B — Room and wall geometry engine

The API stores room polygons by project and floor, validates that rooms remain within the plot and do not overlap, calculates room areas/perimeters, and derives wall segments from room edges. Shared room edges are deduplicated. See `docs/api/projects.md` for endpoints and payload examples. This is a geometric foundation, not a construction or code-compliance certification.

### Work Package 3C — Interactive 2D studio

The browser client now includes a project-linked 2D floor editor. It draws rooms by drag, supports room selection/movement, corner resizing and polygon vertex reshaping, room metadata edits, deletion, undo/redo, floor switching, debounced autosave, derived wall display, and SVG export. The API validates geometry when saving and supports clearing a floor layout. The editor is a geometric planning surface, not a certified construction drawing tool. Door/window openings, wall thickness, vertex insertion/removal, 3D editing, live PostgreSQL validation, and browser production-build verification remain pending.


## Work Package 4A — Parametric architectural components

The floor-layout model now supports per-room wall thickness (75–500 mm, default 150 mm) and wall-anchored door/window openings. Openings use a boundary edge index, offset, width, height, and sill height, are persisted with room geometry, and are shown as editable markers in the 2D studio. The API rejects openings that extend beyond an edge, overlap one another on the same edge, reference missing edges, or use invalid door sill/vertical dimensions. This is geometric authoring support only; it does not establish structural adequacy, accessibility, fire safety, or code compliance.

### Parametric staircase concept preview (WP4B)

The 2D studio includes a staircase calculator for straight, L-turn and U-turn concepts. It balances the riser count against the floor-to-floor height, reports actual riser height, total goings, flight split and longest flight run, and flags the 2R+T proportion against a clearly labeled reference band. It is a conceptual dimensional aid—not a code-compliance, accessibility, fire-safety or structural approval.

### Work Package 4C — Openings, wall classification & circulation

- Door openings support a stored swing direction (`left`, `right`, or `none`). Window swing direction is rejected; window head height is reported as sill height plus opening height.
- Floor-layout responses classify each room wall segment as `external` when it lies on the saved plot boundary, otherwise `internal` (a geometric label, not a material specification).
- Exact shared wall segments produce room-adjacency records with shared length and a `connected_by_door` indicator.
- Door-connected adjacency is converted into circulation components, making isolated rooms visible in the studio inspector.
- Adjacency currently recognizes exact shared full-edge matches. Partial collinear overlaps, door clearances, swing arcs, accessible routes, and egress compliance are not analysed.


## Design intelligence indicators (WP4D)

The floor studio includes an early-stage daylight/ventilation planning panel. It reports each room's floor area, number of windows, gross window opening area and window-opening-area-to-floor-area ratio. The ratio is a geometric screening indicator only: it is not a daylight simulation, ventilation model, or code-compliance calculation. Orientation, glazing, shading, external obstructions, airflow paths, climate and actual free opening area are not modelled.

An optional traditional Vastu reference mode displays general room-type guidance. It is explicitly cultural/traditional context, not scientific evidence, a mandatory design rule, or engineering advice.

API: `GET /api/v1/projects/{project_id}/design-analysis/{floor_number}?include_vastu=false`. Requires an authenticated owner session.

## BrahmaAI Design Assistant (WP5A)

The 2D Studio includes a first-release assistant panel. It uses a deterministic local rules engine to extract a small set of room requirements, ask clarifying questions, and inspect saved room/opening records. It returns structured draft briefs and review suggestions without changing the floor plan. The initial rules-based assistant was subsequently extended by WP5B with optional local-model interpretation and persistent project-scoped conversations. See `docs/api/design-assistant.md` for the API contract and limitations.

### Local AI design assistant (WP5B)

The assistant can connect to an already-running Ollama-compatible local model runtime. Local inference is disabled by default and never falls back to a cloud provider. Configure `LOCAL_LLM_ENABLED=true`, set `LOCAL_LLM_MODEL` to an installed model name, and set `LOCAL_LLM_BASE_URL` to an endpoint reachable from the FastAPI process. The authenticated `GET /api/v1/assistant/status` endpoint reports readiness without disclosing the configured endpoint. The API does not install a model runtime or download model weights.

WP5B adds persistent project/floor-scoped conversations, bounded multi-turn context, strict structured model responses, deterministic geometry preflight, and editable layout proposals. Proposal previews are isolated from the saved 2D plan and autosave. Only the explicit Apply action revalidates and atomically saves a proposal; Reject leaves saved geometry unchanged.

When the API runs in Docker, `127.0.0.1` points to the API container itself, not the host or another service. Configure a backend-reachable service hostname (for example, a Compose service name) when the model runtime runs separately. See `backend/.env.example` and `docs/api/local-llm.md` for runtime, timeout, history, API and safety details.

### WP5C + WP5D — AI-assisted floor-plan generation and spatial optimization

The 2D Studio has a separate **Generate floor-plan options** action. The configured local model only interprets the user's requirements into a strict typed planning brief; it never supplies room coordinates. The deterministic planner supports exact axis-aligned rectangular plots and emits up to three validated, editable room-layout candidates. Parking and explicitly requested corridor rooms are supported.

WP5D replaces WP5C's row-based shelf packing with bounded deterministic spatial search across room-order seeds, legal orientations and room-edge/corner anchors. It uses backtracking, overlap/containment pruning, mandatory adjacency/privacy gates and canonical memoization. Structured room aspect-ratio and long-axis preferences influence ranking without resizing hard dimensions. Candidate analysis reports door-connected room groups, assigned/unallocated plot area, leftover-space fragmentation, and a versioned score. The preview warns when the search budget is reached and when room groups are disconnected; neither a heuristic score nor a door-connectivity graph is a professional safety or compliance certification.

Each candidate is stored as an independent existing assistant proposal and can be restored from its conversation. The studio lets users compare candidates, switch previews, edit room names/types/vertices, and explicitly apply or reject the selected candidate. Preview and candidate switching never autosave; Apply revalidates against the current plot and base-layout fingerprint. Irregular plots are unsupported rather than approximated by a bounding rectangle. Search limits, room defaults and score weights are product heuristics; search exhaustion is not proof that no other arrangement exists. Free-text circulation/orientation notes remain unverified unless represented by structured fields. Long-axis orientation uses the plot's local axes; entrance-side mapping assumes a north-up local plan and must be checked against actual project orientation. This remains a conceptual layout generator, not a construction, structural, accessibility, fire-egress or regulatory compliance tool. See `docs/api/design-assistant.md` and the WP5D implementation plan for endpoint and algorithm details.

## WP5E — Complete Architectural Intelligence (planning release)

The 2D editor includes a metric furniture studio for bedroom, living, dining, kitchen, bathroom, study, and utility rooms. Add items from room-filtered presets, drag them within the plan, select them for coordinate and footprint editing, rotate in quarter turns, duplicate, or remove. Placed furniture is persisted with each room. Catalog dimensions are editable starter values, not product/manufacturer specifications.

Use **Preview arrangement** to request up to three deterministic furniture-layout candidates for supported orthogonal rectangular rooms. Compare candidate scores and assumptions, edit candidate coordinates/dimensions, and explicitly apply the selected candidate. The server rechecks the source-layout fingerprint and validates the complete layout before saving; a stale preview or invalid geometry is rejected. Use **Review usability & openings** for area accounting, furniture/clearance warnings, and advisory door/window placement suggestions. Suggestions do not automatically change existing openings.

The authenticated API exposes `POST /api/v1/projects/{project_id}/design-optimization/preview` (`furniture_arrangement`, `opening_suggestions`, or `full_review`) and explicit application at `POST /api/v1/projects/{project_id}/design-optimization/apply`. Preview is read-only; application is CSRF-protected and stale-preview safe. The planner uses bounded deterministic geometric heuristics and reports unsupported geometry rather than approximating it with bounding boxes.

**Limitations:** The planner does not simulate full door swing, occupant behaviour, daylight, airflow, structure, fire egress, accessibility, plumbing/electrical, HVAC, or local building-code compliance. Clearances are adjustable planning heuristics, not statutory minima. It is not CAD/BIM, does not produce certified construction documents, and does not replace qualified professional review or site verification.

## GitHub and contribution notes

- CI runs the backend pytest suite and dependency-free frontend Node.js tests on pushes and pull requests targeting `main`.
- Contribution guidance is in [`CONTRIBUTING.md`](CONTRIBUTING.md); security reporting guidance is in [`SECURITY.md`](SECURITY.md).
- Copy the supplied `.env.example` files for local configuration. Never commit real credentials or private project data.
- **License:** No open-source license has been selected for this repository yet. Until a license is added, the source is not granted an open-source reuse license.

## Verification snapshot

The latest recorded WP5E verification is 166 backend tests passing and 20 frontend Node.js tests passing. Python compilation and SQLite migration upgrade/downgrade regression checks passed. A full Next.js production build and semantic TypeScript check remain unverified because frontend dependencies were not installed in the development environment. Browser-level interaction, live PostgreSQL, and live local-model integration tests have not been run. See [`progress.md`](progress.md) for the detailed evidence and limitations.
