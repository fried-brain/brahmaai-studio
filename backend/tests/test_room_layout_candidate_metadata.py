from app.schemas.room_layout_candidates import LayoutCandidate, CandidateScore, PlannerResult


def test_legacy_wp5c_candidate_payload_parses_with_wp5d_metadata_defaults():
    candidate = LayoutCandidate.model_validate({
        "candidate_key": "legacy-key",
        "template": "public_first",
        "title": "Legacy layout",
        "rooms": [],
        "score": {"total": 80, "breakdown": {"adjacency": 80}},
    })
    assert candidate.planner_version == "1.0"
    assert candidate.score_version == "1.0"
    assert candidate.search_status == "complete"
    assert candidate.utilization is None
    assert candidate.circulation_components == []


def test_search_exhausted_is_an_explicit_planner_result_state():
    result = PlannerResult(status="search_exhausted", reasons=["Budget reached"])
    assert result.status == "search_exhausted"


def test_legacy_wp5c_proposal_remains_valid_without_wp5d_fields():
    from app.schemas.assistant_ai import LayoutProposalDraft

    proposal = LayoutProposalDraft.model_validate({
        "schema_version": "1.0", "title": "Legacy", "floor_number": 0,
        "rooms": [{
            "proposal_id": "room-1", "name": "Living", "room_type": "living",
            "vertices_mm": [{"x": 0.0, "y": 0.0}, {"x": 3000.0, "y": 0.0},
                            {"x": 3000.0, "y": 3000.0}, {"x": 0.0, "y": 3000.0}],
        }],
        "candidate_key": "legacy", "planner_version": "1.0", "template": "public_first",
        "score": 80, "score_breakdown": {"adjacency": 80},
    })
    assert proposal.score_version == "1.0"
    assert proposal.search_status == "complete"
    assert proposal.utilization is None
    assert proposal.circulation_components == []


def test_wp5d_proposal_metadata_and_new_seed_labels_are_valid():
    from app.schemas.assistant_ai import LayoutProposalDraft

    proposal = LayoutProposalDraft.model_validate({
        "schema_version": "1.0", "title": "Optimized", "floor_number": 0,
        "rooms": [{
            "proposal_id": "room-1", "name": "Living", "room_type": "living",
            "vertices_mm": [{"x": 0.0, "y": 0.0}, {"x": 3000.0, "y": 0.0},
                            {"x": 3000.0, "y": 3000.0}, {"x": 0.0, "y": 3000.0}],
        }],
        "candidate_key": "wp5d", "planner_version": "2.0", "template": "largest_first",
        "score": 90, "score_breakdown": {"circulation": 90}, "score_version": "2.0",
        "search_status": "budget_exhausted",
        "utilization": {"plot_area_mm2": 100000000, "assigned_area_mm2": 9000000,
                        "unallocated_area_mm2": 91000000, "utilization_percent": 9},
        "circulation_components": [["Living"]],
    })
    assert proposal.score_version == "2.0"
    assert proposal.search_status == "budget_exhausted"
    assert proposal.utilization.utilization_percent == 9
    assert proposal.circulation_components == [["Living"]]
