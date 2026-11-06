"use client";

import { useState } from "react";

type Result = {
  configuration: string; floor_to_floor_mm: number; riser_count: number; actual_riser_mm: number;
  going_count: number; flight_count: number; risers_per_flight: number[]; flight_run_mm: number;
  comfort_sum_2r_plus_t_mm: number; comfort_indicator: string; notes: string[]; is_code_certified: false;
};

export default function StaircasePlanner({ projectId, csrfToken }: { projectId: string; csrfToken: string }) {
  const [height, setHeight] = useState("3000");
  const [riser, setRiser] = useState("175");
  const [tread, setTread] = useState("280");
  const [width, setWidth] = useState("1000");
  const [landing, setLanding] = useState("1000");
  const [configuration, setConfiguration] = useState("U");
  const [result, setResult] = useState<Result | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function calculate() {
    setBusy(true); setMessage(""); setResult(null);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"}/projects/${projectId}/staircase/preview`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify({ floor_to_floor_mm: Number(height), preferred_riser_mm: Number(riser), tread_depth_mm: Number(tread), clear_width_mm: Number(width), landing_depth_mm: Number(landing), configuration }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Check the staircase dimensions and try again.");
      setResult(body);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Staircase preview failed."); }
    finally { setBusy(false); }
  }

  return <section className="staircase-planner" aria-label="Parametric staircase planner">
    <div className="card-kicker">PARAMETRIC STAIRCASE · CONCEPT PREVIEW</div>
    <p className="muted">Enter floor-to-floor height and preferred dimensions. The planner balances the riser count and estimates the longest flight run.</p>
    <div className="staircase-fields">
      <label>Floor height · mm<input type="number" min="1501" max="6000" value={height} onChange={event => setHeight(event.target.value)}/></label>
      <label>Preferred riser · mm<input type="number" min="101" max="250" value={riser} onChange={event => setRiser(event.target.value)}/></label>
      <label>Tread depth · mm<input type="number" min="180" max="450" value={tread} onChange={event => setTread(event.target.value)}/></label>
      <label>Clear width · mm<input type="number" min="600" max="3000" value={width} onChange={event => setWidth(event.target.value)}/></label>
      <label>Landing depth · mm<input type="number" min="600" max="6000" value={landing} onChange={event => setLanding(event.target.value)}/></label>
      <label>Configuration<select value={configuration} onChange={event => setConfiguration(event.target.value)}><option value="straight">Straight</option><option value="L">L-turn</option><option value="U">U-turn</option></select></label>
    </div>
    <button className="studio-tool" onClick={calculate} disabled={busy}>{busy ? "Calculating…" : "Calculate staircase ↗"}</button>
    {message && <p className="form-error" role="alert">{message}</p>}
    {result && <div className="staircase-results" aria-live="polite">
      <div className="inspector-metrics"><div><strong>{result.riser_count}</strong><span>RISERS</span></div><div><strong>{result.actual_riser_mm} mm</strong><span>ACTUAL RISER</span></div><div><strong>{result.flight_run_mm} mm</strong><span>LONGEST FLIGHT RUN</span></div></div>
      <p>{result.flight_count} flight(s) · {result.going_count} goings total · risers per flight: {result.risers_per_flight.join(" / ")}</p>
      <p><strong>2R + T:</strong> {result.comfort_sum_2r_plus_t_mm} mm · {result.comfort_indicator.replaceAll("_", " ")}</p>
      {result.notes.map(note => <p className="inspector-help" key={note}>{note}</p>)}
      <p className="plan-disclaimer">This is a dimensional concept preview only. It is not code-certified, structurally verified, or a construction drawing.</p>
    </div>}
  </section>;
}
