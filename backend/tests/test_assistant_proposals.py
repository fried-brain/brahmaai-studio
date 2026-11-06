import json
from sqlalchemy import select
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Project, User
from app.models.assistant import AssistantProposalRecord
from app.models.project import Plot, Room
from app.services.assistant_conversations import create_conversation
from app.services.assistant_proposals import create_pending_proposal, fingerprint_floor_state, validate_layout_proposal


def proposal(rooms=None):
    return {
        "schema_version": "1.0", "title": "Ground floor draft", "assumptions": [], "warnings": [], "floor_number": 0,
        "rooms": rooms if rooms is not None else [{
            "proposal_id": "living-1", "name": "Living", "room_type": "living",
            "vertices_mm": [{"x": 0.0, "y": 0.0}, {"x": 4000.0, "y": 0.0}, {"x": 4000.0, "y": 4000.0}, {"x": 0.0, "y": 4000.0}],
            "wall_thickness_mm": 150.0, "openings": [],
        }],
    }


def setup_records():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "proposal@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "proposal@example.com", "password": "StrongPass123!"})
    with client.app.state.session_factory() as db:
        owner = db.scalar(select(User).where(User.email == "proposal@example.com"))
        project = Project(owner_id=owner.id, name="Proposal home")
        project.plot = Plot(shape="rectangle", width_mm=10000, length_mm=10000)
        db.add(project)
        db.flush()
        conversation = create_conversation(db, project, owner, 0, "Design a home")
        db.commit()
        return client, db, owner, project, conversation


def test_valid_proposal_persists_as_draft_with_owner_project_floor_and_local_ids():
    client, db, owner, project, conversation = setup_records()
    saved_rooms = []
    record, result = create_pending_proposal(db, conversation, project, owner, proposal(), saved_rooms)
    db.commit()
    loaded = db.get(AssistantProposalRecord, record.id)
    assert loaded.status == "draft"
    assert loaded.owner_id == owner.id and loaded.project_id == project.id
    assert loaded.conversation_id == conversation.id and loaded.floor_number == 0
    assert json.loads(loaded.proposal_json)["rooms"][0]["proposal_id"] == "living-1"
    assert result.valid is True


def test_outside_plot_and_overlapping_rooms_are_marked_needs_revision():
    client, db, owner, project, conversation = setup_records()
    outside = proposal([{
        "proposal_id": "outside", "name": "Outside", "room_type": "living",
        "vertices_mm": [{"x": 9000.0, "y": 9000.0}, {"x": 12000.0, "y": 9000.0}, {"x": 12000.0, "y": 12000.0}],
        "wall_thickness_mm": 150.0, "openings": [],
    }])
    record, result = create_pending_proposal(db, conversation, project, owner, outside, [])
    assert record.status == "needs_revision"
    assert any("inside the plot" in issue["message"] for issue in result.issues)

    overlapping = proposal([proposal()["rooms"][0], {
        "proposal_id": "overlap", "name": "Kitchen", "room_type": "kitchen",
        "vertices_mm": [{"x": 2000.0, "y": 2000.0}, {"x": 5000.0, "y": 2000.0}, {"x": 5000.0, "y": 5000.0}, {"x": 2000.0, "y": 5000.0}],
        "wall_thickness_mm": 150.0, "openings": [],
    }])
    other, result2 = create_pending_proposal(db, conversation, project, owner, overlapping, [])
    assert other.status == "needs_revision"
    assert any("overlaps" in issue["message"] for issue in result2.issues)


def test_invalid_polygon_duplicate_name_and_opening_edge_are_actionable():
    client, db, owner, project, conversation = setup_records()
    invalid = proposal([{
        "proposal_id": "bad", "name": "Kitchen", "room_type": "kitchen",
        "vertices_mm": [{"x": 0.0, "y": 0.0}, {"x": 4000.0, "y": 0.0}, {"x": 0.0, "y": 0.0}],
        "wall_thickness_mm": 150.0, "openings": [],
    }])
    result = validate_layout_proposal(project, 0, invalid["rooms"])
    assert not result.valid and result.issues

    bad_opening = proposal([{
        "proposal_id": "bad-opening", "name": "Kitchen", "room_type": "kitchen",
        "vertices_mm": [{"x": 0.0, "y": 0.0}, {"x": 4000.0, "y": 0.0}, {"x": 4000.0, "y": 4000.0}],
        "wall_thickness_mm": 150.0,
        "openings": [{"kind": "door", "edge_index": 9, "offset_mm": 0.0, "width_mm": 900.0, "height_mm": 2100.0, "sill_height_mm": 0.0, "swing_direction": "left"}],
    }])
    result = validate_layout_proposal(project, 0, bad_opening["rooms"])
    assert not result.valid and any("edge" in issue["message"].lower() for issue in result.issues)


def test_floor_state_fingerprint_is_stable_and_changes_with_geometry_or_openings():
    client, db, owner, project, conversation = setup_records()
    first = fingerprint_floor_state(project, 0, [])
    second = fingerprint_floor_state(project, 0, [])
    assert first == second
    room = Room(project_id=project.id, floor_number=0, name="Living", room_type="living",
                geometry_json='[{"x":0,"y":0},{"x":4000,"y":0},{"x":4000,"y":4000}]',
                wall_thickness_mm=150, openings_json='[]')
    changed = fingerprint_floor_state(project, 0, [room])
    assert changed != first
    room.openings_json = '[{"kind":"window","edge_index":0,"offset_mm":100,"width_mm":900}]'
    assert fingerprint_floor_state(project, 0, [room]) != changed


def test_duplicate_room_names_and_overlapping_openings_are_rejected():
    client, db, owner, project, conversation = setup_records()
    duplicate_names = proposal([proposal()["rooms"][0], {
        "proposal_id": "living-2", "name": "living", "room_type": "bedroom",
        "vertices_mm": [{"x": 5000.0, "y": 0.0}, {"x": 9000.0, "y": 0.0}, {"x": 9000.0, "y": 4000.0}],
        "wall_thickness_mm": 150.0, "openings": [],
    }])
    result = validate_layout_proposal(project, 0, duplicate_names["rooms"])
    assert not result.valid and any("unique" in issue["message"].lower() for issue in result.issues)

    overlapping_openings = proposal([{
        "proposal_id": "living-openings", "name": "Living", "room_type": "living",
        "vertices_mm": [{"x": 0.0, "y": 0.0}, {"x": 4000.0, "y": 0.0}, {"x": 4000.0, "y": 4000.0}],
        "wall_thickness_mm": 150.0,
        "openings": [
            {"kind": "door", "edge_index": 0, "offset_mm": 0.0, "width_mm": 1000.0, "height_mm": 2100.0, "sill_height_mm": 0.0, "swing_direction": "left"},
            {"kind": "window", "edge_index": 0, "offset_mm": 500.0, "width_mm": 1000.0, "height_mm": 1200.0, "sill_height_mm": 900.0, "swing_direction": "none"},
        ],
    }])
    result = validate_layout_proposal(project, 0, overlapping_openings["rooms"])
    assert not result.valid and any("overlap" in issue["message"].lower() for issue in result.issues)
