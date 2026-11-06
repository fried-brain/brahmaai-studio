import hashlib
import json
from app.schemas.layouts import FurnitureInput, RoomInput
from app.schemas.design_optimization import FurnitureArrangementCandidate, FurniturePlannerResult
from app.services.furniture_geometry import furniture_bounds, rectangles_overlap, validate_furniture


def _orthogonal_rectangle(room: RoomInput) -> bool:
    points = [(p.x, p.y) for p in room.vertices_mm]
    if len(points) != 4:
        return False
    return all(abs(points[i][0] - points[(i + 1) % 4][0]) < 1e-7 or abs(points[i][1] - points[(i + 1) % 4][1]) < 1e-7 for i in range(4))


def _candidate_for_variant(room, items, bounds, variant, budget):
    minx, maxx, miny, maxy = bounds
    placed = []
    explored = 0
    for item in sorted(items, key=lambda value: (-value.width_mm * value.depth_mm, value.item_id)):
        found = None
        for rotation in (item.rotation_deg, 90 if item.rotation_deg in (0, 180) else 0):
            width, height = (item.depth_mm, item.width_mm) if rotation in (90, 270) else (item.width_mm, item.depth_mm)
            step = max(100, min(width, height) // 2)
            x_values = []
            x = minx + 50 + width / 2
            while x + width / 2 <= maxx - 50:
                x_values.append(x); x += step
            y_values = []
            y = miny + 50 + height / 2
            while y + height / 2 <= maxy - 50:
                y_values.append(y); y += step
            if variant in (1, 3): x_values.reverse()
            if variant in (2, 3): y_values.reverse()
            for y in y_values:
                for x in x_values:
                    if explored >= budget:
                        return None, explored, True
                    explored += 1
                    candidate = item.model_copy(update={"x_mm": x, "y_mm": y, "rotation_deg": rotation})
                    if all(not rectangles_overlap(furniture_bounds(candidate), furniture_bounds(previous)) for previous in placed):
                        found = candidate
                        break
                if found:
                    break
            if found:
                break
        if found is None:
            return None, explored, False
        placed.append(found)
    issues = validate_furniture(room, placed)
    if any(issue.severity == "error" for issue in issues):
        return None, explored, False
    normalized = [item.model_dump(mode="json") for item in placed]
    key = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]
    candidate = FurnitureArrangementCandidate(candidate_key=key, placements=placed, issues=issues, score=max(0, 100 - len(issues) * 5), assumptions=["Rectangular orthogonal room; 50 mm planning wall margin.", f"Deterministic anchor order variant {variant + 1}."])
    return candidate, explored, False


def generate_furniture_arrangements(room: RoomInput, requested_items: list[FurnitureInput] | None, *, max_candidates: int = 3, search_budget: int = 5000) -> FurniturePlannerResult:
    if not _orthogonal_rectangle(room):
        return FurniturePlannerResult(status="unsupported_geometry")
    items = list(requested_items if requested_items is not None else (room.furniture or []))
    if not items:
        return FurniturePlannerResult(status="infeasible")
    xs = [point.x for point in room.vertices_mm]; ys = [point.y for point in room.vertices_mm]
    bounds = (min(xs), max(xs), min(ys), max(ys))
    candidates = []
    explored_total = 0
    exhausted = False
    for variant in range(min(3, max(1, max_candidates))):
        candidate, explored, hit_budget = _candidate_for_variant(room, items, bounds, variant, max(1, search_budget - explored_total))
        explored_total += explored
        exhausted = exhausted or hit_budget
        if candidate and all(candidate.candidate_key != existing.candidate_key for existing in candidates):
            candidates.append(candidate)
        if explored_total >= search_budget:
            break
    if candidates:
        return FurniturePlannerResult(status="complete", candidates=candidates[:max_candidates], explored=explored_total)
    return FurniturePlannerResult(status="search_exhausted" if exhausted else "infeasible", explored=explored_total)
