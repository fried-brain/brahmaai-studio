import hashlib
import json
import math
from dataclasses import dataclass
from app.schemas.layouts import LayoutUpdate
from app.schemas.room_layout_candidates import CandidateScore, CandidateValidation, LayoutCandidate, PlannerResult
from app.schemas.room_planning import RoomPlanningBrief
from app.services.layouts import plot_vertices, validate_layout_update
from app.services.room_layout_search import SearchLimits, search_room_layouts

PLANNER_VERSION = "2.0"
ROOM_DEFAULTS = {
    "living": (3600, 4200), "bedroom": (3000, 3600), "kitchen": (2700, 3000),
    "bathroom": (1500, 2100), "dining": (2700, 3000), "study": (2400, 3000),
    "utility": (1800, 2100), "staircase": (2500, 4000), "corridor": (1200, 3000),
    "parking": (3000, 5500), "other": (3000, 3000),
}
BASE_WEIGHTS = {"adjacency": 15, "circulation": 20, "privacy": 10, "aspect_ratio": 10, "orientation_fit": 10, "compactness": 10, "plot_utilization": 15, "fragmentation": 10}

@dataclass(frozen=True)
class PlotBounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self): return self.max_x - self.min_x

    @property
    def depth(self): return self.max_y - self.min_y

    @property
    def area(self): return self.width * self.depth


def rectangular_plot_bounds(plot) -> PlotBounds | None:
    if plot is None:
        return None
    try:
        vertices = plot_vertices(plot)
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None
    if len(vertices) != 4 or len(set(vertices)) != 4:
        return None
    min_x = min(point[0] for point in vertices); max_x = max(point[0] for point in vertices)
    min_y = min(point[1] for point in vertices); max_y = max(point[1] for point in vertices)
    expected = {(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)}
    if set(vertices) != expected or max_x - min_x <= 0 or max_y - min_y <= 0:
        return None
    if getattr(plot, "width_mm", None) is not None and abs(plot.width_mm - (max_x - min_x)) > 1:
        return None
    if getattr(plot, "length_mm", None) is not None and abs(plot.length_mm - (max_y - min_y)) > 1:
        return None
    return PlotBounds(min_x, min_y, max_x, max_y)


def _expand_rooms(brief: RoomPlanningBrief):
    rooms = []
    assumptions = []
    for requirement in brief.required_rooms:
        default_width, default_depth = ROOM_DEFAULTS[requirement.room_type]
        width = float(requirement.preferred_width_mm or default_width)
        depth = float(requirement.preferred_depth_mm or default_depth)
        if requirement.preferred_width_mm is None:
            assumptions.append(f"{requirement.room_type.title()} dimensions defaulted to {default_width} × {default_depth} mm; product heuristic only.")
        for index in range(requirement.quantity):
            if requirement.name and requirement.quantity == 1:
                name = requirement.name.strip()
            else:
                name = f"{requirement.room_type.title()} {index + 1}"
            rooms.append({"name": name, "room_type": requirement.room_type, "width": width, "depth": depth,
                          "mode": requirement.dimension_mode, "allow_rotation": requirement.allow_rotation,
                          "target_aspect_ratio": requirement.target_aspect_ratio,
                          "long_axis_orientation": requirement.long_axis_orientation})
    if brief.hard_constraints:
        assumptions.append("Original hard-constraint notes are preserved for review; only structured room, dimension, adjacency and privacy fields are enforceable by planner version 2.0.")
        assumptions.extend(f"User-stated hard constraint: {item}" for item in brief.hard_constraints)
    if brief.circulation_preferences:
        assumptions.append("Free-text circulation preferences are preserved for review but are not automatically enforced by planner version 2.0.")
    if brief.orientation_preferences:
        assumptions.append("Free-text orientation preferences are preserved for review but are not automatically enforced by planner version 2.0.")
    assumptions.append("Candidate scores compare geometric heuristics only; they are not a professional quality or compliance rating.")
    return rooms, assumptions


def _room_vertices(room):
    x, y, width, depth = room["x"], room["y"], room["width"], room["depth"]
    return [{"x": x, "y": y}, {"x": x + width, "y": y}, {"x": x + width, "y": y + depth}, {"x": x, "y": y + depth}]


def _shared_edge(a, b):
    ax1, ay1, ax2, ay2 = a["x"], a["y"], a["x"] + a["width"], a["y"] + a["depth"]
    bx1, by1, bx2, by2 = b["x"], b["y"], b["x"] + b["width"], b["y"] + b["depth"]
    if abs(ax2 - bx1) <= 1e-7 or abs(bx2 - ax1) <= 1e-7:
        lo, hi = max(ay1, by1), min(ay2, by2)
        if hi - lo > 1e-7:
            if abs(ax2 - bx1) <= 1e-7:
                return (1, 3, hi - lo, lo, hi)
            return (3, 1, hi - lo, lo, hi)
    if abs(ay2 - by1) <= 1e-7 or abs(by2 - ay1) <= 1e-7:
        lo, hi = max(ax1, bx1), min(ax2, bx2)
        if hi - lo > 1e-7:
            if abs(ay2 - by1) <= 1e-7:
                return (2, 0, hi - lo, lo, hi)
            return (0, 2, hi - lo, lo, hi)
    return None


def _make_openings(placements, bounds, entrance_side=None):
    room_openings = {room["name"]: [] for room in placements}
    connected_pairs = []
    for index, a in enumerate(placements):
        for b in placements[index + 1:]:
            shared = _shared_edge(a, b)
            if not shared:
                continue
            edge_a, edge_b, length, low, high = shared
            connected_pairs.append((a["name"], b["name"], length))
            if length >= 900:
                width = min(900.0, length - 100.0)
                center = (low + high) / 2
                # Offsets are measured from each polygon edge's directed start.
                if edge_a == 1:
                    offset_a = center - a["y"] - width / 2
                elif edge_a == 3:
                    offset_a = a["y"] + a["depth"] - center - width / 2
                elif edge_a == 2:
                    offset_a = a["x"] + a["width"] - center - width / 2
                else:
                    offset_a = center - a["x"] - width / 2
                if edge_b == 1:
                    offset_b = center - b["y"] - width / 2
                elif edge_b == 3:
                    offset_b = b["y"] + b["depth"] - center - width / 2
                elif edge_b == 2:
                    offset_b = b["x"] + b["width"] - center - width / 2
                else:
                    offset_b = center - b["x"] - width / 2
                opening_a = {"kind": "door", "edge_index": edge_a, "offset_mm": max(0.0, offset_a), "width_mm": width, "height_mm": 2100.0, "sill_height_mm": 0.0, "swing_direction": "none"}
                opening_b = {**opening_a, "edge_index": edge_b, "offset_mm": max(0.0, offset_b)}
                room_openings[a["name"]].append(opening_a)
                room_openings[b["name"]].append(opening_b)
    entrance_placed = False
    side_edge = {"north": 0, "east": 1, "south": 2, "west": 3}.get(entrance_side)
    if side_edge is not None:
        preferred_rooms = sorted(placements, key=lambda room: (room["room_type"] not in {"living", "dining"}, room["name"].casefold()))
        for room in preferred_rooms:
            x, y, w, d = room["x"], room["y"], room["width"], room["depth"]
            edge_lengths = {0: (abs(y - bounds.min_y) <= 1e-7, w),
                            1: (abs(x + w - bounds.max_x) <= 1e-7, d),
                            2: (abs(y + d - bounds.max_y) <= 1e-7, w),
                            3: (abs(x - bounds.min_x) <= 1e-7, d)}
            touches, length = edge_lengths[side_edge]
            if touches and length >= 1100:
                door_width = 1000.0
                room_openings[room["name"]].append({
                    "kind": "door", "edge_index": side_edge, "offset_mm": (length - door_width) / 2,
                    "width_mm": door_width, "height_mm": 2100.0, "sill_height_mm": 0.0,
                    "swing_direction": "none",
                })
                entrance_placed = True
                break
    for room in placements:
        if room["room_type"] not in {"living", "bedroom", "kitchen", "dining", "study"}:
            continue
        x, y, w, d = room["x"], room["y"], room["width"], room["depth"]
        exterior_edges = []
        if abs(y - bounds.min_y) <= 1e-7: exterior_edges.append((0, w))
        if abs(x + w - bounds.max_x) <= 1e-7: exterior_edges.append((1, d))
        if abs(y + d - bounds.max_y) <= 1e-7: exterior_edges.append((2, w))
        if abs(x - bounds.min_x) <= 1e-7: exterior_edges.append((3, d))
        if exterior_edges:
            exterior_edges = [item for item in exterior_edges if not (entrance_placed and item[0] == side_edge)]
            if exterior_edges:
                edge_index, length = max(exterior_edges, key=lambda item: (item[1], -item[0]))
            else:
                continue
            if length >= 1400:
                width = min(1200.0, length - 100.0)
                room_openings[room["name"]].append({
                    "kind": "window", "edge_index": edge_index, "offset_mm": (length - width) / 2,
                    "width_mm": width, "height_mm": 1200.0, "sill_height_mm": 900.0, "swing_direction": "none",
                })
    return room_openings, connected_pairs, entrance_placed


def _privacy_ok(placements, brief):
    by_key = {room["name"].casefold(): room for room in placements}
    by_type = {}
    for room in placements: by_type.setdefault(room["room_type"], []).append(room)
    for pref in brief.privacy_preferences:
        if pref.priority != "must": continue
        a = by_key.get(pref.room_a.casefold()) or next(iter(by_type.get(pref.room_a, [])), None)
        b = by_key.get(pref.room_b.casefold()) or next(iter(by_type.get(pref.room_b, [])), None)
        if not a or not b:
            return False
        adjacent = _shared_edge(a, b) is not None
        if pref.relation == "separate" and adjacent: return False
        if pref.relation == "group" and not adjacent: return False
    return True


def _adjacency_met(placements, preference):
    a = next((room for room in placements if room["room_type"] == preference.room_a or room["name"].casefold() == preference.room_a.casefold()), None)
    b = next((room for room in placements if room is not a and (room["room_type"] == preference.room_b or room["name"].casefold() == preference.room_b.casefold())), None)
    return bool(a and b and _shared_edge(a, b))


def _circulation_components(placements, bounds, entrance_side=None):
    room_openings, connected_pairs, _ = _make_openings(placements, bounds, entrance_side)
    graph = {room["name"]: set() for room in placements}
    for room_a, room_b, shared_length in connected_pairs:
        if shared_length < 900:
            continue
        doors_a = [item for item in room_openings[room_a] if item["kind"] == "door"]
        doors_b = [item for item in room_openings[room_b] if item["kind"] == "door"]
        if doors_a and doors_b:
            graph[room_a].add(room_b)
            graph[room_b].add(room_a)
    components = []
    remaining = set(graph)
    while remaining:
        start = min(remaining, key=str.casefold)
        stack = [start]
        component = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(graph[current] - component)
        remaining -= component
        components.append(sorted(component, key=str.casefold))
    components.sort(key=lambda item: (item[0].casefold(), len(item)))
    return components


def _unallocated_components(placements, bounds):
    xs = sorted({bounds.min_x, bounds.max_x, *(room["x"] for room in placements), *(room["x"] + room["width"] for room in placements)})
    ys = sorted({bounds.min_y, bounds.max_y, *(room["y"] for room in placements), *(room["y"] + room["depth"] for room in placements)})
    cells = set()
    for row in range(len(ys) - 1):
        for column in range(len(xs) - 1):
            x1, x2 = xs[column], xs[column + 1]
            y1, y2 = ys[row], ys[row + 1]
            if x2 - x1 <= 1e-7 or y2 - y1 <= 1e-7:
                continue
            center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
            occupied = any(
                room["x"] <= center_x <= room["x"] + room["width"]
                and room["y"] <= center_y <= room["y"] + room["depth"]
                for room in placements
            )
            if not occupied:
                cells.add((row, column))
    components = 0
    while cells:
        components += 1
        stack = [cells.pop()]
        while stack:
            row, column = stack.pop()
            for neighbor in ((row - 1, column), (row + 1, column), (row, column - 1), (row, column + 1)):
                if neighbor in cells:
                    cells.remove(neighbor)
                    stack.append(neighbor)
    return components


def _score(placements, brief, bounds):
    adjacency_items = brief.adjacency_preferences
    adjacency_ratio = (sum(_adjacency_met(placements, item) for item in adjacency_items) / len(adjacency_items)) if adjacency_items else 1.0
    components = _circulation_components(placements, bounds, brief.entrance_side)
    circulation_ratio = max((len(component) for component in components), default=0) / len(placements) if placements else 0.0

    privacy_preferences = brief.privacy_preferences
    privacy_hits = 0
    for pref in privacy_preferences:
        a, b = _resolve_room_pair(placements, pref.room_a, pref.room_b)
        adjacent = bool(a and b and _shared_edge(a, b))
        if a and b and ((pref.relation == "separate" and not adjacent) or (pref.relation == "group" and adjacent)):
            privacy_hits += 1
    privacy_ratio = privacy_hits / len(privacy_preferences) if privacy_preferences else 1.0

    aspect_rooms = [room for room in placements if room.get("target_aspect_ratio") is not None]
    aspect_ratio_fit = 1.0
    if aspect_rooms:
        fits = []
        for room in aspect_rooms:
            actual = room["width"] / room["depth"]
            target = float(room["target_aspect_ratio"])
            fits.append(max(0.0, 1.0 - abs(math.log(actual / target)) / math.log(20)))
        aspect_ratio_fit = sum(fits) / len(fits)

    orientation_values = []
    for room in placements:
        expected = room.get("long_axis_orientation")
        if not expected:
            continue
        if abs(room["width"] - room["depth"]) <= 1e-7:
            orientation_values.append(0.5)
        elif expected == "east_west":
            orientation_values.append(1.0 if room["width"] > room["depth"] else 0.0)
        else:
            orientation_values.append(1.0 if room["depth"] > room["width"] else 0.0)
    entrance_placed = _make_openings(placements, bounds, brief.entrance_side)[2] if brief.entrance_side else None
    if entrance_placed is not None:
        orientation_values.append(1.0 if entrance_placed else 0.0)
    orientation_fit = sum(orientation_values) / len(orientation_values) if orientation_values else 1.0

    compactness_values = []
    for room in placements:
        ratio = max(room["width"] / room["depth"], room["depth"] / room["width"])
        compactness_values.append(min(1.0, 2.0 / (ratio + 1.0 / ratio)))
    compactness = sum(compactness_values) / len(compactness_values) if compactness_values else 0.0

    plot_area = bounds.area
    assigned_area = sum(room["width"] * room["depth"] for room in placements)
    unallocated_area = max(0.0, plot_area - assigned_area)
    utilization_ratio = assigned_area / plot_area if plot_area else 0.0
    leftover_components = _unallocated_components(placements, bounds)
    fragmentation_ratio = 1.0 if leftover_components <= 1 else 1.0 / leftover_components

    ratios = {
        "adjacency": adjacency_ratio,
        "circulation": circulation_ratio,
        "privacy": privacy_ratio,
        "aspect_ratio": aspect_ratio_fit,
        "orientation_fit": orientation_fit,
        "compactness": compactness,
        "plot_utilization": utilization_ratio,
        "fragmentation": fragmentation_ratio,
    }
    active = set(ratios)
    if not adjacency_items:
        active.discard("adjacency")
    if not privacy_preferences:
        active.discard("privacy")
    if not aspect_rooms:
        active.discard("aspect_ratio")
    if not orientation_values:
        active.discard("orientation_fit")
    weights = {key: BASE_WEIGHTS[key] for key in active}
    weight_total = sum(weights.values()) or 1
    weights = {key: value * 100 / weight_total for key, value in weights.items()}
    raw = {key: ratios[key] * weights[key] for key in weights}
    breakdown = {key: int(value) for key, value in raw.items()}
    rounded_total = round(sum(raw.values()))
    remainder = rounded_total - sum(breakdown.values())
    if remainder:
        largest = max(raw, key=lambda key: raw[key] - int(raw[key]))
        breakdown[largest] += remainder
    utilization = {
        "plot_area_mm2": plot_area,
        "assigned_area_mm2": assigned_area,
        "unallocated_area_mm2": unallocated_area,
        "utilization_percent": round(utilization_ratio * 100, 2),
    }
    return CandidateScore(total=sum(breakdown.values()), breakdown=breakdown), utilization, components, leftover_components


def _resolve_room_pair(placements, room_a, room_b):
    a = next((room for room in placements if room["room_type"] == room_a or room["name"].casefold() == room_a.casefold()), None)
    b = next((room for room in placements if room is not a and (room["room_type"] == room_b or room["name"].casefold() == room_b.casefold())), None)
    return a, b


def _candidate_distance(a, b, bounds):
    a_rooms = {room["name"]: room for room in a.rooms}
    b_rooms = {room["name"]: room for room in b.rooms}
    common = sorted(set(a_rooms) & set(b_rooms), key=str.casefold)
    if not common:
        return 0.0
    diagonal = math.hypot(bounds.width, bounds.depth) or 1.0
    distances = []
    for name in common:
        a_points = a_rooms[name]["vertices_mm"]
        b_points = b_rooms[name]["vertices_mm"]
        ax = sum(point["x"] for point in a_points) / len(a_points)
        ay = sum(point["y"] for point in a_points) / len(a_points)
        bx = sum(point["x"] for point in b_points) / len(b_points)
        by = sum(point["y"] for point in b_points) / len(b_points)
        distances.append(math.hypot(ax - bx, ay - by) / diagonal)
    return sum(distances) / len(distances)


def _build_candidate(placements, bounds, brief, template, assumptions):
    room_openings, connected_pairs, entrance_placed = _make_openings(placements, bounds, brief.entrance_side)
    unmet = []
    for preference in brief.adjacency_preferences:
        if not _adjacency_met(placements, preference):
            unmet.append(f"{preference.room_a} and {preference.room_b} are not adjacent.")
    for preference in brief.privacy_preferences:
        if preference.priority == "prefer":
            a = next((room for room in placements if room["room_type"] == preference.room_a or room["name"].casefold() == preference.room_a.casefold()), None)
            b = next((room for room in placements if room is not a and (room["room_type"] == preference.room_b or room["name"].casefold() == preference.room_b.casefold())), None)
            adjacent = bool(a and b and _shared_edge(a, b))
            if (preference.relation == "separate" and adjacent) or (preference.relation == "group" and not adjacent):
                unmet.append(f"Privacy preference '{preference.relation}' for {preference.room_a} and {preference.room_b} was not met.")
    rooms = []
    ordered_placements = sorted(placements, key=lambda item: item["name"].casefold())
    for index, room in enumerate(ordered_placements):
        rooms.append({
            "proposal_id": f"room-{index + 1}", "name": room["name"], "room_type": room["room_type"],
            "vertices_mm": _room_vertices(room), "wall_thickness_mm": 150.0,
            "openings": room_openings[room["name"]],
        })
    score, utilization, circulation_components, leftover_components = _score(placements, brief, bounds)
    canonical = {"brief": brief.model_dump(mode="json"), "planner_version": PLANNER_VERSION, "rooms": rooms}
    candidate_key = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    warnings = list(unmet)
    if not brief.entrance_side:
        warnings.append("External entrance location needs user confirmation; no entrance door was assumed.")
    elif not entrance_placed:
        warnings.append("No suitable room edge was found on the requested entrance side; confirm the entrance location manually.")
    if brief.orientation_preferences:
        warnings.append("Free-text orientation preferences are recorded but not spatially scored by planner version 2.0.")
    if len(circulation_components) > 1:
        warnings.append("Door-connected room groups are disconnected; this is not fire-egress, accessibility, or building-code approval.")
    if brief.required_rooms and any(item.long_axis_orientation for item in brief.required_rooms):
        assumptions.append("Long-axis orientation uses the plot's local width/depth axes; verify the north-up transform before applying.")
    if leftover_components > 1:
        warnings.append(f"Unallocated plot area is split into {leftover_components} edge-disconnected regions.")
    if brief.entrance_side and entrance_placed:
        assumptions.append("Entrance-side mapping assumes a north-up local plan: north=min-y, east=max-x, south=max-y, west=min-x. Verify this against the project's actual orientation before applying.")
    if brief.vastu_mode != "off":
        assumptions.append("Vastu mode is an optional traditional reference; planner version 2.0 does not certify or score Vastu compliance.")
    return LayoutCandidate(
        candidate_key=candidate_key, planner_version=PLANNER_VERSION, score_version="2.0",
        template=template, title=f"{template.replace('_', ' ').title()} layout", rooms=rooms,
        score=score, utilization=utilization, circulation_components=circulation_components,
        assumptions=list(dict.fromkeys(assumptions)), warnings=warnings, unmet_preferences=unmet,
    )


def generate_layout_candidates(plot, brief: RoomPlanningBrief, planner_config: dict | None = None) -> PlannerResult:
    bounds = rectangular_plot_bounds(plot)
    if bounds is None:
        return PlannerResult(status="unsupported_plot_geometry", reasons=["Automatic generation currently requires an exact axis-aligned rectangular plot."])
    rooms, assumptions = _expand_rooms(brief)
    room_names = [room["name"].strip().casefold() for room in rooms]
    if len(room_names) != len(set(room_names)):
        return PlannerResult(status="infeasible", reasons=["Room names must be unique. Give each requested room a distinct name."])
    total_area = sum(room["width"] * room["depth"] for room in rooms)
    if total_area > bounds.area + 1e-7:
        room_names = ", ".join(room["name"] for room in rooms)
        return PlannerResult(status="infeasible", reasons=[f"Required rooms ({room_names}) total {total_area:.0f} mm², exceeding plot area ({bounds.area:.0f} mm²). No rooms were silently reduced."])
    for room in rooms:
        orientations = [(room["width"], room["depth"])]
        if room["allow_rotation"] and room["width"] != room["depth"]:
            orientations.append((room["depth"], room["width"]))
        if not any(width <= bounds.width + 1e-7 and depth <= bounds.depth + 1e-7 for width, depth in orientations):
            return PlannerResult(status="infeasible", reasons=[f"Required dimensions for {room['name']} exceed plot bounds in every permitted orientation. No dimensions were reduced."])

    config = planner_config or {}
    allowed_limit_keys = {"max_nodes", "max_solutions", "max_depth"}
    limits = SearchLimits(**{key: value for key, value in config.items() if key in allowed_limit_keys})
    search_result = search_room_layouts(rooms, bounds, brief, limits)
    candidates = []
    seen_geometries = set()
    reasons = []
    for solution in search_result.solutions:
        placements = list(solution.placements)
        if not _privacy_ok(placements, brief):
            continue
        if any(item.priority == "must_be_adjacent" and not _adjacency_met(placements, item) for item in brief.adjacency_preferences):
            continue
        candidate = _build_candidate(placements, bounds, brief, solution.seed_label, assumptions.copy())
        candidate_rooms = [{key: value for key, value in room.items() if key != "proposal_id"} for room in candidate.rooms]
        try:
            layout = LayoutUpdate.model_validate({"floor_number": brief.floor_number, "rooms": candidate_rooms})
            validate_layout_update(plot, layout)
        except Exception as exc:
            reasons.append(f"{solution.seed_label}: generated geometry failed validation: {str(exc)[:300]}")
            continue
        geometry_signature = json.dumps(
            sorted(candidate.rooms, key=lambda room: (room["name"].casefold(), room["name"])),
            sort_keys=True, separators=(",", ":"),
        )
        if geometry_signature not in seen_geometries:
            seen_geometries.add(geometry_signature)
            if search_result.budget_exhausted:
                candidate = candidate.model_copy(update={"search_status": "budget_exhausted"})
            candidates.append(candidate)
    candidates.sort(key=lambda item: (-item.score.total, item.template, item.candidate_key))
    diverse_candidates = []
    for candidate in candidates:
        if all(_candidate_distance(candidate, selected, bounds) >= 0.08 for selected in diverse_candidates):
            diverse_candidates.append(candidate)
        if len(diverse_candidates) == 3:
            break
    candidates = diverse_candidates
    if not candidates:
        if search_result.budget_exhausted:
            return PlannerResult(status="search_exhausted", reasons=["The bounded layout search reached its configured limit before finding a validated candidate. This does not prove that no possible manual arrangement exists."], planner_version=PLANNER_VERSION, search_status="budget_exhausted")
        return PlannerResult(status="infeasible", reasons=reasons or ["The complete supported anchor search found no valid arrangement. This search result does not prove mathematical impossibility."], planner_version=PLANNER_VERSION)
    return PlannerResult(status="layout_candidates", candidates=candidates[:3], reasons=reasons,
                         planner_version=PLANNER_VERSION,
                         search_status="budget_exhausted" if search_result.budget_exhausted else "complete")


def validate_layout_candidate(project, floor_number: int, candidate: LayoutCandidate) -> CandidateValidation:
    from app.services.assistant_proposals import validate_layout_proposal
    proposal_rooms = candidate.rooms
    result = validate_layout_proposal(project, floor_number, proposal_rooms)
    return CandidateValidation(valid=result.valid, issues=result.issues)
