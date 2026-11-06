export function appendConversationMessage(items, message) {
  return [...items, { ...message }];
}

export function serializeProposalEdit(proposal) {
  const rooms = (proposal?.rooms ?? []).map(room => ({
    proposal_id: room.proposal_id,
    name: room.name,
    room_type: room.room_type,
    vertices_mm: (room.vertices_mm ?? []).map(point => ({ x: Number(point.x), y: Number(point.y) })),
    wall_thickness_mm: Number(room.wall_thickness_mm ?? 150),
    openings: (room.openings ?? []).map(opening => ({ ...opening })),
  }));
  return JSON.stringify({
    schema_version: proposal?.schema_version ?? "1.0",
    title: proposal?.title ?? "Draft layout",
    assumptions: proposal?.assumptions ?? [],
    warnings: proposal?.warnings ?? [],
    floor_number: Number(proposal?.floor_number ?? 0),
    candidate_key: proposal?.candidate_key,
    planner_version: proposal?.planner_version,
    template: proposal?.template,
    score: proposal?.score,
    score_breakdown: proposal?.score_breakdown ?? {},
    unmet_preferences: proposal?.unmet_preferences ?? [],
    score_version: proposal?.score_version ?? "1.0",
    search_status: proposal?.search_status ?? "complete",
    utilization: proposal?.utilization ?? null,
    circulation_components: proposal?.circulation_components ?? [],
    rooms,
  });
}

export function isProposalPreviewOnly(savedRooms, proposalPreview) {
  if (!proposalPreview?.savedRoomsSnapshot) return false;
  return JSON.stringify(savedRooms) === proposalPreview.savedRoomsSnapshot
    && ["draft", "needs_revision"].includes(proposalPreview.status);
}

export function sortLayoutCandidates(candidates) {
  return (candidates ?? []).map((candidate, index) => ({ candidate, index }))
    .sort((left, right) => Number(right.candidate.score ?? 0) - Number(left.candidate.score ?? 0) || left.index - right.index)
    .map(item => item.candidate);
}

export function selectLayoutCandidate(candidates, candidateKey) {
  return (candidates ?? []).find(candidate => candidate.candidateKey === candidateKey) ?? null;
}

export function candidateActionTarget(candidates, candidateKey) {
  return selectLayoutCandidate(candidates, candidateKey)?.proposalId ?? null;
}

export const ROOM_TYPE_OPTIONS = ["living", "bedroom", "kitchen", "bathroom", "dining", "study", "utility", "staircase", "corridor", "parking", "other"];
export const ROOM_TYPE_COLORS = {
  living: "#c6d5a7", bedroom: "#b8c9dd", kitchen: "#e4c59b", bathroom: "#a8d1cf",
  dining: "#d5b6d0", study: "#c5b8df", utility: "#c3c9a5", staircase: "#d0c5b3",
  corridor: "#b7c9bb", parking: "#d5c08f", other: "#c6c6c6",
};

export function canPreviewLayoutCandidates(outcome, candidates) {
  return outcome === "layout_candidates" && Array.isArray(candidates) && candidates.length > 0;
}


export function getProposalPlanningSummary(proposal) {
  return {
    scoreVersion: proposal?.score_version ?? "1.0",
    searchStatus: proposal?.search_status ?? "complete",
    utilization: proposal?.utilization ?? null,
    circulationComponents: Array.isArray(proposal?.circulation_components) ? proposal.circulation_components : [],
  };
}
