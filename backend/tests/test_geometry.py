from fastapi.testclient import TestClient

from app.main import create_app


def authenticated_client():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "geometry@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "geometry@example.com", "password": "StrongPass123!"})
    return client, {"X-CSRF-Token": login.json()["csrf_token"]}


def test_polygon_plot_persists_vertices_and_calculates_area_and_perimeter():
    client, headers = authenticated_client()
    created = client.post("/api/v1/projects", headers=headers, json={
        "name": "L-shaped site", "category": "residential",
        "plot": {
            "shape": "polygon", "unit": "ft",
            "vertices": [
                {"x": 0, "y": 0}, {"x": 20, "y": 0},
                {"x": 20, "y": 10}, {"x": 10, "y": 10},
                {"x": 10, "y": 20}, {"x": 0, "y": 20},
            ],
            "orientation": "east",
        },
    })

    assert created.status_code == 201
    plot = created.json()["plot"]
    assert plot["shape"] == "polygon"
    assert plot["area_sq_ft"] == 300
    assert plot["perimeter_mm"] == 24384
    assert plot["vertices_mm"] == [
        {"x": 0, "y": 0}, {"x": 6096, "y": 0},
        {"x": 6096, "y": 3048}, {"x": 3048, "y": 3048},
        {"x": 3048, "y": 6096}, {"x": 0, "y": 6096},
    ]
    fetched = client.get(f"/api/v1/projects/{created.json()['id']}")
    assert fetched.json()["plot"] == plot


def test_polygon_plot_rejects_self_intersection():
    client, headers = authenticated_client()
    response = client.post("/api/v1/projects", headers=headers, json={
        "name": "Invalid bow tie", "plot": {
            "shape": "polygon", "unit": "m",
            "vertices": [
                {"x": 0, "y": 0}, {"x": 4, "y": 4},
                {"x": 0, "y": 4}, {"x": 4, "y": 0},
            ],
        },
    })
    assert response.status_code == 422
    assert "self-intersect" in response.text.lower()


def test_polygon_plot_rejects_duplicate_vertices():
    client, headers = authenticated_client()
    response = client.post("/api/v1/projects", headers=headers, json={
        "name": "Duplicate corner", "plot": {
            "shape": "polygon", "unit": "m",
            "vertices": [
                {"x": 0, "y": 0}, {"x": 4, "y": 0},
                {"x": 4, "y": 0}, {"x": 0, "y": 4},
            ],
        },
    })
    assert response.status_code == 422
    assert "duplicate vertices" in response.text.lower()


def test_existing_plot_can_be_replaced_with_polygon_geometry():
    client, headers = authenticated_client()
    created = client.post("/api/v1/projects", headers=headers, json={"name": "Editable site"})
    project_id = created.json()["id"]
    updated = client.put(f"/api/v1/projects/{project_id}/plot", headers=headers, json={
        "shape": "polygon", "unit": "m",
        "vertices": [
            {"x": 0, "y": 0}, {"x": 12, "y": 0},
            {"x": 12, "y": 8}, {"x": 0, "y": 8},
        ],
    })
    assert updated.status_code == 200
    assert updated.json()["plot"]["area_sq_ft"] == 1033.335
    assert updated.json()["plot"]["shape"] == "polygon"


def test_polygon_containment_and_shared_wall_overlap_rules():
    from app.services.geometry import polygon_within_polygon, polygons_overlap

    plot = [(0, 0), (10000, 0), (10000, 10000), (0, 10000)]
    left_room = [(0, 0), (5000, 0), (5000, 10000), (0, 10000)]
    right_room = [(5000, 0), (10000, 0), (10000, 10000), (5000, 10000)]
    crossing_room = [(4000, 4000), (7000, 4000), (7000, 7000), (4000, 7000)]
    outside_room = [(9000, 9000), (11000, 9000), (11000, 11000), (9000, 11000)]

    assert polygon_within_polygon(left_room, plot)
    assert polygon_within_polygon(right_room, plot)
    assert not polygon_within_polygon(outside_room, plot)
    assert not polygons_overlap(left_room, right_room)
    assert polygons_overlap(left_room, crossing_room)


def test_identical_room_footprints_count_as_overlap():
    from app.services.geometry import polygons_overlap

    first = [(0, 0), (4000, 0), (4000, 3000), (0, 3000)]
    same_reversed = [(0, 3000), (4000, 3000), (4000, 0), (0, 0)]
    assert polygons_overlap(first, same_reversed)
