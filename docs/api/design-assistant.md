# Design Assistant API

## `POST /api/v1/projects/{project_id}/assistant/message`

Authenticated, project-owner-scoped endpoint. Requires the normal session cookie and `X-CSRF-Token` header.

Request:

```json
{
  "message": "Design a 3 bedroom, 2 bathroom home",
  "floor_number": 0,
  "conversation_id": null
}
```

`message` is required and limited to 2,000 characters. `floor_number` defaults to `0` and is limited to -5 through 50. `conversation_id` is optional; when supplied it must belong to the authenticated user, project and same floor. A floor mismatch returns HTTP 409 `conversation_floor_mismatch`.

Response includes `reply`, `intent`, `response_type`, `clarifying_questions`, `suggestions`, optional `proposal`, `changes_applied` (always false on message generation), `engine`, `model`, `conversation_id`, `proposal_id` and `proposal_metadata`.

`engine` is `local_llm` only when the configured local model returns a valid schema-conforming response. Otherwise the deterministic WP5A assistant is used and labeled `local_rules`. The browser cannot choose the model endpoint or name. No cloud fallback exists.

## Conversation endpoints

- `GET /api/v1/projects/{project_id}/assistant/conversations?limit=20`
- `GET /api/v1/projects/{project_id}/assistant/conversations/{conversation_id}`

Both are authenticated, owner-scoped and read-only. The list limit is 1–100. Transcripts are returned in chronological order and include engine/model metadata and proposal references.

## Proposal endpoints

- `GET /api/v1/projects/{project_id}/assistant/proposals/{proposal_id}`
- `POST /api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/apply`
- `POST /api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/reject`

GET is authenticated and owner-scoped. Apply and Reject also require `X-CSRF-Token`. Apply accepts `{ "proposal": <edited-layout-proposal> }` and revalidates the exact edited payload against the current plot and floor state. It atomically replaces rooms and marks the proposal applied. Reject changes proposal status only.

Stable action error codes:

- `proposal_invalid` — HTTP 422; submitted proposal geometry or schema is invalid.
- `proposal_stale` — HTTP 409; plot or floor changed after proposal generation.
- `proposal_not_pending` — HTTP 409; proposal was already applied or rejected.

Non-owned project, conversation and proposal identifiers return 404. Mutating endpoints require CSRF.

## Local model readiness

`GET /api/v1/assistant/status` requires authentication and returns `enabled`, `configured`, `reachable`, `model_available` and a stable `code` (`disabled`, `model_not_configured`, `model_unavailable`, or `ready`). It never returns the configured URL or internal network details. See `docs/api/local-llm.md` for runtime configuration, bounded history and Docker networking.

## Safety and scope

The assistant is a conceptual architectural planning aid. Model output is treated as untrusted structured data and passed through deterministic schema, polygon, plot-containment, overlap and opening validation. Draft proposals do not mutate saved rooms. The frontend keeps proposal preview separate from autosave. Only explicit Apply can replace saved floor geometry, and Apply repeats validation against the latest saved state. This is not structural, MEP, fire, accessibility, building-code or construction-readiness certification.

## Typed floor-plan requirement interpretation

WP5C adds a separate planning brief contract in `backend/app/schemas/room_planning.py`. The local model may return only a `planning_brief` or `clarification`; unknown fields, unsupported room types, invalid dimensions, duplicate adjacency pairs, and any model-supplied geometry are rejected. The interpreter returns `model_unavailable` or `invalid_model_response` rather than attempting a cloud fallback or repairing malformed output. The interpreter never returns room coordinates; deterministic planning owns all geometry.

Planning briefs support exact room quantities, preferred/minimum/exact dimensions in millimetres, mandatory/preferred adjacency, privacy relationships, circulation notes, entrance side, orientation notes and optional traditional Vastu reference mode (off by default). Product dimension defaults are disclosed as heuristics, not legal minimums or professional recommendations.

## WP5C + WP5D deterministic floor-plan generation and spatial optimization

### `POST /api/v1/projects/{project_id}/assistant/layout-generation`

Authenticated, project-owner-scoped and CSRF-protected. Request:

```json
{
  "message": "Generate a 3 bedroom home with living, kitchen, bathroom and parking",
  "floor_number": 0,
  "conversation_id": null
}
```

The request uses the same message (1–2,000 characters), floor (-5 through 50) and conversation ownership rules as the chat endpoint. The local model returns only a strict `RoomPlanningBrief` or clarification; it does not return coordinates. The WP5D deterministic planner (version `2.0`) creates up to three alternatives using bounded depth-first spatial search across room-order seeds, permitted orientations, and anchors at plot/placed-room edges and corners. It uses deterministic tie-breaking, hard-constraint pruning, a node budget and canonical partial-state memoization. Candidate `template` is retained as seed provenance; WP5D adds `largest_first` and `adjacency_first` while continuing to read the WP5C seed values. Room dimension defaults and all assumptions are disclosed in the proposal.

The response `outcome` is one of:

- `layout_candidates` — one or more independently persisted draft candidates.
- `clarification` — the local model needs another user answer; no candidate is persisted.
- `missing_plot` — define plot dimensions before generation.
- `unsupported_plot_geometry` — only exact axis-aligned rectangles are supported; irregular plots are not replaced by a bounding box.
- `infeasible` — preflight hard dimensions/aggregate area fail, or the complete supported anchor search finds no validated candidate. A completed anchor search is still a heuristic search, not a mathematical proof that no manual arrangement exists.
- `search_exhausted` — the bounded node/solution budget was reached before any candidate was found; this is explicitly not proof of infeasibility.
- `model_unavailable` — the configured local model runtime/model is not ready; no cloud fallback occurs.
- `invalid_model_response` — malformed, out-of-contract or geometry-bearing model output was rejected.

A successful response includes `conversation_id`, `planner_version`, `search_status` (`complete` or `budget_exhausted`) and `candidates[]`. Each candidate includes its own `proposal_id`, stable geometry-based `candidate_key`, seed label, score (0–100), `score_version`, component breakdown, `utilization` (`plot_area_mm2`, `assigned_area_mm2`, `unallocated_area_mm2`, `utilization_percent`), named `circulation_components`, editable proposal JSON, status and validation issues. If some candidates were found before the search limit, they are returned with `search_status="budget_exhausted"`; the UI identifies the search as incomplete. Candidate records are separate existing assistant proposals. Generation and candidate listing do not change saved floor rooms. New metadata is stored in existing proposal JSON; no database migration is required.

### `GET /api/v1/projects/{project_id}/assistant/conversations/{conversation_id}/proposals`

Authenticated and owner-scoped. Returns all deterministic planner candidates for that project/conversation, ordered by score descending with creation order preserved for ties. Each candidate can be restored and selected in the 2D preview. Existing non-WP5C proposals are not included in this candidate-set endpoint. Legacy WP5C candidate proposals without WP5D metadata remain readable and receive neutral display defaults (`score_version="1.0"`, `search_status="complete"`, no utilization summary and no circulation components).

Entrance-side placement uses a north-up local coordinate convention (north=min-y, east=max-x, south=max-y, west=min-x); the candidate assumption explicitly asks users to verify this against the project's actual orientation. The UI exposes `Generate floor-plan options` as a distinct action from ordinary assistant chat. Candidate switching and edits affect preview state only. Apply uses the selected candidate's existing proposal ID and the existing fresh geometry validation/base-layout fingerprint check; Reject changes only the selected proposal's status. Parking is a supported room type.

### WP5D planning fields, score and limits

`RoomRequirement` supports optional `target_aspect_ratio` (room width ÷ depth, positive and at most 20) and `long_axis_orientation` (`north_south` or `east_west`). These are soft ranking preferences; they do not override exact/minimum dimensions or `allow_rotation`. The local axis orientation must be verified against the real plot orientation. Free-text orientation/circulation notes remain preserved but unenforced.

Planner defaults are 20,000 expanded search nodes and at most 24 internally retained solutions before diversity selection returns up to three. Code-level hard ceilings are 100,000 nodes, 100 retained solutions and depth 100; request payloads cannot increase these values. The internal planner configuration may lower limits for tests. Search status is `complete` or `budget_exhausted`. The planner distinguishes obvious preflight failures (such as total room area exceeding plot area or a hard room dimension exceeding both permitted orientations) from an exhausted search. Even a complete search over supported anchors does not prove mathematical impossibility.

Score version `2.0` uses a 100-point normalized weighted breakdown: adjacency 15, door-connected circulation 20, privacy 10, aspect-ratio fit 10, orientation fit 10, compactness 10, plot utilization 15, and unallocated-space fragmentation 10. Preference-dependent components are omitted and remaining weights are renormalized when the user supplied no corresponding preference. Hard constraints remain gates, not soft score points. Candidate diversity compares normalized room-centroid displacement; layouts with less than 0.08 mean normalized displacement are not returned as separate options.

A requested `corridor` is a normal rectangular room requirement and reserves actual plot area. Circulation components are connected groups of rooms sharing a wall with generated paired door openings. Fragmentation counts edge-connected unallocated regions on a compressed room-boundary grid. These are geometric planning indicators only: no corridor-width, travel-distance, door-clearance, fire-separation, egress, accessibility, daylight, ventilation, structural or local-code compliance is certified. Vastu remains an optional traditional reference, off by default. No database migration is introduced by WP5D.
