# WP5E Complete Architectural Intelligence Implementation Plan

> **For agentic workers:** Use the host's available task-by-task implementation workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent furniture planning, deterministic opening suggestions, and room-usability analysis to BrahmaAI Studio's existing 2D architectural editor without silently changing user-approved geometry.

**Architecture:** Keep the backend authoritative for furniture geometry, validation, deterministic arrangement, opening suggestions, usability analysis, and stale-preview protection. Persist furniture as JSON on each room, expose non-mutating optimization previews and an explicit validated apply endpoint, and extend the existing SVG editor with focused furniture controls and issue overlays. Reuse the current project ownership, CSRF, SQLAlchemy, Pydantic, FastAPI, and Next.js patterns.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, pytest, TypeScript, React 19, Next.js 15, Node's built-in test runner, SVG.

## Global Constraints

- Scope is existing single-floor layouts: furniture planning, opening optimization, and room-usability analysis.
- The feature is an early-stage planning aid, not CAD/BIM and not certification of structure, fire egress, accessibility, daylight, ventilation, plumbing/electrical, or local codes.
- Millimetres are canonical for all persisted and API geometry. Furniture coordinates are center points in the same plot coordinate frame as room vertices, never screen pixels.
- Furniture footprints are rectangles with quarter-turn rotations only (0, 90, 180, 270 degrees). Persist placed dimensions so catalog changes never silently resize existing items.
- Catalog dimensions are editable starting presets, not manufacturer specifications.
- Hard validation covers positive dimensions, unique item IDs, supported rotations, room containment with the configured 50 mm default planning wall margin, and direct furniture overlap. Opening/approach/working-clearance conflicts are warnings unless a specific hard geometric conflict applies.
- Clearance values are configurable planning heuristics, not code minima. Do not describe heuristic movement paths as accessible routes or certified egress.
- Never silently move, resize, rotate, add, or delete user furniture or openings. Preview is non-mutating; application requires explicit user action and complete server-side revalidation.
- Automatic placement is supported only for orthogonal rectangular rooms with axis-aligned edges. Do not approximate unsupported geometry with bounding boxes; return a structured unsupported-geometry result.
- Door/window suggestions must preserve current opening records unless the user explicitly applies a reviewed edit. Do not claim exact hinge swing simulation; use conservative swing-clearance estimates only.
- Existing project ownership checks and CSRF protection apply to every state-changing endpoint. Recompute fingerprints, validation, and scores on the server.
- Keep existing assistant proposal Apply/Reject behavior intact. Integrate furniture into proposal validation/persistence without weakening stale-proposal checks.
- Old clients that omit `furniture` preserve saved furniture only when a room can be matched by case-folded name. If furniture-bearing rooms cannot be matched safely, return a conflict instead of silently deleting furniture. An explicit `furniture: []` clears it.
- Keep the core deterministic and local-first. No external AI service is required for geometry, search, or validation.
- Workspace currently has no `.git` directory. Do not claim commits were created; if Git is initialized later, commit each independently passing task using the messages listed below.

---

### Task 1: Persist and validate room furniture data

**Files:**
- Modify: `backend/app/models/project.py` — add `Room.furniture_json` text column with default `[]`.
- Create: `backend/migrations/versions/0008_room_furniture.py` — add non-null `furniture_json` with server default `[]`; downgrade drops only this column.
- Modify: `backend/app/schemas/layouts.py` — define furniture/catalog schemas and extend room input/output.
- Modify: `backend/app/services/layouts.py` — preserve furniture for legacy omitted-field payloads and persist explicit furniture arrays.
- Modify: `backend/app/api/projects.py` — serialize furniture in layout output.
- Modify: `backend/app/schemas/assistant_ai.py` and `backend/app/services/assistant_proposals.py` — ensure proposal layout validation and application carry furniture and include furniture in stale-layout fingerprints.
- Test: `backend/tests/test_furniture_schemas.py` (create).
- Test: `backend/tests/test_furniture_persistence.py` (create).
- Test: `backend/tests/test_assistant_proposals.py` (extend).

**Interfaces:**
- `FurnitureInput`: `item_id: str`, `catalog_type: str`, `name: str`, `x_mm: float`, `y_mm: float`, `width_mm: float`, `depth_mm: float`, `rotation_deg: Literal[0, 90, 180, 270]`.
- `RoomInput.furniture: list[FurnitureInput] | None`; `None` means omitted by a legacy client, while `[]` means explicitly clear.
- `RoomOutput.furniture: list[FurnitureInput]` always returns an array.
- `persist_floor_rooms(db, project_id, payload)` retains its existing signature and gains safe room-name matching for omitted furniture.

- [x] **Step 1: Add focused failing tests**

Test Pydantic acceptance of each quarter-turn and rejection of unsupported rotation, zero/negative footprint dimensions, blank identifiers/names, duplicate `item_id` values within one room, and more than the agreed bounded furniture count (maximum 100 items per room). Test that `RoomOutput` defaults missing legacy furniture to `[]`. Add persistence tests for: explicit furniture save/reload; explicit empty array clears; omitted field on a same-name room preserves furniture; omitted field on a renamed room with existing furniture returns a conflict; omitted field on a room without furniture remains backward-compatible. Extend proposal tests to assert furniture participates in serialized proposals and stale hashes.

- [x] **Step 2: Verify the relevant failures**

Run: `cd backend && pytest tests/test_furniture_schemas.py tests/test_furniture_persistence.py tests/test_assistant_proposals.py -q`
Expected: new tests fail because the schema, column, compatibility merge, and fingerprint integration do not yet exist; existing proposal tests continue to collect.

- [x] **Step 3: Implement the minimum persistence contract**

Add `furniture_json` to the SQLAlchemy Room model and migration `0008_room_furniture` after `0007_assistant_proposals`. Define strict bounded Pydantic furniture data. Add `furniture` to room serialization. In `persist_floor_rooms`, load the existing floor before deletion, index saved rooms by `name.strip().casefold()`, and for omitted furniture copy the prior room's decoded `furniture_json` only on an unambiguous name match. If any unmatched existing room contains furniture and the incoming legacy payload could discard it, raise a dedicated `ValueError`/domain conflict before deleting any rows. Explicit arrays are authoritative. Ensure the route maps the domain conflict to HTTP 409 and rolls back. Include furniture in `fingerprint_floor_state`, proposal draft schemas, validation, and apply path. Preserve all existing opening and geometry behavior.

- [x] **Step 4: Verify the focused pass**

Run: `cd backend && pytest tests/test_furniture_schemas.py tests/test_furniture_persistence.py tests/test_assistant_proposals.py -q`
Expected: all focused tests pass; explicit empty arrays clear furniture and legacy omitted payloads cannot silently erase it.

- [x] **Step 5: Run the affected integration check**

Run: `cd backend && pytest tests/test_projects.py tests/test_assistant_proposals.py -q`
Expected: existing layout/opening/proposal flows pass with furniture defaulting to an empty array.

- [x] **Step 6: Record the independently passing deliverable**

If the workspace has been initialized as a Git repository, commit the task files with `feat: persist room furniture layouts`; otherwise leave the working tree uncommitted and report that this workspace has no Git metadata.

### Task 2: Build deterministic furniture geometry, arrangement, opening, and usability services

**Files:**
- Create: `backend/app/schemas/design_optimization.py` — optimization request/response, issue, candidate, and suggestion contracts.
- Create: `backend/app/services/furniture_catalog.py` — typed catalog presets and room-type filtering.
- Create: `backend/app/services/furniture_geometry.py` — rectangle transforms, containment, overlap, clearance zones, and opening intersection helpers.
- Create: `backend/app/services/furniture_planner.py` — deterministic bounded arrangement search.
- Create: `backend/app/services/opening_optimizer.py` — reasoned door/window suggestions.
- Create: `backend/app/services/room_usability.py` — room metrics, access, circulation and connectivity heuristics.
- Reuse: `backend/app/services/geometry.py` for established polygon primitives where suitable.
- Test: `backend/tests/test_furniture_catalog.py` (create).
- Test: `backend/tests/test_furniture_geometry.py` (create).
- Test: `backend/tests/test_furniture_planner.py` (create).
- Test: `backend/tests/test_opening_optimizer.py` (create).
- Test: `backend/tests/test_room_usability.py` (create).

**Interfaces:**
- `catalog_for_room(room_type: str) -> list[dict]` returns stable catalog IDs, names, default dimensions, and applicable room types.
- `validate_furniture(room: RoomInput, furniture: list[FurnitureInput], wall_margin_mm: float = 50) -> list[FurnitureIssue]` returns stable issue codes, severity, item IDs, and explanatory messages.
- `generate_furniture_arrangements(room: RoomInput, requested_items: list[FurnitureInput] | None, *, max_candidates: int = 3, search_budget: int = 5000) -> FurniturePlannerResult` is deterministic and bounded.
- `suggest_openings(rooms: list[RoomInput], plot_context: dict, floor_number: int) -> list[OpeningSuggestion]` returns suggestions with reason and assumptions; it never mutates inputs.
- `analyze_room_usability(rooms: list[RoomInput], *, clearance_preferences: dict | None = None) -> RoomUsabilityResult` returns metrics, warnings, and disconnected circulation components.

- [x] **Step 1: Add focused failing tests**

Catalog tests assert stable IDs, dimensions, and room-type filtering. Geometry tests cover 0/90/180/270 rotations, center-to-corner transforms, boundary containment, 50 mm wall margin, direct overlaps, openings on each edge, and approach-clearance warnings. Planner tests cover repeatability, at most three distinct candidates, deterministic tie-breaking, explicit item preservation, search-budget exhaustion distinct from infeasibility, and unsupported nonorthogonal room geometry. Opening tests cover shared-wall adjacency, existing opening preservation, blocked door/window positions, road-facing side ambiguity, and no external entrance suggestion when road side is unknown. Usability tests cover area and unoccupied-area metrics, obstructed approach zones, interrupted narrow corridors, disconnected room graph, and Vastu being absent unless separately requested.

- [x] **Step 2: Verify the relevant failures**

Run: `cd backend && pytest tests/test_furniture_catalog.py tests/test_furniture_geometry.py tests/test_furniture_planner.py tests/test_opening_optimizer.py tests/test_room_usability.py -q`
Expected: collection or assertion failures identify the missing modules and required geometry behavior.

- [x] **Step 3: Implement deterministic services**

Create catalog presets for the spec's bedroom, living, dining, kitchen, bathroom, study, and utility items. Implement rotated rectangular footprints using center coordinates and quarter turns. Validate strict geometry separately from advisory clearance zones. Detect opening conflicts by projecting furniture/clearance rectangles onto wall-edge intervals. Implement bounded candidate generation only for orthogonal rectangular rooms, with deterministic anchor ordering, stable scoring, stable tie-breaking, and explicit statuses (`complete`, `search_exhausted`, `unsupported_geometry`, `infeasible`). Return up to three distinct candidates with candidate key, solver version, placements, issue list, score breakdown, assumptions, and unmet preferences. Implement opening suggestions from room adjacency and plot context; do not alter openings. Implement usability metrics and heuristic movement graph without claims of code compliance or accessibility certification.

- [x] **Step 4: Verify the focused pass**

Run: `cd backend && pytest tests/test_furniture_catalog.py tests/test_furniture_geometry.py tests/test_furniture_planner.py tests/test_opening_optimizer.py tests/test_room_usability.py -q`
Expected: all tests pass; deterministic repeated calls produce byte-equivalent normalized candidates and unsupported geometry is reported rather than approximated.

- [x] **Step 5: Run the affected integration check**

Run: `cd backend && pytest tests/test_geometry.py tests/test_projects.py -q`
Expected: existing room geometry and opening validation remain unchanged.

- [x] **Step 6: Record the independently passing deliverable**

If Git metadata exists, commit with `feat: add deterministic architectural planning engines`; otherwise do not fabricate a commit.

### Task 3: Expose non-mutating optimization preview and stale-safe apply APIs

**Files:**
- Modify: `backend/app/api/projects.py` — add preview/apply routes and request dispatch.
- Modify: `backend/app/schemas/design_optimization.py` — finalize strict API contracts.
- Create: `backend/app/services/design_optimization.py` — orchestration, source fingerprint, preview assembly, apply validation.
- Modify: `backend/app/services/layouts.py` — atomic persistence path and compatibility handling shared by apply.
- Test: `backend/tests/test_design_optimization_api.py` (create).

**Interfaces:**
- `POST /api/v1/projects/{project_id}/design-optimization/preview` accepts `DesignOptimizationPreviewInput(floor_number, operation, room_ids?, requested_items_by_room?, clearance_preferences?)`; `operation` is `furniture_arrangement | opening_suggestions | full_review`.
- Preview returns `DesignOptimizationPreview(source_layout_fingerprint, operation, candidates, opening_suggestions, room_analyses, issues, solver_version)` and never writes to the database.
- `POST /api/v1/projects/{project_id}/design-optimization/apply` accepts `DesignOptimizationApplyInput(floor_number, source_layout_fingerprint, rooms: list[RoomInput])` and returns the saved `LayoutOutput`.
- `fingerprint_optimization_source(project, floor_number, rooms) -> str` hashes plot context and canonical saved room geometry, openings, and furniture.
- `build_optimization_preview(...)` composes only the requested operation and returns deterministic output.
- `apply_optimization_layout(...)` recomputes fingerprint, validates the complete submitted layout, and persists in one transaction.

- [x] **Step 1: Add focused failing API tests**

Test preview for each operation and full review; preview does not change database rows; missing floor and unknown room IDs return stable 404/422 outcomes; owner isolation returns 404; missing CSRF on apply returns 403; valid CSRF is accepted. Test preview fingerprint changes when plot, geometry, openings, or furniture changes. Test apply rejects stale fingerprint with HTTP 409 and no partial writes; rejects invalid furniture/room geometry with HTTP 422 and no partial writes; accepts edited valid room layout and persists it; a database failure rolls back the entire floor replacement.

- [x] **Step 2: Verify the relevant failures**

Run: `cd backend && pytest tests/test_design_optimization_api.py -q`
Expected: route-not-found or contract failures demonstrate the missing API behavior.

- [x] **Step 3: Implement preview and apply orchestration**

Load the owned project using `owned_project`, fetch only the requested floor, and canonicalize the source state. Preview calls only deterministic services and returns a fingerprint; do not call `db.add`, `db.delete`, or `commit` in preview. Apply checks the submitted fingerprint against a fresh canonical hash before parsing/persisting the full layout. Return HTTP 409 with code `optimization_preview_stale` for stale source; HTTP 422 with structured validation issues for invalid layout; do not write any room until all request and geometry validation passes. Keep owner and CSRF dependencies consistent with current project routes. Bound request item count, candidate count, and solver budget at the schema/service boundary. Wrap persistence in a transaction with rollback on any exception. Reuse the same layout serializer for the response.

- [x] **Step 4: Verify the focused pass**

Run: `cd backend && pytest tests/test_design_optimization_api.py -q`
Expected: all API tests pass, including non-mutation, ownership, CSRF, stale fingerprint, and atomic rollback assertions.

- [x] **Step 5: Run the affected integration check**

Run: `cd backend && pytest tests/test_projects.py tests/test_assistant_proposals.py tests/test_design_optimization_api.py -q`
Expected: existing layout and assistant proposal flows still pass with the new furniture-aware fingerprint and persistence.

- [x] **Step 6: Record the independently passing deliverable**

If Git metadata exists, commit with `feat: add architectural optimization preview api`; otherwise leave changes uncommitted.

### Task 4: Integrate editable furniture studio and review overlays into the SVG editor

**Files:**
- Create: `frontend/app/components/FurnitureStudio.tsx` — catalog, item inspector, selection, placement and candidate controls.
- Create: `frontend/app/components/OptimizationReviewPanel.tsx` — preview candidates, opening suggestions, usability issues, apply/reject controls.
- Create: `frontend/app/lib/furniture-geometry.ts` — pure mm-to-SVG geometry and footprint transform helpers.
- Create: `frontend/tests/furniture-geometry.test.mjs` — pure transform tests.
- Modify: `frontend/app/components/PlanEditor.tsx` — extend Room type, render furniture SVG, include furniture in autosave payload, integrate panels and stale state.
- Modify: `frontend/app/globals.css` — focused studio styles.
- Modify: `frontend/app/page.tsx` only if props/context wiring is needed; prefer keeping integration inside PlanEditor.

**Interfaces:**
- Frontend `FurnitureItem` mirrors the backend fields exactly: `item_id`, `catalog_type`, `name`, `x_mm`, `y_mm`, `width_mm`, `depth_mm`, `rotation_deg`.
- `furnitureToSvgRect(item, scale, origin)` and `rotateFurniture(item, direction)` are pure helpers with unit tests.
- `FurnitureStudio` receives selected room, catalog, selected item, and callbacks; it does not own or persist project data.
- `OptimizationReviewPanel` receives preview state, edited candidate layout, busy state, and explicit `onApply`/`onDiscard` callbacks.

- [x] **Step 1: Add focused failing frontend tests**

Test center-point conversion to SVG rectangle, 90-degree footprint swap, rotation normalization, and stable serialization of furniture. Add component-level tests using the repository's available test setup only if dependencies already support it; otherwise keep interactions covered by extracting pure state/transform helpers and exercising them through `node --test`.

- [x] **Step 2: Verify the relevant failures**

Run: `cd frontend && node --test tests/furniture-geometry.test.mjs`
Expected: missing helper module or assertions fail before implementation.

- [x] **Step 3: Implement furniture editing and review UI**

Extend the room client type with `furniture: FurnitureItem[]`. Render each item as a selectable SVG group with a footprint rectangle, label, and rotation transform in the existing plot coordinate frame. Support catalog drag/drop into a room, selection, move, rotate, resize, duplicate, and delete. Ensure pointer-to-mm conversion uses the same transform as room editing. Include furniture arrays in the autosave payload so existing debounce saves preserve them. Add controls to request arrangement/opening/full-review previews, compare up to three candidates, inspect reasons and assumptions, edit candidate furniture before apply, and explicitly apply or discard. Do not autosave a server preview; do not apply invalid or stale preview state. Display hard errors distinctly from advisory clearance warnings. Preserve existing PlanEditor room/opening editing, assistant proposals, and save status behavior.

- [x] **Step 4: Verify the focused pass**

Run: `cd frontend && node --test tests/furniture-geometry.test.mjs tests/*.test.mjs`
Expected: new geometry tests and all existing assistant/layout geometry tests pass.

- [x] **Step 5: Run the affected integration check**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: TypeScript and Next.js production build pass when frontend dependencies are installed. In the current workspace `node_modules` is absent, so if these commands report missing executables, record them as environment-blocked rather than passing; do not install dependencies implicitly.

- [x] **Step 6: Record the independently passing deliverable**

If Git metadata exists, commit with `feat: add interactive furniture planning studio`; otherwise do not claim a commit.

### Task 5: End-to-end regression, migration verification, and user-facing documentation

**Files:**
- Create: `backend/tests/test_design_optimization_workflow.py` — full API workflow.
- Create: `backend/tests/test_furniture_migration.py` — migration upgrade/backfill/downgrade checks.
- Modify: `README.md` — feature description, setup, limits, and workflow.
- Modify: `progress.md` — WP5E completion evidence and remaining environment limitations.
- Modify: `docs/specs/2026-11-06-wp5e-complete-architectural-intelligence-design.md` only if implementation reveals a documented deviation; do not rewrite the approved requirements silently.

**Interfaces:**
- End-to-end flow: saved layout GET → preview POST → user-edited complete layout → apply POST → saved layout GET.
- Migration path: current head `0007_assistant_proposals` → `0008_room_furniture`; existing rooms backfill to `furniture_json='[]'`.

- [x] **Step 1: Add failing end-to-end and migration tests**

Build a fixture with adjacent rooms, a plot road-facing side, doors/windows, and one existing furniture item. Assert preview leaves the stored floor unchanged, candidate response is stable, an edited valid layout applies, and subsequent GET returns exact furniture and opening data. Assert a stale preview after an independent layout save is rejected. Migration test creates a database at revision `0007_assistant_proposals`, inserts an existing room, upgrades to `0008_room_furniture`, and verifies the row remains with `[]`; downgrade removes the new column cleanly.

- [x] **Step 2: Verify the relevant failures**

Run: `cd backend && pytest tests/test_design_optimization_workflow.py tests/test_furniture_migration.py -q`
Expected: workflow fails until all feature layers are integrated; migration fails until the new revision exists.

- [x] **Step 3: Complete integration and documentation**

Fix only integration defects exposed by the workflow. Document furniture editing, the three preview operations, explicit apply, deterministic limitations, supported geometry, heuristic clearances, and the non-certification boundary. Update progress with concrete test commands and truthful environment status. Ensure API OpenAPI schemas describe the new contracts and no documentation implies code compliance or physics/civil-engineering certification.

- [x] **Step 4: Verify the full backend and frontend test suites**

Run: `cd backend && pytest -q`
Expected: all existing and new backend tests pass. Then run: `cd frontend && node --test tests/*.test.mjs`
Expected: all frontend Node tests pass.

- [x] **Step 5: Verify migration and static checks**

Run: `cd backend && alembic upgrade head` against a disposable configured test database, followed by `alembic downgrade 0007_assistant_proposals` and `alembic upgrade head`.
Expected: migration upgrades and downgrades without losing pre-existing room rows. Run `python -m compileall app tests` from `backend`; expected no syntax errors. Run frontend `npx tsc --noEmit` and `npm run build` only where dependencies are installed; report missing dependencies as blocked, not passed.

- [x] **Step 6: Record the completed deliverable**

If Git metadata exists, commit with `feat: deliver WP5E architectural intelligence`; otherwise report that the workspace has no `.git` directory. Summarize test evidence and explicitly list checks not run because PostgreSQL, frontend dependencies, local LLM, or browser automation are unavailable.

## Unresolved Product Decisions

- **Catalog localization:** The initial preset catalog will use metric millimetre dimensions and neutral names. Local manufacturer-specific catalogs and regional product standards are outside this release; add them only when a user supplies a target market or catalog source.
- **Clearance preference values:** The feature will expose editable planning preferences with conservative defaults, but these values remain user-adjustable heuristics. They must not be presented as statutory minimums.
- **Opening optimization authority:** Suggestions are advisory. The initial release will not automatically add or move openings; users may edit openings in the existing editor and then apply a reviewed complete layout.
- **Solver budget:** Initial deterministic budget is capped at 5,000 candidate evaluations per room and at most three returned candidates. Performance tuning may lower the cap based on measured latency, but must not increase it without regression/performance evidence.
- **Furniture support for nonorthogonal rooms:** Manual placement can be validated against polygon geometry where supported by the geometry primitives; automatic arrangement returns `unsupported_geometry` for nonorthogonal or non-axis-aligned room edges.
