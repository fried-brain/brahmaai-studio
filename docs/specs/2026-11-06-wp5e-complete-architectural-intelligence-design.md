# WP5E — Complete Architectural Intelligence Studio

**Status:** Approved by user
**Date:** 6 November 2026
**Project:** BrahmaAI Studio
**Scope:** Furniture planning, opening optimization, and room-usability analysis for existing single-floor layouts

## 1. Objective

Extend BrahmaAI Studio's existing 2D floor-plan editor with a deterministic, editable architectural-planning layer. Users will be able to place and edit furniture, receive automatic furniture-arrangement alternatives, review door/window placement suggestions, and inspect practical room-clearance and circulation warnings. The system will reuse existing room geometry and layout validation, preserve explicit user approval for generated changes, and persist furniture as part of each room's layout data.

WP5E is an early-stage architectural planning aid. It is not a CAD/BIM replacement and does not certify structural stability, fire egress, accessibility, daylight, ventilation, plumbing, electrical, or local building-code compliance.

## 2. Repository findings

The current application uses:

- FastAPI with Pydantic v2 schemas and SQLAlchemy persistence.
- `RoomInput`, `OpeningInput`, `LayoutUpdate`, and `LayoutOutput` in `backend/app/schemas/layouts.py`.
- `Room.geometry_json` and `Room.openings_json` persisted by `backend/app/services/layouts.py`.
- Existing plot containment and room-overlap checks in `backend/app/services/layouts.py` and `backend/app/services/geometry.py`.
- Existing door/window edge-index and offset representation, including width, height, sill height, and a coarse swing direction.
- `serialize_layout` and authenticated layout GET/PUT endpoints in `backend/app/api/projects.py`.
- A React/TypeScript SVG editor in `frontend/app/components/PlanEditor.tsx`, with derived walls, room selection, drag/resize, opening controls, and a design-analysis panel.
- Existing deterministic analysis in `backend/app/services/design_analysis.py` and a separate staircase preview feature.

The current `Room` persistence model has no furniture field. Furniture cannot safely be placed in the existing room polygon or opening JSON without mixing distinct domain concepts. WP5E therefore requires a dedicated nullable JSON-text column and an Alembic migration, with an empty-list compatibility default for existing rooms.

## 3. Approaches considered

1. **Frontend-only furniture overlay.** Fast to prototype, but furniture would not be persisted or validated by the backend and could disappear or become invalid after reload. Not selected.
2. **Backend-owned furniture geometry with an editable SVG overlay (selected).** Furniture is a typed part of room layout data; deterministic backend services validate and generate arrangements; the frontend renders and edits the same geometry. This preserves the existing project source of truth and can be tested independently.
3. **Full 3D/BIM interior engine.** Offers richer visualization but substantially expands scope, dependencies, rendering, asset, and data-model requirements. Deferred to a later package.

## 4. Selected architecture

### 4.1 Furniture domain and persistence

Add a strict `FurnitureInput` model with a stable item identifier, catalog type, display name, placement center coordinates `x_mm`/`y_mm` in millimetres, footprint width/depth, and quarter-turn rotation (0/90/180/270). Center coordinates use the same plot coordinate frame as room vertices, not screen pixels. Furniture footprints are rectangular and axis-aligned in the canonical plan after rotation normalization. The catalog supplies documented default dimensions for supported item types; users may resize an item within explicit schema bounds.

Initial catalog groups:

- Bedroom: single/double/queen/king bed, bedside table, wardrobe, dresser.
- Living: sofa variants, armchair, coffee table, TV console, side table.
- Dining: dining table variants and chair footprints.
- Kitchen: counter run, refrigerator, sink unit, hob/cooktop, pantry/storage.
- Bathroom: WC, washbasin, shower footprint, bathtub.
- Study/utility: desk, office chair, bookshelf, washer, storage cabinet.

Catalog dimensions are starting planning presets, not manufacturer specifications. Each placed item retains its actual dimensions in the persisted layout so later catalog changes do not silently resize existing projects.

Add non-null `furniture_json` text to the existing `Room` model and a forward Alembic migration with server default `[]`. Existing rows migrate to an empty JSON array. Extend `RoomInput`, `RoomOutput`, proposal room schemas, layout serialization, persistence, and frontend layout types. Older clients that omit furniture on an update must not accidentally erase existing furniture: the implementation must define a backward-compatible update policy and test it. The policy is to preserve stored furniture when the incoming room with the same case-folded room name omits the furniture field, while an explicitly supplied empty list clears it. If a room with existing furniture is renamed or replaced by an older client that omits furniture, the server returns a conflict rather than silently discarding items. New clients send explicit furniture arrays and may rename rooms safely.

### 4.2 Geometry and placement validation

Create a focused furniture geometry service that:

- Normalizes quarter-turn rotations and calculates the resulting rectangular footprint.
- Confirms the footprint is wholly within its owning room polygon with a configurable wall-clearance margin.
- Rejects furniture-to-furniture footprint overlap within a room.
- Detects intersections with door/window opening zones where those zones can be derived from the existing edge-index and offset representation.
- Calculates item-specific approach/working clearances as advisory zones, not as a hard universal standard.
- Reports exact issue paths and item identifiers so the editor can highlight the affected item.

Hard validation applies to footprint containment, positive dimensions, valid rotation, unique item IDs per room, and direct furniture overlap. Clearance-zone conflicts are warnings by default because some functional clearances can overlap and should be reviewed in context. No furniture may be silently moved, resized, or removed to make validation pass.

The initial furniture solver supports orthogonal rectangular rooms and axis-aligned room edges. For non-orthogonal rooms, manual furniture placement remains available only when the footprint passes polygon containment; automatic placement returns an explicit unsupported-geometry result rather than approximating the room with a bounding box.

### 4.3 Deterministic furniture arrangement engine

Add a backend service that creates a bounded set of furniture arrangements from the room type, dimensions, user-selected catalog items, and existing openings. It uses deterministic candidate anchors, quarter-turn orientations, stable tie-breaking, and a strict internal search budget. It returns up to three distinct arrangements, each with:

- Stable candidate key and solver version.
- Furniture item placements.
- Fit/containment and collision validation results.
- Clearance warnings and unmet preferences.
- Score breakdown for footprint fit, access/clearance quality, usable floor area, and arrangement compactness.
- Assumptions, including any catalog defaults used.

The engine does not invent furniture requirements. The user chooses a room preset or item list, or explicitly asks for a suggested furnishing set. If room type is unknown or item intent is ambiguous, the UI asks the user to choose rather than silently furnishing it. Search exhaustion is reported separately from proven geometric impossibility.

### 4.4 Door and window positioning assistant

Add a deterministic opening-suggestion service that analyzes room adjacency, shared wall segments, plot-boundary edges, road-facing metadata, existing openings, and furniture clearance zones. It may suggest:

- Shared-wall door positions where adjacent rooms have no suitable door.
- Alternative positions for existing door/window openings when they conflict with furniture or block a preferred route.
- Exterior window positions on eligible room boundary edges.
- An external entrance position only when road-facing side or explicit user input makes the side unambiguous.

Suggestions preserve the existing `OpeningInput` contract: edge index, offset, width, height, sill height, and swing direction. Because the existing model does not represent hinge offset or a full swing arc, WP5E must label swing-clearance checks as conservative geometric estimates and must not claim exact door-swing simulation. Existing openings are never automatically moved or deleted. Each suggestion includes a reason and any assumptions; the user previews and chooses which suggestions to apply.

### 4.5 Room usability and circulation analysis

Extend the current design-analysis service or add a separate room-usability service to report:

- Room area and furniture-covered area.
- Approximate remaining unoccupied floor area.
- Furniture collision and boundary violations.
- Item approach/working-clearance warnings.
- Door access and opening obstruction warnings.
- Narrow or interrupted movement corridors based on configured heuristic widths.
- Unconnected room graph components using the existing door-connected adjacency data.

All thresholds are labelled as configurable planning heuristics. Results are advisory and do not constitute accessibility, egress, or building-code certification. Vastu remains disabled by default and, if shown, remains a separate traditional cultural reference only.

### 4.6 API and proposal flow

Keep existing authenticated project ownership and CSRF protections. Extend the existing layout GET/PUT contract additively to include room furniture. Add `POST /api/v1/projects/{project_id}/design-optimization/preview` with a strict request containing floor number, operation (`furniture_arrangement`, `opening_suggestions`, or `full_review`), and explicit room/item selections. The preview endpoint reads the saved layout, runs deterministic services, validates outputs, and returns preview candidates/issues plus a deterministic source-layout fingerprint; it does not mutate saved rooms.

Applying an accepted optimization result uses a dedicated authenticated `POST /api/v1/projects/{project_id}/design-optimization/apply` endpoint with the preview fingerprint and the complete edited layout. The server recomputes the current fingerprint, rejects stale previews, revalidates room geometry, furniture footprints, and openings, and persists atomically. Ordinary manual layout edits continue through the existing layout PUT endpoint. Existing assistant proposal Apply/Reject behavior remains unchanged.

### 4.7 Frontend studio

Add a focused furniture palette/inspector component and pure geometry helpers rather than placing all furniture logic in `PlanEditor.tsx`. Extend the SVG plan view to render furniture footprints, labels, selection handles, rotation, and clearance overlays. Support:

- Drag from a room-specific catalog into the selected room.
- Select, move, rotate by 90 degrees, resize within bounds, duplicate, and delete.
- Toggle furniture labels and clearance overlays.
- Request automatic arrangement candidates and compare their score/warnings.
- Preview door/window suggestions separately from saved geometry.
- Apply selected changes only after explicit user action.
- Undo/redo for manual furniture edits using the editor's existing history model or a compatible extension.

The frontend must show validation errors at the relevant furniture/opening item and must never save invalid or stale preview geometry as if it were accepted.

## 5. API and schema contracts

Proposed typed additions:

- `FurnitureInput`: `item_id`, `catalog_type`, `name`, center coordinates `x_mm`/`y_mm`, `width_mm`, `depth_mm`, `rotation_deg`.
- `FurnitureIssue`: `code`, `item_id`, `message`, optional geometry/path context.
- `FurnitureArrangementCandidate`: `candidate_key`, `solver_version`, `items`, `score`, `score_breakdown`, `warnings`, `assumptions`, `unmet_preferences`.
- `OpeningSuggestion`: `room_id`, `opening`, `action` (`add` or `move`), `reason`, `assumptions`.
- `DesignOptimizationPreview`: `source_layout_fingerprint`, `operation`, `candidates`, `opening_suggestions`, `analysis`, `issues`. The apply request contains `floor_number`, `source_layout_fingerprint`, and the complete edited room list.

Exact field constraints, bounds, and serialization details will be finalized in the implementation plan against the existing Pydantic and TypeScript conventions. All request models forbid unknown fields. Browser requests cannot supply solver budgets, model URLs, or privileged configuration.

## 6. Compatibility and migration

- Add one Alembic migration for non-null `rooms.furniture_json` text with server default `[]`, matching the existing `openings_json` migration convention.
- Existing room records deserialize with `furniture=[]`; database inserts that omit the column receive `[]` from the server default.
- Existing WP5C/WP5D proposal records without furniture deserialize with `furniture=[]`.
- Existing clients omitting the new field must preserve furniture on updates when room identity can be matched safely; otherwise return a clear conflict rather than silently deleting data.
- Keep existing opening serialization and all current room geometry semantics unchanged.
- Do not add a separate furniture table or external asset library in WP5E.

## 7. Security, performance, and failure handling

- Enforce project ownership on every new endpoint and CSRF on mutations.
- Bound room count, furniture item count, dimensions, candidate count, and solver operations server-side.
- Never trust client-supplied scores, validation outcomes, source fingerprints, or candidate metadata; recompute server-side.
- Reject stale previews and malformed furniture/opening references.
- Keep preview generation non-mutating and use explicit apply/save.
- Return structured outcomes for missing floor, unsupported room geometry, no feasible arrangement, search exhaustion, invalid selection, stale layout, and validation failure.
- No external network service or paid AI provider is required for the deterministic core.

## 8. Testing strategy

Backend tests cover schema strictness, migration defaults, old-payload compatibility, furniture containment, wall margin, overlap, opening conflict, rotation, catalog dimensions, deterministic candidate generation, candidate diversity, search budget, unsupported geometry, opening suggestion reasons, source fingerprint staleness, atomic apply/no-partial-write behavior, owner isolation, CSRF, and non-mutating preview behavior.

Frontend tests cover furniture rendering data transforms, drag/drop and rotation geometry, resize bounds, selection/duplicate/delete, warning display, candidate switching, preview/apply separation, stale preview handling, and preservation of furniture during layout saves and reloads.

Integration checks cover the full GET → preview → edit → validated PUT → GET round trip, plus Alembic upgrade/downgrade/upgrade smoke tests. Dependency-backed Next.js build, browser rendering, live PostgreSQL and runtime integration must be reported separately if unavailable.

## 9. Explicit exclusions

- Full 3D visualization, photorealistic rendering, AR/VR, and manufacturer-specific BIM libraries.
- Structural calculations, foundation/beam/column sizing, load analysis, fire-egress certification, accessibility certification, and legal code approval.
- Daylight, thermal, acoustic, ventilation, plumbing, electrical, and HVAC simulation.
- Automatic construction documentation, quantity take-offs, contractor pricing, or permit-ready drawings.
- Automatic application of generated furniture or opening changes without user review.

## 10. Acceptance criteria

1. Furniture is typed, editable, persisted per room, and restored after reload.
2. Existing projects and old clients remain compatible; omission of furniture cannot silently erase stored items.
3. Furniture footprints are validated against room boundaries, other furniture, and relevant opening zones.
4. Deterministic furnishing can produce up to three distinct, valid arrangements or a precise non-success outcome.
5. Door/window suggestions are explainable, validated, preview-only, and never silently alter existing openings.
6. Room-usability analysis identifies relevant collisions, clearance concerns, obstructions, and circulation warnings with explicit heuristic/non-certification language.
7. The editor supports manual furniture placement and editing with undo/redo and visible validation feedback.
8. Preview and Apply are separate; stale or invalid data cannot overwrite the saved floor plan.
9. Existing WP5C/WP5D layout generation, proposals, opening behavior, staircase preview, and project ownership/CSRF behavior remain compatible.
10. Backend/frontend tests, migration checks, and archive integrity pass; unavailable environment-dependent checks are clearly disclosed.
