# WP5C — AI Floor Plan Generation Engine Design Specification

**Status:** Approved architectural direction; awaiting specification review
**Date:** 2026-11-05
**Project:** BrahmaAI Studio

## 1. Purpose

WP5C turns a user's natural-language requirements into one or more editable, geometrically validated floor-plan proposals for a single selected floor. The local language model interprets intent and explains choices; deterministic application code computes room geometry, checks constraints, and creates proposal records. No generated design is applied automatically.

## 2. Product scope

### Included

- Convert a natural-language brief and known project/floor context into a typed room-planning brief.
- Ask focused clarification questions when required inputs are missing or contradictory.
- Generate up to three distinct candidate layouts for one floor when feasible.
- Place rectangular, axis-aligned room polygons within a supported rectangular plot boundary.
- Represent room names/types, dimensions, coordinates, wall thickness, doors and windows using the existing proposal contract.
- Consider requested room relationships, privacy zoning, circulation, plot orientation and optional traditional Vastu preferences.
- Score and explain candidates using transparent, deterministic criteria.
- Run the existing server-side layout and proposal validators before saving candidates as pending proposals.
- Reuse the existing proposal preview, edit, apply and reject workflow.
- Explain infeasible or unsupported requests instead of silently dropping requirements or violating geometry.

### Excluded from WP5C

- Multi-floor coordination or automatic stair alignment between floors.
- Irregular, curved, non-orthogonal or highly concave plot packing. Such plots receive an explicit unsupported-geometry response and retain manual editing; no rectangular plot approximation may be presented as exact.
- Structural engineering, foundation/beam/column sizing, fire-egress certification, accessibility certification, daylight simulation, CFD ventilation simulation or building-code approval.
- Automatic construction drawings, material take-offs, cost estimates or contractor-ready documentation.
- Automatic mutation of saved floor plans without explicit user approval.

## 3. User experience

1. The user opens a project and selects one floor in the existing 2D Studio.
2. The user describes the desired plan, for example: number and type of rooms, parking, orientation, privacy preferences, adjacency requests and optional Vastu preferences.
3. The assistant combines the prompt with the selected project's plot dimensions, orientation and existing floor context.
4. The local model returns a strict structured `RoomPlanningBrief` or a clarification response. It does not supply final room coordinates.
5. If required information is missing, the assistant asks concise questions and preserves the conversation context.
6. The deterministic planner creates up to three candidate arrangements, where feasible.
7. Each candidate is validated against the actual plot and existing layout contract. Invalid candidates are discarded with explicit issue details; they are never stored as valid proposals.
8. The user sees candidate summaries, a score breakdown, assumptions, warnings and a preview in the existing proposal editor.
9. The user can edit a candidate. Existing apply logic revalidates the edited geometry and checks the base-layout hash before persistence.
10. The user explicitly applies or rejects the proposal.

## 4. Architecture

### 4.1 Requirement interpreter

Use the existing `LocalLLMClient` and assistant orchestration boundary. Add a strict discriminated response schema for planning clarification and a `RoomPlanningBrief`. The model may extract requirements and explain them, but it must not return authoritative geometry, run tools, access files, execute SQL or call arbitrary URLs.

The interpreter receives only the current user's message, bounded conversation context, selected floor number, plot facts and relevant saved layout summary. It must not infer unprovided legal requirements or present traditional Vastu preferences as engineering facts.

### 4.2 Deterministic planner

A new pure service receives a validated brief and normalized rectangular plot bounds. It generates rectangular room placements in millimetres. It must use deterministic algorithms and stable candidate identifiers so the same normalized input and planner version produce the same candidate geometry and score ordering.

The initial planner uses orthogonal zoning and partition patterns:

- Public zone: living and dining spaces, with requested entrance access.
- Private zone: bedrooms and associated rooms, with privacy weighting.
- Service zone: kitchen, bathrooms and utility spaces, with adjacency preferences.
- Circulation zone: explicit corridor/entry areas only when needed by the requested topology.

Room placement must be non-overlapping, within plot bounds, and use the configured dimensions or labelled product defaults. The planner may return fewer than three candidates if fewer distinct valid candidates exist. It must return an infeasibility result rather than forcing a fit by violating the brief's hard constraints.

### 4.3 Candidate validation

Every candidate is converted into the existing `LayoutProposalDraft` contract and passed through `validate_layout_proposal` / `validate_layout_update`. Validation covers polygon validity, plot containment, room overlap and opening edge/interval rules. Additional planner checks cover required room counts, requested adjacency feasibility, unique room names and circulation connectivity as defined below.

A candidate with any hard validation issue is not marked valid. Soft warnings (for example, a requested adjacency not achieved) may remain visible only when the candidate is otherwise geometrically valid and the unmet preference is clearly reported.

### 4.4 Scoring and ranking

Scores are deterministic and explainable. The initial score is a weighted 0–100 comparison aid composed of:

- Hard requirement satisfaction: candidate must pass hard requirements to be eligible.
- Requested room adjacency satisfaction.
- Circulation connectivity and unnecessary corridor-area penalty.
- Privacy zoning preference satisfaction.
- Room dimension deviation from requested/preferred dimensions.
- Usable-area ratio, with no claim that a higher ratio is inherently safer or better.
- Orientation/Vastu preference satisfaction when explicitly enabled.

The response must show component scores and unmet preferences. Score weights are versioned configuration, not hidden model judgement. A score is a design comparison aid, not a quality certification.

### 4.5 Proposal lifecycle

Reuse existing `AssistantProposalRecord`, `create_pending_proposal`, `validate_layout_proposal`, `apply_pending_proposal` and `reject_pending_proposal`. Candidate alternatives may be represented as a single proposal record containing a selected candidate plus alternate candidate summaries, or separate proposal records. This storage choice must be resolved during implementation design against the existing persistence model; externally, every candidate the user can preview must have a stable identifier and be independently rejectable or selectable without changing saved geometry.

The existing base-layout fingerprint remains mandatory. Apply must revalidate the final edited proposal and fail with a conflict if the underlying floor plan changed after generation.

## 5. Supported plot geometry

WP5C generation supports a four-sided axis-aligned rectangular plot in the project's normalized millimetre coordinate system. The rectangle may be rotated relative to compass orientation through project metadata, but generated room polygons remain axis-aligned in plot-local coordinates. The planner must verify that the stored plot is rectangular within a documented numerical tolerance before generating.

If the plot is irregular, has non-right-angle corners, has holes, or cannot be normalized unambiguously, return a structured `unsupported_plot_geometry` response with a clear explanation and keep the existing manual editor available. Do not silently substitute a bounding rectangle.

## 6. Brief contract

The planning brief contains:

- `floor_number`.
- `required_rooms`: room type, quantity and optional user-provided name.
- `preferred_dimensions_mm`: optional width/depth preferences per room type or named room.
- `hard_constraints`: explicit non-negotiable user constraints only.
- `adjacency_preferences`: room pairs with `must_be_adjacent` or `prefer_adjacent` semantics.
- `privacy_preferences`: explicit separation or grouping requests.
- `circulation_preferences`: entry/access and corridor preferences.
- `parking`: optional vehicle-space count and user-provided target dimensions.
- `orientation_preferences`: entrance/facing preferences grounded in project orientation.
- `vastu_mode`: `off` or `traditional_reference`; default `off`.
- `notes`: user-supplied free-text requirements with length limits.

Unknown or unspecified dimensions remain unspecified; the planner uses documented, configurable product defaults only for non-hard preferences and records each default in the candidate assumptions. The defaults are not code minimums or professional recommendations. Conflicting hard constraints must trigger clarification or infeasibility, not silent normalization.

## 7. Interfaces

Proposed backend interfaces (names may be adjusted to match existing module conventions without changing behavior):

- `parse_room_planning_brief(messages, project_context, floor_number) -> PlanningBriefResult`
- `generate_layout_candidates(plot, brief, planner_config) -> list[LayoutCandidate]`
- `validate_layout_candidate(project, floor_number, candidate) -> CandidateValidation`
- `score_layout_candidate(candidate, brief, planner_config) -> CandidateScore`
- `create_layout_candidate_proposals(db, conversation, project, user, candidates, saved_rooms) -> list[AssistantProposalRecord]`

Proposed API behavior:

- Existing `POST /api/v1/projects/{project_id}/assistant/message` remains the user entry point.
- A planning request returns either clarification, infeasibility, or a candidate proposal response.
- Existing proposal GET/apply/reject endpoints remain the only persistence lifecycle operations.
- Any new candidate-selection endpoint must be authenticated, project-owner scoped and CSRF-protected for state-changing requests.

Frontend interfaces:

- Extend `DesignAssistant.tsx` to show candidate count, feasibility and clarification state.
- Extend `ProposalPreview.tsx` to switch among candidates, show per-candidate score components, assumptions and warnings, and preserve edit/apply/reject behavior.
- Keep candidate switching local to preview state; it must not mutate saved room geometry.

## 8. Failure and edge-case behavior

- Missing plot: ask the user to define plot geometry before generation.
- Unsupported non-rectangular plot: return `unsupported_plot_geometry`; do not approximate.
- Missing required brief fields: ask focused clarification questions.
- Contradictory hard constraints: return clarification or `infeasible_requirements` with the conflicting requirements identified.
- Requested room set exceeds available area under configured preferences: return infeasibility and identify the dominant area conflict; do not silently shrink hard dimensions.
- No candidate passes geometry validation: return no candidates with structured validation reasons; do not create a pending valid proposal.
- Some candidates pass and others fail: show only valid candidates and include a count/reason summary for discarded candidates.
- Local model unavailable or malformed: use the existing explicitly identified deterministic assistant fallback only for supported rule-based interpretation; if it cannot safely form a brief, ask the user to retry/configure the local model. Never switch to cloud.
- Apply after saved plan changed: return stale-proposal conflict and require regeneration.
- Unauthorized project/conversation/proposal: preserve existing not-found/ownership behavior and do not leak records.

## 9. Security and safety constraints

- Local model calls remain server-side through `LocalLLMClient`.
- Strict Pydantic schemas reject extra fields and malformed coordinates/room data.
- Model output is untrusted input; all geometry and ownership checks run server-side.
- The model cannot execute tools, SQL, shell commands, filesystem operations or arbitrary network requests.
- Preserve authentication, project ownership, CSRF and request-size protections.
- Bound model context, output bytes, candidate count, room count and generation time using existing settings where available; any new limits must be documented and tested.
- No cloud fallback and no automatic model download.
- All design notes must distinguish geometrical checks from professional engineering/code review.

## 10. Testing and acceptance criteria

### Requirement interpreter

- Extract room counts and types from a representative natural-language brief.
- Preserve explicit dimensions and hard constraints exactly.
- Ask for clarification when room count/dimensions conflict or required plot data is absent.
- Reject extra schema fields and malformed enum values.
- Verify no cloud endpoint is called when the local model is unavailable.

### Deterministic planner

- Generate at least one valid layout for a supported rectangular plot and a feasible small room brief.
- Generate distinct stable candidates when more than one valid zoning arrangement exists.
- Verify deterministic output and ranking for identical inputs/configuration.
- Verify all room vertices are within bounds, rooms do not overlap, room names are unique and all dimensions are positive.
- Verify hard adjacency constraints or return explicit infeasibility.
- Verify impossible area requirements return no candidate instead of shrinking hard dimensions.
- Verify irregular plot input returns `unsupported_plot_geometry`.

### Validation and proposal lifecycle

- Every generated candidate passes the existing proposal validator before it is offered as valid.
- Invalid candidates are discarded with structured issue paths/messages.
- Candidate preview does not alter saved rooms.
- Switching candidates does not alter saved rooms.
- Edited proposal application revalidates geometry and updates only the selected floor.
- Stale base-layout hash prevents applying a proposal after a saved layout change.
- Rejection leaves saved room geometry unchanged.

### Frontend

- Candidate switching updates the preview and score summary.
- Assumptions and warnings are visible and accessible.
- Empty, infeasible, unsupported and model-unavailable states are clearly communicated.
- Apply and Reject remain explicit actions.

### Regression

- Run backend suite: `PYTHONPATH=backend pytest -v -p no:cacheprovider`.
- Run frontend geometry and assistant tests: `node --test frontend/tests/*.test.mjs`.
- Run migration upgrade/downgrade/re-upgrade using the documented SQLite test URL.
- Run Python compile and TSX syntax transpilation checks.
- Full Next.js build, browser E2E, PostgreSQL runtime and live local-model integration are release checks when their dependencies/services are available; they must not be reported as passing when not run.

## 11. Open implementation decisions

These are deliberately deferred to the implementation plan because they affect module boundaries and persistence shape, but not the approved user experience:

1. Whether alternatives are stored as multiple proposal records or as candidates under one parent proposal. Prefer the smallest schema change that preserves stable independent preview and selection.
2. Exact initial room-dimension preference defaults and score weights. They must be explicit, configurable, versioned and labelled as product heuristics rather than statutory standards.
3. Whether the initial orthogonal zoning generator uses a small enumerated set of templates or a deterministic partition search. Select based on testable coverage and bounded execution time; no stochastic unrepeatable placement.

## 12. Non-goals and claims policy

A successful generated plan means only that it satisfies the implemented geometric and stated preference checks. It does not establish structural safety, construction feasibility, code compliance, fire safety, accessibility, daylight adequacy, ventilation adequacy or Vastu validity. User-facing language must preserve these distinctions.
