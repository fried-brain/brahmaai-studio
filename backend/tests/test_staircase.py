from fastapi.testclient import TestClient

from app.main import create_app


def _client():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "stairs@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "stairs@example.com", "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Stair test"}).json()
    return client, headers, project["id"]


def test_staircase_preview_calculates_balanced_risers_and_run():
    client, headers, project_id = _client()
    response = client.post(f"/api/v1/projects/{project_id}/staircase/preview", headers=headers, json={
        "floor_to_floor_mm": 3000,
        "preferred_riser_mm": 175,
        "tread_depth_mm": 280,
        "clear_width_mm": 1000,
        "landing_depth_mm": 1000,
        "configuration": "straight",
    })
    assert response.status_code == 200
    result = response.json()
    assert result["riser_count"] == 17
    assert result["actual_riser_mm"] == 176.471
    assert result["total_rise_mm"] == 3000
    assert result["going_count"] == 16
    assert result["flight_run_mm"] == 4480
    assert result["comfort_indicator"] == "within_reference_band"
    assert result["is_code_certified"] is False


def test_staircase_preview_rejects_impossible_dimensions_and_unknown_projects():
    client, headers, project_id = _client()
    invalid = client.post(f"/api/v1/projects/{project_id}/staircase/preview", headers=headers, json={
        "floor_to_floor_mm": 3000, "preferred_riser_mm": 0, "tread_depth_mm": 280,
        "clear_width_mm": 1000, "landing_depth_mm": 1000, "configuration": "straight",
    })
    assert invalid.status_code == 422
    missing = client.post("/api/v1/projects/not-owned/staircase/preview", headers=headers, json={
        "floor_to_floor_mm": 3000, "preferred_riser_mm": 175, "tread_depth_mm": 280,
        "clear_width_mm": 1000, "landing_depth_mm": 1000, "configuration": "straight",
    })
    assert missing.status_code == 404


def test_u_staircase_preview_reports_split_and_flags_unbalanced_proportions():
    client, headers, project_id = _client()
    response = client.post(f"/api/v1/projects/{project_id}/staircase/preview", headers=headers, json={
        "floor_to_floor_mm": 3000, "preferred_riser_mm": 120, "tread_depth_mm": 180,
        "clear_width_mm": 1000, "landing_depth_mm": 1000, "configuration": "U",
    })
    assert response.status_code == 200
    result = response.json()
    assert result["flight_count"] == 2
    assert result["risers_per_flight"] == [13, 12]
    assert result["comfort_indicator"] == "outside_reference_band"
    assert any("2R+T" in note for note in result["notes"])
