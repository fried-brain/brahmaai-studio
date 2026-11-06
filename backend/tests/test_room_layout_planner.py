from types import SimpleNamespace

from app.schemas.room_planning import RoomPlanningBrief
from app.services.room_layout_planner import generate_layout_candidates


def plot(width=10000, length=10000, x=0, y=0):
    return SimpleNamespace(
        shape="rectangle", width_mm=width, length_mm=length, geometry_json=None,
    )


def brief(**overrides):
    value = {
        "floor_number": 0,
        "required_rooms": [
            {"room_type": "living", "quantity": 1},
            {"room_type": "kitchen", "quantity": 1},
            {"room_type": "bedroom", "quantity": 2},
            {"room_type": "bathroom", "quantity": 1},
        ],
        "adjacency_preferences": [],
        "privacy_preferences": [],
        "circulation_preferences": [],
        "vastu_mode": "off",
    }
    value.update(overrides)
    return RoomPlanningBrief.model_validate(value)


def test_rectangular_plot_produces_valid_deterministic_distinct_candidates():
    first = generate_layout_candidates(plot(), brief())
    second = generate_layout_candidates(plot(), brief())
    assert first.status == "layout_candidates"
    assert 1 <= len(first.candidates) <= 3
    assert [item.candidate_key for item in first.candidates] == [item.candidate_key for item in second.candidates]
    assert len({item.candidate_key for item in first.candidates}) == len(first.candidates)
    for candidate in first.candidates:
        assert candidate.score.total >= 0 and candidate.score.total <= 100
        assert candidate.score.total == sum(candidate.score.breakdown.values())
        assert candidate.planner_version == "2.0"
        assert candidate.score_version == "2.0"
        assert len(candidate.rooms) == 5


def test_hard_exact_dimensions_are_preserved_or_reported_infeasible():
    result = generate_layout_candidates(plot(5000, 5000), brief(required_rooms=[
        {"room_type": "living", "quantity": 1, "preferred_width_mm": 6000, "preferred_depth_mm": 6000, "dimension_mode": "exact"},
    ]))
    assert result.status == "infeasible"
    assert result.candidates == []
    assert any("living" in reason.lower() or "fit" in reason.lower() for reason in result.reasons)


def test_must_be_adjacent_is_a_hard_gate_and_preferred_adjacency_is_scored():
    result = generate_layout_candidates(plot(), brief(
        required_rooms=[
            {"room_type": "kitchen", "quantity": 1},
            {"room_type": "dining", "quantity": 1},
            {"room_type": "bedroom", "quantity": 1},
        ],
        adjacency_preferences=[{"room_a": "kitchen", "room_b": "dining", "priority": "must_be_adjacent"}],
    ))
    assert result.status == "layout_candidates"
    assert all("kitchen" in " ".join(room["name"].lower() for room in candidate.rooms) for candidate in result.candidates)


def test_non_rectangular_plot_is_rejected_without_bounding_box_approximation():
    irregular = SimpleNamespace(
        shape="polygon", width_mm=None, length_mm=None,
        geometry_json='[{"x":0,"y":0},{"x":10000,"y":0},{"x":8000,"y":10000},{"x":0,"y":10000}]',
    )
    result = generate_layout_candidates(irregular, brief())
    assert result.status == "unsupported_plot_geometry"
    assert result.candidates == []


def test_parking_is_a_valid_room_type_in_layout_schema():
    from app.schemas.layouts import RoomInput
    room = RoomInput.model_validate({
        "name": "Parking", "room_type": "parking",
        "vertices_mm": [{"x": 0, "y": 0}, {"x": 3000, "y": 0}, {"x": 3000, "y": 5500}, {"x": 0, "y": 5500}],
    })
    assert room.room_type == "parking"


def test_mandatory_adjacency_creates_matching_door_openings_on_both_rooms():
    result = generate_layout_candidates(plot(), brief(
        required_rooms=[{"room_type": "kitchen", "quantity": 1}, {"room_type": "dining", "quantity": 1}, {"room_type": "bedroom", "quantity": 1}],
        adjacency_preferences=[{"room_a": "kitchen", "room_b": "dining", "priority": "must_be_adjacent"}],
    ))
    assert result.status == "layout_candidates"
    for candidate in result.candidates:
        kitchen = next(room for room in candidate.rooms if room["room_type"] == "kitchen")
        dining = next(room for room in candidate.rooms if room["room_type"] == "dining")
        kitchen_door = next(item for item in kitchen["openings"] if item["kind"] == "door")
        dining_door = next(item for item in dining["openings"] if item["kind"] == "door")
        assert kitchen_door["width_mm"] == dining_door["width_mm"]
        assert kitchen_door["width_mm"] == 900
        assert candidate.unmet_preferences == []


def test_entrance_door_is_only_created_for_an_explicit_axis_aligned_side():
    requested = generate_layout_candidates(plot(), brief(
        required_rooms=[{"room_type": "living", "quantity": 1}], entrance_side="west",
    ))
    unspecified = generate_layout_candidates(plot(), brief(required_rooms=[{"room_type": "living", "quantity": 1}]))
    assert requested.status == "layout_candidates"
    assert any(opening["kind"] == "door" for opening in requested.candidates[0].rooms[0]["openings"])
    assert not any(opening["kind"] == "door" for opening in unspecified.candidates[0].rooms[0]["openings"])


def test_plot_local_origin_is_preserved_for_rectangular_polygon():
    shifted = SimpleNamespace(
        shape="polygon", width_mm=10000, length_mm=10000,
        geometry_json='[{"x":5000,"y":7000},{"x":15000,"y":7000},{"x":15000,"y":17000},{"x":5000,"y":17000}]',
    )
    result = generate_layout_candidates(shifted, brief(required_rooms=[{"room_type": "living", "quantity": 1}]))
    assert result.status == "layout_candidates"
    point = result.candidates[0].rooms[0]["vertices_mm"][0]
    assert point["x"] >= 5000 and point["y"] >= 7000


def test_candidates_disclose_defaults_and_unparsed_hard_constraint_notes():
    result = generate_layout_candidates(plot(), brief(
        required_rooms=[{"room_type": "living", "quantity": 1}],
        hard_constraints=["Keep the prayer room away from bathrooms"],
    ))
    assert result.status == "layout_candidates"
    assumptions = result.candidates[0].assumptions
    assert any("product heuristic only" in item for item in assumptions)
    assert any("only structured" in item for item in assumptions)
    assert any("prayer room" in item for item in assumptions)


def test_duplicate_explicit_room_names_return_infeasible_instead_of_invalid_proposal():
    result = generate_layout_candidates(plot(), brief(required_rooms=[
        {"room_type": "living", "quantity": 1, "name": "Main Room"},
        {"room_type": "study", "quantity": 1, "name": " main room "},
    ]))
    assert result.status == "infeasible"
    assert any("unique" in reason.lower() for reason in result.reasons)


def test_free_text_circulation_and_orientation_preferences_are_disclosed_as_unenforced():
    result = generate_layout_candidates(plot(), brief(
        required_rooms=[{"room_type": "living", "quantity": 1}],
        circulation_preferences=["Keep the entry hall unobstructed"],
        orientation_preferences=["Study faces north"],
    ))
    assumptions = result.candidates[0].assumptions
    assert any("circulation preferences" in item.lower() and "not automatically enforced" in item.lower() for item in assumptions)
    assert any("orientation preferences" in item.lower() and "not automatically enforced" in item.lower() for item in assumptions)


def test_search_deduplicates_equivalent_geometry_across_ordering_seeds():
    result = generate_layout_candidates(plot(), brief(required_rooms=[{"room_type": "living", "quantity": 1}]))
    assert result.status == "layout_candidates"
    signatures = [
        tuple(sorted((room["name"], tuple((point["x"], point["y"]) for point in room["vertices_mm"])) for room in candidate.rooms))
        for candidate in result.candidates
    ]
    assert len(signatures) == len(set(signatures))


def test_bounded_search_finds_non_row_packing_for_three_rotatable_rectangles():
    result = generate_layout_candidates(plot(10000, 10000), brief(required_rooms=[
        {"room_type": "other", "quantity": 3, "preferred_width_mm": 6000,
         "preferred_depth_mm": 4000, "dimension_mode": "preferred", "allow_rotation": True},
    ]))
    assert result.status == "layout_candidates"
    assert result.candidates
    assert len(result.candidates[0].rooms) == 3


def test_search_budget_exhaustion_is_not_reported_as_proven_infeasibility():
    result = generate_layout_candidates(plot(10000, 10000), brief(required_rooms=[
        {"room_type": "other", "quantity": 3, "preferred_width_mm": 6000,
         "preferred_depth_mm": 4000, "dimension_mode": "preferred", "allow_rotation": True},
    ]), planner_config={"max_nodes": 1})
    assert result.status == "search_exhausted"
    assert result.search_status == "budget_exhausted"
    assert result.candidates == []


def test_structured_aspect_ratio_and_long_axis_preferences_are_scored_without_resizing():
    result = generate_layout_candidates(plot(), brief(required_rooms=[
        {"room_type": "other", "quantity": 1, "preferred_width_mm": 4000,
         "preferred_depth_mm": 3000, "dimension_mode": "exact", "allow_rotation": False,
         "target_aspect_ratio": 4 / 3, "long_axis_orientation": "east_west"},
    ]))
    assert result.status == "layout_candidates"
    candidate = result.candidates[0]
    assert "aspect_ratio" in candidate.score.breakdown
    assert "orientation_fit" in candidate.score.breakdown
    points = candidate.rooms[0]["vertices_mm"]
    xs = [point["x"] for point in points]
    ys = [point["y"] for point in points]
    assert max(xs) - min(xs) == 4000
    assert max(ys) - min(ys) == 3000


def test_absent_room_proportion_preferences_do_not_add_score_penalties():
    result = generate_layout_candidates(plot(), brief(required_rooms=[{"room_type": "living", "quantity": 1}]))
    assert result.status == "layout_candidates"
    assert "aspect_ratio" not in result.candidates[0].score.breakdown
    assert "orientation_fit" not in result.candidates[0].score.breakdown


def test_explicit_corridor_reserves_real_area_and_is_reported_in_utilization():
    result = generate_layout_candidates(plot(), brief(required_rooms=[
        {"room_type": "living", "quantity": 1, "preferred_width_mm": 4000, "preferred_depth_mm": 4000},
        {"room_type": "corridor", "quantity": 1, "preferred_width_mm": 2000, "preferred_depth_mm": 4000},
    ]))
    assert result.status == "layout_candidates"
    candidate = result.candidates[0]
    assert any(room["room_type"] == "corridor" for room in candidate.rooms)
    assert candidate.utilization.assigned_area_mm2 == 24_000_000
    assert candidate.utilization.plot_area_mm2 == 100_000_000
    assert candidate.utilization.unallocated_area_mm2 == 76_000_000
    assert candidate.utilization.utilization_percent == 24


def test_mandatory_privacy_separation_reports_disconnected_room_components():
    result = generate_layout_candidates(plot(), brief(
        required_rooms=[{"room_type": "living", "quantity": 1}, {"room_type": "bedroom", "quantity": 1}],
        privacy_preferences=[{"room_a": "living", "room_b": "bedroom", "relation": "separate", "priority": "must"}],
    ))
    assert result.status == "layout_candidates"
    candidate = result.candidates[0]
    assert len(candidate.circulation_components) == 2
    assert sorted(len(component) for component in candidate.circulation_components) == [1, 1]
    assert any("not fire" in warning.lower() or "egress" in warning.lower() for warning in candidate.warnings)


def test_corridor_with_mandatory_adjacency_connects_the_room_graph():
    result = generate_layout_candidates(plot(), brief(
        required_rooms=[
            {"room_type": "living", "quantity": 1},
            {"room_type": "corridor", "quantity": 1, "preferred_width_mm": 2000, "preferred_depth_mm": 4000},
            {"room_type": "bedroom", "quantity": 1},
        ],
        adjacency_preferences=[
            {"room_a": "living", "room_b": "corridor", "priority": "must_be_adjacent"},
            {"room_a": "corridor", "room_b": "bedroom", "priority": "must_be_adjacent"},
        ],
    ))
    assert result.status == "layout_candidates"
    assert len(result.candidates[0].circulation_components) == 1
    assert len(result.candidates[0].circulation_components[0]) == 3


def test_returned_candidates_are_distinct_by_normalized_room_centroid_displacement():
    result = generate_layout_candidates(plot(), brief(required_rooms=[{"room_type": "living", "quantity": 1}]))
    assert result.status == "layout_candidates"
    candidates = result.candidates
    assert 1 <= len(candidates) <= 3
    diagonal = (plot().width_mm ** 2 + plot().length_mm ** 2) ** 0.5
    centers = []
    for candidate in candidates:
        points = candidate.rooms[0]["vertices_mm"]
        centers.append((sum(p["x"] for p in points) / 4, sum(p["y"] for p in points) / 4))
    for index, center in enumerate(centers):
        for other in centers[index + 1:]:
            distance = ((center[0] - other[0]) ** 2 + (center[1] - other[1]) ** 2) ** 0.5
            assert distance / diagonal >= 0.08


def test_minimum_dimensions_are_never_reduced_by_search():
    result = generate_layout_candidates(plot(10000, 10000), brief(required_rooms=[
        {"room_type": "other", "quantity": 1, "preferred_width_mm": 4200,
         "preferred_depth_mm": 3100, "dimension_mode": "minimum", "allow_rotation": False},
    ]))
    assert result.status == "layout_candidates"
    points = result.candidates[0].rooms[0]["vertices_mm"]
    assert max(point["x"] for point in points) - min(point["x"] for point in points) == 4200
    assert max(point["y"] for point in points) - min(point["y"] for point in points) == 3100


def test_search_respects_non_zero_plot_origin():
    shifted = SimpleNamespace(
        shape="rectangle", width_mm=10000, length_mm=10000,
        geometry_json='[{"x":1000,"y":2000},{"x":11000,"y":2000},{"x":11000,"y":12000},{"x":1000,"y":12000}]',
    )
    result = generate_layout_candidates(shifted, brief(required_rooms=[{"room_type": "living", "quantity": 1}]))
    assert result.status == "layout_candidates"
    for candidate in result.candidates:
        for room in candidate.rooms:
            assert all(point["x"] >= 1000 and point["y"] >= 2000 for point in room["vertices_mm"])
