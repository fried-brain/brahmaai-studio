# WP5D — Intelligent Spatial Layout Optimization

**Status:** Approved by user
**Date:** 2026-11-05
**Project:** BrahmaAI Studio

## 1. Objective

Replace the WP5C three-order shelf-packing heuristic with a bounded, deterministic spatial-search engine that can discover more useful rectangular room arrangements while preserving the current planning-brief, proposal-persistence, validation, preview, and explicit Apply/Reject workflow.

WP5D remains a single-floor concept-planning feature for exact axis-aligned rectangular plots. It does not attempt to become a general CAD/BIM solver or certify structural, fire, accessibility, MEP, daylight, ventilation, or local building-code compliance.

## 2. Current-state findings

The existing `room_layout_planner.py` expands typed room requirements, orders rooms under three fixed templates, and packs them left-to-right in rows. It tests only a narrow set of orientations and can reject a brief when those row arrangements fail even if another arrangement may exist. Its current score uses adjacency, door-connected graph reachability, privacy, dimension fit, usable area, and optional entrance placement. The existing proposal validators are the final geometry gate, and generation persists candidates without changing saved floor geometry.

The existing typed brief supports room dimensions, rotation, mandatory/preferred adjacency, privacy, circulation notes, entrance side, and orientation notes. Free-text circulation and orientation notes are not currently enforced by the planner. The candidate schema records a planner version, score breakdown, assumptions, warnings, and unmet preferences.

## 3. Approaches considered

1. **Expand fixed templates.** Low implementation risk, but still dependent on hand-authored orderings and likely to miss valid arrangements.
2. **Bounded deterministic spatial search (selected).** Explore a finite set of legal placements and orientations, prune invalid partial layouts early, and retain a diverse top set. This is more capable while keeping runtime predictable and results reproducible.
3. **External/general-purpose optimization solver.** Potentially powerful, but adds dependency, deployment, and reproducibility costs that are unnecessary for the current rectangular-room scope.

## 4. Selected design

### 4.1 Search model

- Use deterministic, axis-aligned rectangular placement only.
- Enumerate room ordering heuristics (large/most-constrained first, adjacency-group first, and public/private/service priorities) as search seeds, not as independent layout templates.
- For each room, enumerate allowed width/depth orientations. Exact dimensions remain exact; minimum dimensions may not be reduced; preferred dimensions may use documented defaults only when no explicit dimensions were supplied.
- Generate placement anchors from the plot origin and the edges/corners of already placed rooms. Candidate placements must be inside the plot and must not overlap any placed room.
- Use bounded depth-first/backtracking search with deterministic tie-breaking, early pruning, memoization of equivalent partial states where safe, and a strict node/attempt budget.
- Preserve no more than three distinct geometries, ranked by the deterministic score. Candidate identity must be based on normalized geometry and brief, not on a template label.
- If the search budget is exhausted without a solution, report `search_exhausted`/bounded-search-not-found semantics rather than claiming mathematical infeasibility. Keep truly proven failures (e.g. aggregate required room area exceeds plot area, invalid/duplicate room identities, hard dimensions exceeding plot bounds) distinguishable.

### 4.2 Room proportions and orientation

- Add optional typed room preferences for target aspect ratio and long-axis orientation (`north_south` or `east_west`).
- Preferences influence candidate ordering and score; they never override hard dimensions, plot containment, or rotation restrictions.
- Add score components for aspect-ratio fit and preferred orientation fit. If no preference is supplied, omit or neutralize that component rather than penalizing the room.
- State clearly that the coordinate frame is north-up only where the project has not supplied a verified orientation transform; the existing entrance-side mapping assumption remains visible.

### 4.3 Circulation and corridors

- Treat an explicitly requested corridor as a first-class `corridor` room requirement with user-specified or product-default dimensions, so its floor area is physically reserved and validated like any other room.
- Build the room connectivity graph from shared wall segments with usable paired door openings. Report disconnected components and isolated rooms as warnings and score penalties; do not label this as compliant circulation or safe egress.
- Where feasible, prefer layouts that connect public/common spaces to the corridor and corridor to private/service rooms. Do not invent doors across non-shared walls or create openings that fail existing opening validation.
- Free-text circulation notes remain preserved and shown as assumptions until represented by structured brief fields; WP5D must not pretend arbitrary prose has been enforced.

### 4.4 Plot utilization and fragmentation

- Score usable area using room area, leftover-space fragmentation, and room compactness/proportion fit rather than a single fixed target utilization ratio.
- Report total assigned room area, plot area, utilization percentage, and approximate unallocated area in candidate metadata or score details.
- Do not fill leftover space with artificial rooms or silently resize requested rooms.

### 4.5 Scoring and candidate diversity

- Use a documented, versioned score breakdown covering hard-constraint satisfaction (hard constraints remain gates, not soft points), adjacency, privacy, door-connected circulation, aspect-ratio fit, orientation fit, room compactness, and plot utilization/fragmentation.
- Keep scores deterministic and within 0–100. Document weights and neutral behavior when a preference is absent.
- Deduplicate using normalized room geometry and openings. Select candidates with both quality and spatial diversity so the top three are not trivial translations or tiny variants of one arrangement.
- Include planner version `2.0` and score version metadata in candidates. Maintain backward compatibility when reading persisted WP5C (`1.0`) proposals.

## 5. API, persistence, and frontend compatibility

- Keep existing layout-generation request and response endpoint paths and ownership/CSRF behavior.
- Keep the existing candidate persistence model and proposal Apply/Reject lifecycle; no database migration is expected unless implementation discovers a concrete need.
- Extend response metadata additively for search status, utilization, disconnected circulation components, and scoring version. Existing consumers must tolerate older candidates with missing optional metadata.
- Update the candidate preview to display useful new score details, plot utilization, and circulation warnings without changing preview-only edits or the selected-candidate Apply/Reject semantics.
- Continue to validate every completed candidate through the existing layout and proposal validators before persistence.

## 6. Failure handling and safety

- Unsupported irregular plots remain rejected without bounding-box approximation.
- Search-budget exhaustion is distinct from proven impossibility.
- No candidate is persisted if it fails schema, plot-containment, overlap, opening, or proposal validation.
- Generation remains non-mutating; only explicit Apply changes saved floor geometry and revalidates against current project state.
- Search limits are configurable internally with safe defaults and hard ceilings; request payloads cannot increase them.
- No remote model is introduced into geometry generation. The local model continues to interpret user intent into a typed brief; deterministic code owns coordinates.

## 7. Testing strategy

- Unit tests for candidate anchors, orientation enumeration, overlap/containment pruning, deterministic ordering, search-budget termination, memoization correctness, and normalized geometry deduplication.
- Regression fixtures where WP5C shelf packing fails but a valid alternative exists, and where no valid arrangement exists under hard dimensions.
- Tests for exact/minimum dimensions never being reduced, aspect-ratio/orientation scoring, corridor area reservation, connectivity component reporting, and paired door validation.
- Candidate scoring tests for score bounds, deterministic breakdown, absent-preference neutrality, and candidate diversity.
- API regression tests for ownership, CSRF, persistence, no saved-floor mutation, stale Apply protection, and compatibility with existing WP5C proposals.
- Frontend tests for optional metadata, display of new score details, candidate switching, edits, Apply and Reject behavior.
- Run the complete backend and frontend unit suites, Python compilation, TSX syntax checks, and migration smoke test. Report unavailable dependency-backed build/browser/live-service checks honestly.

## 8. Acceptance criteria

1. A deterministic bounded-search planner replaces the WP5C shelf-packing loop and emits up to three distinct candidates.
2. A regression case demonstrates discovery of a valid arrangement that the previous row packer misses.
3. Search budget exhaustion is not misreported as proof of infeasibility.
4. Hard dimensions, containment, non-overlap, openings, and proposal validation remain enforced.
5. Explicit corridor requirements reserve real floor area; circulation connectivity is reported with clear non-certification language.
6. Room proportion/orientation preferences affect ranking without violating hard constraints.
7. Candidate scores and metadata are deterministic, versioned, and backward compatible with WP5C persisted proposals.
8. Existing API security, persistence, Apply/Reject and frontend selection behavior remain intact.
9. All available automated verification passes; unavailable runtime checks are explicitly listed.

## 9. Explicit non-goals

- Arbitrary polygon plots, curved walls, non-rectangular rooms, multi-floor optimization, furniture placement, structural engineering, MEP routing, material selection, construction drawings, fire/egress approval, accessibility certification, or regulatory compliance.
- Treating a door-connectivity graph as proof of safe or compliant circulation.
- Treating traditional Vastu notes as scientific or mandatory engineering constraints.
