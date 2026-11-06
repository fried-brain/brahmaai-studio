import json

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.local_llm import LocalModelReply, LocalModelStatus


class PlanningModel:
    def __init__(self, payload=None):
        self.payload = payload or {
            "type": "planning_brief", "reply": "I have prepared three room options.",
            "brief": {
                "floor_number": 0,
                "required_rooms": [
                    {"room_type": "living", "quantity": 1},
                    {"room_type": "kitchen", "quantity": 1},
                    {"room_type": "bedroom", "quantity": 2},
                    {"room_type": "bathroom", "quantity": 1},
                ],
                "adjacency_preferences": [], "privacy_preferences": [],
                "circulation_preferences": [], "vastu_mode": "off",
            },
        }
        self.calls = 0

    def status(self):
        return LocalModelStatus(True, True, True, True, "ready", "Ready")

    def chat(self, messages, response_schema):
        self.calls += 1
        return LocalModelReply(json.dumps(self.payload), "test-local-planner")


def setup_client(monkeypatch, email="planner@example.com", with_plot=True, model=None):
    settings = Settings(local_llm_enabled=True, local_llm_model="test-local-planner")
    app = create_app(database_url="sqlite://", create_tables=True, settings=settings)
    client = TestClient(app)
    monkeypatch.setattr(app.state, "local_llm_client", model or PlanningModel())
    client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    payload = {"name": "Generation Home"}
    if with_plot:
        payload["plot"] = {"shape": "rectangle", "width": 10, "length": 10, "unit": "m"}
    project = client.post("/api/v1/projects", headers=headers, json=payload).json()
    return client, headers, project["id"]


def test_generation_persists_independent_candidates_without_mutating_saved_floor(monkeypatch):
    model = PlanningModel()
    client, headers, project_id = setup_client(monkeypatch, model=model)
    response = client.post(f"/api/v1/projects/{project_id}/assistant/layout-generation", headers=headers, json={
        "message": "Create a three-bedroom home", "floor_number": 0,
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["outcome"] == "layout_candidates"
    assert 1 <= len(result["candidates"]) <= 3
    assert len({item["proposal_id"] for item in result["candidates"]}) == len(result["candidates"])
    assert result["planner_version"] == "2.0"
    assert result["search_status"] in {"complete", "budget_exhausted"}
    for candidate in result["candidates"]:
        assert candidate["score_version"] == "2.0"
        assert candidate["search_status"] in {"complete", "budget_exhausted"}
        assert candidate["utilization"]["plot_area_mm2"] == 100_000_000
        assert isinstance(candidate["circulation_components"], list)
    assert client.get(f"/api/v1/projects/{project_id}/layout/0").status_code == 404
    conversation_id = result["conversation_id"]
    restored = client.get(f"/api/v1/projects/{project_id}/assistant/conversations/{conversation_id}/proposals")
    assert restored.status_code == 200
    assert {item["proposal_id"] for item in restored.json()} == {item["proposal_id"] for item in result["candidates"]}
    assert restored.json()[0]["score_version"] == "2.0"
    assert restored.json()[0]["utilization"]["plot_area_mm2"] == 100_000_000
    assert model.calls == 1


def test_missing_plot_returns_explicit_outcome_without_calling_model(monkeypatch):
    model = PlanningModel()
    client, headers, project_id = setup_client(monkeypatch, email="missingplot@example.com", with_plot=False, model=model)
    response = client.post(f"/api/v1/projects/{project_id}/assistant/layout-generation", headers=headers, json={
        "message": "Design the house", "floor_number": 0,
    })
    assert response.status_code == 200
    assert response.json()["outcome"] == "missing_plot"
    assert response.json()["candidates"] == []
    assert model.calls == 0


def test_candidate_listing_is_project_and_conversation_owner_scoped(monkeypatch):
    owner, headers, project_id = setup_client(monkeypatch, email="ownerplanner@example.com")
    generated = owner.post(f"/api/v1/projects/{project_id}/assistant/layout-generation", headers=headers, json={
        "message": "Create a home", "floor_number": 0,
    }).json()
    conversation_id = generated["conversation_id"]
    other, other_headers, other_project = setup_client(monkeypatch, email="otherplanner@example.com")
    assert other.get(f"/api/v1/projects/{project_id}/assistant/conversations/{conversation_id}/proposals").status_code == 404
    assert other.get(f"/api/v1/projects/{other_project}/assistant/conversations/{conversation_id}/proposals").status_code == 404


def test_clarification_persists_turn_without_creating_candidates(monkeypatch):
    model = PlanningModel({
        "type": "clarification", "reply": "I need one more detail.",
        "questions": ["How many bathrooms are required?"], "suggestions": [],
    })
    client, headers, project_id = setup_client(monkeypatch, email="clarifyplanner@example.com", model=model)
    response = client.post(f"/api/v1/projects/{project_id}/assistant/layout-generation", headers=headers, json={
        "message": "Plan a house", "floor_number": 0,
    })
    assert response.status_code == 200
    result = response.json()
    assert result["outcome"] == "clarification"
    assert result["questions"] == ["How many bathrooms are required?"]
    assert result["candidates"] == []
    transcript = client.get(f"/api/v1/projects/{project_id}/assistant/conversations/{result['conversation_id']}")
    assert [item["role"] for item in transcript.json()["messages"]] == ["user", "assistant"]
    assert client.get(f"/api/v1/projects/{project_id}/assistant/conversations/{result['conversation_id']}/proposals").json() == []


def test_irregular_plot_is_not_approximated_and_model_is_not_called(monkeypatch):
    model = PlanningModel()
    client, headers, project_id = setup_client(monkeypatch, email="irregularplanner@example.com", model=model)
    changed = client.put(f"/api/v1/projects/{project_id}/plot", headers=headers, json={
        "shape": "polygon", "unit": "m", "vertices": [
            {"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 8, "y": 10}, {"x": 0, "y": 10},
        ],
    })
    assert changed.status_code == 200
    response = client.post(f"/api/v1/projects/{project_id}/assistant/layout-generation", headers=headers, json={
        "message": "Generate a plan", "floor_number": 0,
    })
    assert response.status_code == 200
    assert response.json()["outcome"] == "unsupported_plot_geometry"
    assert response.json()["candidates"] == []
    assert model.calls == 0


def test_stale_candidate_cannot_overwrite_a_newer_saved_floor(monkeypatch):
    client, headers, project_id = setup_client(monkeypatch, email="staleplanner@example.com")
    generated = client.post(f"/api/v1/projects/{project_id}/assistant/layout-generation", headers=headers, json={
        "message": "Create a home", "floor_number": 0,
    }).json()
    candidate = generated["candidates"][0]
    changed_plot = client.put(f"/api/v1/projects/{project_id}/plot", headers=headers, json={
        "shape": "rectangle", "width": 11, "length": 10, "unit": "m",
    })
    assert changed_plot.status_code == 200
    apply = client.post(
        f"/api/v1/projects/{project_id}/assistant/proposals/{candidate['proposal_id']}/apply",
        headers=headers, json={"proposal": candidate["proposal"]},
    )
    assert apply.status_code == 409
    assert apply.json()["detail"]["code"] == "proposal_stale"
    assert client.get(f"/api/v1/projects/{project_id}/layout/0").status_code == 404


def test_rejecting_one_candidate_changes_only_that_candidate_status(monkeypatch):
    client, headers, project_id = setup_client(monkeypatch, email="rejectplanner@example.com")
    generated = client.post(f"/api/v1/projects/{project_id}/assistant/layout-generation", headers=headers, json={
        "message": "Create a home", "floor_number": 0,
    }).json()
    candidates = generated["candidates"]
    assert len(candidates) >= 2
    rejected_id = candidates[0]["proposal_id"]
    response = client.post(f"/api/v1/projects/{project_id}/assistant/proposals/{rejected_id}/reject", headers=headers)
    assert response.status_code == 200
    restored = client.get(f"/api/v1/projects/{project_id}/assistant/conversations/{generated['conversation_id']}/proposals").json()
    statuses = {item["proposal_id"]: item["status"] for item in restored}
    assert statuses[rejected_id] == "rejected"
    assert all(status == "draft" for proposal_id, status in statuses.items() if proposal_id != rejected_id)
    assert client.get(f"/api/v1/projects/{project_id}/layout/0").status_code == 404


def test_applying_selected_candidate_preserves_candidate_metadata_for_reload(monkeypatch):
    client, headers, project_id = setup_client(monkeypatch, email="applyplanner@example.com")
    generated = client.post(f"/api/v1/projects/{project_id}/assistant/layout-generation", headers=headers, json={
        "message": "Create a home", "floor_number": 0,
    }).json()
    candidate = generated["candidates"][0]
    applied = client.post(
        f"/api/v1/projects/{project_id}/assistant/proposals/{candidate['proposal_id']}/apply",
        headers=headers, json={"proposal": candidate["proposal"]},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "applied"
    saved = client.get(f"/api/v1/projects/{project_id}/layout/0")
    assert saved.status_code == 200
    restored = client.get(f"/api/v1/projects/{project_id}/assistant/conversations/{generated['conversation_id']}/proposals")
    assert restored.status_code == 200
    selected = next(item for item in restored.json() if item["proposal_id"] == candidate["proposal_id"])
    assert selected["status"] == "applied"
    assert selected["candidate_key"] == candidate["candidate_key"]
    assert selected["score"] == candidate["score"]


def test_search_exhausted_is_returned_as_distinct_generation_outcome(monkeypatch):
    from app.schemas.room_layout_candidates import PlannerResult
    client, headers, project_id = setup_client(monkeypatch, email="budgetplanner@example.com")
    monkeypatch.setattr("app.api.projects.generate_layout_candidates", lambda plot, brief: PlannerResult(
        status="search_exhausted", search_status="budget_exhausted",
        reasons=["Search node budget reached."],
    ))
    response = client.post(f"/api/v1/projects/{project_id}/assistant/layout-generation", headers=headers, json={
        "message": "Create a home", "floor_number": 0,
    })
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "search_exhausted"
    assert response.json()["search_status"] == "budget_exhausted"
    assert response.json()["candidates"] == []
