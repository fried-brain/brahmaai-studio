from fastapi.testclient import TestClient

from app.main import create_app


def test_user_can_create_and_retrieve_project_with_plot():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={
        "email": "architect@example.com",
        "password": "StrongPass123!",
        "display_name": "Architect",
    })
    login = client.post("/api/v1/auth/login", json={
        "email": "architect@example.com",
        "password": "StrongPass123!",
    })
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}

    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "East-facing family home",
        "category": "residential",
        "plot": {"shape": "rectangle", "width": 50, "length": 30, "unit": "ft", "orientation": "east"},
    })

    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "East-facing family home"
    assert project["plot"]["width_mm"] == 15240
    assert project["plot"]["length_mm"] == 9144
    assert project["plot"]["area_sq_ft"] == 1500
    fetched = client.get(f"/api/v1/projects/{project['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == project["id"]


def test_user_cannot_read_another_users_project():
    app = create_app(database_url="sqlite://", create_tables=True)
    owner = TestClient(app)
    owner.post("/api/v1/auth/register", json={"email": "owner@example.com", "password": "StrongPass123!"})
    owner_login = owner.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "StrongPass123!"})
    owner_project = owner.post("/api/v1/projects", headers={"X-CSRF-Token": owner_login.json()["csrf_token"]}, json={"name": "Private project", "category": "residential"})
    assert owner_project.status_code == 201

    intruder = TestClient(app)
    intruder.post("/api/v1/auth/register", json={"email": "intruder@example.com", "password": "StrongPass123!"})
    intruder.post("/api/v1/auth/login", json={"email": "intruder@example.com", "password": "StrongPass123!"})
    response = intruder.get(f"/api/v1/projects/{owner_project.json()['id']}")
    assert response.status_code == 404


def test_project_list_update_archive_and_plot_update():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "lister@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "lister@example.com", "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    created = client.post("/api/v1/projects", headers=headers, json={"name": "Starter", "category": "residential"})
    project_id = created.json()["id"]

    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [project_id]

    updated_plot = client.put(f"/api/v1/projects/{project_id}/plot", headers=headers, json={
        "shape": "rectangle", "width": 30, "length": 50, "unit": "ft", "orientation": "east"
    })
    assert updated_plot.status_code == 200
    assert updated_plot.json()["plot"]["area_sq_ft"] == 1500

    updated = client.patch(f"/api/v1/projects/{project_id}", headers=headers, json={"name": "Renamed", "category": "commercial"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["category"] == "commercial"

    archived = client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert archived.status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
    assert client.get("/api/v1/projects").json() == []


def test_project_creation_requires_authentication_and_rejects_invalid_plot():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    assert client.post("/api/v1/projects", json={"name": "No session"}).status_code == 401
    client.post("/api/v1/auth/register", json={"email": "invalid@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "invalid@example.com", "password": "StrongPass123!"})
    response = client.post("/api/v1/projects", headers={"X-CSRF-Token": login.json()["csrf_token"]}, json={
        "name": "Invalid dimensions", "plot": {"width": 0, "length": 50, "unit": "ft"}
    })
    assert response.status_code == 422


def test_project_layout_creates_rooms_and_derived_wall_segments():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "layout@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "layout@example.com", "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "Two room home",
        "plot": {"shape": "rectangle", "width": 30, "length": 40, "unit": "ft"},
    })
    project_id = created.json()["id"]

    response = client.put(f"/api/v1/projects/{project_id}/layout", headers=headers, json={
        "floor_number": 0,
        "rooms": [
            {"name": "Living", "room_type": "living", "vertices_mm": [
                {"x": 0, "y": 0}, {"x": 3000, "y": 0}, {"x": 3000, "y": 4000}, {"x": 0, "y": 4000}
            ]},
            {"name": "Bedroom", "room_type": "bedroom", "vertices_mm": [
                {"x": 3000, "y": 0}, {"x": 6000, "y": 0}, {"x": 6000, "y": 4000}, {"x": 3000, "y": 4000}
            ]},
        ],
    })

    assert response.status_code == 200
    layout = response.json()
    assert layout["floor_number"] == 0
    assert len(layout["rooms"]) == 2
    assert layout["rooms"][0]["area_sq_ft"] == 129.167
    assert len(layout["walls"]) == 7
    shared_walls = [wall for wall in layout["walls"] if len(wall["room_ids"]) == 2]
    assert len(shared_walls) == 1
    fetched = client.get(f"/api/v1/projects/{project_id}/layout/0")
    assert fetched.status_code == 200
    assert fetched.json() == layout
    assert all(wall["length_mm"] == 3000 or wall["length_mm"] == 4000 for wall in layout["walls"])


def test_project_layout_rejects_rooms_outside_plot():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "outside@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "outside@example.com", "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "Bounded home", "plot": {"shape": "rectangle", "width": 10, "length": 10, "unit": "m"}
    })
    response = client.put(f"/api/v1/projects/{created.json()['id']}/layout", headers=headers, json={
        "floor_number": 0,
        "rooms": [{"name": "Oversized", "room_type": "other", "vertices_mm": [
            {"x": 0, "y": 0}, {"x": 12000, "y": 0}, {"x": 12000, "y": 5000}, {"x": 0, "y": 5000}
        ]}],
    })
    assert response.status_code == 422
    assert "inside the plot" in response.text.lower()


def test_project_layout_rejects_overlapping_rooms():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "overlap@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "overlap@example.com", "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "Overlapping rooms", "plot": {"shape": "rectangle", "width": 20, "length": 20, "unit": "ft"}
    })
    response = client.put(f"/api/v1/projects/{created.json()['id']}/layout", headers=headers, json={
        "floor_number": 0,
        "rooms": [
            {"name": "A", "room_type": "living", "vertices_mm": [
                {"x": 0, "y": 0}, {"x": 4000, "y": 0}, {"x": 4000, "y": 4000}, {"x": 0, "y": 4000}
            ]},
            {"name": "B", "room_type": "bedroom", "vertices_mm": [
                {"x": 3000, "y": 3000}, {"x": 6000, "y": 3000}, {"x": 6000, "y": 6000}, {"x": 3000, "y": 6000}
            ]},
        ],
    })
    assert response.status_code == 422
    assert "overlap" in response.text.lower()


def test_user_can_clear_a_floor_layout_after_deleting_its_last_room():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "clear-layout@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "clear-layout@example.com", "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "Clearable", "plot": {"shape": "rectangle", "width": 10, "length": 10, "unit": "m"}
    })
    project_id = created.json()["id"]
    saved = client.put(f"/api/v1/projects/{project_id}/layout", headers=headers, json={
        "floor_number": 0,
        "rooms": [{"name": "Living", "room_type": "living", "vertices_mm": [
            {"x": 0, "y": 0}, {"x": 3000, "y": 0}, {"x": 3000, "y": 3000}, {"x": 0, "y": 3000}
        ]}],
    })
    assert saved.status_code == 200

    cleared = client.delete(f"/api/v1/projects/{project_id}/layout/0", headers=headers)
    assert cleared.status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}/layout/0").status_code == 404


def test_layout_persists_wall_thickness_and_validated_door_window_openings():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "openings@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "openings@example.com", "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "Openings home", "plot": {"shape": "rectangle", "width": 10, "length": 10, "unit": "m"}
    })
    project_id = created.json()["id"]
    payload = {
        "floor_number": 0,
        "rooms": [{
            "name": "Living", "room_type": "living", "wall_thickness_mm": 200,
            "vertices_mm": [{"x": 0, "y": 0}, {"x": 4000, "y": 0}, {"x": 4000, "y": 4000}, {"x": 0, "y": 4000}],
            "openings": [
                {"kind": "door", "edge_index": 0, "offset_mm": 500, "width_mm": 900, "height_mm": 2100, "sill_height_mm": 0},
                {"kind": "window", "edge_index": 1, "offset_mm": 800, "width_mm": 1200, "height_mm": 1200, "sill_height_mm": 900},
            ],
        }],
    }
    saved = client.put(f"/api/v1/projects/{project_id}/layout", headers=headers, json=payload)
    assert saved.status_code == 200
    room = saved.json()["rooms"][0]
    assert room["wall_thickness_mm"] == 200
    assert [opening["kind"] for opening in room["openings"]] == ["door", "window"]
    assert room["openings"][0]["edge_index"] == 0
    assert client.get(f"/api/v1/projects/{project_id}/layout/0").json()["rooms"][0]["openings"] == room["openings"]


def test_layout_rejects_opening_that_exceeds_its_wall_segment():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "bad-opening@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "bad-opening@example.com", "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "Bad opening", "plot": {"shape": "rectangle", "width": 10, "length": 10, "unit": "m"}
    })
    payload = {
        "floor_number": 0,
        "rooms": [{
            "name": "Living", "room_type": "living",
            "vertices_mm": [{"x": 0, "y": 0}, {"x": 4000, "y": 0}, {"x": 4000, "y": 4000}, {"x": 0, "y": 4000}],
            "openings": [{"kind": "door", "edge_index": 0, "offset_mm": 3500, "width_mm": 900, "height_mm": 2100, "sill_height_mm": 0}],
        }],
    }
    response = client.put(f"/api/v1/projects/{created.json()['id']}/layout", headers=headers, json=payload)
    assert response.status_code == 422
    assert "opening must fit within its wall" in response.text.lower()



def test_layout_rejects_overlapping_openings_on_the_same_wall():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "overlap-openings@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "overlap-openings@example.com", "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "Opening collision", "plot": {"shape": "rectangle", "width": 10, "length": 10, "unit": "m"}
    })
    payload = {"floor_number": 0, "rooms": [{
        "name": "Living", "vertices_mm": [{"x": 0, "y": 0}, {"x": 4000, "y": 0}, {"x": 4000, "y": 4000}, {"x": 0, "y": 4000}],
        "openings": [
            {"kind": "door", "edge_index": 0, "offset_mm": 500, "width_mm": 1000, "height_mm": 2100},
            {"kind": "window", "edge_index": 0, "offset_mm": 1200, "width_mm": 1000, "height_mm": 1200, "sill_height_mm": 900},
        ],
    }]}
    response = client.put(f"/api/v1/projects/{created.json()['id']}/layout", headers=headers, json=payload)
    assert response.status_code == 422
    assert "cannot overlap" in response.text.lower()


def test_layout_classifies_external_walls_and_reports_door_connected_adjacency():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "adjacency@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "adjacency@example.com", "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    project_id = client.post("/api/v1/projects", headers=headers, json={
        "name": "Adjacency home", "plot": {"shape": "rectangle", "width": 6, "length": 4, "unit": "m"}
    }).json()["id"]
    response = client.put(f"/api/v1/projects/{project_id}/layout", headers=headers, json={
        "floor_number": 0,
        "rooms": [
            {"name": "Living", "vertices_mm": [{"x": 0, "y": 0}, {"x": 3000, "y": 0}, {"x": 3000, "y": 4000}, {"x": 0, "y": 4000}],
             "openings": [{"kind": "door", "edge_index": 1, "offset_mm": 1000, "width_mm": 900, "height_mm": 2100, "swing_direction": "left"}]},
            {"name": "Bedroom", "vertices_mm": [{"x": 3000, "y": 0}, {"x": 6000, "y": 0}, {"x": 6000, "y": 4000}, {"x": 3000, "y": 4000}]},
        ],
    })
    assert response.status_code == 200
    layout = response.json()
    shared = next(wall for wall in layout["walls"] if len(wall["room_ids"]) == 2)
    assert shared["classification"] == "internal"
    external = [wall for wall in layout["walls"] if len(wall["room_ids"]) == 1]
    assert all(wall["classification"] == "external" for wall in external)
    assert len(layout["adjacencies"]) == 1
    assert layout["adjacencies"][0]["connected_by_door"] is True
    assert any(component["room_count"] == 2 for component in layout["circulation_components"])
    living = next(room for room in layout["rooms"] if room["name"] == "Living")
    assert living["openings"][0]["swing_direction"] == "left"


def test_layout_rejects_swinging_windows_and_reports_window_head_height():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "windowheight@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "windowheight@example.com", "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    project_id = client.post("/api/v1/projects", headers=headers, json={
        "name": "Window heights", "plot": {"shape": "rectangle", "width": 6, "length": 4, "unit": "m"}
    }).json()["id"]
    payload = {"floor_number": 0, "rooms": [{"name": "Living", "vertices_mm": [
        {"x": 0, "y": 0}, {"x": 3000, "y": 0}, {"x": 3000, "y": 4000}, {"x": 0, "y": 4000}],
        "openings": [{"kind": "window", "edge_index": 0, "offset_mm": 500, "width_mm": 1200,
                      "height_mm": 1200, "sill_height_mm": 900}]}]}
    saved = client.put(f"/api/v1/projects/{project_id}/layout", headers=headers, json=payload)
    assert saved.status_code == 200
    assert saved.json()["rooms"][0]["openings"][0]["head_height_mm"] == 2100
    payload["rooms"][0]["openings"][0]["swing_direction"] = "left"
    invalid = client.put(f"/api/v1/projects/{project_id}/layout", headers=headers, json=payload)
    assert invalid.status_code == 422


def test_design_analysis_reports_window_area_indicators_and_optional_vastu_notes():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "analysis@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "analysis@example.com", "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    project_id = client.post("/api/v1/projects", headers=headers, json={
        "name": "Analysis home", "plot": {"shape": "rectangle", "width": 6, "length": 4, "unit": "m", "orientation": "east"}
    }).json()["id"]
    saved = client.put(f"/api/v1/projects/{project_id}/layout", headers=headers, json={
        "floor_number": 0,
        "rooms": [{"name": "Living", "room_type": "living", "vertices_mm": [
            {"x": 0, "y": 0}, {"x": 3000, "y": 0}, {"x": 3000, "y": 4000}, {"x": 0, "y": 4000}],
            "openings": [{"kind": "window", "edge_index": 0, "offset_mm": 500, "width_mm": 1500,
                          "height_mm": 1200, "sill_height_mm": 900}]}],
    })
    assert saved.status_code == 200
    analysis = client.get(f"/api/v1/projects/{project_id}/design-analysis/0?include_vastu=true")
    assert analysis.status_code == 200
    result = analysis.json()
    living = result["rooms"][0]
    assert living["floor_area_sq_m"] == 12
    assert living["window_opening_area_sq_m"] == 1.8
    assert living["window_to_floor_ratio_percent"] == 15
    assert living["daylight_planning_indicator"] == "higher_allowance"
    assert living["ventilation_planning_indicator"] == "higher_allowance"
    assert result["vastu_mode"] == "traditional_reference_only"
    assert result["vastu_notes"]
    assert result["is_code_certified"] is False
