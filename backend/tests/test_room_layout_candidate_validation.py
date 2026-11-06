from types import SimpleNamespace

from app.schemas.room_planning import RoomPlanningBrief
from app.services.room_layout_planner import generate_layout_candidates, validate_layout_candidate


def test_every_generated_candidate_passes_existing_proposal_and_layout_validation():
    project = SimpleNamespace(plot=SimpleNamespace(
        shape="rectangle", width_mm=10000, length_mm=10000, geometry_json=None,
    ))
    brief = RoomPlanningBrief.model_validate({
        "floor_number": 0,
        "required_rooms": [{"room_type": "living", "quantity": 1}, {"room_type": "bedroom", "quantity": 1}],
        "adjacency_preferences": [], "privacy_preferences": [], "circulation_preferences": [],
    })
    result = generate_layout_candidates(project.plot, brief)
    assert result.status == "layout_candidates"
    for candidate in result.candidates:
        validation = validate_layout_candidate(project, 0, candidate)
        assert validation.valid, validation.issues
