from app.schemas.layouts import FurnitureInput, RoomInput
from app.schemas.design_optimization import FurnitureIssue
from app.services.geometry import point_location, polygon_within_polygon


def furniture_bounds(item: FurnitureInput) -> tuple[float, float, float, float]:
    width, depth = (item.depth_mm, item.width_mm) if item.rotation_deg in (90, 270) else (item.width_mm, item.depth_mm)
    return item.x_mm-width/2, item.y_mm-depth/2, item.x_mm+width/2, item.y_mm+depth/2


def rectangles_overlap(a, b) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def _inside_bounds(bounds, polygon, margin):
    x1,y1,x2,y2 = bounds
    if x2 - x1 <= 2 * margin or y2 - y1 <= 2 * margin:
        return False
    inset = [(x1+margin,y1+margin),(x2-margin,y1+margin),(x2-margin,y2-margin),(x1+margin,y2-margin)]
    return polygon_within_polygon(inset, polygon) and all(point_location(point, polygon) != "outside" for point in inset)


def validate_furniture(room: RoomInput, furniture: list[FurnitureInput], wall_margin_mm: float = 50) -> list[FurnitureIssue]:
    issues=[]; polygon=[(p.x,p.y) for p in room.vertices_mm]
    for i,item in enumerate(furniture):
        bounds=furniture_bounds(item)
        if not _inside_bounds(bounds, polygon, wall_margin_mm):
            issues.append(FurnitureIssue(code="furniture_outside_room", severity="error", item_ids=[item.item_id], message=f"{item.name} does not fit inside the room with {wall_margin_mm:g} mm planning margin."))
        for other in furniture[:i]:
            if rectangles_overlap(bounds, furniture_bounds(other)):
                issues.append(FurnitureIssue(code="furniture_overlap", severity="error", item_ids=[other.item_id,item.item_id], message=f"{item.name} overlaps {other.name}."))
        for opening in room.openings:
            if opening.kind == "door":
                issues.append(FurnitureIssue(code="door_approach_review", severity="warning", item_ids=[item.item_id], message=f"Review access between {item.name} and the door on wall edge {opening.edge_index}."))
    return issues
