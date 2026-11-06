import test from "node:test";
import assert from "node:assert/strict";
import { sortLayoutCandidates, selectLayoutCandidate, candidateActionTarget, ROOM_TYPE_OPTIONS, ROOM_TYPE_COLORS, canPreviewLayoutCandidates, serializeProposalEdit, getProposalPlanningSummary } from "../app/components/assistant-state.mjs";

const candidates = [
  { proposalId: "a", candidateKey: "key-a", score: 80, proposal: { title: "A" } },
  { proposalId: "b", candidateKey: "key-b", score: 95, proposal: { title: "B" } },
  { proposalId: "c", candidateKey: "key-c", score: 95, proposal: { title: "C" } },
];

test("candidate sorting is stable and score-descending", () => {
  assert.deepEqual(sortLayoutCandidates(candidates).map(item => item.proposalId), ["b", "c", "a"]);
});

test("selecting a candidate returns only that candidate and does not mutate the set", () => {
  const original = structuredClone(candidates);
  const selected = selectLayoutCandidate(candidates, "key-b");
  assert.equal(selected.proposal.title, "B");
  assert.deepEqual(candidates, original);
});

test("apply and reject actions target the currently selected proposal id", () => {
  assert.equal(candidateActionTarget(candidates, "key-c"), "c");
  assert.equal(candidateActionTarget(candidates, "missing"), null);
});

test("parking is an available room type with a distinct room color", () => {
  assert.ok(ROOM_TYPE_OPTIONS.includes("parking"));
  assert.ok(ROOM_TYPE_COLORS.parking);
  assert.notEqual(ROOM_TYPE_COLORS.parking, ROOM_TYPE_COLORS.other);
});

test("clarification and failure outcomes never create an applicable preview", () => {
  for (const outcome of ["clarification", "infeasible", "unsupported_plot_geometry", "model_unavailable", "invalid_model_response", "missing_plot", "search_exhausted"]) {
    assert.equal(canPreviewLayoutCandidates(outcome, []), false);
    assert.equal(canPreviewLayoutCandidates(outcome, candidates), false);
  }
  assert.equal(canPreviewLayoutCandidates("layout_candidates", candidates), true);
});


test("WP5D planning metadata survives preview edits and restores safe legacy defaults", () => {
  const proposal = {
    schema_version: "1.0", title: "Optimized", floor_number: 0, rooms: [],
    score_version: "2.0", search_status: "budget_exhausted",
    utilization: { plot_area_mm2: 100000000, assigned_area_mm2: 25000000, unallocated_area_mm2: 75000000, utilization_percent: 25 },
    circulation_components: [["Living", "Corridor"], ["Bedroom"]],
  };
  const serialized = JSON.parse(serializeProposalEdit(proposal));
  assert.equal(serialized.score_version, "2.0");
  assert.equal(serialized.search_status, "budget_exhausted");
  assert.equal(serialized.utilization.utilization_percent, 25);
  assert.deepEqual(serialized.circulation_components, [["Living", "Corridor"], ["Bedroom"]]);
  assert.deepEqual(getProposalPlanningSummary({}), { scoreVersion: "1.0", searchStatus: "complete", utilization: null, circulationComponents: [] });
});
