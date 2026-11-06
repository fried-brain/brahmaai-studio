from app.schemas.layouts import RoomInput
from app.schemas.design_optimization import RoomUsability, FurnitureIssue
from app.services.geometry import polygon_area_mm2
from app.services.furniture_geometry import furniture_bounds, rectangles_overlap, validate_furniture


def analyze_room_usability(rooms: list[RoomInput], *, clearance_preferences: dict | None = None) -> list[RoomUsability]:
    results=[]
    for room in rooms:
        polygon=[(p.x,p.y) for p in room.vertices_mm]
        area=polygon_area_mm2(polygon)
        furniture=room.furniture or []
        occupied=sum(item.width_mm*item.depth_mm for item in furniture)
        issues=validate_furniture(room,furniture)
        for opening in room.openings:
            if opening.kind=="door":
                issues.append(FurnitureIssue(code="door_access_review",severity="warning",message=f"Review clear approach to door on edge {opening.edge_index}."))
        if occupied>area:
            issues.append(FurnitureIssue(code="high_furniture_coverage",severity="warning",message="Furniture footprint area exceeds room area; verify layout geometry."))
        results.append(RoomUsability(room_name=room.name,area_mm2=area,furniture_area_mm2=occupied,unoccupied_area_mm2=max(0,area-occupied),issues=issues))
    return results
