import json

from app.services.geometry import polygon_area_mm2


def _allowance(ratio_percent: float) -> str:
    if ratio_percent <= 0:
        return "no_window_recorded"
    if ratio_percent < 8:
        return "limited_allowance"
    if ratio_percent < 15:
        return "moderate_allowance"
    return "higher_allowance"


def analyze_rooms(rooms, include_vastu: bool = False) -> dict:
    results = []
    vastu_notes: list[str] = []
    traditional_room_guidance = {
        "living": "Traditional Vastu references commonly favour a living area toward the north or east; treat this as an optional cultural preference, not a technical requirement.",
        "kitchen": "Traditional Vastu references commonly associate kitchens with the south-east; treat this as an optional cultural preference, not a technical requirement.",
        "bedroom": "Traditional Vastu references commonly favour a principal bedroom toward the south-west; treat this as an optional cultural preference, not a technical requirement.",
        "study": "Some traditional Vastu references suggest a study area toward the north or east; treat this as an optional cultural preference, not a technical requirement.",
    }

    for room in rooms:
        vertices_data = json.loads(room.geometry_json)
        vertices = [(point["x"], point["y"]) for point in vertices_data]
        floor_area_m2 = polygon_area_mm2(vertices) / 1_000_000
        openings = json.loads(room.openings_json or "[]")
        windows = [opening for opening in openings if opening.get("kind") == "window"]
        gross_window_area_m2 = sum(
            float(opening["width_mm"]) * float(opening["height_mm"]) / 1_000_000
            for opening in windows
        )
        ratio = gross_window_area_m2 / floor_area_m2 * 100 if floor_area_m2 > 0 else 0
        rounded_ratio = round(ratio, 2)
        results.append({
            "room_id": room.id,
            "room_name": room.name,
            "room_type": room.room_type,
            "floor_area_sq_m": round(floor_area_m2, 3),
            "window_count": len(windows),
            "window_opening_area_sq_m": round(gross_window_area_m2, 3),
            "window_to_floor_ratio_percent": rounded_ratio,
            "daylight_planning_indicator": _allowance(ratio),
            "ventilation_planning_indicator": _allowance(ratio),
            "note": "Window gross opening area is a preliminary planning proxy only; it does not account for orientation, shading, glazing, obstructions, opening type, airflow paths or climate.",
        })
        if include_vastu and room.room_type in traditional_room_guidance:
            vastu_notes.append(f"{room.name}: {traditional_room_guidance[room.room_type]}")

    return {
        "rooms": results,
        "vastu_mode": "traditional_reference_only" if include_vastu else "disabled",
        "vastu_notes": vastu_notes,
        "method_note": "These are early-stage geometric indicators, not daylight simulation, ventilation modelling, health guidance or code-compliance checks.",
        "is_code_certified": False,
    }
