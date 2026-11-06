# BrahmaAI Studio

<p align="center">
  <strong>Imagine Beyond Boundaries. Build Within Possibilities.</strong><br />
  A practical, geometry-aware workspace for planning homes and spaces.
</p>

<p align="center">
  <a href="https://github.com/fried-brain/brahmaai-studio"><img alt="Repository" src="https://img.shields.io/badge/GitHub-brahmaai--studio-181717?logo=github" /></a>
  <img alt="Frontend" src="https://img.shields.io/badge/Frontend-Next.js%2015-black?logo=next.js" />
  <img alt="Backend" src="https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi" />
  <img alt="Database" src="https://img.shields.io/badge/Database-PostgreSQL%20%2B%20PostGIS-4169E1?logo=postgresql" />
  <img alt="AI" src="https://img.shields.io/badge/AI-Local--first-7C3AED" />
</p>

---

## What is BrahmaAI Studio?

**BrahmaAI Studio** is a web-first architectural planning application that brings plot setup, 2D floor-plan editing, furniture planning, and AI-assisted design workflows into one workspace.

The goal is to make early-stage spatial planning easier to explore and revise—while keeping geometry validation, user review, and explicit approval at the centre of the workflow.

The current implementation focuses on **validated 2D planning**. It is not a CAD/BIM replacement and does not claim to produce certified construction documents.

## At a glance

| Area | What is available |
|---|---|
| Project workspace | Account-based projects and plot configuration |
| Plot geometry | Rectangular and polygon plot data, unit normalization and validation |
| 2D floor studio | Room drawing, moving, resizing, vertex editing, floors, undo/redo and SVG export |
| Architectural elements | Wall thickness, door/window openings and conceptual staircase previews |
| Design analysis | Room area, window-area indicators, wall classification and room adjacency |
| AI design assistant | Project conversations, clarifications and structured draft proposals |
| Floor-plan generation | Bounded deterministic search, multiple candidate layouts and approval-gated application |
| Furniture studio | Room-aware catalog, placement, rotation, editing, duplication and persistence |
| Optimization review | Furniture arrangement candidates, opening suggestions and usability findings |

## Product principles

- **Geometry before appearance.** Plans are checked against plot boundaries and room-overlap rules.
- **AI assists; users decide.** Model output is treated as untrusted input and validated before it can affect a saved plan.
- **Preview is not save.** Drafts and optimization candidates remain separate from the saved layout until the user explicitly applies one.
- **Local-first AI.** An optional Ollama-compatible runtime can be used; the assistant does not silently fall back to a cloud model.
- **Honest scope.** Heuristic planning indicators are labelled as such, not presented as engineering certification.

## Screens and workflows

### 1. Project and plot setup
Create a project, select its category, and define a plot. Rectangular plot dimensions accept `mm`, `cm`, `m`, `in`, or `ft`; values are normalized to millimetres. The API also supports validated polygon boundaries.

### 2. Interactive 2D floor studio
Draw rooms, select and move them, resize corners, reshape polygon vertices, edit room details, switch floors, undo/redo changes, and export an SVG. The backend remains authoritative for plot containment and geometry validation.

### 3. Architectural planning tools
Add wall thickness and wall-anchored door/window openings. Inspect room adjacency and simplified door-connected circulation. The staircase preview calculates conceptual dimensions for straight, L-turn, and U-turn arrangements.

### 4. AI-assisted design
Chat with the project-scoped assistant, answer clarifying questions, and review structured proposals. The optional local model interprets requirements; deterministic code owns geometry generation and validation.

### 5. Floor-plan options
Generate up to three candidate layouts for supported orthogonal rectangular plots. Compare candidate assumptions and scores, edit a preview, then explicitly apply or reject it. Search is bounded: reaching its budget is reported as incomplete, not as proof that no other arrangement exists.

### 6. Furniture planning and review
Place and edit metric furniture footprints in supported room types. Preview deterministic arrangement candidates, compare alternatives, and apply a selected candidate only after server-side validation. Opening suggestions and usability findings are advisory and do not silently alter the plan.

## Architecture

```text
brahmaai-studio/
├── backend/              FastAPI API, SQLAlchemy models, Alembic migrations, tests
├── frontend/             Next.js app, interactive 2D studio and furniture editor
├── docs/                 API contracts, design notes and implementation plans
├── infrastructure/       Deployment and operations assets (where present)
├── docker-compose.yml    Local PostgreSQL/PostGIS and API services
├── progress.md           Verification notes and implementation ledger
└── README.md
```

### Technology stack

| Layer | Technology |
|---|---|
| Web application | Next.js 15, React 19, TypeScript |
| API | Python 3.11+, FastAPI, Pydantic |
| Persistence | PostgreSQL, PostGIS, SQLAlchemy |
| Schema migrations | Alembic |
| Authentication | Argon2id password hashing, opaque HttpOnly sessions, CSRF protection |
| Local AI integration | Ollama-compatible HTTP runtime (optional) |
| Geometry and planning | Deterministic validation and bounded spatial-search algorithms |
| Tests | Pytest and Node.js built-in test runner |

## Getting started

### Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- Docker Engine and Docker Compose
- Git

### Option A — Start the database and API with Docker

1. Clone the repository:

   ```bash
   git clone https://github.com/fried-brain/brahmaai-studio.git
   cd brahmaai-studio
   ```

2. Set a local database password. For example:

   ```bash
   export POSTGRES_PASSWORD="replace-with-a-strong-local-password"
   ```

   On Windows PowerShell, use:

   ```powershell
   $env:POSTGRES_PASSWORD = "replace-with-a-strong-local-password"
   ```

3. Build and start PostgreSQL/PostGIS and the API:

   ```bash
   docker compose up --build
   ```

   The API container waits for the database health check and runs Alembic migrations before starting FastAPI.

4. In a second terminal, start the frontend:

   ```bash
   cd frontend
   cp .env.example .env.local
   npm ci
   npm run dev
   ```

5. Open the application:

   - Web app: [http://localhost:3000](http://localhost:3000)
   - API health: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
   - Interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Option B — Run the backend directly

Start a PostgreSQL instance first, then:

```bash
cd backend
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -e '.[test]'
cp .env.example .env
```

Edit `backend/.env` and set `DATABASE_URL` to your PostgreSQL connection string. Then run:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
cp .env.example .env.local
npm ci
npm run dev
```

## Configuration

The repository includes example environment files. Copy them for local use and replace values as needed. **Never commit real credentials, production secrets, or private user data.**

### Backend — `backend/.env`

| Variable | Purpose | Example / default |
|---|---|---|
| `APP_ENV` | Runtime environment | `development` |
| `DATABASE_URL` | SQLAlchemy database connection | PostgreSQL URL |
| `SESSION_COOKIE_NAME` | Session cookie name | `bas_session` |
| `SESSION_TTL_HOURS` | Session lifetime | `24` |
| `SECURE_COOKIES` | HTTPS-only cookie transport | `false` locally; `true` in production |
| `CORS_ORIGINS` | Allowed browser origins | `http://localhost:3000` |
| `LOCAL_LLM_ENABLED` | Enable local model integration | `false` |
| `LOCAL_LLM_BASE_URL` | Reachable local model endpoint | `http://127.0.0.1:11434` |
| `LOCAL_LLM_MODEL` | Installed model identifier | Set explicitly when enabling |

Additional local-model timeout and context limits are documented in `backend/.env.example`.

### Frontend — `frontend/.env.local`

| Variable | Purpose | Local default |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Browser-visible API base URL | `http://localhost:8000/api/v1` |

For deployment, use the public HTTPS API URL and configure the backend CORS allowlist to the exact frontend origin. Set `SECURE_COOKIES=true` when serving over HTTPS. Use a managed secret store and a strong, unique database password; do not use the Compose development fallback in production.

### Optional local AI runtime

BrahmaAI Studio can connect to an already-running Ollama-compatible model endpoint. Local inference is disabled by default. To enable it:

1. Install and run a compatible local model runtime yourself.
2. Pull or otherwise make an appropriate model available in that runtime.
3. Set `LOCAL_LLM_ENABLED=true`, `LOCAL_LLM_BASE_URL`, and `LOCAL_LLM_MODEL` in the backend environment.
4. Ensure the FastAPI process can reach that endpoint.

When the API runs inside Docker, `127.0.0.1` refers to the API container—not the host machine or another container. Use a reachable service hostname or network address. The application does not install the runtime or download model weights, and it does not use a cloud fallback. See [`docs/api/local-llm.md`](docs/api/local-llm.md).

## Security model

- Passwords are hashed using Argon2id; plaintext passwords are not stored.
- Login uses a high-entropy opaque session token in an HttpOnly, SameSite=Lax cookie.
- Only a SHA-256 hash of the session token is persisted.
- Authenticated write requests require the session-specific `X-CSRF-Token` header.
- Project, conversation, and proposal resources are scoped to their owner.
- AI-generated and edited geometry is validated by deterministic server-side rules before application.
- Production deployments should use HTTPS, secure cookies, exact CORS origins, managed secrets, and a non-default database password.

## API overview

All API routes are prefixed with `/api/v1`.

| Area | Representative endpoints |
|---|---|
| Health | `GET /health` |
| Authentication | `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/logout` |
| Projects | `POST /projects`, `GET /projects`, `GET /projects/{project_id}` |
| Plot | `PUT /projects/{project_id}/plot` |
| Floor layout | `PUT /projects/{project_id}/layout`, `GET /projects/{project_id}/layout/{floor_number}` |
| Design assistant | `POST /projects/{project_id}/assistant/message` |
| Floor-plan generation | `POST /projects/{project_id}/assistant/layout-generation` |
| Optimization | `POST /projects/{project_id}/design-optimization/preview`, `POST /projects/{project_id}/design-optimization/apply` |

See [`docs/api/projects.md`](docs/api/projects.md), [`docs/api/design-assistant.md`](docs/api/design-assistant.md), and [`docs/api/local-llm.md`](docs/api/local-llm.md) for request/response details and limitations.

## Development and tests

### Backend tests

```bash
cd backend
pip install -e '.[test]'
pytest -q
```

### Frontend tests and checks

```bash
cd frontend
npm ci
npm run test:geometry
npm run lint
npm run build
```

The Node.js geometry suite uses the built-in test runner and does not require a separate test framework. Lint/build output may include non-fatal warnings; review the actual command exit status and output rather than treating warnings as test failures.

### Latest recorded verification

The latest development verification recorded for the current WP5E implementation:

| Check | Recorded result |
|---|---|
| Backend test suite | **166 passed** |
| Frontend geometry tests | **20 passed** |
| Python compilation | Passed |
| SQLite migration regression | Passed |
| Frontend production build | Completed successfully in the development workspace |
| Frontend lint | 0 errors; 3 warnings |
| Production dependency audit (`npm audit --omit=dev`) | 0 vulnerabilities reported |
| Full dependency audit | 6 moderate findings in development dependencies at the time checked |

These results are a development snapshot, not a guarantee for every deployment environment. Live PostgreSQL/PostGIS, live local-model integration, browser end-to-end behavior, and production hosting still require environment-specific verification. Review [`progress.md`](progress.md) for the implementation ledger and additional evidence.

## Current scope and limitations

BrahmaAI Studio is an early-stage planning tool. The current implementation does **not**:

- Perform structural calculations or certify load-bearing capacity.
- Certify compliance with local building codes, Vastu requirements, accessibility rules, fire safety, or egress standards.
- Simulate daylight, ventilation, occupant behaviour, HVAC, plumbing, or electrical systems.
- Replace a measured site survey or qualified architect/engineer review.
- Provide a complete 3D CAD/BIM workflow or certified construction-document output.

Furniture dimensions and clearances are planning inputs or heuristics, not manufacturer specifications or statutory minima. Staircase and circulation indicators are conceptual. Always verify site conditions and have proposed designs reviewed by appropriately qualified local professionals before construction.

## Roadmap

The following are directions for continued development, not claims that these capabilities are already complete:

- Production deployment and live database verification.
- Stronger browser-level and end-to-end regression coverage.
- Continued refinement of the 2D editing experience and architectural components.
- Expanded local AI workflows with transparent assumptions and safe review controls.
- Future 3D planning capabilities, subject to a separate validated implementation.

## Contributing

Contributions, issue reports, and thoughtful design feedback are welcome.

- Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before submitting changes.
- Review [`SECURITY.md`](SECURITY.md) for vulnerability reporting.
- Keep tests and documentation aligned with behavior.
- Do not include secrets, personal data, or unlicensed third-party assets.

## License

**No open-source license has been selected yet.** Until a license is added to this repository, no general permission is granted to use, modify, or redistribute this code. Contact the repository owner for permission.

---

<p align="center">
  <strong>BrahmaAI Studio</strong><br />
  <em>Plan thoughtfully. Validate carefully. Build responsibly.</em>
</p>
