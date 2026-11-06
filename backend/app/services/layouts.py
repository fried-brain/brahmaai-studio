import json

from app.schemas.layouts import LayoutUpdate
from app.services.geometry import polygon_within_polygon, polygons_overlap


def plot_vertices(plot) -> list[tuple[float, float]]:
    if plot.geometry_json:
        return [(point["x"], point["y"]) for point in json.loads(plot.geometry_json)]
    return [(0.0, 0.0), (plot.width_mm, 0.0), (plot.width_mm, plot.length_mm), (0.0, plot.length_mm)]


def validate_layout_update(plot, payload: LayoutUpdate) -> list[tuple[float, float]]:
    if plot is None:
        raise ValueError("Define the plot before creating a floor layout")
    boundary = plot_vertices(plot)
    room_polygons: list[tuple[str, list[tuple[float, float]]]] = []
    for room in payload.rooms:
        vertices = [(point.x, point.y) for point in room.vertices_mm]
        if not polygon_within_polygon(vertices, boundary):
            raise ValueError(f"Room '{room.name}' must remain inside the plot")
        for other_name, other_vertices in room_polygons:
            if polygons_overlap(vertices, other_vertices):
                raise ValueError(f"Room '{room.name}' overlaps room '{other_name}'")
        room_polygons.append((room.name, vertices))
    return boundary


def persist_floor_rooms(db, project_id: str, payload: LayoutUpdate):
    from app.models.project import Room

    existing = db.query(Room).filter(Room.project_id == project_id, Room.floor_number == payload.floor_number).all()
    by_name = {}
    for previous in existing:
        by_name.setdefault(previous.name.strip().casefold(), []).append(previous)
    incoming_names = {room.name.strip().casefold() for room in payload.rooms}
    unmatched_with_furniture = [r.name for r in existing if json.loads(getattr(r, "furniture_json", "[]") or "[]") and r.name.strip().casefold() not in incoming_names]
    if unmatched_with_furniture and any(room.furniture is None for room in payload.rooms):
        raise ValueError("Legacy layout update cannot safely preserve furniture for renamed or removed rooms; send explicit furniture arrays")
    db.query(Room).filter(Room.project_id == project_id, Room.floor_number == payload.floor_number).delete()
    stored_rooms = []
    for room in payload.rooms:
        furniture = room.furniture
        if furniture is None:
            matches = by_name.get(room.name.strip().casefold(), [])
            if len(matches) > 1:
                raise ValueError("Cannot safely match existing room furniture")
            furniture_data = json.loads(matches[0].furniture_json or "[]") if matches else []
        else:
            furniture_data = [item.model_dump() for item in furniture]
        stored = Room(
            project_id=project_id,
            floor_number=payload.floor_number,
            name=room.name.strip(),
            room_type=room.room_type,
            geometry_json=json.dumps([point.model_dump() for point in room.vertices_mm], separators=(",", ":")),
            wall_thickness_mm=room.wall_thickness_mm,
            openings_json=json.dumps([opening.model_dump() for opening in room.openings], separators=(",", ":")),
            furniture_json=json.dumps(furniture_data, separators=(",", ":")),
        )
        db.add(stored)
        stored_rooms.append(stored)
    db.flush()
    return stored_rooms
