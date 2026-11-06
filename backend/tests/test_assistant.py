from fastapi.testclient import TestClient

from app.main import create_app


def _signed_in_client(email: str = "assistant@example.com"):
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123!"})
    return client, {"X-CSRF-Token": login.json()["csrf_token"]}


def test_assistant_extracts_design_brief_and_asks_for_missing_requirements():
    client, headers = _signed_in_client()
    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "East Home", "plot": {"shape": "rectangle", "width": 30, "length": 50, "unit": "ft", "orientation": "east"}
    })
    project_id = created.json()["id"]

    response = client.post(f"/api/v1/projects/{project_id}/assistant/message", headers=headers, json={
        "message": "Design a 3 bedroom, 2 bathroom home", "floor_number": 0,
    })

    assert response.status_code == 200
    result = response.json()
    assert result["intent"] == "design_brief"
    assert result["proposal"]["details"]["requested_counts"] == {"bedrooms": 3, "bathrooms": 2}
    assert result["proposal"]["details"]["plot"]["orientation"] == "east"
    assert any("floors" in question for question in result["clarifying_questions"])
    assert result["changes_applied"] is False


def test_assistant_reviews_saved_room_openings_without_mutating_layout():
    client, headers = _signed_in_client("review-assistant@example.com")
    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "Review Home", "plot": {"shape": "rectangle", "width": 10, "length": 10, "unit": "m"}
    })
    project_id = created.json()["id"]
    layout = {
        "floor_number": 0,
        "rooms": [{"name": "Living", "room_type": "living", "vertices_mm": [
            {"x": 0, "y": 0}, {"x": 4000, "y": 0}, {"x": 4000, "y": 4000}, {"x": 0, "y": 4000}
        ], "openings": []}],
    }
    assert client.put(f"/api/v1/projects/{project_id}/layout", headers=headers, json=layout).status_code == 200

    response = client.post(f"/api/v1/projects/{project_id}/assistant/message", headers=headers, json={
        "message": "Review my layout", "floor_number": 0,
    })
    assert response.status_code == 200
    result = response.json()
    assert result["intent"] == "review_layout"
    assert any("No window" in suggestion for suggestion in result["suggestions"])
    assert any("No door" in suggestion for suggestion in result["suggestions"])
    assert result["changes_applied"] is False
    assert client.get(f"/api/v1/projects/{project_id}/layout/0").json()["rooms"][0]["name"] == "Living"


def test_assistant_is_owner_scoped_and_requires_csrf():
    owner, owner_headers = _signed_in_client("assistant-owner@example.com")
    created = owner.post("/api/v1/projects", headers=owner_headers, json={"name": "Private"})
    project_id = created.json()["id"]
    assert owner.post(f"/api/v1/projects/{project_id}/assistant/message", json={"message": "help"}).status_code == 403

    other, other_headers = _signed_in_client("assistant-other@example.com")
    response = other.post(f"/api/v1/projects/{project_id}/assistant/message", headers=other_headers, json={"message": "help"})
    assert response.status_code == 404


def test_assistant_persists_multi_turn_conversation_and_rejects_floor_switch():
    client, headers = _signed_in_client("assistant-conversation-flow@example.com")
    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "Conversation Home", "plot": {"shape": "rectangle", "width": 30, "length": 50, "unit": "ft", "orientation": "east"}
    })
    project_id = created.json()["id"]
    first = client.post(f"/api/v1/projects/{project_id}/assistant/message", headers=headers, json={
        "message": "Design a 3 bedroom home", "floor_number": 0,
    })
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]
    assert first.json()["engine"] == "local_rules"
    second = client.post(f"/api/v1/projects/{project_id}/assistant/message", headers=headers, json={
        "message": "Two bathrooms", "floor_number": 0, "conversation_id": conversation_id,
    })
    assert second.status_code == 200
    transcript = client.get(f"/api/v1/projects/{project_id}/assistant/conversations/{conversation_id}")
    assert transcript.status_code == 200
    assert [message["role"] for message in transcript.json()["messages"]] == ["user", "assistant", "user", "assistant"]
    wrong_floor = client.post(f"/api/v1/projects/{project_id}/assistant/message", headers=headers, json={
        "message": "Continue upstairs", "floor_number": 1, "conversation_id": conversation_id,
    })
    assert wrong_floor.status_code == 409
    assert wrong_floor.json()["detail"]["code"] == "conversation_floor_mismatch"


def test_local_llm_layout_proposal_is_persisted_as_unapplied_draft():
    import json
    from app.services.local_llm import LocalModelReply, LocalModelStatus

    class FakeLLM:
        def status(self):
            return LocalModelStatus(True, True, True, True, "ready", "ready")
        def chat(self, messages, schema):
            return LocalModelReply(json.dumps({
                "type": "layout_proposal", "reply": "Here is an editable draft.", "proposal": {
                    "schema_version": "1.0", "title": "Ground floor draft", "assumptions": [], "warnings": [],
                    "floor_number": 0, "rooms": [{
                        "proposal_id": "living-a", "name": "Living", "room_type": "living",
                        "vertices_mm": [{"x": 0.0, "y": 0.0}, {"x": 4000.0, "y": 0.0}, {"x": 4000.0, "y": 4000.0}, {"x": 0.0, "y": 4000.0}],
                        "wall_thickness_mm": 150.0, "openings": [],
                    }],
                },
            }), "test-model")

    client, headers = _signed_in_client("assistant-proposal-api@example.com")
    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "Proposal Home", "plot": {"shape": "rectangle", "width": 10, "length": 10, "unit": "m"}
    })
    project_id = created.json()["id"]
    client.app.state.local_llm_client = FakeLLM()
    response = client.post(f"/api/v1/projects/{project_id}/assistant/message", headers=headers, json={
        "message": "Create a layout", "floor_number": 0,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "local_llm"
    assert body["response_type"] == "layout_proposal"
    assert body["proposal_id"]
    assert body["proposal_metadata"]["status"] == "draft"
    assert body["changes_applied"] is False
    assert client.get(f"/api/v1/projects/{project_id}/layout/0").status_code == 404
    transcript = client.get(f"/api/v1/projects/{project_id}/assistant/conversations/{body['conversation_id']}")
    assert transcript.status_code == 200
    assert transcript.json()["messages"][-1]["proposal_id"] == body["proposal_id"]


def test_assistant_message_cannot_override_server_side_model_endpoint():
    client, headers = _signed_in_client("assistant-no-endpoint-override@example.com")
    created = client.post("/api/v1/projects", headers=headers, json={"name": "No Endpoint Override"})
    project_id = created.json()["id"]
    response = client.post(f"/api/v1/projects/{project_id}/assistant/message", headers=headers, json={
        "message": "help", "floor_number": 0, "local_llm_base_url": "http://attacker.invalid:9999",
        "local_llm_model": "attacker-model",
    })
    assert response.status_code == 200
    assert response.json()["engine"] == "local_rules"
    assert client.app.state.settings.local_llm_base_url == "http://127.0.0.1:11434"
