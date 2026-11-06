"use client";

import { candidateActionTarget, selectLayoutCandidate, ROOM_TYPE_OPTIONS } from "./assistant-state.mjs";
import { serializeProposalEdit, getProposalPlanningSummary } from "./assistant-state.mjs";

type Coordinate = { x: number; y: number };
type ProposalRoom = {
  proposal_id: string;
  name: string;
  room_type: string;
  vertices_mm: Coordinate[];
  wall_thickness_mm: number;
  openings: Array<Record<string, unknown>>;
};
export type LayoutProposal = {
  schema_version: string;
  title: string;
  assumptions: string[];
  warnings: string[];
  floor_number: number;
  rooms: ProposalRoom[];
  candidate_key?: string;
  planner_version?: string;
  template?: string;
  score?: number;
  score_breakdown?: Record<string, number>;
  unmet_preferences?: string[];
  score_version?: string;
  search_status?: "complete" | "budget_exhausted";
  utilization?: { plot_area_mm2: number; assigned_area_mm2: number; unallocated_area_mm2: number; utilization_percent: number } | null;
  circulation_components?: string[][];
};
export type LayoutCandidateView = {
  proposalId: string;
  candidateKey: string;
  template: string;
  score: number;
  scoreBreakdown: Record<string, number>;
  scoreVersion?: string;
  searchStatus?: "complete" | "budget_exhausted";
  utilization?: LayoutProposal["utilization"];
  circulationComponents?: string[][];
  proposal: LayoutProposal;
  status: "draft" | "needs_revision" | "applied" | "rejected";
  validationIssues: Array<{ path: string; message: string }>;
};
export type ProposalPreviewState = {
  proposalId: string;
  proposal: LayoutProposal;
  status: "draft" | "needs_revision" | "applied" | "rejected";
  validationIssues: Array<{ path: string; message: string }>;
  savedRoomsSnapshot: string;
  candidates?: LayoutCandidateView[];
  candidateKey?: string;
};

export default function ProposalPreview({
  value, onChange, onApply, onReject, busy = false,
}: {
  value: ProposalPreviewState;
  onChange: (proposal: LayoutProposal, candidate?: LayoutCandidateView) => void;
  onApply: (proposalId: string, proposalJson: string) => void;
  onReject: (proposalId: string) => void;
  busy?: boolean;
}) {
  function updateRoom(index: number, patch: Partial<ProposalRoom>) {
    onChange({ ...value.proposal, rooms: value.proposal.rooms.map((room, roomIndex) => roomIndex === index ? { ...room, ...patch } : room) });
  }

  function updateVertex(roomIndex: number, vertexIndex: number, axis: "x" | "y", raw: string) {
    const rooms = value.proposal.rooms.map((room, index) => index !== roomIndex ? room : {
      ...room,
      vertices_mm: room.vertices_mm.map((point, pointIndex) => pointIndex !== vertexIndex ? point : { ...point, [axis]: Number(raw) }),
    });
    onChange({ ...value.proposal, rooms });
  }

  const pending = value.status === "draft" || value.status === "needs_revision";
  const selectedActionId = value.candidates?.length && value.candidateKey
    ? candidateActionTarget(value.candidates, value.candidateKey) ?? value.proposalId
    : value.proposalId;
  const planningSummary = getProposalPlanningSummary(value.proposal);
  function chooseCandidate(candidateKey: string) {
    const candidate = selectLayoutCandidate(value.candidates ?? [], candidateKey);
    if (candidate) onChange(candidate.proposal, candidate);
  }
  return <section className="proposal-preview" aria-label="AI layout proposal preview">
    <div className="design-analysis-heading">
      <div><span className="card-kicker">AI-GENERATED · SEPARATE PREVIEW</span><h3>{value.proposal.title}</h3></div>
      <span className={`proposal-state ${value.status}`}>{value.status.replaceAll("_", " ").toUpperCase()}</span>
    </div>
    <p className="inspector-help">This proposal is separate from your saved floor plan. Editing it does not trigger autosave. Applying it will replace the rooms on this floor after fresh server-side validation.</p>
    {value.candidates && value.candidates.length > 1 && <label className="candidate-select">Compare generated layouts<select aria-label="Select generated layout candidate" value={value.candidateKey ?? value.candidates[0].candidateKey} onChange={event => chooseCandidate(event.target.value)} disabled={busy}>{value.candidates.map(candidate => <option key={candidate.candidateKey} value={candidate.candidateKey}>{candidate.template.replaceAll("_", " ")} · {candidate.score}/100</option>)}</select></label>}
    {value.candidates && value.candidates.length > 0 && <div className="candidate-score" aria-label="Candidate score"><strong>DESIGN SCORE · {value.candidates.find(item => item.candidateKey === value.candidateKey)?.score ?? value.candidates[0].score}/100 · SCORING {planningSummary.scoreVersion}</strong><ul>{Object.entries(value.candidates.find(item => item.candidateKey === value.candidateKey)?.scoreBreakdown ?? value.candidates[0].scoreBreakdown).map(([key, score]) => <li key={key}>{key.replaceAll("_", " ")}: {score}</li>)}</ul></div>}
    {planningSummary.utilization && <div className="assistant-detail" aria-label="Plot utilization"><strong>PLOT UTILIZATION · {planningSummary.utilization.utilization_percent.toFixed(1)}%</strong><p>Assigned room area: {(planningSummary.utilization.assigned_area_mm2 / 1_000_000).toFixed(2)} m² · Unallocated area: {(planningSummary.utilization.unallocated_area_mm2 / 1_000_000).toFixed(2)} m²</p></div>}
    {planningSummary.searchStatus === "budget_exhausted" && <div className="proposal-issues" role="status"><strong>SEARCH LIMIT REACHED</strong><p>These are the best validated options found before the search limit. The search was incomplete; this does not prove that no better arrangement exists.</p></div>}
    {planningSummary.circulationComponents.length > 1 && <div className="proposal-issues"><strong>DISCONNECTED ROOM GROUPS</strong><ul>{planningSummary.circulationComponents.map((component, index) => <li key={`component-${index}`}>{component.join(", ")}</li>)}</ul><small>Door connectivity is a geometric indicator only—not fire-egress, accessibility, or building-code approval.</small></div>}
    {(value.proposal.unmet_preferences ?? []).length > 0 && <div className="proposal-issues"><strong>UNMET PREFERENCES</strong><ul>{value.proposal.unmet_preferences?.map(item => <li key={item}>{item}</li>)}</ul></div>}
    {value.validationIssues.length > 0 && <div className="proposal-issues" role="alert"><strong>DESIGN ISSUES TO REVIEW</strong><ul>{value.validationIssues.map((issue, index) => <li key={`${issue.path}-${index}`}><b>{issue.path}</b>: {issue.message}</li>)}</ul></div>}
    {value.proposal.assumptions.length > 0 && <div className="assistant-detail"><strong>ASSUMPTIONS</strong><ul>{value.proposal.assumptions.map(item => <li key={item}>{item}</li>)}</ul></div>}
    {value.proposal.warnings.length > 0 && <div className="assistant-detail"><strong>WARNINGS</strong><ul>{value.proposal.warnings.map(item => <li key={item}>{item}</li>)}</ul></div>}
    <div className="proposal-room-list">{value.proposal.rooms.map((room, roomIndex) => <fieldset className="proposal-room" key={room.proposal_id}>
      <legend>{room.name || `Room ${roomIndex + 1}`}</legend>
      <div className="proposal-fields">
        <label>Room name<input value={room.name} maxLength={100} onChange={event => updateRoom(roomIndex, { name: event.target.value })} disabled={!pending || busy}/></label>
        <label>Room type<select value={room.room_type} onChange={event => updateRoom(roomIndex, { room_type: event.target.value })} disabled={!pending || busy}>{ROOM_TYPE_OPTIONS.map(type => <option key={type} value={type}>{type}</option>)}</select></label>
      </div>
      <div className="proposal-coordinates">{room.vertices_mm.map((point, vertexIndex) => <div className="proposal-coordinate" key={`${room.proposal_id}-${vertexIndex}`}>
        <span>Vertex {vertexIndex + 1}</span>
        <label>X · mm<input type="number" value={point.x} onChange={event => updateVertex(roomIndex, vertexIndex, "x", event.target.value)} disabled={!pending || busy}/></label>
        <label>Y · mm<input type="number" value={point.y} onChange={event => updateVertex(roomIndex, vertexIndex, "y", event.target.value)} disabled={!pending || busy}/></label>
      </div>)}</div>
      <small>{room.vertices_mm.length} vertices · {room.openings.length} openings · {room.wall_thickness_mm} mm wall thickness</small>
    </fieldset>)}</div>
    {pending && <div className="proposal-actions"><button className="studio-tool" disabled={busy} onClick={() => onReject(selectedActionId)}>Reject draft</button><button className="studio-tool active" disabled={busy} onClick={() => onApply(selectedActionId, serializeProposalEdit(value.proposal))}>{busy ? "Applying…" : "Apply to saved floor ↗"}</button></div>}
    {!pending && <p className="inspector-help">This proposal is no longer pending and cannot be applied again.</p>}
  </section>;
}
