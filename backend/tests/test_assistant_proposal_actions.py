import json

from sqlalchemy import select
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Project, User
from app.models.assistant import AssistantProposalRecord
from app.models.project import Room
from app.services.assistant_conversations import create_conversation
from app.services.assistant_proposals import create_pending_proposal


def draft(name="Living", x=0.0):
    return {
        "schema_version": "1.0", "title": "Ground floor", "assumptions": [], "warnings": [], "floor_number": 0,
        "rooms": [{
            "proposal_id": "living-1", "name": name, "room_type": "living",
            "vertices_mm": [{"x": x, "y": 0.0}, {"x": x + 4000.0, "y": 0.0}, {"x": x + 4000.0, "y": 4000.0}, {"x": x, "y": 4000.0}],
            "wall_thickness_mm": 150.0, "openings": [],
        }],
    }


def setup_proposal(email="actions@example.com", saved=True):
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "Apply Home", "plot": {"shape": "rectangle", "width": 10, "length": 10, "unit": "m"}
    })
    project_id = created.json()["id"]
    if saved:
        layout = {"floor_number": 0, "rooms": [{
            "name": "Existing", "room_type": "living",
            "vertices_mm": [{"x": 0, "y": 0}, {"x": 3000, "y": 0}, {"x": 3000, "y": 3000}, {"x": 0, "y": 3000}],
            "wall_thickness_mm": 150, "openings": [],
        }]}
        assert client.put(f"/api/v1/projects/{project_id}/layout", headers=headers, json=layout).status_code == 200
    with client.app.state.session_factory() as db:
        owner = db.scalar(select(User).where(User.email == email))
        project = db.get(Project, project_id)
        conversation = create_conversation(db, project, owner, 0, "Create a floor plan")
        saved_rooms = list(db.scalars(select(Room).where(Room.project_id == project_id, Room.floor_number == 0)).all())
        record, _ = create_pending_proposal(db, conversation, project, owner, draft(), saved_rooms)
        db.commit()
        proposal_id = record.id
        conversation_id = conversation.id
    return client, headers, project_id, proposal_id, conversation_id


def get_rooms(client, project_id):
    response = client.get(f"/api/v1/projects/{project_id}/layout/0")
    return [] if response.status_code == 404 else response.json()["rooms"]


def test_apply_persists_edited_rooms_and_marks_proposal_applied():
    client, headers, project_id, proposal_id, _ = setup_proposal()
    edited = draft(name="Great Living")
    response = client.post(f"/api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/apply", headers=headers, json={"proposal": edited})
    assert response.status_code == 200
    assert response.json()["status"] == "applied"
    assert response.json()["applied_at"] is not None
    rooms = get_rooms(client, project_id)
    assert [room["name"] for room in rooms] == ["Great Living"]
    again = client.post(f"/api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/apply", headers=headers, json={"proposal": edited})
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "proposal_not_pending"


def test_apply_requires_csrf_and_owner_scope():
    client, headers, project_id, proposal_id, _ = setup_proposal("owner-actions@example.com")
    assert client.post(f"/api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/apply", json={"proposal": draft()}).status_code == 403
    other = TestClient(create_app(database_url="sqlite://", create_tables=True))
    other.post("/api/v1/auth/register", json={"email": "other-actions@example.com", "password": "StrongPass123!"})
    login = other.post("/api/v1/auth/login", json={"email": "other-actions@example.com", "password": "StrongPass123!"})
    other_headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    assert other.post(f"/api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/apply", headers=other_headers, json={"proposal": draft()}).status_code == 404


def test_invalid_edited_proposal_does_not_change_saved_rooms_or_status():
    client, headers, project_id, proposal_id, _ = setup_proposal("invalid-actions@example.com")
    before = get_rooms(client, project_id)
    invalid = draft(x=9000.0)
    response = client.post(f"/api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/apply", headers=headers, json={"proposal": invalid})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "proposal_invalid"
    assert get_rooms(client, project_id) == before
    record = client.get(f"/api/v1/projects/{project_id}/assistant/proposals/{proposal_id}")
    assert record.json()["status"] == "draft"


def test_stale_proposal_is_marked_needs_revision_and_never_overwrites_newer_layout():
    client, headers, project_id, proposal_id, _ = setup_proposal("stale-actions@example.com")
    replacement = {"floor_number": 0, "rooms": [{
        "name": "Newer room", "room_type": "bedroom",
        "vertices_mm": [{"x": 0, "y": 0}, {"x": 3500, "y": 0}, {"x": 3500, "y": 3500}, {"x": 0, "y": 3500}],
        "wall_thickness_mm": 150, "openings": [],
    }]}
    assert client.put(f"/api/v1/projects/{project_id}/layout", headers=headers, json=replacement).status_code == 200
    response = client.post(f"/api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/apply", headers=headers, json={"proposal": draft()})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "proposal_stale"
    assert [room["name"] for room in get_rooms(client, project_id)] == ["Newer room"]
    record = client.get(f"/api/v1/projects/{project_id}/assistant/proposals/{proposal_id}")
    assert record.json()["status"] == "needs_revision"


def test_reject_changes_only_proposal_status():
    client, headers, project_id, proposal_id, _ = setup_proposal("reject-actions@example.com")
    before = get_rooms(client, project_id)
    response = client.post(f"/api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/reject", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert get_rooms(client, project_id) == before
    repeated = client.post(f"/api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/reject", headers=headers)
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["code"] == "proposal_not_pending"


def test_apply_rolls_back_room_deletion_when_persistence_fails(monkeypatch):
    from app.services import layouts
    from app.services.assistant_proposals import apply_pending_proposal, ProposalActionError

    client, headers, project_id, proposal_id, _ = setup_proposal("rollback-actions@example.com")
    before = get_rooms(client, project_id)
    with client.app.state.session_factory() as db:
        owner = db.scalar(select(User).where(User.email == "rollback-actions@example.com"))
        project = db.get(Project, project_id)
        def fail_after_delete(session, project_id, payload):
            session.query(Room).filter(Room.project_id == project_id, Room.floor_number == payload.floor_number).delete()
            session.flush()
            raise RuntimeError("simulated write failure")
        monkeypatch.setattr(layouts, "persist_floor_rooms", fail_after_delete)
        try:
            apply_pending_proposal(db, project, owner, proposal_id, draft())
            assert False, "Expected simulated database failure"
        except RuntimeError as error:
            assert "simulated" in str(error)
    assert get_rooms(client, project_id) == before
    assert client.get(f"/api/v1/projects/{project_id}/assistant/proposals/{proposal_id}").json()["status"] == "draft"
