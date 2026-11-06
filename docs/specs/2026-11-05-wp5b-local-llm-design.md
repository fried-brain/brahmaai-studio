# WP5B Design — Local LLM Integration and Approval-Gated Layout Proposals

**Product:** BrahmaAI Studio
**Package:** WP5B
**Status:** Proposed design — awaiting user review
**Date:** 2026-11-05

## 1. Goal

Upgrade the WP5A deterministic design assistant into a local-first, multi-turn AI assistant that can produce editable room-layout proposals. The assistant must preserve the existing geometry engine as the authority for geometric validity and must never modify a saved floor plan without a separate, explicit user approval action.

The release is an integration layer, not a bundled model distribution. It connects to a separately installed, running Ollama-compatible local model service. No cloud fallback is permitted in this package.

## 2. Existing project context

The repository contains a FastAPI backend, SQLAlchemy persistence, Alembic migrations, a Next.js/React frontend, authenticated project APIs, deterministic plot/room geometry validation, and a WP5A assistant endpoint at `POST /api/v1/projects/{project_id}/assistant/message`.

WP5A currently:
- accepts a message and floor number;
- uses a deterministic rules engine;
- returns clarification questions, suggestions and an optional brief proposal;
- does not persist conversation history or generate room polygons;
- does not mutate a floor plan.

The current `DesignAssistant` component holds its transcript in React state, while `PlanEditor` owns room geometry and saves it through the existing layout API. WP5B should preserve these boundaries rather than letting the model write directly to the database or editor state.

## 3. Approaches considered

### A. Local-first Ollama-compatible runtime — recommended

The backend calls a configurable local model endpoint. Advantages: local inference, no required external AI account, and no cloud processing fallback. Trade-offs: the user must install/start a compatible model runtime, choose a model, and provide sufficient compute. Model quality and latency depend on the selected hardware/model.

### B. Cloud AI provider

Potentially stronger model quality and easier operation on low-powered devices, but requires credentials, network access and external data processing. This conflicts with the current local-AI product decision and is excluded from WP5B.

### C. Hybrid local/cloud routing

Could improve availability but introduces provider selection, privacy disclosure, credentials, routing and billing concerns. It is excluded from WP5B to keep the privacy boundary clear.

## 4. Approved design direction

### 4.1 Local model gateway

Add a backend-only model client configured through environment settings:
- `LOCAL_LLM_ENABLED` (default `false`);
- `LOCAL_LLM_BASE_URL` (default `http://127.0.0.1:11434`);
- `LOCAL_LLM_MODEL` (unset until configured);
- connect/read timeout and maximum response size settings.

Use the Ollama-compatible chat API with a structured-output/JSON response contract. The backend must check model availability and return a clear `model_unavailable` or `model_not_configured` state. The local rules engine remains available as a clearly identified fallback when the model is disabled/unavailable; the UI must disclose which engine answered. There is no automatic cloud fallback.

The model endpoint is server configuration only. It must never be accepted from a browser request or message. Validate the configured URL scheme and reject credentials embedded in the URL. Deployment documentation must explain that `127.0.0.1` means the backend container itself when Docker is used; Compose users need a reachable service name or host gateway configured explicitly.

### 4.2 Conversation persistence and isolation

Persist conversations and messages in PostgreSQL through new SQLAlchemy models and Alembic migration(s):
- conversation belongs to exactly one user and project;
- conversation records the active floor number, title/created/updated timestamps;
- messages store role, bounded text, engine/model metadata and optional structured proposal JSON;
- conversations and messages are accessible only to the owning authenticated user and project.

The message endpoint accepts an optional `conversation_id`. If absent, create a conversation. If supplied, verify both owner and project association. Bound conversation history sent to the model by a configurable recent-message count and token/character budget; never send unbounded history. Provide a way to list or load a project's conversations and retrieve a transcript. Do not store secrets or credentials in prompts or logs.

### 4.3 Context assembly and orchestration

The backend assembles a compact, typed context from the selected project: plot dimensions/shape/orientation, selected floor, saved room names/types/vertices, wall thickness and openings, plus relevant user-approved brief facts from conversation messages. Only the minimum project data needed for the current request is sent to the local model.

The system prompt defines the assistant as an architectural planning aide. Model output is untrusted data, not executable instructions. The model has no database, filesystem, shell, network tool, or arbitrary API tool access. All geometry and project operations remain explicit backend functions.

If the model is unavailable or returns malformed output, return a safe, user-readable error or the deterministic WP5A fallback. Do not treat malformed model text as a valid proposal.

### 4.4 Structured layout proposals

The model may return one of three response classes:
1. `clarification`: ask a bounded set of missing/ambiguous design questions;
2. `answer`: explain or review the project using the supplied context;
3. `layout_proposal`: return a draft room schedule and geometry for one selected floor.

A layout proposal contains a schema version, title, assumptions, warnings, target floor, and rooms. Each room has a stable proposal-local ID, name, room type, and polygon vertices in millimetres. Openings are optional and must reference valid room boundary edges using the existing opening schema. The initial WP5B proposal generator supports room polygons and existing door/window data only; it does not generate structural columns, beams, foundations, plumbing, electrical, stair construction details or 3D geometry.

The model may suggest dimensions but cannot authoritatively calculate or certify structural performance, code compliance, fire egress, accessibility, daylight or ventilation adequacy. Existing deterministic geometry validation is authoritative for plot containment, polygon validity, room overlap, opening edge fit and opening overlap. Validation failures are returned as actionable issues; the system must not silently repair or apply invalid geometry.

### 4.5 Preview, edit and approval workflow

The proposal is displayed as a separate, non-persistent preview layer in the existing 2D Studio. It must not replace the currently saved room state. The user can inspect the draft and edit supported room fields/vertices before approval.

Approval is an explicit action. The backend revalidates the final submitted proposal against the latest saved plot/layout state and the existing geometry rules. On success it persists the approved layout through the same domain validation path as normal layout saves and marks the proposal applied. Rejecting or dismissing a proposal leaves the saved plan unchanged. A stale proposal (plot or layout changed after generation) must be flagged and revalidated; the user must see material conflicts before applying it.

The UI must distinguish `Draft`, `Needs revision`, `Applied`, and `Rejected` states. No auto-apply, hidden mutation, or model-triggered save is allowed.

### 4.6 Frontend experience

Extend `DesignAssistant` to:
- create/resume a conversation and restore transcript from the backend;
- show whether the current response came from the local model or deterministic fallback;
- render clarifying questions, answer text, warnings and structured proposals;
- open a proposal in a separate 2D preview layer;
- allow editing supported room geometry before approval;
- require a deliberate Apply/Reject action and show validation feedback.

`PlanEditor` remains the owner of the saved layout. The proposal preview should be isolated state and should not enter the autosave pipeline until the user confirms Apply. Keep the existing editor controls and autosave behavior intact.

## 5. API contract (proposed)

Retain `POST /api/v1/projects/{project_id}/assistant/message` and extend its request with optional `conversation_id`. Response includes `conversation_id`, `engine` (`local_llm` or `local_rules`), `model` when applicable, response type, clarification/questions, suggestions, and optional proposal metadata.

Add owner-scoped endpoints:
- `GET /api/v1/projects/{project_id}/assistant/conversations` — list recent conversations;
- `GET /api/v1/projects/{project_id}/assistant/conversations/{conversation_id}` — load transcript;
- `POST /api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/apply` — revalidate and explicitly apply a pending proposal;
- `POST /api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/reject` — reject without changing the saved layout;
- `GET /api/v1/assistant/status` — report whether local model integration is enabled/configured/reachable, without exposing credentials or internal network details.

All mutating endpoints require the existing CSRF protection. All endpoints enforce project ownership. Error responses use stable codes for `model_not_configured`, `model_unavailable`, `invalid_model_output`, `proposal_invalid`, `proposal_stale`, and `proposal_not_pending`.

## 6. Data flow

1. Browser submits a message with project, floor and optional conversation ID.
2. API authenticates user, verifies project ownership and loads the bounded transcript plus relevant project context.
3. Orchestrator calls the configured local model, or the deterministic rules engine if local AI is disabled/unavailable.
4. Structured output is parsed against strict Pydantic schemas.
5. If it contains geometry, deterministic geometry services validate it without saving.
6. Conversation, message and pending proposal are persisted; response returns to the browser.
7. Browser displays proposal separately from saved rooms.
8. User edits and chooses Apply; API reloads current plot/layout, revalidates and persists atomically, then marks proposal applied.

## 7. Security, privacy and reliability

- Never expose model endpoint, filesystem path or model credentials to the browser.
- No cloud fallback or external AI transmission in WP5B.
- Treat all model output as untrusted; validate every field and bound all arrays, strings, vertices and message sizes.
- Keep model requests time-bounded and response-size-limited; avoid indefinite synchronous waits.
- Prevent cross-user/project conversation and proposal access.
- Keep apply/reject operations CSRF-protected and transactionally consistent.
- Do not execute model-produced code, SQL, shell commands, URLs or tool calls.
- Log operational error codes and latency, not full private conversations by default.
- Make clear that AI proposals are conceptual design assistance, not certified construction documents or professional engineering advice.

## 8. Testing and acceptance criteria

### Backend
- Local model client tests with a deterministic mock HTTP boundary: successful structured response, timeout, unreachable endpoint, non-success status, oversized/malformed output.
- Settings tests for disabled, missing model and invalid endpoint configuration.
- Conversation persistence, transcript ordering, bounded history, owner isolation and project association tests.
- Schema tests reject unknown response types, invalid room geometry shape, oversized arrays and invalid opening references.
- Proposal tests cover valid geometry, outside-plot rooms, overlapping rooms, invalid openings, stale proposals, duplicate apply, reject and cross-user access.
- Atomicity test proves a failed apply leaves saved rooms and proposal state unchanged.
- Existing WP1–WP5A tests remain green; migration upgrade/downgrade/re-upgrade is tested.

### Frontend
- Unit tests for conversation serialization, response rendering and proposal preview isolation.
- Verify proposal preview does not mutate saved-room state or trigger autosave.
- Verify Apply invokes the explicit approval endpoint and Reject leaves saved layout untouched.
- Typecheck, production build and browser test the full chat → clarification → proposal → preview/edit → apply/reject flow when dependencies/browser runtime are available.

### Acceptance
- With a configured local model, the assistant returns genuine model-generated multi-turn responses and structured proposals.
- With the model unavailable, the user sees a clear status and deterministic fallback; no cloud call occurs.
- A valid proposal can be previewed and edited without changing saved geometry.
- Only an explicit, successful approval applies geometry after fresh server-side validation.
- Invalid or stale proposals never mutate the saved plan.

## 9. Scope exclusions

- Bundling/downloading model weights or installing Ollama automatically.
- Cloud model providers, cloud fallback, billing or API-key management.
- Autonomous agents, browser tools, arbitrary function calling or shell/file access.
- Structural engineering, material sizing, foundations, beams/columns, MEP design, fire engineering, code certification or construction-ready drawing generation.
- Automatic 3D generation or photorealistic rendering.
- Full collaborative multi-user editing and real-time shared sessions.

## 10. Implementation sequencing

Implement in vertical slices with test-first development:
1. Configuration, model gateway, health/status and deterministic fallback.
2. Conversation persistence, bounded context and transcript APIs.
3. Strict response schema and model orchestration.
4. Proposal persistence and deterministic preflight geometry validation.
5. Preview isolation and user-editable proposal UI.
6. Explicit apply/reject endpoints with transaction and stale-state protection.
7. Full regression, migration and deployment documentation.

## 11. Self-review checklist

- **Placeholders:** No TBD/TODO placeholders remain.
- **Consistency:** Local-only model calls, deterministic geometry validation, and approval-gated persistence are consistent across API, UI and data flow.
- **Scope:** The package is a substantial vertical feature but is decomposed into seven implementation slices; no cloud AI, structural engineering or 3D generation is implied.
- **Ambiguity:** The model endpoint is server-configured; proposal geometry uses millimetres; the selected floor is explicit; previews are non-persistent; apply always revalidates current project state.
