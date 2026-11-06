# WP5D — Intelligent Spatial Layout Optimization Implementation Plan

> **For agentic workers:** Use the host's available task-by-task implementation workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the WP5C row packer with a deterministic bounded spatial-search planner that produces up to three meaningfully different, validator-approved rectangular room layouts and explains search limits, proportions, utilization, and circulation.

**Architecture:** Keep the public generation API and proposal lifecycle, but move geometry discovery into a bounded depth-first search over deterministic room-order seeds, legal orientations, and anchors derived from already placed room edges. Extend typed preferences and candidate metadata additively; validate each completed layout with the existing geometry and proposal validators before persistence. Rank candidates using a versioned score and select for both quality and spatial diversity.

**Tech Stack:** Python 3.11+, Pydantic v2, FastAPI, existing geometry/layout validators, pytest; Next.js 15, React 19, TypeScript, Node test runner.

## Global Constraints

- Exact axis-aligned rectangular plots only; never approximate irregular plots with bounding boxes.
- Exact dimensions remain exact; minimum dimensions are never reduced; preferred dimensions remain the requested target or documented product defaults when omitted.
- Hard constraints are gates, not soft score bonuses.
- Search is deterministic and bounded by internal safe defaults and hard ceilings; request data cannot raise those limits.
- Search-budget exhaustion must not be described as proof of mathematical impossibility.
- Every candidate must pass existing layout and proposal validation before persistence.
- Generation must not mutate saved floor geometry; only explicit Apply can do so after current-state revalidation.
- Local model interpretation may create typed intent only; deterministic planner code owns coordinates. No remote model or new solver dependency is introduced.
- Corridors reserve real rectangular floor area. Connectivity warnings are not a claim of safe or compliant egress.
- Free-text circulation/orientation notes remain disclosed as unverified unless represented by structured fields.
- Vastu remains optional traditional reference material, not a scientific or engineering guarantee.
- Persisted WP5C planner-version `1.0` proposals remain readable and actionable.
- Scores are deterministic planning heuristics, not professional quality, structural, fire, accessibility, MEP, daylight, ventilation, or building-code certification.

---

### Task 1: Add typed room proportion preferences and planner search contracts

**Files:**
- Modify: `backend/app/schemas/room_planning.py`
- Modify: `backend/app/schemas/room_layout_candidates.py`
- Create: `backend/app/services/room_layout_search.py`
- Test: `backend/tests/test_room_planning_schemas.py`
- Test: `backend/tests/test_room_layout_search.py`

**Interfaces:**
- Existing input: `RoomPlanningBrief`, `RoomRequirement`, `generate_layout_candidates(plot, brief, planner_config=None)`.
- Add to `RoomRequirement`: optional `target_aspect_ratio: StrictFloat | StrictInt | None` and optional `long_axis_orientation: Literal["north_south", "east_west"] | None`. Both are preferences only; no preference means neutral scoring. Aspect ratio is width/depth in the brief's local coordinate frame.
- Add immutable internal search contracts in `room_layout_search.py`: `SearchLimits(max_nodes, max_solutions, max_depth)`, `SearchSolution(placements: tuple[dict, ...], seed_label: str)` and `SearchResult(solutions: tuple[SearchSolution, ...], nodes_visited: int, budget_exhausted: bool)`, and `search_room_layouts(rooms, bounds, brief, limits) -> SearchResult`. Keep internal contracts private to the planner package unless tests demonstrate a stable public seam is needed.
- Add candidate metadata fields with defaults for backward compatibility: `score_version: str = "1.0"`, `search_status: Literal["complete", "budget_exhausted"] = "complete"`, `utilization: UtilizationSummary | None`, and `circulation_components: list[list[str]] = []`. `UtilizationSummary` contains `plot_area_mm2`, `assigned_area_mm2`, `unallocated_area_mm2`, and `utilization_percent`. `PlannerResult.status` is exactly `Literal["layout_candidates", "infeasible", "unsupported_plot_geometry", "search_exhausted"]`; `search_exhausted` means the node budget ended before a solution was found and is not proof of infeasibility.

- [x] **Step 1: Add focused failing schema and search-contract tests**

Add schema tests for accepted ratio/orientation preferences, omitted preferences, invalid non-positive ratios, and invalid orientation literals. Add search tests proving the new search result reports node count and budget exhaustion distinctly from a complete no-solution search. Add compatibility tests proving old WP5C candidate dictionaries still parse with metadata defaults.

- [x] **Step 2: Verify the relevant failures**

Run: `cd backend && pytest -q tests/test_room_planning_schemas.py tests/test_room_layout_search.py`
Expected: collection or assertion failures because the new preference fields, search contracts, and additive metadata do not yet exist. Confirm failures are behavioral, not import/setup errors.

- [x] **Step 3: Implement the minimum contracts**

Add strict optional preference fields without changing existing required-room defaults. Reject only invalid values that violate the new declared field type/range. Add internal search dataclasses and safe default limits (initial recommendation: 20,000 expanded nodes, depth bounded by the 100-room schema cap, and at most 24 internally retained solutions before public ranking selects up to 3); hard ceilings are code constants and cannot be overridden by API payloads. Add backward-compatible optional candidate/result metadata. Do not yet replace the current planner loop in this task.

- [x] **Step 4: Verify the focused pass**

Run: `cd backend && pytest -q tests/test_room_planning_schemas.py tests/test_room_layout_search.py`
Expected: all focused tests pass, including old candidate deserialization.

- [x] **Step 5: Run the affected integration check**

Run: `cd backend && pytest -q tests/test_room_layout_candidate_validation.py`
Expected: existing candidate validation remains green with metadata defaults.

- [x] **Step 6: Commit the passing deliverable**

No Git metadata is present in the supplied workspace, so preserve the task boundary in the plan and record the completed files in `progress.md`; do not claim a commit.

---

### Task 2: Replace shelf packing with bounded deterministic spatial search

**Files:**
- Modify: `backend/app/services/room_layout_planner.py`
- Modify: `backend/app/services/room_layout_search.py`
- Test: `backend/tests/test_room_layout_search.py`
- Test: `backend/tests/test_room_layout_planner.py`
- Test: `backend/tests/test_room_layout_candidate_validation.py`

**Interfaces:**
- Consume: `RoomPlanningBrief`, expanded room records, `PlotBounds`, `SearchLimits`, `search_room_layouts(...)`.
- Produce: deterministic ordered placement sets with room `name`, `room_type`, `x`, `y`, `width`, `depth`, `mode`, and `allow_rotation`; include search node count and exhaustion state.
- Keep `generate_layout_candidates(plot, brief, planner_config=None) -> PlannerResult` as the public planner entry point.

- [x] **Step 1: Add regression tests that fail against WP5C packing**

Create a small rectangular-plot fixture with a deliberately awkward set of hard-sized rectangles where the old left-to-right row packer fails but a legal non-row arrangement exists. Assert the new planner returns at least one candidate, every room remains inside the plot, and no pair overlaps. Add tests for alternate orientations, non-zero plot origin, deterministic repeated runs, exact/minimum dimensions not being reduced, and a tiny search budget that returns explicit exhaustion rather than proven infeasibility.

- [x] **Step 2: Verify the relevant failures**

Run: `cd backend && pytest -q tests/test_room_layout_search.py tests/test_room_layout_planner.py -k 'backtracking or orientation or budget or origin'`
Expected: the new regression case fails because the current packer is row-only and has no search-budget status; existing setup and imports must succeed.

- [x] **Step 3: Implement bounded placement search**

Generate deterministic room-order seeds using (a) largest/most-constrained first (`largest_first`), (b) mandatory-adjacency group first (`adjacency_first`), and (c) public/private/service priority (`public_first`, `private_first`, `service_cluster`). Preserve the three WP5C seed labels and add the two new labels as additive enum values. Generate only legal orientations: preserve exact and minimum dimensions; rotate only when `allow_rotation` is true; do not silently scale dimensions. For each room, enumerate anchors at the plot origin and at edges/corners of already placed rooms, then prune anchors that leave the plot or overlap an existing room. Use deterministic tie-breaking, bounded depth-first backtracking, a node budget, and safe memoization keyed by canonical partial placements plus remaining room identities. As soon as both endpoints of a mandatory adjacency or privacy rule are placed, prune the branch if that hard relationship is already violated. Return the best distinct completed placement sets found before the budget. If aggregate required area exceeds plot area or a hard room dimension cannot fit either allowed orientation, retain a proven preflight failure; otherwise distinguish complete search with no solution from budget exhaustion with no solution. Never use bounding-box approximation for irregular plots.

- [x] **Step 4: Verify the focused pass**

Run: `cd backend && pytest -q tests/test_room_layout_search.py tests/test_room_layout_planner.py -k 'backtracking or orientation or budget or origin'`
Expected: the awkward-fit regression produces a valid layout; repeated calls produce identical geometry and search counts; exhausted searches report exhaustion.

- [x] **Step 5: Run the affected integration check**

Run: `cd backend && pytest -q tests/test_room_layout_planner.py tests/test_room_layout_candidate_validation.py`
Expected: existing hard adjacency/privacy, openings, plot containment, deterministic candidate, and proposal-validation tests remain green. Update assertions that intentionally encode WP5C planner version/template internals to the versioned WP5D contract without weakening behavioral checks.

- [x] **Step 6: Commit the passing deliverable**

No Git metadata is present; record the completed search-engine task in `progress.md` and preserve the existing WP5C archive unchanged.

---

### Task 3: Add circulation, proportions, utilization scoring, and diverse candidate ranking

**Files:**
- Modify: `backend/app/services/room_layout_planner.py`
- Modify: `backend/app/schemas/room_layout_candidates.py`
- Test: `backend/tests/test_room_layout_planner.py`
- Test: `backend/tests/test_room_layout_candidate_validation.py`

**Interfaces:**
- Consume: completed placements from `search_room_layouts`, room proportion preferences, existing `_shared_edge`, `_make_openings`, and layout validators.
- Produce: `LayoutCandidate` planner version `2.0`, score version `2.0`, normalized geometry identity, score breakdown, `search_status`, utilization summary (`plot_area_mm2`, `assigned_area_mm2`, `unallocated_area_mm2`, `utilization_percent`), and named disconnected circulation components.
- Existing `LayoutCandidate.proposal_payload(floor_number)` remains the persistence boundary; new keys are additive.

- [x] **Step 1: Add focused failing scoring and metadata tests**

Test that target aspect ratio and long-axis orientation influence ranking but never override hard dimensions or rotation restrictions; absent preferences add no penalty. Test that an explicit `corridor` requirement occupies real plot area and appears in room geometry. Test that disconnected room groups are returned as named components, a corridor connecting rooms changes the graph result, and no claim of code-compliant egress is emitted. Test utilization arithmetic, score range/sum, deterministic score breakdown, candidate deduplication, and selection of geometrically diverse alternatives instead of three near-identical layouts.

- [x] **Step 2: Verify the relevant failures**

Run: `cd backend && pytest -q tests/test_room_layout_planner.py -k 'aspect_ratio or long_axis or corridor or disconnected or utilization or diverse'`
Expected: new assertions fail because WP5C does not score structured proportions, return utilization/circulation components, or select by diversity.

- [x] **Step 3: Implement versioned scoring and candidate selection**

Set planner version `2.0` and score version `2.0`. Preserve the existing `template` enum values (`public_first`, `private_first`, `service_cluster`) as seed provenance and add `largest_first` and `adjacency_first` as additive values. Calculate normalized aspect-ratio deviation and long-axis orientation fit only when supplied. Derive the room graph from actual shared wall segments that receive valid paired door openings; report all connected components, including isolated rooms. Reserve corridor area through the existing typed `corridor` room requirement and defaults; do not invent corridor space from prose. Report assigned and unallocated area without filling leftover space. Score adjacency (15), door-connected circulation (20), privacy (10), aspect-ratio fit (10), orientation fit (10), compactness (10), plot utilization (15), and fragmentation (10). Omit preference-dependent components when no corresponding preference exists, then renormalize active weights to 100; hard constraints remain gates, not score points. Keep hard constraints as gates. Normalize geometry for deduplication, then choose up to three candidates by descending score with a deterministic diversity threshold: compare centroids for matching room names, normalize distances by the plot diagonal, and require a mean displacement of at least 0.08 for an additional candidate. If fewer than three candidates meet the threshold, return fewer rather than cosmetic duplicates. Compute unallocated-space fragmentation from a compressed grid formed by room x/y boundaries, count edge-connected unallocated components, and include that component count in the score breakdown. If the search stopped at its budget, preserve that status even when some candidates were found. Ensure assumptions and warnings explicitly state that connectivity is not fire/egress approval and scores are heuristics only.

- [x] **Step 4: Verify the focused pass**

Run: `cd backend && pytest -q tests/test_room_layout_planner.py -k 'aspect_ratio or long_axis or corridor or disconnected or utilization or diverse'`
Expected: all proportion, corridor, connectivity, utilization, scoring, and diversity assertions pass deterministically.

- [x] **Step 5: Run the affected integration check**

Run: `cd backend && pytest -q tests/test_room_layout_planner.py tests/test_room_layout_candidate_validation.py`
Expected: every selected candidate passes the existing geometry/layout validation and no saved project geometry is touched by planner execution.

- [x] **Step 6: Commit the passing deliverable**

No Git metadata is present; update `progress.md` with score version, planner version, limits, and test evidence.

---

### Task 4: Surface WP5D metadata through API and editable candidate preview

**Files:**
- Modify: `backend/app/schemas/room_layout_generation.py`
- Modify: `backend/app/api/projects.py`
- Modify: `frontend/app/components/DesignAssistant.tsx`
- Modify: `frontend/app/components/ProposalPreview.tsx`
- Modify: `frontend/app/components/assistant-state.mjs`
- Modify: `frontend/app/components/assistant-state.d.mts`
- Modify: `frontend/tests/layout-candidates.test.mjs`
- Modify: `backend/tests/test_room_layout_generation_api.py`
- Modify: `backend/tests/test_room_layout_candidate_ownership.py`
- Modify: `docs/api/design-assistant.md`
- Modify: `README.md`
- Modify: `progress.md`

**Interfaces:**
- Existing endpoints remain: `POST /api/v1/projects/{project_id}/assistant/layout-generation` and `GET /api/v1/projects/{project_id}/assistant/conversations/{conversation_id}/proposals`.
- Add response metadata fields for search status, score version, utilization summary, and disconnected components. Preserve existing outcome values except add `search_exhausted` for a completed search with no candidate because the internal budget was exhausted; partial candidate success remains `layout_candidates` with `search_status="budget_exhausted"`.
- Frontend candidate state keeps the existing selected-candidate Apply/Reject identity and preview-only edits.

- [x] **Step 1: Add focused failing API and frontend tests**

API tests assert metadata survives generation, persistence, conversation restore, and candidate reload; `search_exhausted` is distinguishable from proven infeasible; partial candidate success includes a budget-exhausted marker; old WP5C proposals without new fields still load and remain actionable. Preserve owner isolation, CSRF, stale Apply protection, and no-mutation-on-generation tests. Frontend tests assert utilization and disconnected-circulation warnings render when present, optional metadata is safe when absent, selected-candidate Apply/Reject targets remain unchanged, and old candidate data renders without errors.

- [x] **Step 2: Verify the relevant failures**

Run: `cd backend && pytest -q tests/test_room_layout_generation_api.py tests/test_room_layout_candidate_ownership.py`
Run: `cd frontend && node --test tests/layout-candidates.test.mjs`
Expected: tests fail on missing metadata/outcome handling or display assertions, not on test setup.

- [x] **Step 3: Implement additive API and frontend integration**

Map `PlannerResult.status="search_exhausted"` to API outcome `search_exhausted`; map candidate-level `search_status` to `complete` or `budget_exhausted`. Persist `score_version`, `search_status`, `utilization`, and `circulation_components` in the existing proposal JSON payload and restore them without a migration. Keep proposal owner checks, CSRF, candidate filtering, validation, and Apply/Reject code paths intact. In the preview, display utilization, unallocated area, score version, search-budget warning, and disconnected room groups with non-certification copy. Treat absent WP5C fields as optional and preserve current preview-only edit serialization and selected proposal IDs. Document planner v2.0 fields, search exhaustion semantics, defaults/limits, and compatibility behavior.

- [x] **Step 4: Verify the focused pass**

Run: `cd backend && pytest -q tests/test_room_layout_generation_api.py tests/test_room_layout_candidate_ownership.py`
Run: `cd frontend && node --test tests/layout-candidates.test.mjs`
Expected: API metadata round-trips, old proposals remain usable, and frontend warnings/metrics render without breaking candidate actions.

- [x] **Step 5: Run full available verification**

Run: `cd backend && PYTHONPATH=. pytest -q -p no:cacheprovider`
Expected: all backend tests pass.
Run: `cd frontend && node --test tests/*.test.mjs`
Expected: all frontend Node tests pass.
Run: `python -m compileall -q backend/app backend/tests`
Expected: Python compilation succeeds.
Run the existing TSX syntax-transpile check for all frontend component files and the temporary SQLite Alembic upgrade/downgrade/upgrade smoke test used by WP5C.
Expected: all source syntax and migration checks pass. Attempt `npm run build` and `npx tsc --noEmit -p tsconfig.json` only if dependencies are installed; otherwise report the dependency limitation without claiming success. Browser, live PostgreSQL, and live Ollama checks remain separate runtime checks.

- [x] **Step 6: Update final project status and package the deliverable**

Update README/progress/API docs with exact verification results and remaining runtime limitations. Create `/mnt/data/brahmaai-studio-work-package-5d.zip`, verify its archive integrity with `unzip -t`, and report only verified paths. No Git commit is possible because this workspace has no `.git` metadata.

---

## Unresolved externally observable decisions

- The search limits are engineering defaults, not user-facing settings. The implementation will use fixed safe defaults and code-level hard ceilings; any future user-configurable quality/time control requires a separate product decision.
- Aspect ratio is defined as room width divided by depth in the plot's local coordinate frame. Long-axis orientation uses the existing north-up assumption only when the project's orientation transform is unavailable; the UI must disclose that assumption.
- Circulation connectivity means graph connectivity through shared walls with validated paired doors. It does not imply corridor-width, travel-distance, fire-separation, accessibility, or egress compliance.
- A search that finds some candidates before exhausting its budget returns those candidates with an explicit incomplete-search warning; a search that finds none returns `search_exhausted`, not proven infeasible.
