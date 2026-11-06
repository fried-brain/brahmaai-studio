import json

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.local_llm import LocalModelReply, LocalModelStatus


def _proposal(name="AI Living"):
    return {
        "type": "layout_proposal",
        "reply": "Here is a draft living-room layout for review.",
        "proposal": {
            "schema_version": "1.0",
            "title": "Ground floor concept",
            "assumptions": ["Dimensions are in millimetres"],
            "warnings": ["Conceptual layout only"],
            "floor_number": 0,
            "rooms": [{
                "proposal_id": "room-living-1",
                "name": name,
                "room_type": "living",
                "vertices_mm": [
                    {"x": 0.0, "y": 0.0}, {"x": 4000.0, "y": 0.0},
                    {"x": 4000.0, "y": 4000.0}, {"x": 0.0, "y": 4000.0},
                ],
                "wall_thickness_mm": 150.0,
                "openings": [],
            }],
        },
    }


class _ReadyLocalModel:
    def status(self):
        return LocalModelStatus(True, True, True, True, "ready", "Ready")

    def chat(self, messages, response_schema):
        return LocalModelReply(json.dumps(_proposal()), "test-local-model")


def test_full_local_ai_proposal_preview_transcript_and_explicit_apply(monkeypatch):
    settings = Settings(local_llm_enabled=True, local_llm_model="test-local-model")
    app = create_app(database_url="sqlite://", create_tables=True, settings=settings)
    with TestClient(app) as client:
        monkeypatch.setattr(app.state, "local_llm_client", _ReadyLocalModel())
        client.post("/api/v1/auth/register", json={"email": "workflow@example.com", "password": "StrongPass123!"})
        login = client.post("/api/v1/auth/login", json={"email": "workflow@example.com", "password": "StrongPass123!"})
        headers = {"X-CSRF-Token": login.json()["csrf_token"]}
        project = client.post("/api/v1/projects", headers=headers, json={
            "name": "AI Workflow Home",
            "plot": {"shape": "rectangle", "width": 10, "length": 10, "unit": "m"},
        }).json()
        project_id = project["id"]

        chat = client.post(f"/api/v1/projects/{project_id}/assistant/message", headers=headers, json={
            "message": "Create a living room layout", "floor_number": 0,
        })
        assert chat.status_code == 200
        result = chat.json()
        assert result["engine"] == "local_llm"
        assert result["response_type"] == "layout_proposal"
        assert result["proposal_metadata"]["status"] == "draft"
        conversation_id = result["conversation_id"]
        proposal_id = result["proposal_id"]

        # Proposal generation is preview-only; the saved floor remains empty.
        assert client.get(f"/api/v1/projects/{project_id}/layout/0").status_code == 404

        transcript = client.get(f"/api/v1/projects/{project_id}/assistant/conversations/{conversation_id}")
        assert transcript.status_code == 200
        assert [message["role"] for message in transcript.json()["messages"]] == ["user", "assistant"]
        assert transcript.json()["messages"][-1]["proposal_id"] == proposal_id

        # Editing the proposal is client-side until this explicit Apply action.
        edited = _proposal("Approved Living")["proposal"]
        apply = client.post(
            f"/api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/apply",
            headers=headers,
            json={"proposal": edited},
        )
        assert apply.status_code == 200
        assert apply.json()["status"] == "applied"
        saved = client.get(f"/api/v1/projects/{project_id}/layout/0")
        assert saved.status_code == 200
        assert [room["name"] for room in saved.json()["rooms"]] == ["Approved Living"]
