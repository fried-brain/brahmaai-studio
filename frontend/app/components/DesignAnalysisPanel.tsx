"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

type RoomIndicator = {
  room_id: string;
  room_name: string;
  room_type: string;
  floor_area_sq_m: number;
  window_count: number;
  window_opening_area_sq_m: number;
  window_to_floor_ratio_percent: number;
  daylight_planning_indicator: string;
  ventilation_planning_indicator: string;
  note: string;
};
type Analysis = {
  rooms: RoomIndicator[];
  vastu_mode: string;
  vastu_notes: string[];
  method_note: string;
  is_code_certified: false;
};

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, character => character.toUpperCase());
}

export default function DesignAnalysisPanel({ projectId, floorNumber, refreshKey }: { projectId: string; floorNumber: number; refreshKey: string }) {
  const [includeVastu, setIncludeVastu] = useState(false);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [status, setStatus] = useState("Loading design indicators…");

  const load = useCallback(async () => {
    setStatus("Updating design indicators…");
    try {
      const response = await fetch(`${API_BASE}/projects/${projectId}/design-analysis/${floorNumber}?include_vastu=${includeVastu}`, {
        credentials: "include", cache: "no-store",
      });
      if (response.status === 404) {
        setAnalysis(null);
        setStatus("Save at least one room to generate design indicators.");
        return;
      }
      if (!response.ok) throw new Error("Design analysis is currently unavailable.");
      setAnalysis(await response.json());
      setStatus("Analysis updated from the saved floor plan.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to analyse this floor.");
    }
  }, [projectId, floorNumber, includeVastu]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 900);
    return () => window.clearTimeout(timer);
  }, [load, refreshKey]);

  return (
    <section className="design-analysis-panel" aria-label="Architectural planning indicators">
      <div className="design-analysis-heading">
        <div><span className="card-kicker">BRAHMAAI · DESIGN INTELLIGENCE</span><h3>Daylight & ventilation planning</h3></div>
        <button className="studio-tool" onClick={() => void load()}>↻ Refresh</button>
      </div>
      <p className="inspector-help">Preliminary window-to-floor-area indicators from saved room geometry. These are not daylight simulation or airflow calculations.</p>
      {analysis?.rooms.length ? <div className="design-analysis-grid">
        {analysis.rooms.map(room => <article className="design-analysis-card" key={room.room_id}>
          <strong>{room.room_name}</strong><span className="design-analysis-meta">{room.floor_area_sq_m} m² · {room.window_count} windows</span>
          <div className="design-analysis-ratio">{room.window_to_floor_ratio_percent}% <small>window / floor</small></div>
          <div className="design-analysis-indicators"><span>Daylight proxy <b>{label(room.daylight_planning_indicator)}</b></span><span>Ventilation proxy <b>{label(room.ventilation_planning_indicator)}</b></span></div>
        </article>)}
      </div> : <p className="inspector-help">{status}</p>}
      {analysis && <>
        <p className="inspector-help">{analysis.method_note}</p>
        <label className="vastu-toggle"><input type="checkbox" checked={includeVastu} onChange={event => setIncludeVastu(event.target.checked)}/> Include traditional Vastu reference notes (optional)</label>
        {analysis.vastu_notes.length > 0 && <div className="vastu-notes"><strong>Traditional reference notes</strong>{analysis.vastu_notes.map(note => <p key={note}>{note}</p>)}</div>}
        <p className="analysis-status" role="status">{status} · Not code-certified.</p>
      </>}
    </section>
  );
}
