from app.services.room_layout_search import SearchLimits, SearchResult, search_room_layouts


def test_search_result_exposes_deterministic_budget_exhaustion_state():
    result = SearchResult(solutions=(), nodes_visited=7, budget_exhausted=True)
    assert result.solutions == ()
    assert result.nodes_visited == 7
    assert result.budget_exhausted is True


def test_search_limits_are_bounded_and_keep_internal_solution_budget():
    limits = SearchLimits(max_nodes=100, max_solutions=4, max_depth=10)
    assert limits.max_nodes == 100
    assert limits.max_solutions == 4
    assert limits.max_depth == 10


def test_search_limits_reject_values_above_hard_ceiling():
    import pytest
    with pytest.raises(ValueError):
        SearchLimits(max_nodes=100_001)


def test_search_finds_non_overlapping_alternative_and_is_deterministic():
    from types import SimpleNamespace
    from app.schemas.room_planning import RoomPlanningBrief

    bounds = SimpleNamespace(min_x=0.0, min_y=0.0, max_x=10000.0, max_y=10000.0)
    rooms = [
        {"name": f"Other {index}", "room_type": "other", "width": 6000.0, "depth": 4000.0,
         "mode": "preferred", "allow_rotation": True}
        for index in range(1, 4)
    ]
    brief = RoomPlanningBrief.model_validate({"floor_number": 0, "required_rooms": [
        {"room_type": "other", "quantity": 3, "preferred_width_mm": 6000, "preferred_depth_mm": 4000}
    ]})
    first = search_room_layouts(rooms, bounds, brief)
    second = search_room_layouts(rooms, bounds, brief)
    assert first.solutions
    assert first.solutions == second.solutions
    for solution in first.solutions:
        for index, room in enumerate(solution.placements):
            assert room["x"] >= bounds.min_x and room["y"] >= bounds.min_y
            assert room["x"] + room["width"] <= bounds.max_x
            assert room["y"] + room["depth"] <= bounds.max_y
            for other in solution.placements[index + 1:]:
                overlap_x = min(room["x"] + room["width"], other["x"] + other["width"]) - max(room["x"], other["x"])
                overlap_y = min(room["y"] + room["depth"], other["y"] + other["depth"]) - max(room["y"], other["y"])
                assert not (overlap_x > 0 and overlap_y > 0)


def test_search_stops_at_explicit_node_budget():
    from types import SimpleNamespace
    from app.schemas.room_planning import RoomPlanningBrief

    bounds = SimpleNamespace(min_x=0.0, min_y=0.0, max_x=10000.0, max_y=10000.0)
    rooms = [{"name": f"Living {index}", "room_type": "living", "width": 4000.0, "depth": 4000.0,
              "mode": "preferred", "allow_rotation": True} for index in range(1, 4)]
    brief = RoomPlanningBrief.model_validate({"floor_number": 0, "required_rooms": [{"room_type": "living", "quantity": 3}]})
    result = search_room_layouts(rooms, bounds, brief, SearchLimits(max_nodes=1))
    assert result.nodes_visited == 1
    assert result.budget_exhausted is True
