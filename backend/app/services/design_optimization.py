from app.schemas.layouts import RoomInput, CoordinateMM, OpeningInput, FurnitureInput, LayoutUpdate
from app.schemas.design_optimization import DesignOptimizationPreviewInput, DesignOptimizationPreview, FurniturePlannerResult
from app.services.assistant_proposals import fingerprint_floor_state
from app.services.furniture_planner import generate_furniture_arrangements
from app.services.opening_optimizer import suggest_openings
from app.services.room_usability import analyze_room_usability
from app.services.furniture_geometry import validate_furniture
from app.services.layouts import validate_layout_update
import json


def orm_rooms_to_inputs(rooms) -> list[RoomInput]:
    result=[]
    for room in rooms:
        result.append(RoomInput(name=room.name,room_type=room.room_type,vertices_mm=json.loads(room.geometry_json),wall_thickness_mm=room.wall_thickness_mm,openings=json.loads(room.openings_json or "[]"),furniture=json.loads(getattr(room,"furniture_json","[]") or "[]")))
    return result


def build_optimization_preview(project, floor_number: int, rooms, payload: DesignOptimizationPreviewInput) -> DesignOptimizationPreview:
    source=fingerprint_floor_state(project,floor_number,rooms)
    inputs=orm_rooms_to_inputs(rooms)
    by_name={r.name:r for r in inputs}
    candidates={}
    if payload.operation in {"furniture_arrangement","full_review"}:
        for name,room in by_name.items():
            if payload.room_ids and not any(r.id in payload.room_ids and r.name==name for r in rooms): continue
            requested=payload.requested_items_by_room.get(name)
            candidates[name]=generate_furniture_arrangements(room,requested)
    plot_vertices = json.loads(project.plot.geometry_json) if project.plot and project.plot.geometry_json else ([{"x":0,"y":0},{"x":project.plot.width_mm,"y":0},{"x":project.plot.width_mm,"y":project.plot.length_mm},{"x":0,"y":project.plot.length_mm}] if project.plot and project.plot.width_mm and project.plot.length_mm else [])
    plot_points = [(point["x"],point["y"]) for point in plot_vertices]
    openings=suggest_openings(inputs,{"road_facing_side":getattr(project.plot,"road_facing_side",None) if project.plot else None,"plot_vertices":plot_points},floor_number) if payload.operation in {"opening_suggestions","full_review"} else []
    analyses=analyze_room_usability(inputs,clearance_preferences=payload.clearance_preferences) if payload.operation=="full_review" else []
    return DesignOptimizationPreview(source_layout_fingerprint=source,operation=payload.operation,candidates=candidates,opening_suggestions=openings,room_analyses=analyses)


def apply_optimization_layout(db, project, floor_number: int, source_fingerprint: str, rooms: list[RoomInput]):
    from sqlalchemy import select
    from app.models.project import Room
    current=list(db.scalars(select(Room).where(Room.project_id==project.id,Room.floor_number==floor_number)).all())
    if fingerprint_floor_state(project,floor_number,current)!=source_fingerprint:
        raise ValueError("optimization_preview_stale")
    if any(room.furniture is None for room in rooms):
        raise ValueError("Every room must include an explicit furniture array when applying an optimization preview")
    payload=LayoutUpdate(floor_number=floor_number,rooms=rooms)
    validate_layout_update(project.plot,payload)
    furniture_errors = [issue.message for room in rooms for issue in validate_furniture(room, room.furniture or []) if issue.severity == "error"]
    if furniture_errors:
        raise ValueError("; ".join(furniture_errors))
    return payload
