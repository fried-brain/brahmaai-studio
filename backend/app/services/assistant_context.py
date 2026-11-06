import json

from app.schemas.layouts import parse_room


def build_project_context(project, floor_number: int, rooms: list) -> dict:
    plot = project.plot
    plot_data = None
    if plot is not None:
        plot_data = {
            "shape": plot.shape,
            "width_mm": plot.width_mm,
            "length_mm": plot.length_mm,
            "vertices_mm": json.loads(plot.geometry_json) if plot.geometry_json else None,
            "orientation": plot.orientation,
            "road_facing_side": plot.road_facing_side,
        }
    selected_rooms = []
    for room in rooms:
        if room.floor_number != floor_number:
            continue
        selected_rooms.append({
            "name": room.name,
            "room_type": room.room_type,
            "vertices_mm": parse_room(room),
            "wall_thickness_mm": room.wall_thickness_mm,
            "openings": json.loads(room.openings_json or "[]"),
        })
    return {
        "project": {"category": project.category},
        "plot": plot_data,
        "floor_number": floor_number,
        "rooms": selected_rooms,
    }


def build_bounded_history(messages: list, max_messages: int, max_characters: int) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    used = 0
    for message in reversed(messages):
        role = message.role if hasattr(message, "role") else message.get("role")
        content = message.content if hasattr(message, "content") else message.get("content", "")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        if len(selected) >= max_messages or used >= max_characters:
            break
        remaining = max_characters - used
        if len(content) > remaining:
            content = content[-remaining:]
        if not content:
            break
        selected.append({"role": role, "content": content})
        used += len(content)
    selected.reverse()
    return selected
