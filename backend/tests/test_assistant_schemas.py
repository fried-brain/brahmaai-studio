import pytest
from pydantic import ValidationError

from app.schemas.assistant_ai import parse_assistant_ai_response


def test_strict_assistant_response_accepts_clarification_and_answer():
    clarification = parse_assistant_ai_response({
        "type": "clarification", "reply": "I need one detail.",
        "clarifying_questions": ["How many floors?"], "suggestions": [],
    })
    answer = parse_assistant_ai_response({"type": "answer", "reply": "A compact layout is possible.", "suggestions": []})
    assert clarification.type == "clarification"
    assert answer.type == "answer"


def test_strict_assistant_response_accepts_valid_layout_proposal():
    response = parse_assistant_ai_response({
        "type": "layout_proposal", "reply": "Here is a draft.",
        "proposal": {
            "schema_version": "1.0", "title": "Compact plan", "assumptions": [], "warnings": [],
            "floor_number": 0, "rooms": [{
                "proposal_id": "room-a", "name": "Living", "room_type": "living",
                "vertices_mm": [{"x": 0, "y": 0}, {"x": 4000, "y": 0}, {"x": 4000, "y": 4000}, {"x": 0, "y": 4000}],
                "wall_thickness_mm": 150, "openings": [],
            }],
        },
    })
    assert response.type == "layout_proposal"
    assert response.proposal.rooms[0].proposal_id == "room-a"


@pytest.mark.parametrize("payload", [
    {"type": "unknown", "reply": "x"},
    {"type": "answer", "reply": "x", "suggestions": [], "extra": True},
    {"type": "answer", "suggestions": []},
    {"type": "layout_proposal", "reply": "x", "proposal": {"schema_version": "1.0", "title": "x", "assumptions": [], "warnings": [], "floor_number": 0, "rooms": []}},
])
def test_assistant_schema_rejects_unknown_extra_missing_or_empty_proposal(payload):
    with pytest.raises(ValidationError):
        parse_assistant_ai_response(payload)


def test_layout_proposal_rejects_unsupported_room_type_and_blank_name():
    base_room = {
        "proposal_id": "r1", "name": "Kitchen", "room_type": "basement_pool",
        "vertices_mm": [{"x": 0, "y": 0}, {"x": 4000, "y": 0}, {"x": 4000, "y": 4000}],
        "wall_thickness_mm": 150, "openings": [],
    }
    payload = {"type": "layout_proposal", "reply": "draft", "proposal": {
        "schema_version": "1.0", "title": "Plan", "assumptions": [], "warnings": [], "floor_number": 0, "rooms": [base_room],
    }}
    with pytest.raises(ValidationError):
        parse_assistant_ai_response(payload)
    base_room["room_type"] = "kitchen"
    base_room["name"] = "  "
    with pytest.raises(ValidationError):
        parse_assistant_ai_response(payload)


def test_layout_proposal_rejects_out_of_range_coordinates_and_bad_opening_edges():
    room = {
        "proposal_id": "r1", "name": "Kitchen", "room_type": "kitchen",
        "vertices_mm": [{"x": 0, "y": 0}, {"x": 4000, "y": 0}, {"x": 4000, "y": 4000}],
        "wall_thickness_mm": 150,
        "openings": [{"kind": "door", "edge_index": 8, "offset_mm": 0, "width_mm": 900, "height_mm": 2100, "sill_height_mm": 0, "swing_direction": "left"}],
    }
    payload = {"type": "layout_proposal", "reply": "draft", "proposal": {
        "schema_version": "1.0", "title": "Plan", "assumptions": [], "warnings": [], "floor_number": 0, "rooms": [room],
    }}
    with pytest.raises(ValidationError):
        parse_assistant_ai_response(payload)
    room["openings"] = []
    room["vertices_mm"][0]["x"] = 200000
    with pytest.raises(ValidationError):
        parse_assistant_ai_response(payload)
