# WP5B Local LLM Integration and Approval-Gated Layout Proposals Implementation Plan

> **For agentic workers:** Use the host's available task-by-task implementation workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade BrahmaAI Studio's deterministic assistant into a local-first, multi-turn assistant that creates validated, editable room-layout proposals which are applied only after explicit user approval.

**Architecture:** Keep FastAPI as the only model gateway and use a configurable Ollama-compatible `/api/chat` endpoint with JSON output. Persist owner-scoped conversations, messages and proposals in SQLAlchemy; assemble bounded project context; validate every generated/final layout through the existing Pydantic and geometry domain rules. Keep the saved PlanEditor layout and proposal preview in separate state until the user invokes the explicit apply endpoint.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, httpx, pytest, Next.js 15, React 19, TypeScript, Node's built-in test runner.

## Global Constraints

- Local inference only. No cloud provider, cloud fallback, model-weight download or model-runtime installation is part of this package.
- The model endpoint and model name are server-side settings only; never accept them from a browser request or chat message.
- `LOCAL_LLM_ENABLED` defaults to `false`; the default base URL is `http://127.0.0.1:11434`; no default model is assumed.
- Validate endpoint scheme (`http` or `https`) and reject embedded URL credentials. Do not expose endpoint, internal network details, credentials or filesystem paths to browser clients.
- A disabled, unconfigured or unavailable local model uses the deterministic WP5A rules engine as a clearly identified fallback. There is no silent cloud routing.
- Conversation and proposal access must be scoped to the authenticated owner and the associated project. All mutating routes require the existing CSRF dependency.
- Bound incoming messages to 2,000 characters, stored assistant messages to 12,000 characters, model history to the newest 12 messages and 12,000 total characters, model output to 1,000,000 bytes, proposal rooms to 100, vertices per room to 100, openings per room to 100, and model request duration to configured connect/read timeouts. Never send unbounded transcript/project data to the model.
- Treat model output as untrusted data. No model-produced code, SQL, shell commands, URLs, filesystem operations or tool calls may be executed.
- Geometry calculations and validation remain deterministic. Use existing `RoomInput`, `LayoutUpdate`, `validate_polygon`, `polygon_within_polygon` and `polygons_overlap` behavior as the authoritative geometric boundary.
- Proposals are millimetre-coordinate room polygons plus optional existing door/window opening data. No structural, MEP, 3D, fire, accessibility, building-code or construction-readiness certification is implied.
- A generated proposal never changes saved rooms. Preview edits remain client-side until explicit Apply. Apply revalidates against the latest plot and floor state and commits room replacement plus proposal status atomically. Reject never changes saved rooms.
- The existing WP5A assistant response shape and deterministic fallback behavior remain backward compatible where practical; update tests and frontend types together when extending it.
- Repository has no Git metadata at plan creation. Do not claim commits or create a repository history unless the user separately authorizes Git initialization.

---

### Task 1: Local model configuration, Ollama-compatible gateway and status endpoint

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/pyproject.toml`
- Create: `backend/app/services/local_llm.py`
- Create: `backend/app/schemas/assistant_status.py`
- Create: `backend/app/api/assistant.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_local_llm.py`
- Test: `backend/tests/test_assistant_status.py`
- Modify: `README.md`

**Interfaces:**
- `Settings.local_llm_enabled: bool = False`
- `Settings.local_llm_base_url: str = "http://127.0.0.1:11434"`
- `Settings.local_llm_model: str | None = None`
- `Settings.local_llm_connect_timeout_seconds: float = 3.0`
- `Settings.local_llm_read_timeout_seconds: float = 45.0`
- `Settings.local_llm_max_response_bytes: int = 1_000_000`
- `Settings.local_llm_max_history_messages: int = 12`
- `Settings.local_llm_max_history_characters: int = 12_000`
- `LocalLLMClient(settings, http_client=None)` with `status() -> LocalModelStatus` and `chat(messages, response_schema) -> LocalModelReply`
- `GET /api/v1/assistant/status` returns only `enabled`, `configured`, `reachable`, `model_available`, and a stable status code; it must not return the base URL or network address.
- `LocalModelStatus` distinguishes `disabled`, `model_not_configured`, `model_unavailable`, and `ready`.
- `LocalModelReply` contains the returned text and configured model identifier, not arbitrary model-controlled routing metadata.

- [ ] **Step 1: Add the focused failing tests**

Test settings defaults, invalid URL schemes, URL user-info rejection, disabled status, missing model status, reachable `/api/tags` response with the configured model, model-not-listed response, timeout, connection refusal, non-2xx response, invalid JSON and response bodies larger than `LOCAL_LLM_MAX_RESPONSE_BYTES`. Mock only the HTTP transport boundary using `httpx.MockTransport`; assert status codes and that the response never contains the configured URL.

- [ ] **Step 2: Verify the relevant failure**

Run: `cd backend && pytest -q tests/test_local_llm.py tests/test_assistant_status.py`
Expected: non-zero exit because the settings, gateway and status route do not exist yet; the failure must be an import/route assertion for the missing behavior, not test setup.

- [ ] **Step 3: Implement the minimum behavior**

Add `httpx>=0.27,<1.0` to backend runtime dependencies. Validate settings at construction: accept only `http`/`https`, reject username/password components, require positive timeout/size values, and do not accept endpoint overrides in API payloads. Implement a synchronous, bounded HTTP client for Ollama-compatible `GET /api/tags` and `POST /api/chat` with `stream: false` and `format: "json"`. Enforce connect/read timeouts and response-byte limits before parsing. Translate timeout, connection, HTTP and malformed JSON failures into typed internal gateway errors. Add the status router to `create_app`; status must not require project ownership but must require an authenticated session, consistent with the assistant being a user feature. Add environment examples and document that `127.0.0.1` inside Docker refers to the API container, so Compose deployments must configure a reachable model-service hostname.

- [ ] **Step 4: Verify the focused pass**

Run: `cd backend && pytest -q tests/test_local_llm.py tests/test_assistant_status.py`
Expected: all gateway and status tests pass, including unavailable and oversized-response cases.

- [ ] **Step 5: Run the affected integration check**

Run: `cd backend && pytest -q tests/test_health.py tests/test_auth.py tests/test_assistant.py`
Expected: existing health, authentication and WP5A assistant behavior remains green.

### Task 2: Persist conversations/messages and expose owner-scoped transcript APIs

**Files:**
- Create: `backend/app/models/assistant.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/migrations/versions/0006_assistant_conversations.py`
- Modify: `backend/migrations/env.py`
- Create: `backend/app/schemas/assistant_conversations.py`
- Create: `backend/app/services/assistant_conversations.py`
- Modify: `backend/app/api/projects.py`
- Test: `backend/tests/test_assistant_conversations.py`

**Interfaces:**
- `AssistantConversation`: `id`, `project_id`, `owner_id`, `floor_number`, `title`, `created_at`, `updated_at`; belongs to one project and one user.
- `AssistantMessage`: `id`, `conversation_id`, `role`, `content`, `engine`, `model_name`, `response_type`, optional JSON text `proposal_json`, `created_at`.
- `create_conversation(db, project, owner, floor_number, title)`; derive the initial title deterministically from the first user message, truncated to 80 characters.
- `append_message(db, conversation, role, content, engine, model_name=None, response_type=None, proposal_json=None)`
- `get_owned_conversation(db, project_id, owner_id, conversation_id)`
- `list_conversations(db, project_id, owner_id, limit)` and `load_transcript(db, conversation)`
- `GET /api/v1/projects/{project_id}/assistant/conversations`
- `GET /api/v1/projects/{project_id}/assistant/conversations/{conversation_id}`

- [ ] **Step 1: Add the focused failing tests**

Test that a conversation and its messages persist and reload in chronological order; a conversation is associated with the correct owner, project and floor; list returns only the requested project's conversations in most-recently-updated order; loading another user's or another project's conversation returns 404; invalid conversation IDs do not leak existence; transcript message content and model metadata are serialized; list limit is bounded; and migration downgrade removes the new tables cleanly.

- [ ] **Step 2: Verify the relevant failure**

Run: `cd backend && pytest -q tests/test_assistant_conversations.py`
Expected: non-zero exit because the models, migration and routes are not implemented.

- [ ] **Step 3: Implement the minimum behavior**

Create `assistant_conversations` and `assistant_messages` tables with UUID-string primary keys, indexed owner/project/conversation foreign keys, cascade deletion, role and engine strings, bounded content columns and timestamps. Register models in `app.models` and Alembic metadata. Add migration `0006_assistant_conversations` after `0005_architectural_openings`. Add Pydantic output schemas and service functions. Every query must filter by project ID and owner ID; do not rely only on a client-supplied conversation ID. Require CSRF for message creation only; transcript/list routes are read-only and use authenticated ownership checks. Use stable 404 for non-owned conversation IDs.

- [ ] **Step 4: Verify the focused pass**

Run: `cd backend && pytest -q tests/test_assistant_conversations.py`
Expected: all persistence, chronological ordering, owner isolation and serialization tests pass.

- [ ] **Step 5: Run the affected integration check**

Run: `cd backend && pytest -q tests/test_auth.py tests/test_projects.py tests/test_assistant.py tests/test_assistant_conversations.py`
Expected: existing owner scoping, project routes and assistant tests remain green.

### Task 3: Strict model response schemas, bounded context assembly and multi-turn orchestration

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/schemas/assistant_ai.py`
- Create: `backend/app/services/assistant_context.py`
- Create: `backend/app/services/assistant_orchestrator.py`
- Modify: `backend/app/schemas/assistant.py`
- Modify: `backend/app/services/assistant.py`
- Modify: `backend/app/api/projects.py`
- Test: `backend/tests/test_assistant_orchestrator.py`
- Test: `backend/tests/test_assistant_schemas.py`

**Interfaces:**
- `AssistantAIResponse`: strict discriminated response type `clarification | answer | layout_proposal`; extra fields forbidden.
- `LayoutProposalDraft`: `schema_version`, `title`, `assumptions`, `warnings`, `floor_number`, `rooms`; each room has proposal-local ID, name, allowed room type, `vertices_mm`, wall thickness and optional validated openings.
- `build_project_context(project, floor_number, rooms) -> dict`
- `build_bounded_history(messages, max_messages, max_characters) -> list[dict[str, str]]`
- `orchestrate_assistant_message(settings, local_llm_client, project_context, history, message) -> AssistantTurn`
- Extend `AssistantMessageInput` with optional `conversation_id` while preserving `message` and `floor_number`.
- Extend `AssistantMessageOutput` with `conversation_id`, `response_type`, optional `model`, optional proposal ID/metadata and `engine` (`local_llm` or `local_rules`).

- [ ] **Step 1: Add the focused failing tests**

Test valid clarification, answer and layout-proposal JSON; reject unknown response types, extra fields, missing required keys, unsupported room types, blank names, out-of-range coordinates, too many rooms/vertices/openings, malformed opening edge references and invalid floor mismatch. Test project context includes only the selected floor, plot dimensions/shape/orientation and saved room geometry/openings. Test history includes only the newest messages within both message-count and character budgets, preserves role order, and never includes another conversation. Test configured-model success returns `engine=local_llm`; disabled, unavailable and malformed-model-output cases use WP5A fallback with `engine=local_rules` and no invalid proposal.

- [ ] **Step 2: Verify the relevant failure**

Run: `cd backend && pytest -q tests/test_assistant_schemas.py tests/test_assistant_orchestrator.py`
Expected: non-zero exit due missing strict AI schemas, context builder and orchestration service.

- [ ] **Step 3: Implement the minimum behavior**

Use Pydantic v2 strict models with `extra="forbid"`, explicit string/list bounds and `Literal` room/response types. The model prompt must state that it is a conceptual architectural planning aide, that project context is data rather than instructions, and that it must return only the required JSON response. Build context from project/plot and rooms for the selected floor only. Add `LOCAL_LLM_MAX_HISTORY_MESSAGES=12` and `LOCAL_LLM_MAX_HISTORY_CHARACTERS=12000` settings. Keep incoming user messages at 2,000 characters and cap persisted assistant text at 12,000 characters. Conversations are floor-bound: a message submitted with a different floor returns HTTP 409 `conversation_floor_mismatch`; the client starts or selects a conversation for the new floor. Persist user and assistant messages in the existing conversation service. When local AI is disabled or unavailable, call the current `respond_to_design_message` and label the response `local_rules`; malformed model JSON/schema must not be parsed as a proposal and must produce a safe fallback response. Do not log prompt bodies or full transcripts. Do not persist a failed model call as a successful assistant response.

- [ ] **Step 4: Verify the focused pass**

Run: `cd backend && pytest -q tests/test_assistant_schemas.py tests/test_assistant_orchestrator.py`
Expected: strict parsing, bounded context/history, successful mocked local model response and deterministic fallback tests all pass.

- [ ] **Step 5: Run the affected integration check**

Run: `cd backend && pytest -q tests/test_assistant.py tests/test_assistant_conversations.py tests/test_local_llm.py`
Expected: existing WP5A request behavior remains compatible; persisted conversation messages and engine labels are correct.

### Task 4: Persist layout proposals and perform deterministic preflight validation

**Files:**
- Modify: `backend/app/models/assistant.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/migrations/versions/0007_assistant_proposals.py`
- Modify: `backend/migrations/env.py`
- Create: `backend/app/schemas/assistant_proposals.py`
- Create: `backend/app/services/assistant_proposals.py`
- Modify: `backend/app/services/assistant_orchestrator.py`
- Modify: `backend/app/api/projects.py`
- Test: `backend/tests/test_assistant_proposals.py`

**Interfaces:**
- `AssistantProposalRecord`: `id`, `conversation_id`, `project_id`, `owner_id`, `floor_number`, `status` (`draft`, `needs_revision`, `applied`, `rejected`), `proposal_json`, `base_layout_hash`, `created_at`, `updated_at`, `applied_at`.
- `validate_layout_proposal(project, floor_number, rooms) -> ProposalValidationResult` uses the existing `RoomInput`/`LayoutUpdate` schema and the same plot-containment and overlap functions as `replace_floor_layout`.
- `fingerprint_floor_state(project, floor_number, saved_rooms) -> str` hashes a canonical representation of plot geometry plus the selected floor's saved room geometry/openings.
- `create_pending_proposal(...)` persists draft or needs-revision state and validation issues; invalid geometry is never marked apply-ready.

- [ ] **Step 1: Add the focused failing tests**

Test a valid proposal is stored as `draft`; outside-plot rooms, overlapping rooms, invalid polygons, duplicate room names, openings referencing missing edges and overlapping openings are marked `needs_revision` with actionable field-level issues; proposal data is tied to the generating conversation/project/owner/floor; proposal-local IDs remain stable; canonical state fingerprints are stable for equivalent data and change when plot geometry or any selected-floor room/opening changes; malformed proposal JSON cannot be persisted as apply-ready.

- [ ] **Step 2: Verify the relevant failure**

Run: `cd backend && pytest -q tests/test_assistant_proposals.py`
Expected: non-zero exit because proposal persistence and deterministic preflight validation are missing.

- [ ] **Step 3: Implement the minimum behavior**

Add the proposal table and migration `0007_assistant_proposals` after `0006_assistant_conversations`. Validate model-generated room data through the same Pydantic `RoomInput`/`LayoutUpdate` contracts used by the normal layout API, then call the same containment/overlap domain checks. Refactor the layout validation loop into a shared pure service function so the normal layout save and proposal preflight cannot drift. Store proposals as JSON text plus a canonical floor-state fingerprint. Record validation issues and use `needs_revision` for invalid drafts; never silently clip, move, normalize or repair generated room polygons. A proposal is only `draft` when all geometry checks pass.

- [ ] **Step 4: Verify the focused pass**

Run: `cd backend && pytest -q tests/test_assistant_proposals.py`
Expected: proposal state, invalid geometry, opening validation and state fingerprint tests pass.

- [ ] **Step 5: Run the affected integration check**

Run: `cd backend && pytest -q tests/test_geometry.py tests/test_projects.py tests/test_assistant_proposals.py`
Expected: shared geometry validation preserves all existing plot/layout behavior and rejects the same invalid layouts in both paths.

### Task 5: Conversation chat UI, separate proposal preview and editable draft controls

**Files:**
- Modify: `frontend/app/components/DesignAssistant.tsx`
- Create: `frontend/app/components/ProposalPreview.tsx`
- Modify: `frontend/app/components/PlanEditor.tsx`
- Modify: `frontend/app/globals.css`
- Create: `frontend/tests/assistant.test.mjs`
- Create: `frontend/app/components/assistant-state.mjs`
- Create: `frontend/app/components/assistant-state.d.mts`

**Interfaces:**
- `DesignAssistant` receives `projectId`, `floorNumber`, `csrfToken`, `onProposalPreview(proposal)` and `onProposalClear()`.
- `ProposalPreview` receives a proposal and `onChange`, `onApply`, `onReject`; it renders draft state, validation issues, assumptions and warnings.
- `assistant-state.mjs` exports pure `appendConversationMessage`, `serializeProposalEdit`, and `isProposalPreviewOnly` helpers for testable client state behavior.
- `PlanEditor` owns `savedRooms` and `proposalPreview` as distinct states; preview rooms must never enter the autosave signature or layout PUT payload.

- [ ] **Step 1: Add the focused failing tests**

Test conversation response normalization, engine labeling, stable transcript serialization, proposal room name/type/vertex edits, and that preview changes do not alter the saved-room serialization used by autosave. Test changing floor/project clears or suspends the preview rather than showing a proposal on the wrong floor. Test that dismissing/rejecting a preview leaves the saved-room snapshot unchanged.

- [ ] **Step 2: Verify the relevant failure**

Run: `cd frontend && node --test tests/assistant.test.mjs`
Expected: non-zero exit because the assistant state helpers and proposal preview behavior do not exist.

- [ ] **Step 3: Implement the minimum behavior**

Extend `DesignAssistant` to load/list conversations, resume a selected conversation, submit `conversation_id`, and render assistant engine/model labels, clarifications, answer text, warnings and proposal state. Render a separate proposal preview overlay in the PlanEditor SVG without touching `rooms`, `lastSavedRef` or autosave inputs. Add editable room name/type and numeric vertex coordinate controls; preserve opening data and proposal-local IDs during edits. Show `Draft` or `Needs revision`. Keep Apply available for pending proposals so server-side validation can return actionable issues after edits; never call the layout save endpoint from the preview editor. Use accessible labels and live status/error regions.

- [ ] **Step 4: Verify the focused pass**

Run: `cd frontend && node --test tests/assistant.test.mjs tests/geometry.test.mjs`
Expected: preview isolation, serialization and existing geometry tests all pass.

- [ ] **Step 5: Run the affected integration check**

Run: `cd frontend && node -e "const ts=require('typescript'); const fs=require('fs'); for (const f of ['app/components/DesignAssistant.tsx','app/components/ProposalPreview.tsx','app/components/PlanEditor.tsx']) { const s=fs.readFileSync(f,'utf8'); const r=ts.transpileModule(s,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022},reportDiagnostics:true}); const errors=(r.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error); if(errors.length){ console.error(f,errors.map(e=>ts.flattenDiagnosticMessageText(e.messageText,'\\n'))); process.exitCode=1; } else console.log(f+': syntax OK'); }"
Expected: all changed TSX files transpile without syntax diagnostics. A full Next.js typecheck/build and browser render remain separate final verification gates requiring installed dependencies and a browser runtime.

### Task 6: Explicit apply/reject endpoints, fresh-state protection and atomic persistence

**Files:**
- Create: `backend/app/schemas/assistant_proposals.py` (apply request/output additions)
- Modify: `backend/app/services/assistant_proposals.py`
- Modify: `backend/app/api/projects.py`
- Create: `backend/app/services/layouts.py` (extract shared layout validation/persistence from the existing project route)
- Test: `backend/tests/test_assistant_proposal_actions.py`

**Interfaces:**
- `POST /api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/apply` with edited proposal JSON in request body; authenticated, owner-scoped and CSRF-protected.
- `POST /api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/reject`; authenticated, owner-scoped and CSRF-protected.
- `apply_pending_proposal(db, project, owner, proposal_id, edited_rooms) -> AppliedProposalResult`
- `reject_pending_proposal(db, project, owner, proposal_id) -> ProposalRecordOutput`
- Stable error codes: `proposal_invalid`, `proposal_stale`, `proposal_not_pending`.

- [ ] **Step 1: Add the focused failing tests**

Test valid Apply persists the submitted edited rooms and marks proposal `applied`; Apply requires CSRF and project ownership; edited rooms are revalidated even if the original draft was valid; out-of-plot/overlapping/invalid-opening edits return `proposal_invalid` and leave saved rooms plus proposal status unchanged; a changed plot or floor layout returns `proposal_stale` with no mutation; repeated Apply and Apply after Reject return `proposal_not_pending`; Reject marks a pending proposal `rejected` without changing rooms; cross-user/project proposal IDs return 404; a database failure during apply rolls back both room replacement and proposal state.

- [ ] **Step 2: Verify the relevant failure**

Run: `cd backend && pytest -q tests/test_assistant_proposal_actions.py`
Expected: non-zero exit because apply/reject routes and transaction-safe state transitions are not implemented.

- [ ] **Step 3: Implement the minimum behavior**

On Apply, load project and proposal with owner/project filters, require status `draft` or `needs_revision`, compare the saved base fingerprint to the current plot+floor fingerprint, and return HTTP 409 with code `proposal_stale` if they differ. The user must generate/review a fresh proposal after a stale response; do not attempt automatic merge. Validate the exact edited room payload again with `LayoutUpdate`, shared plot containment and overlap validation. Within one database transaction, replace the target floor's rooms using the same persistence function as the ordinary layout API and mark proposal `applied`. On any exception, rollback both changes. If the fingerprint changed, set the proposal to `needs_revision`, record a stale-state issue, return HTTP 409 `proposal_stale`, and leave saved rooms unchanged; the user must generate a fresh proposal rather than applying an old one. Reject only pending `draft` or `needs_revision` proposals and only changes proposal state. Return stable error payloads with `code` and user-readable `message`; do not return raw SQL/exception text.

- [ ] **Step 4: Verify the focused pass**

Run: `cd backend && pytest -q tests/test_assistant_proposal_actions.py`
Expected: apply/reject, stale-state, validation, owner/CSRF, duplicate-action and atomic rollback tests pass.

- [ ] **Step 5: Run the affected integration check**

Run: `cd backend && pytest -q tests/test_projects.py tests/test_assistant_proposals.py tests/test_assistant_proposal_actions.py`
Expected: normal layout saving and proposal application share validation/persistence semantics without regressions.

### Task 7: Full integration regression, migrations and deployment guidance

**Files:**
- Modify: `README.md`
- Modify: `backend/.env.example`
- Modify: `docs/api/design-assistant.md`
- Create: `docs/api/local-llm.md`
- Modify: `progress.md`
- Test: all backend tests under `backend/tests/`
- Test: all frontend tests under `frontend/tests/`

**Interfaces:**
- Documented environment contract matches `Settings` exactly.
- Documented route contracts match FastAPI schemas and actual response codes.
- `GET /api/v1/assistant/status` reports model readiness without endpoint disclosure.

- [ ] **Step 1: Add remaining acceptance tests**

Add any missing end-to-end API test covering register/login → create project → start conversation → multi-turn clarification → structured proposal → load transcript → preview-only state → edit → Apply or Reject. Include disabled-model fallback, unavailable-model fallback, malformed JSON fallback, cross-project conversation access and stale proposal rejection. Verify the original saved layout before and after every non-Apply path.

- [ ] **Step 2: Verify acceptance gaps before final integration**

Run: `cd backend && pytest -q tests/test_assistant.py tests/test_assistant_conversations.py tests/test_assistant_orchestrator.py tests/test_assistant_proposals.py tests/test_assistant_proposal_actions.py`
Expected: any remaining failures identify a missing acceptance behavior; fix implementation or test setup before proceeding, without weakening assertions.

- [ ] **Step 3: Complete documentation and deployment guidance**

Document local Ollama-compatible runtime prerequisites, model selection/configuration, status endpoint, Docker networking (`127.0.0.1` refers to the API container), timeout and history settings, conversation endpoints, proposal states, Apply/Reject behavior, stable errors, privacy boundary and the architectural disclaimer. Explain that this package does not install Ollama or download weights and has no cloud fallback. Update progress with exact verified outcomes only.

- [ ] **Step 4: Run the full backend suite**

Run: `cd backend && PYTHONPATH=. pytest -v -p no:cacheprovider`
Expected: all backend tests pass with zero failures.

- [ ] **Step 5: Verify migration round trip**

Run from `backend`: `rm -f /tmp/brahmaai_wp5b_migration.db && DATABASE_URL=sqlite:////tmp/brahmaai_wp5b_migration.db PYTHONPATH=. alembic upgrade head && DATABASE_URL=sqlite:////tmp/brahmaai_wp5b_migration.db PYTHONPATH=. alembic downgrade base && DATABASE_URL=sqlite:////tmp/brahmaai_wp5b_migration.db PYTHONPATH=. alembic upgrade head`
Expected: migration chain upgrades, downgrades and re-upgrades without error, including revisions `0006` and `0007`.

- [ ] **Step 6: Run frontend tests and syntax/type/build checks available in the environment**

Run: `cd frontend && node --test tests/*.test.mjs`
Expected: all frontend unit tests pass. Then run the TypeScript syntax transpilation check from Task 5. If npm dependencies are installed, additionally run `npm run build` and `npx tsc --noEmit`; if unavailable, report those checks as not run rather than passing.

- [ ] **Step 7: Verify release boundaries**

Manually or through integration tests confirm: no browser request can set the model endpoint; status does not disclose it; no cloud fallback exists; proposals never enter autosave; Apply is the only path that replaces saved room geometry; stale/invalid/unauthorized/rejected proposals never mutate the plan; all routes enforce ownership and mutating routes enforce CSRF.

## Unresolved external execution prerequisites

- A compatible local model runtime and a model must be installed and running separately. Their model identity, hardware needs and inference quality depend on the user's machine; the project must report unavailable status until configured.
- Docker deployments must provide a backend-reachable model service hostname. The implementation cannot assume the model runtime is on the API container's loopback interface.
- Full browser rendering, Next.js production build and live PostgreSQL verification depend on installing frontend dependencies, providing a browser runtime and providing a live PostgreSQL service. SQLite migration and API tests are useful evidence but do not replace those deployment checks.
