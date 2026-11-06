import pytest
from pydantic import ValidationError

from app.schemas.room_planning import parse_room_planning_response


def valid_brief():
    return {
        "type": "planning_brief",
        "reply": "I have enough information to draft this floor.",
        "brief": {
            "floor_number": 0,
            "required_rooms": [
                {"room_type": "bedroom", "quantity": 3},
                {"room_type": "kitchen", "quantity": 1},
                {"room_type": "living", "quantity": 1},
                {"room_type": "parking", "quantity": 1, "preferred_width_mm": 3000, "preferred_depth_mm": 5500, "dimension_mode": "preferred"},
            ],
            "adjacency_preferences": [
                {"room_a": "kitchen", "room_b": "dining", "priority": "must_be_adjacent"},
                {"room_a": "living", "room_b": "dining", "priority": "prefer_adjacent"},
            ],
            "privacy_preferences": [
                {"room_a": "living", "room_b": "bedroom", "relation": "separate", "priority": "must"}
            ],
            "circulation_preferences": ["Keep the entrance connected to living"],
            "entrance_side": "east",
            "orientation_preferences": ["living faces east"],
            "vastu_mode": "off",
            "hard_constraints": ["Three bedrooms"],
            "notes": "Family home",
        },
    }


def test_planning_brief_preserves_room_dimensions_preferences_and_floor():
    parsed = parse_room_planning_response(valid_brief())
    assert parsed.type == "planning_brief"
    assert parsed.brief.floor_number == 0
    parking = next(room for room in parsed.brief.required_rooms if room.room_type == "parking")
    assert (parking.preferred_width_mm, parking.preferred_depth_mm, parking.dimension_mode) == (3000, 5500, "preferred")
    assert parsed.brief.adjacency_preferences[0].priority == "must_be_adjacent"
    assert parsed.brief.privacy_preferences[0].relation == "separate"
    assert parsed.brief.entrance_side == "east"


def test_planning_clarification_is_a_typed_response():
    parsed = parse_room_planning_response({
        "type": "clarification", "reply": "I need one detail before planning.",
        "questions": ["What is the plot width and length?"], "suggestions": [],
    })
    assert parsed.type == "clarification"
    assert parsed.questions == ["What is the plot width and length?"]


@pytest.mark.parametrize("mutate", [
    lambda value: value.update(extra="no"),
    lambda value: value["brief"].update(extra="no"),
    lambda value: value["brief"]["required_rooms"][0].update(room_type="pool"),
    lambda value: value["brief"]["required_rooms"][0].update(quantity=-1),
    lambda value: value["brief"].update(floor_number=99),
    lambda value: value["brief"]["required_rooms"][0].update(preferred_width_mm=-100),
    lambda value: value["brief"].update(notes="x" * 2001),
    lambda value: value["brief"].update(adjacency_preferences=[
        {"room_a": "kitchen", "room_b": "dining", "priority": "must_be_adjacent"},
        {"room_a": "dining", "room_b": "kitchen", "priority": "must_be_adjacent"},
    ]),
    lambda value: value["brief"].update(vertices_mm=[{"x": 0, "y": 0}]),
])
def test_planning_brief_rejects_invalid_or_geometry_bearing_payloads(mutate):
    payload = valid_brief()
    mutate(payload)
    with pytest.raises(ValidationError):
        parse_room_planning_response(payload)


def test_planning_brief_rejects_more_room_instances_than_proposal_contract():
    payload = {
        "type": "planning_brief", "reply": "Ready", "brief": {
            "floor_number": 0, "required_rooms": [{"room_type": "bedroom", "quantity": 20}] * 6,
            "adjacency_preferences": [], "privacy_preferences": [], "circulation_preferences": [],
        },
    }
    with pytest.raises(ValidationError):
        parse_room_planning_response(payload)


def test_room_requirement_accepts_structured_proportion_and_axis_preferences():
    payload = valid_brief()
    payload["brief"]["required_rooms"][0]["target_aspect_ratio"] = 1.25
    payload["brief"]["required_rooms"][0]["long_axis_orientation"] = "east_west"
    parsed = parse_room_planning_response(payload)
    bedroom = parsed.brief.required_rooms[0]
    assert bedroom.target_aspect_ratio == 1.25
    assert bedroom.long_axis_orientation == "east_west"


def test_room_requirement_rejects_invalid_proportion_and_axis_preferences():
    for field, value in (("target_aspect_ratio", 0), ("target_aspect_ratio", 20.1), ("long_axis_orientation", "diagonal")):
        payload = valid_brief()
        payload["brief"]["required_rooms"][0][field] = value
        with pytest.raises(ValidationError):
            parse_room_planning_response(payload)
