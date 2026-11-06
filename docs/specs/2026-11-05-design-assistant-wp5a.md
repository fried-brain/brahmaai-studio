# WP5A — BrahmaAI Design Assistant (implemented scope)

## Goal
Add a safe, project-aware assistant entry point to the 2D Studio that turns natural-language requests into a structured draft brief, asks for missing information, and reviews saved room/opening records.

## Architecture
- FastAPI endpoint: `POST /api/v1/projects/{project_id}/assistant/message`.
- Project ownership and CSRF checks reuse existing dependencies.
- Deterministic local service interprets a small, explicit set of phrases and saved project facts.
- Response schema separates reply, clarifying questions, suggestions and optional proposal.
- Next.js client panel renders a session-only transcript and submits messages with the existing CSRF token.

## Safety and user control
- Assistant never writes to project, plot, room or opening records.
- Every proposal is marked as requiring user approval.
- The current engine is disclosed as local rules, not an LLM.
- Geometry, code, structural, fire, accessibility, daylight and airflow claims are not inferred from these checks.

## Verification
- Tests observed HTTP 404 for the new route before implementation.
- The same endpoint behavior tests passed after implementation.
- Full backend and frontend geometry suites are recorded in `progress.md`.

## Deferred
- LLM provider integration / local model runtime.
- Conversation persistence and project-level history.
- Full room-layout generation and conflict-checked application of user-approved geometry proposals.
- Multi-turn stateful requirement resolution.
