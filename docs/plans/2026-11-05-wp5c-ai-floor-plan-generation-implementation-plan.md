# WP5C AI Floor Plan Generation Engine Implementation Plan

> **For agentic workers:** Use the host's available task-by-task implementation workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a user's natural-language single-floor brief into up to three deterministic, geometrically valid, editable floor-plan candidates, without modifying saved geometry until explicit approval.

**Architecture:** A local-model interpreter converts conversation context into a strict `RoomPlanningBrief`; a pure deterministic planner creates axis-aligned rectangular room placements and openings; existing proposal validation and approval services persist each candidate independently. The frontend adds a candidate selector and routes each selected proposal through the existing edit/apply/reject workflow.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy, Alembic-compatible existing models, Python deterministic geometry services, Next.js 15, React 19, TypeScript, Node test runner, pytest.

## Global Constraints

- Generate one selected floor at a time.
- Generate only for an exact axis-aligned rectangular plot. Do not approximate irregular plots with a bounding rectangle.
- The local model interprets requirements and explains; it never supplies authoritative room coordinates.
- Geometry placement, validation, candidate scoring and ordering are deterministic and versioned.
- Generate no more than three candidates; fewer are valid when fewer distinct feasible arrangements exist.
- Hard constraints must be satisfied or the result must be an explicit clarification/infeasibility response. Never silently shrink hard dimensions or drop a required room.
- Product dimension defaults are heuristics, not legal minimums, professional recommendations or code compliance claims. Every default used must be disclosed in candidate assumptions.
- Candidate previews do not modify saved rooms. Applying a candidate requires explicit user action, fresh server-side validation and the existing base-layout fingerprint check.
- No cloud fallback, model auto-installation, model-provided tools, SQL, shell, filesystem access or arbitrary URL access.
- Preserve authentication, CSRF, project ownership and bounded model context/output.
- Vastu mode defaults to off. If enabled, it is labelled as an optional traditional reference and never as an engineering rule.
- Do not claim structural safety, construction readiness, accessibility, fire-egress, daylight, ventilation or regulatory compliance.
- This workspace has no `.git` metadata; implementation steps must not claim commits or create Git history. Keep the task ledger in `progress.md` and produce a verified ZIP artifact at release.

---

## Repository facts and selected implementation decisions

Observed repository entry points:

- `backend/app/api/projects.py` owns project, layout, assistant-message and proposal endpoints.
- `backend/app/schemas/assistant_ai.py` defines strict local-model output schemas.
- `backend/app/schemas/assistant.py` defines assistant request/response contracts.
- `backend/app/schemas/layouts.py` defines room geometry and opening validation.
- `backend/app/services/local_llm.py` provides the server-side Ollama-compatible client.
- `backend/app/services/assistant_conversations.py` stores bounded project/floor conversations.
- `backend/app/services/assistant_proposals.py` creates independent proposal records, fingerprints the base layout and applies/rejects proposals.
- `backend/app/services/layouts.py` and `backend/app/services/geometry.py` provide deterministic geometry validation.
- `frontend/app/components/DesignAssistant.tsx`, `ProposalPreview.tsx` and `PlanEditor.tsx` implement chat, proposal preview and explicit apply/reject.
- Backend tests run with `PYTHONPATH=backend pytest -v -p no:cacheprovider`.
- Frontend tests run with `node --test frontend/tests/*.test.mjs` from `frontend/`.

Implementation decisions resolving the specification's open points:

1. **Candidate persistence:** Store each candidate as its own existing `AssistantProposalRecord`. This provides stable IDs and independent apply/reject without a new parent table or migration. Add a conversation-scoped owned-proposal listing endpoint so all candidates can be restored after reload. The assistant transcript's existing `proposal_id` remains the primary candidate pointer for backward compatibility.
2. **Planner algorithm:** Use a bounded deterministic shelf-packing planner with three named ordering strategies (`public_first`, `private_first`, `service_cluster`). Try unrotated and rotated room rectangles where allowed by the brief. This is deliberately bounded and explainable; it is not a general-purpose packing optimizer.
3. **Product defaults and scoring:** Version the initial constants as `planner_version = "1.0"`. Default room dimensions (width × depth, mm): living 3600×4200; bedroom 3000×3600; kitchen 2700×3000; bathroom 1500×2100; dining 2700×3000; study 2400×3000; utility 1800×2100; staircase 2500×4000; corridor 1200×3000; parking 3000×5500; other 3000×3000. These are product starting assumptions only. Score eligible candidates out of 100 with adjacency 25, circulation 25, privacy 15, dimension fit 15, usable-area comparison 10 and orientation/traditional preference 10. If no orientation preference is supplied, redistribute that component's weight proportionally among the active components. Hard constraints are eligibility gates, not score bonuses.
4. **Parking representation:** Add `parking` to the existing room-type literal and frontend room-type palette. The database stores room types as strings, so no schema migration is required.
5. **Generation API:** Add `POST /api/v1/projects/{project_id}/assistant/layout-generation` for the generation/clarification flow and `GET /api/v1/projects/{project_id}/assistant/conversations/{conversation_id}/proposals` for candidate restoration. Existing generic assistant chat and existing proposal apply/reject endpoints remain compatible.
6. **Entry/access semantics:** An external entry door is placed only when the brief or project context supplies an unambiguous road-facing side; otherwise the planner records that entrance placement needs user confirmation. Room-to-room doors are placed on shared wall segments. Window openings are placed only on plot-boundary-facing edges of rooms for which a window is requested or a default is appropriate; openings are geometric placeholders, not daylight/ventilation certification.

---

### Task 1: Strict planning brief and local-model interpreter

**Files:**
- Create: `backend/app/schemas/room_planning.py`
- Create: `backend/app/services/room_planning_interpreter.py`
- Modify: `backend/app/schemas/assistant.py`
- Modify: `backend/app/services/assistant_conversations.py` only if the existing transcript helper needs a small reusable query for current context; otherwise reuse current functions unchanged.
- Test: `backend/tests/test_room_planning_interpreter.py`
- Test: `backend/tests/test_room_planning_schemas.py`
- Modify: `docs/api/design-assistant.md`

**Interfaces:**
- Consumes: `LocalLLMClient.status()`, `LocalLLMClient.chat(messages, response_schema)`, `build_bounded_history(...)`, `build_project_context(...)`.
- Produces: `RoomPlanningBrief`, `PlanningClarification`, `PlanningBriefResult`, `room_planning_json_schema()`, and `parse_room_planning_response(value)`.
- `parse_room_planning_brief(client, messages, project_context, floor_number) -> PlanningBriefResult` must never return coordinates or geometry.

- [ ] **Step 1: Add focused failing tests**

Test strict schema parsing for:

- A brief requesting three bedrooms, kitchen, living and parking with explicit floor number.
- Exact/preferred room dimensions in millimetres, preserving the values and dimension mode supplied by the model.
- `must_be_adjacent` and `prefer_adjacent` pairs, privacy separation/grouping, entrance-side preference, parking dimensions and `vastu_mode`.
- A clarification response with one concise question when the plot is absent or hard constraints conflict.
- Rejection of unknown fields, unsupported room types, negative quantities, invalid floor number, malformed dimensions, duplicate adjacency pairs and oversized notes.
- Model output containing coordinates/room polygons is rejected because geometry is not part of the brief contract.
- Disabled/unreachable local model returns a typed `model_unavailable` result; no network call to any cloud provider is made.

Run: `PYTHONPATH=backend pytest -q -p no:cacheprovider backend/tests/test_room_planning_schemas.py backend/tests/test_room_planning_interpreter.py`

Expected red: imports or missing schema/service symbols fail, or the assertions show no strict brief/clarification contract exists.

- [ ] **Step 2: Implement the brief contract and interpreter**

Create strict Pydantic models with `extra="forbid"`:

- `RoomRequirement`: room type (including `parking`), quantity, optional user name, optional preferred width/depth and dimension mode (`preferred`, `minimum`, `exact`).
- `RoomAdjacencyPreference`: two room identifiers/types and priority (`must_be_adjacent`, `prefer_adjacent`).
- `RoomPrivacyPreference`: two room identifiers/types, relation (`separate`, `group`) and priority (`must`, `prefer`).
- `RoomPlanningBrief`: floor number, required rooms, `hard_constraints` as a bounded list of the user's original non-negotiable statements, typed adjacency/privacy preferences, circulation preferences, optional parking, orientation preferences, Vastu mode defaulting to `off`, and bounded notes. The typed fields are the enforceable contract: required-room quantities are exact; `minimum`/`exact` dimensions are hard; `must_be_adjacent` is hard; privacy separation is hard only when its priority is `must`. If a hard statement cannot be represented by a supported typed field, return a clarification rather than claiming it was satisfied.
- `PlanningClarification`: discriminator `type="clarification"`, reply, questions and suggestions.
- `PlanningBriefResponse`: discriminator `type="planning_brief"`, reply and brief.
- `PlanningBriefResult`: `status` (`brief`, `clarification`, `model_unavailable`, `invalid_model_response`), optional brief, reply, questions and safe error code.

The interpreter supplies only project/floor facts and bounded transcript context to the local model. The system prompt says project data and user content are untrusted, the model must not return coordinates, and Vastu is a traditional preference only. Parse with a discriminated Pydantic adapter. Never repair malformed model output by guessing.

- [ ] **Step 3: Verify focused tests**

Run the same focused pytest command.

Expected: all schema and interpreter tests pass; malformed or geometry-bearing model output is rejected; unavailable local model yields a typed result without cloud fallback.

- [ ] **Step 4: Run affected regression tests**

Run: `PYTHONPATH=backend pytest -q -p no:cacheprovider backend/tests/test_local_llm.py backend/tests/test_assistant_orchestrator.py backend/tests/test_assistant_conversations.py`

Expected: existing assistant behavior and transcript storage remain unchanged.

- [ ] **Step 5: Update API documentation**

Document the brief fields, model-unavailable and clarification outcomes, context limits, and the guarantee that the interpreter does not create geometry.

---

### Task 2: Deterministic rectangular room planner, openings, validation and scoring

**Files:**
- Create: `backend/app/services/room_layout_planner.py`
- Create: `backend/app/schemas/room_layout_candidates.py`
- Modify: `backend/app/schemas/layouts.py` (add `parking` to the room-type literal)
- Modify: `backend/app/schemas/assistant_ai.py` (add `parking` to the proposal room-type literal)
- Test: `backend/tests/test_room_layout_planner.py`
- Test: `backend/tests/test_room_layout_candidate_validation.py`

**Interfaces:**
- Consumes: `RoomPlanningBrief`, `plot_vertices(plot)`, `validate_layout_proposal(project, floor_number, rooms)`, `validate_layout_update(plot, payload)`.
- Produces: `LayoutCandidate`, `CandidateScore`, `CandidateValidation`, `PlannerResult`, `generate_layout_candidates(plot, brief, planner_config)`, `score_layout_candidate(candidate, brief, planner_config)`, and `validate_layout_candidate(project, floor_number, candidate)`.
- Planner output is proposal-shaped geometry in millimetres, with stable `candidate_key`, assumptions, warnings, score breakdown and planner version.

- [ ] **Step 1: Add focused failing tests**

Cover:

- A feasible 10,000×10,000 mm rectangular plot with living, kitchen, two bedrooms and bathroom yields at least one valid candidate.
- A 9,000×15,000 mm plot and a feasible brief yield distinct stable candidate keys for different templates; repeated calls with identical normalized inputs produce byte-equivalent room geometry and score ordering.
- Room polygons are axis-aligned rectangles, positive-sized, within the exact plot bounds, non-overlapping, and uniquely named.
- Hard exact/minimum dimensions are preserved; impossible hard dimensions or total room area produce an `infeasible` result with named reasons and no candidate.
- `must_be_adjacent` either holds on a positive-length shared edge or makes that candidate ineligible; `prefer_adjacent` becomes a visible soft warning/score effect when not achieved.
- Privacy separation/grouping changes the deterministic score and is explained in the breakdown.
- Room-to-room door openings fit within shared edges and are recorded on both connected room boundaries; external window openings fit on plot-boundary edges and do not overlap doors/windows.
- `parking` is represented as a typed room and persists through `RoomInput` and `LayoutProposalDraft` validation.
- Rectangle plot input is supported; a polygon with non-axis-aligned, non-rectangular, self-intersecting, holed or ambiguous bounds returns `unsupported_plot_geometry`, never a bounding-box approximation.
- Every valid candidate passes both existing proposal validation and layout validation; invalid candidates are returned as issues and are not eligible for persistence.
- Candidate scores are between 0 and 100, hard requirements are eligibility gates, component weights are deterministic and the explanation matches the score calculation.

Run: `PYTHONPATH=backend pytest -q -p no:cacheprovider backend/tests/test_room_layout_planner.py backend/tests/test_room_layout_candidate_validation.py`

Expected red: missing planner/schema imports or missing deterministic candidate behavior.

- [ ] **Step 2: Implement the bounded planner**

Use planner version `1.0` and the defaults/weights in the repository-decision section above. Normalize only exact rectangular boundaries: four unique corners, axis-aligned edges, opposite sides equal within 1 mm, positive width/depth. Use plot-local origin offsets so non-zero rectangular coordinates remain grounded. Reject all other polygon shapes.

Build room instances from `required_rooms`. Use explicit dimensions where provided; otherwise use the named product defaults and append each used default to `assumptions`. For `minimum`, chosen dimensions must be at least the requested values; for `exact`, they must match; for `preferred`, dimensions are the target for scoring and may be rotated if allowed. Never shrink an exact/minimum requirement to force a fit.

Run a bounded shelf-packing routine for `public_first`, `private_first` and `service_cluster` orderings. For each template, try the permitted width/depth orientations and stable tie-breaks. Do not use random numbers or unbounded search. Return no more than three distinct geometries. A template that cannot fit all rooms within plot bounds is discarded with a reason.

Create axis-aligned four-vertex polygons. Generate a shared-wall door only when two placed room rectangles share a segment long enough for the configured opening; place matching opening records on the corresponding edge of each room. Place a window on an exterior edge only when a suitable edge exists and the opening fits. Door/window offsets must be deterministic and validated by `RoomInput`.

Compute adjacency from shared positive-length edges. Compute circulation connectivity from door-connected room adjacency; report disconnected components and penalize unnecessary isolated rooms. Score only geometrically valid candidates. Include component scores, unmet preferences, assumptions and warnings. Stable candidate keys are hashes of normalized brief, template name, planner version and canonical room geometry.

- [ ] **Step 3: Verify focused tests**

Run the same focused pytest command.

Expected: all feasible examples return deterministic candidates; hard-constraint and unsupported-plot cases return explicit non-candidate outcomes; every eligible candidate passes the existing validators.

- [ ] **Step 4: Run geometry and proposal regression tests**

Run: `PYTHONPATH=backend pytest -q -p no:cacheprovider backend/tests/test_geometry.py backend/tests/test_projects.py backend/tests/test_assistant_proposals.py backend/tests/test_assistant_schemas.py`

Expected: existing manually authored layouts and proposal payloads remain valid; the added `parking` room type is accepted without changing stored database shape.

---

### Task 3: Authenticated generation API and independent candidate persistence

**Files:**
- Modify: `backend/app/api/projects.py`
- Modify: `backend/app/schemas/assistant.py`
- Create: `backend/app/schemas/room_layout_generation.py`
- Modify: `backend/app/schemas/assistant_ai.py` (candidate metadata fields in `LayoutProposalDraft`, with backward-compatible defaults)
- Modify: `backend/app/services/assistant_proposals.py` only if a batch helper is needed to create all valid candidates in one transaction.
- Test: `backend/tests/test_room_layout_generation_api.py`
- Test: `backend/tests/test_room_layout_candidate_ownership.py`
- Modify: `docs/api/design-assistant.md`

**Interfaces:**
- Consumes: `parse_room_planning_brief(...)`, `generate_layout_candidates(...)`, `validate_layout_candidate(...)`, `create_pending_proposal(...)`, `create_conversation(...)`, `load_transcript(...)`, `append_message(...)`.
- Produces: `POST /api/v1/projects/{project_id}/assistant/layout-generation`, `GET /api/v1/projects/{project_id}/assistant/conversations/{conversation_id}/proposals`, and a typed `LayoutGenerationOutput` containing outcome, conversation ID, reply/questions and candidate records.
- Every candidate uses an independent existing `AssistantProposalRecord` ID and base-layout hash; no new database table or migration is required.

- [ ] **Step 1: Add focused failing API tests**

Cover:

- Authenticated + CSRF-protected request with a valid rectangular project and fake local model returns `layout_candidates` with at most three candidates and stable proposal IDs.
- Clarification result persists user/assistant messages but creates no proposal records.
- Missing plot returns `missing_plot`; irregular plot returns `unsupported_plot_geometry`; impossible room brief returns `infeasible`, each with actionable explanation and zero proposal records.
- Candidate preview records are persisted as `draft`; GET conversation proposals restores every candidate and returns only records owned by the authenticated user/project.
- Existing saved floor rooms remain unchanged after generation and after candidate listing.
- Another user's project, conversation or proposal cannot be read or used to generate candidates.
- Applying one candidate uses existing fresh validation and base-layout fingerprint; changing the saved layout before apply returns `proposal_stale` and leaves saved geometry unchanged.
- Rejecting a candidate changes only that candidate's status.
- Malformed local-model output or unavailable runtime returns a safe typed failure and does not call a cloud provider.

Run: `PYTHONPATH=backend pytest -q -p no:cacheprovider backend/tests/test_room_layout_generation_api.py backend/tests/test_room_layout_candidate_ownership.py`

Expected red: route returns 404 or response models/services are missing.

- [ ] **Step 2: Implement the generation route**

Add strict request/response models. The request accepts `message`, `floor_number` and optional `conversation_id`, reusing current length and floor bounds. Require authentication and CSRF for POST. Resolve project ownership before reading context. Enforce conversation ownership and same-floor matching exactly as the existing assistant route.

Load bounded conversation history and current floor rooms. Before invoking the model, verify a plot exists and is an exact supported rectangle. Ask the interpreter for a `RoomPlanningBrief` or clarification. If clarification, persist the turn and return no candidates. If model unavailable/invalid, return an explicit typed outcome without cloud fallback. If brief succeeds, call the deterministic planner, validate every candidate again against the actual project, and persist only valid candidates. Persist all candidate records in one database transaction; if persistence fails, roll back the entire candidate batch. Append one assistant transcript message pointing to the first candidate for backward compatibility.

Add a conversation-owned candidate listing endpoint. It must first resolve the owned project and owned conversation, then query `AssistantProposalRecord` by conversation ID, project ID and owner ID. Sort by score descending and created time, and return proposal JSON, status, validation issues and score metadata. Do not expose another conversation's proposal records.

- [ ] **Step 3: Verify focused API tests**

Run the same focused pytest command.

Expected: valid brief creates independent pending records; clarification/infeasible/unsupported paths create none; all ownership and no-mutation assertions pass.

- [ ] **Step 4: Run complete backend regression suite**

Run: `PYTHONPATH=backend pytest -v -p no:cacheprovider`

Expected: all existing authentication, project, layout, geometry, assistant, proposal and new planning tests pass.

- [ ] **Step 5: Document endpoints and failure outcomes**

Document request/response examples for `layout_candidates`, `clarification`, `missing_plot`, `unsupported_plot_geometry`, `infeasible`, `model_unavailable` and `invalid_model_response`, plus the independent candidate proposal lifecycle.

---

### Task 4: Candidate comparison, preview selection and approval-gated frontend flow

**Files:**
- Modify: `frontend/app/components/DesignAssistant.tsx`
- Modify: `frontend/app/components/ProposalPreview.tsx`
- Modify: `frontend/app/components/PlanEditor.tsx`
- Modify: `frontend/app/globals.css`
- Modify: `frontend/app/components/assistant-state.mjs` only for pure candidate-selection helpers if needed.
- Test: `frontend/tests/assistant.test.mjs`
- Test: `frontend/tests/layout-candidates.test.mjs`
- Modify: `README.md` and `progress.md`

**Interfaces:**
- Consumes: `POST .../assistant/layout-generation` and `GET .../assistant/conversations/{id}/proposals`.
- Produces: frontend `LayoutCandidateView` and `CandidateSetState`, candidate switching, score/assumption/warning display, and existing explicit Apply/Reject callbacks using the selected candidate's proposal ID.
- Existing generic assistant chat remains available; floor-plan generation is a distinct explicit action in the assistant panel.

- [ ] **Step 1: Add focused failing frontend tests**

Cover:

- Candidate list sorting is stable and score-descending; equal scores preserve server order.
- Selecting candidate B updates the preview without changing saved-room snapshot or candidate A's data.
- Apply and Reject callbacks always receive the currently selected candidate's proposal ID.
- Clarification, infeasible, unsupported plot and model-unavailable states render explanatory copy and no Apply button.
- Candidate assumptions, warnings, score components and unmet preferences are exposed as readable text, not color alone.
- Candidate list restoration after conversation reload retains all independent proposal IDs.
- `parking` appears in room-type controls and uses a distinct, legible room fill.

Run: `node --test frontend/tests/layout-candidates.test.mjs frontend/tests/assistant.test.mjs`

Expected red: missing candidate-state helper or missing candidate UI behavior.

- [ ] **Step 2: Implement the generation and candidate UI**

Add a separate `Generate floor-plan options` action beside the existing chat submit action. It calls the new generation endpoint with the same conversation ID and floor. Clarification messages are added to the transcript; the user can answer and generate again. On `layout_candidates`, load all candidate records and pass them to `PlanEditor`.

Extend `ProposalPreview` to show a candidate selector, score total, component breakdown, assumptions, warnings, unmet preferences and validation issues. Switching candidates changes only the displayed proposal. Room coordinate editing continues to be local preview state. Apply/Reject buttons use the selected candidate record ID and existing CSRF-protected endpoints. Applying a candidate refreshes the saved floor; rejecting it leaves saved geometry untouched. On transcript reload, call the conversation proposal-list endpoint and restore all candidates.

Add `parking` to the editor and preview room-type choices and room color map. Use accessible labels, keyboard-operable controls and textual score labels.

- [ ] **Step 3: Verify focused frontend tests**

Run the same Node test command.

Expected: candidate switching and selected-ID callbacks pass; clarification/infeasible states cannot apply; existing assistant state tests remain green.

- [ ] **Step 4: Run frontend unit tests and syntax checks**

Run: `node --test frontend/tests/*.test.mjs` from `frontend/`.

Then transpile every `frontend/app/**/*.tsx` file using the installed TypeScript `transpileModule` API (syntax check only).

Expected: all Node tests pass and every TSX file transpiles without syntax diagnostics. This is not a substitute for a dependency-backed typecheck or Next.js production build.

- [ ] **Step 5: Run final release checks and update documentation**

Run backend suite, frontend suite, Python compile, migration upgrade/downgrade/re-upgrade using the existing SQLite test URL, archive integrity check and inspect the archive contents. Update README/progress with actual verification evidence and remaining environmental limitations.

Expected: tests and migrations pass. If Next.js dependencies, browser runtime, live PostgreSQL or local Ollama model are unavailable, report those checks as not run rather than passing.

---

## Acceptance checklist

- [ ] The model returns only a typed brief or clarification; it never supplies room coordinates.
- [ ] Missing/unsupported plot geometry is explicit and never approximated.
- [ ] At least one feasible rectangular-plot example produces a valid candidate.
- [ ] Up to three distinct deterministic candidates are produced when feasible.
- [ ] Every candidate passes existing proposal and layout validation before persistence.
- [ ] Hard constraints are met or produce explicit infeasibility; no silent shrinking or dropped rooms.
- [ ] Candidate score and component explanation are deterministic and visible.
- [ ] Candidate alternatives persist independently and can be restored after reload.
- [ ] Candidate preview and switching never mutate saved rooms.
- [ ] Apply revalidates and checks the base-layout hash; stale candidates cannot overwrite newer work.
- [ ] Reject changes only proposal status and leaves saved geometry unchanged.
- [ ] Vastu remains opt-in and labelled traditional.
- [ ] All user-facing claims remain within the geometric/planning scope.

## Unresolved external runtime checks

These do not block deterministic unit/API implementation, but they remain release checks requiring services not available in the current workspace: full Next.js build and browser interaction, live PostgreSQL execution, and live Ollama inference with a configured local model. The exact installed model's structured-output compatibility must be verified against a real runtime before enabling production use.
