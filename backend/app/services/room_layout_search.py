"""Bounded deterministic search for axis-aligned rectangular room layouts."""

from dataclasses import dataclass
from typing import Any


DEFAULT_MAX_NODES = 20_000
DEFAULT_MAX_SOLUTIONS = 24
MAX_NODES_HARD_CEILING = 100_000
MAX_SOLUTIONS_HARD_CEILING = 100
MAX_DEPTH_HARD_CEILING = 100
_EPSILON = 1e-7


@dataclass(frozen=True)
class SearchLimits:
    max_nodes: int = DEFAULT_MAX_NODES
    max_solutions: int = DEFAULT_MAX_SOLUTIONS
    max_depth: int = MAX_DEPTH_HARD_CEILING

    def __post_init__(self) -> None:
        if not 1 <= self.max_nodes <= MAX_NODES_HARD_CEILING:
            raise ValueError(f"max_nodes must be between 1 and {MAX_NODES_HARD_CEILING}")
        if not 1 <= self.max_solutions <= MAX_SOLUTIONS_HARD_CEILING:
            raise ValueError(f"max_solutions must be between 1 and {MAX_SOLUTIONS_HARD_CEILING}")
        if not 1 <= self.max_depth <= MAX_DEPTH_HARD_CEILING:
            raise ValueError(f"max_depth must be between 1 and {MAX_DEPTH_HARD_CEILING}")


@dataclass(frozen=True)
class SearchSolution:
    placements: tuple[dict, ...]
    seed_label: str


@dataclass(frozen=True)
class SearchResult:
    solutions: tuple[SearchSolution, ...]
    nodes_visited: int
    budget_exhausted: bool


def _touches_shared_wall(a: dict, b: dict) -> bool:
    ax1, ay1 = a["x"], a["y"]
    ax2, ay2 = ax1 + a["width"], ay1 + a["depth"]
    bx1, by1 = b["x"], b["y"]
    bx2, by2 = bx1 + b["width"], by1 + b["depth"]
    vertical_touch = abs(ax2 - bx1) <= _EPSILON or abs(bx2 - ax1) <= _EPSILON
    horizontal_overlap = min(ay2, by2) - max(ay1, by1) > _EPSILON
    horizontal_touch = abs(ay2 - by1) <= _EPSILON or abs(by2 - ay1) <= _EPSILON
    vertical_overlap = min(ax2, bx2) - max(ax1, bx1) > _EPSILON
    return (vertical_touch and horizontal_overlap) or (horizontal_touch and vertical_overlap)


def _overlaps(a: dict, b: dict) -> bool:
    return (
        min(a["x"] + a["width"], b["x"] + b["width"])
        - max(a["x"], b["x"]) > _EPSILON
        and min(a["y"] + a["depth"], b["y"] + b["depth"])
        - max(a["y"], b["y"]) > _EPSILON
    )


def _resolve_pair(placements: list[dict], room_a: str, room_b: str):
    a = next((room for room in placements if room["room_type"] == room_a or room["name"].casefold() == room_a.casefold()), None)
    b = next((room for room in placements if room is not a and (room["room_type"] == room_b or room["name"].casefold() == room_b.casefold())), None)
    return a, b


def _hard_relationships_hold(placements: list[dict], brief: Any) -> bool:
    for preference in brief.adjacency_preferences:
        if preference.priority != "must_be_adjacent":
            continue
        a, b = _resolve_pair(placements, preference.room_a, preference.room_b)
        if a is not None and b is not None and not _touches_shared_wall(a, b):
            return False
    for preference in brief.privacy_preferences:
        if preference.priority != "must":
            continue
        a, b = _resolve_pair(placements, preference.room_a, preference.room_b)
        if a is None or b is None:
            continue
        adjacent = _touches_shared_wall(a, b)
        if (preference.relation == "separate" and adjacent) or (preference.relation == "group" and not adjacent):
            return False
    return True


def _seed_orders(rooms: list[dict], brief: Any) -> list[tuple[str, list[dict]]]:
    public_rank = {
        "living": 0, "dining": 1, "study": 2, "bedroom": 3, "kitchen": 4,
        "bathroom": 5, "utility": 6, "staircase": 7, "corridor": 8, "parking": 9, "other": 10,
    }
    private_rank = {
        "bedroom": 0, "bathroom": 1, "living": 2, "dining": 3, "study": 4,
        "kitchen": 5, "utility": 6, "staircase": 7, "corridor": 8, "parking": 9, "other": 10,
    }
    service_rank = {
        "kitchen": 0, "dining": 1, "bathroom": 2, "utility": 3, "parking": 4,
        "staircase": 5, "corridor": 6, "living": 7, "bedroom": 8, "study": 9, "other": 10,
    }

    adjacency_order = list(rooms)
    grouped: list[dict] = []
    used: set[str] = set()
    for preference in brief.adjacency_preferences:
        if preference.priority != "must_be_adjacent":
            continue
        a, b = _resolve_pair(adjacency_order, preference.room_a, preference.room_b)
        if a is not None and b is not None and a["name"] not in used and b["name"] not in used:
            grouped.extend((a, b))
            used.update((a["name"], b["name"]))
    adjacency_order = grouped + [room for room in adjacency_order if room["name"] not in used]

    return [
        ("largest_first", sorted(rooms, key=lambda room: (-room["width"] * room["depth"], min(room["width"], room["depth"]), room["name"].casefold()))),
        ("adjacency_first", adjacency_order),
        ("public_first", sorted(rooms, key=lambda room: (public_rank.get(room["room_type"], 99), -room["width"] * room["depth"], room["name"].casefold()))),
        ("private_first", sorted(rooms, key=lambda room: (private_rank.get(room["room_type"], 99), -room["width"] * room["depth"], room["name"].casefold()))),
        ("service_cluster", sorted(rooms, key=lambda room: (service_rank.get(room["room_type"], 99), -room["width"] * room["depth"], room["name"].casefold()))),
    ]


def _placement_anchors(placed: list[dict], bounds: Any, width: float, depth: float):
    xs = {bounds.min_x, bounds.max_x - width}
    ys = {bounds.min_y, bounds.max_y - depth}
    for room in placed:
        xs.update((room["x"], room["x"] + room["width"]))
        ys.update((room["y"], room["y"] + room["depth"]))
    return [
        (x, y)
        for y in sorted(ys)
        for x in sorted(xs)
        if x >= bounds.min_x - _EPSILON
        and y >= bounds.min_y - _EPSILON
        and x + width <= bounds.max_x + _EPSILON
        and y + depth <= bounds.max_y + _EPSILON
    ]


def _partial_state_key(placed: list[dict], remaining: list[dict]) -> tuple:
    placed_key = tuple(sorted(
        (room["name"], round(room["x"], 4), round(room["y"], 4), round(room["width"], 4), round(room["depth"], 4))
        for room in placed
    ))
    return placed_key, tuple(room["name"] for room in remaining)


def _solution_key(placements: list[dict]) -> tuple:
    return tuple(sorted(
        (room["name"], round(room["x"], 4), round(room["y"], 4), round(room["width"], 4), round(room["depth"], 4))
        for room in placements
    ))


def search_room_layouts(rooms: list[dict], bounds: Any, brief: Any, limits: SearchLimits | None = None) -> SearchResult:
    """Find deterministic, non-overlapping placements within a bounded node budget."""
    limits = limits or SearchLimits()
    if len(rooms) > limits.max_depth:
        return SearchResult(solutions=(), nodes_visited=0, budget_exhausted=True)

    solutions: list[SearchSolution] = []
    solution_keys: set[tuple] = set()
    visited_states: set[tuple] = set()
    nodes_visited = 0
    budget_exhausted = False

    def visit(order: list[dict], seed_label: str, index: int, placed: list[dict]) -> None:
        nonlocal nodes_visited, budget_exhausted
        if budget_exhausted or len(solutions) >= limits.max_solutions:
            budget_exhausted = True
            return
        if index == len(order):
            key = _solution_key(placed)
            if key not in solution_keys:
                solution_keys.add(key)
                solutions.append(SearchSolution(placements=tuple(dict(item) for item in placed), seed_label=seed_label))
            return

        remaining = order[index:]
        state_key = _partial_state_key(placed, remaining)
        if state_key in visited_states:
            return
        visited_states.add(state_key)

        source = order[index]
        orientations = [(source["width"], source["depth"])]
        if source["allow_rotation"] and source["width"] != source["depth"]:
            orientations.append((source["depth"], source["width"]))

        for width, depth in orientations:
            for x, y in _placement_anchors(placed, bounds, width, depth):
                if nodes_visited >= limits.max_nodes:
                    budget_exhausted = True
                    return
                nodes_visited += 1
                candidate = {**source, "x": x, "y": y, "width": width, "depth": depth}
                if any(_overlaps(candidate, other) for other in placed):
                    continue
                next_placed = [*placed, candidate]
                if not _hard_relationships_hold(next_placed, brief):
                    continue
                visit(order, seed_label, index + 1, next_placed)
                if budget_exhausted or len(solutions) >= limits.max_solutions:
                    if len(solutions) >= limits.max_solutions:
                        budget_exhausted = True
                    return

    for seed_label, order in _seed_orders(rooms, brief):
        visit(order, seed_label, 0, [])
        if budget_exhausted:
            break

    return SearchResult(solutions=tuple(solutions), nodes_visited=nodes_visited, budget_exhausted=budget_exhausted)
