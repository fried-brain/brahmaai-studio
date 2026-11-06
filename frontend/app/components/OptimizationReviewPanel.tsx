"use client";

export type ReviewIssue = { code: string; severity: string; message: string };
export type ArrangementCandidate = { candidate_key: string; placements: Array<{ item_id: string; name: string; x_mm: number; y_mm: number; width_mm: number; depth_mm: number; rotation_deg: 0 | 90 | 180 | 270; catalog_type: string }>; score: number; assumptions: string[]; issues: ReviewIssue[] };
export default function OptimizationReviewPanel({ candidates, selectedKey, status, issues, openingSuggestions, busy, onSelect, onCandidateChange, onApply, onDiscard }: {
  candidates: ArrangementCandidate[]; selectedKey: string | null; status: string; issues: ReviewIssue[];
  openingSuggestions: Array<{ kind: string; edge_index: number; reason: string }>; busy: boolean;
  onSelect: (key: string) => void; onCandidateChange: (key: string, itemId: string, patch: Partial<ArrangementCandidate["placements"][number]>) => void; onApply: () => void; onDiscard: () => void;
}) {
  if (!status && !candidates.length && !issues.length && !openingSuggestions.length) return null;
  const selected = candidates.find(item => item.candidate_key === selectedKey) ?? candidates[0];
  return <section className="optimization-review" aria-label="Optimization review">
    <div className="room-list-heading">OPTIMIZATION REVIEW</div>
    {status && <p className="inspector-help" role="status">{status}</p>}
    {candidates.length > 0 && <>
      <label className="candidate-select">Arrangement candidates<select value={selected?.candidate_key ?? ""} onChange={event => onSelect(event.target.value)}>{candidates.slice(0, 3).map((candidate, index) => <option key={candidate.candidate_key} value={candidate.candidate_key}>Option {index + 1} · score {candidate.score}</option>)}</select></label>
      {selected && <><p className="inspector-help">{selected.placements.length} items · score {selected.score}/100 · edit candidate before applying</p>
        {selected.placements.map(item=><div className="furniture-fields" key={item.item_id}><strong>{item.name}</strong><label>X<input type="number" value={item.x_mm} onChange={event=>onCandidateChange(selected.candidate_key,item.item_id,{x_mm:Number(event.target.value)})}/></label><label>Y<input type="number" value={item.y_mm} onChange={event=>onCandidateChange(selected.candidate_key,item.item_id,{y_mm:Number(event.target.value)})}/></label><label>W<input type="number" min="100" value={item.width_mm} onChange={event=>onCandidateChange(selected.candidate_key,item.item_id,{width_mm:Math.max(100,Number(event.target.value)||100)})}/></label><label>D<input type="number" min="100" value={item.depth_mm} onChange={event=>onCandidateChange(selected.candidate_key,item.item_id,{depth_mm:Math.max(100,Number(event.target.value)||100)})}/></label><button className="archive-button" type="button" onClick={()=>onCandidateChange(selected.candidate_key,item.item_id,{rotation_deg:((item.rotation_deg+90)%360) as 0|90|180|270})}>Rotate {item.rotation_deg}°</button></div>)}
        <ul className="inspector-help">{selected.assumptions.map((item,index)=><li key={index}>{item}</li>)}</ul>{selected.issues.map((issue,index)=><p key={`${issue.code}-${index}`} className={issue.severity === "error" ? "optimization-error" : "inspector-help"}>{issue.severity.toUpperCase()}: {issue.message}</p>)}</>}
      <div className="tool-group"><button className="studio-tool" disabled={busy || !selected} onClick={onApply}>Apply selected arrangement</button><button className="archive-button" onClick={onDiscard}>Discard preview</button></div>
    </>}
    {issues.map((issue,index)=><p key={`${issue.code}-${index}`} className={issue.severity === "error" ? "optimization-error" : "inspector-help"}>{issue.severity.toUpperCase()}: {issue.message}</p>)}
    {openingSuggestions.map((suggestion,index)=><p key={`opening-${index}`} className="inspector-help">Suggested {suggestion.kind} · wall {suggestion.edge_index + 1}: {suggestion.reason}</p>)}
  </section>;
}
