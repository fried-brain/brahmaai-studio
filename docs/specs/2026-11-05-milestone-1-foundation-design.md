# BrahmaAI Studio — Milestone 1 Design Specification

**Version:** 1.0
**Date:** 5 November 2026
**Status:** Proposed for user review
**Deployment:** Web application
**AI:** Local/rule-based intelligence; no paid AI API required
**Database:** PostgreSQL

## 1. Product objective

BrahmaAI Studio is a browser-based architectural design platform. Milestone 1 establishes persistent projects, plot configuration, deterministic geometry calculations, a project-aware local assistant, authentication foundations, and a maintainable application architecture for later 2D/3D design and engineering modules.

## 2. Architecture

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS and accessible component primitives.
- **Client state:** Zustand for editor/session UI state; server data fetched through typed API clients.
- **Backend:** Python FastAPI with Pydantic request/response schemas.
- **Persistence:** PostgreSQL, SQLAlchemy and Alembic migrations. PostGIS may be enabled for spatial capabilities where useful; basic plot geometry must not depend on PostGIS being present.
- **Geometry:** A backend domain package using deterministic algorithms and millimetres as the canonical internal length unit.
- **Brahma:** Local command interpreter and deterministic rule engine. It reads project state through application services and changes state only through validated commands.
- **Deployment:** Containerized web deployment with separate frontend/backend services where supported. Configuration and secrets remain server-side.

The frontend, application services, geometry domain and persistence layer are separated so later 2D canvas, 3D renderer, material and engineering modules can reuse the same project source of truth.

## 3. Milestone 1 scope

### Included

1. Responsive application shell and dashboard.
2. User registration, login, logout and protected sessions.
3. Project creation, listing, editing, archiving and reopening.
4. Plot configuration: shape metadata, dimensions, unit display, orientation and road-facing metadata.
5. Deterministic geometry functions for unit conversion, rectangular and polygon area, perimeter, and basic input consistency.
6. Persistent project/plot data in PostgreSQL.
7. Basic project-aware Brahma commands: create project, set dimensions, set orientation, read project measurements and explain supported calculations.
8. Database migrations, API documentation, test fixtures and setup/deployment documentation.

### Excluded from Milestone 1

Full wall/room canvas editing, 3D rendering, structural calculations, building-physics simulation, generative image interpretation, professional drawing exports, billing and multi-user real-time collaboration. These remain future milestones and must not be represented as implemented.

## 4. Core data model

Initial relational entities:

- `users`: account identity and password hash / auth metadata.
- `projects`: owner, title, description, status, timestamps and project settings.
- `project_members`: project-level membership and role.
- `plots`: project reference, shape type, canonical dimensions/geometry, display unit, orientation and road-facing metadata.
- `buildings`: project reference and building-level settings.
- `floors`: building reference, level index and elevation metadata.
- `rooms`: floor reference, room type and future geometry payload.
- `walls`: floor reference, endpoints/geometry and thickness metadata.
- `project_versions`: recoverable project snapshots and version metadata.
- `ai_conversations`: project/user association and conversation metadata.
- `audit_logs`: actor, action, resource and timestamp.

Milestone 1 may create forward-compatible tables for later entities, but must not imply that future editor functionality already exists. Referential integrity, indexes and ownership constraints are required.

## 5. Measurement and geometry rules

- Canonical internal length unit: millimetres.
- Supported display/input units: millimetres, metres, feet and inches.
- Conversions must be deterministic and covered by tests.
- Rectangular plot area is calculated from canonical width and depth.
- Polygon area and perimeter use a tested geometry implementation; invalid or degenerate polygons return explicit validation errors.
- The system preserves the user's supplied dimensions; it must not silently substitute values.
- Rounding is a presentation concern. Stored canonical measurements retain sufficient precision for reliable conversion and calculation.

## 6. Brahma local assistant contract

Brahma is not a free-form chatbot in this milestone. It supports a documented set of commands through an interpreter and application-service boundary. Every mutating command must:

1. Resolve the active project and verify access.
2. Parse the requested operation and parameters.
3. Validate parameters using domain rules.
4. Apply the change transactionally.
5. Return the updated persisted state and a human-readable explanation.

If the request is unsupported, ambiguous or invalid, Brahma asks for clarification or explains the limitation. It must never claim a mutation succeeded before persistence confirms it.

## 7. Security and reliability

- Passwords are stored using a modern password-hashing algorithm; plaintext passwords are never stored or logged.
- Authentication and authorization are enforced server-side.
- Every project query and mutation is scoped to the authenticated user's ownership or explicit project membership.
- Request bodies are validated with typed schemas.
- Secrets are loaded from environment configuration and never exposed to the frontend.
- Database writes use transactions and migrations are repeatable in deployment.
- Destructive project operations require recoverability (archive/version snapshot) rather than irreversible deletion by default.

## 8. Error handling and observability

API errors use consistent machine-readable error codes and clear user-facing messages. Validation failures are distinct from authorization failures and unexpected server errors. Server logs must exclude passwords, session tokens and secrets. Health/readiness checks should report service and database availability without disclosing sensitive configuration.

## 9. Testing strategy

- Unit tests for conversion, area, perimeter and polygon validation.
- API tests for authentication, project CRUD and plot persistence.
- Authorization tests proving users cannot read or mutate another user's projects.
- Integration tests for database migrations and persistence across application restarts/test sessions.
- Brahma command tests covering successful mutations, unsupported commands, ambiguous input and invalid dimensions.
- Frontend smoke tests for registration/login, dashboard, project creation and plot setup.

Known-value fixture: a rectangular plot of 30 ft × 50 ft must calculate to 1,500 sq ft (approximately 139.35456 sq m), subject only to documented display rounding.

## 10. Assumptions and decision boundaries

- The first release is a web application, not a native mobile application.
- Local AI means deterministic local parsing/rules in Milestone 1; an optional on-device language model may be evaluated later but is not a dependency.
- PostgreSQL is the primary database. PostGIS is an optional extension, not a blocker for initial geometry calculations.
- Hosting provider, domain, email delivery provider and production object-storage vendor remain deployment choices; local development must work without paid external services.
- Initial authentication may use secure server-managed sessions. OAuth and email verification can be added when deployment credentials/providers are selected.
- Milestone 1 is a foundation, not a claim of professional engineering or construction certification.

## 11. Acceptance criteria

Milestone 1 is accepted when:

1. A user can register, authenticate and log out.
2. A user can create, edit, archive and reopen a project.
3. Project and plot data persist in PostgreSQL across application restarts.
4. A user can enter exact plot dimensions and orientation.
5. Supported unit conversions and geometry calculations pass known-value tests.
6. Invalid or degenerate geometry is rejected with understandable errors.
7. A user cannot access another user's private project through API or UI.
8. Brahma can read the active project's persisted information.
9. Supported Brahma mutations update the actual database state and return the persisted result.
10. Automated backend tests and frontend smoke tests pass, with limitations documented.

## 12. Future extension points

The project/plot model will support subsequent wall and room geometry, a synchronized 2D editor and 3D model, material/surface assignments, engineering-analysis records, document exports, collaboration, quotas and subscriptions. Future modules must consume the same canonical project data rather than maintaining disconnected copies.
