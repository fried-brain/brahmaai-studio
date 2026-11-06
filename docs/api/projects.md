# Projects and Plot API

All routes are prefixed with `/api/v1`. Routes marked **session** require the `bas_session` cookie. Mutating routes additionally require the `X-CSRF-Token` header returned by login.

## Create project

`POST /projects` — session + CSRF; returns `201`.

```json
{
  "name": "East-facing family home",
  "category": "residential",
  "plot": {
    "shape": "rectangle",
    "width": 30,
    "length": 50,
    "unit": "ft",
    "orientation": "east"
  }
}
```

`plot` may be omitted or `null`. Supported categories: `residential`, `commercial`, `industrial`, `other`. Initial plot shape: `rectangle`. Supported units: `mm`, `cm`, `m`, `in`, `ft`.

Dimensions are converted to millimetres and rounded to 0.001 mm. `area_sq_ft` is derived from the stored dimensions; it is not independently stored.

## List projects

`GET /projects` — session; returns only the caller's active projects, most recently updated first.

## Retrieve project

`GET /projects/{project_id}` — session; returns only a project owned by the caller. Missing, archived, and not-owned projects return `404` to avoid disclosing their existence.

## Update project metadata

`PATCH /projects/{project_id}` — session + CSRF. Accepts `name` and `category` using the create-project schema. A plot in this payload is not used; use the plot endpoint instead.

## Configure plot

`PUT /projects/{project_id}/plot` — session + CSRF. Accepts `shape`, `width`, `length`, `unit`, `orientation`, and optional `road_facing_side`.

## Archive project

`DELETE /projects/{project_id}` — session + CSRF; returns `204`. Archiving changes status to `archived`; it does not permanently delete project data. Archived projects are excluded from list and retrieval endpoints.

## Error behavior

- `401`: no valid authenticated session.
- `403`: missing or invalid CSRF token on a mutating route.
- `404`: project does not exist, is archived, or is not owned by the caller.
- `422`: invalid request fields, unsupported units, or non-positive plot dimensions.
- `503`: database is not configured or unavailable.

## Plot geometry (Milestone 1 / Work Package 3)

Plots support `rectangle` and `polygon` shapes. Polygon vertices are supplied as ordered local-plan coordinates in the selected unit; the API converts and persists them in millimetres. The first vertex is not repeated at the end—the final edge is closed automatically.

Example polygon payload:

```json
{
  "shape": "polygon",
  "unit": "ft",
  "vertices": [
    {"x": 0, "y": 0},
    {"x": 20, "y": 0},
    {"x": 20, "y": 10},
    {"x": 10, "y": 10},
    {"x": 10, "y": 20},
    {"x": 0, "y": 20}
  ],
  "orientation": "east"
}
```

The response includes `vertices_mm`, `area_sq_ft`, and `perimeter_mm`. Polygon inputs are rejected when they have fewer than 3 or more than 500 vertices, repeated vertices, zero-length edges, zero enclosed area, or non-adjacent edge intersections/touches. Coordinates are limited to ±100,000 in the submitted unit. This is a 2D site-boundary geometry validator, not a cadastral survey or structural/code-compliance certification.

## Floor layouts, rooms and derived walls

Floor plans are stored per project and floor number. Room coordinates are absolute millimetres in the plot's local coordinate plane, with the plot's lower-left origin at `(0, 0)` for rectangular plots. For polygon plots, coordinates use the same coordinate system as the saved plot vertices.

- `PUT /api/v1/projects/{project_id}/layout` replaces the room layout for one floor. Requires an authenticated session and CSRF token.
- `GET /api/v1/projects/{project_id}/layout/{floor_number}` retrieves a saved floor layout.

Example request:

```json
{
  "floor_number": 0,
  "rooms": [
    {
      "name": "Living",
      "room_type": "living",
      "vertices_mm": [
        {"x": 0, "y": 0},
        {"x": 3000, "y": 0},
        {"x": 3000, "y": 4000},
        {"x": 0, "y": 4000}
      ]
    }
  ]
}
```

The API validates each room polygon, requires it to remain within the plot, and rejects positive-area overlap with other rooms. Rooms may share an exact boundary edge. Wall segments are derived from room polygon edges and identical shared edges are returned once with both adjacent `room_ids`. Each room response includes calculated area in square feet and perimeter in millimetres. Room responses include wall thickness and validated door/window openings. Wall segments are classified as `external` when the full segment lies on the plot boundary and `internal` otherwise; this is a geometric location label, not a material or structural specification. Exact shared wall edges produce adjacency records, and door openings on those edges are used to derive door-connected circulation components.
- `DELETE /api/v1/projects/{project_id}/layout/{floor_number}` clears a floor's room layout. Requires an authenticated session and CSRF token; returns `204` (safe to repeat).

## Interactive 2D studio (Work Package 3C)

The web client opens a 2D editor from a project card when a plot is configured. It supports rectangular room drawing by pointer drag, room selection, drag-to-move, corner resizing, polygon vertex reshaping for non-rectangular rooms, room name/type editing, deletion, undo/redo, floor switching, automatic save, and SVG export. A 100 mm coordinate snap is applied in the editor. The backend remains authoritative: plot containment, room self-intersection, and room overlap are checked on save. Invalid edits remain visible locally with the server validation message so the user can correct them.

The editor currently draws rectangular rooms; reshaping a room can create a non-rectangular polygon. It does not yet add/remove polygon vertices or provide 3D visualization.


### Parametric wall and opening data

Each room in a floor-layout payload may include `wall_thickness_mm` (75–500 mm, default 150) and an `openings` array. Each opening is anchored to a room boundary edge by `edge_index` and stores `kind` (`door` or `window`), `offset_mm`, `width_mm`, `height_mm`, and `sill_height_mm`. Door openings also accept `swing_direction` (`left`, `right`, or `none`); windows must use `none`. Responses include derived `head_height_mm` as sill height plus opening height. The API rejects non-existent edges, openings extending beyond their edge, overlapping openings on one edge, non-zero door sill heights, and unreasonable dimensions. These are geometric consistency checks, not code or structural approvals.

## Parametric staircase preview (Work Package 4B)

`POST /api/v1/projects/{project_id}/staircase/preview` — authenticated session + CSRF token. This stateless endpoint accepts `floor_to_floor_mm`, `preferred_riser_mm`, `tread_depth_mm`, `clear_width_mm`, `landing_depth_mm`, and `configuration` (`straight`, `L`, or `U`). It rounds the riser count to the nearest whole step, recomputes an equal actual riser height so the total rise exactly matches the floor height, distributes risers across one or two flights, and reports the longest flight run. The 2R+T comfort indicator uses a 550–700 mm reference band as a design heuristic only. Flight-run output excludes landings and does not represent a complete stairwell footprint. This endpoint does not certify compliance with local building rules, accessibility, fire egress, headroom, handrails, structural design, or construction suitability; have the design checked by a qualified local professional.


### Wall classification and room circulation (Work Package 4C)

Each returned wall includes `classification` (`external` or `internal`). An external wall is a room edge whose two endpoints lie on the same saved plot-boundary segment. All other room edges are labeled internal; this does not infer wall material, load-bearing status, or fire rating.

`adjacencies` lists exact shared full wall edges, their length, the two room IDs/names, and `connected_by_door`. `circulation_components` groups rooms connected through those door-bearing shared edges. A room in a one-room component is isolated in this simplified door-connectivity graph. Partial collinear edge overlaps are not split or matched; door swing clearance, accessibility, daylight/ventilation, and fire-egress compliance are outside this analysis.
