"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import PlanEditor from "./components/PlanEditor";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

type User = { id: string; email: string; display_name: string | null };
type Plot = { shape: string; width_mm: number | null; length_mm: number | null; display_unit: string; orientation: string | null; road_facing_side: string | null; area_sq_ft: number | null; perimeter_mm?: number | null; vertices_mm: { x: number; y: number }[] | null };
type Project = { id: string; name: string; category: string; status: string; created_at: string; updated_at: string; plot: Plot | null };

async function apiError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : "Please check the submitted information.";
  } catch {
    return "The server could not complete the request.";
  }
}

export default function HomePage() {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [message, setMessage] = useState("Create your account to enter the studio.");
  const [user, setUser] = useState<User | null>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectName, setProjectName] = useState("");
  const [category, setCategory] = useState("residential");
  const [width, setWidth] = useState("");
  const [length, setLength] = useState("");
  const [unit, setUnit] = useState("ft");
  const [orientation, setOrientation] = useState("east");
  const [activeProject, setActiveProject] = useState<Project | null>(null);

  const loadProjects = useCallback(async () => {
    const response = await fetch(`${API_BASE}/projects`, { credentials: "include", cache: "no-store" });
    if (!response.ok) throw new Error(await apiError(response));
    setProjects(await response.json());
  }, []);

  useEffect(() => {
    const storedCsrf = window.sessionStorage.getItem("brahma_csrf");
    if (!storedCsrf) return;
    setCsrfToken(storedCsrf);
    fetch(`${API_BASE}/auth/me`, { credentials: "include", cache: "no-store" })
      .then(async response => {
        if (!response.ok) throw new Error("Session expired");
        setUser(await response.json());
        await loadProjects();
      })
      .catch(() => {
        window.sessionStorage.removeItem("brahma_csrf");
        setCsrfToken(null);
      });
  }, [loadProjects]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("Connecting securely…");
    try {
      if (mode === "register") {
        const registration = await fetch(`${API_BASE}/auth/register`, {
          method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
          body: JSON.stringify({ email, password, display_name: displayName || null }),
        });
        if (!registration.ok) throw new Error(await apiError(registration));
      }
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) throw new Error(await apiError(response));
      const payload = await response.json();
      setUser(payload.user);
      setCsrfToken(payload.csrf_token);
      window.sessionStorage.setItem("brahma_csrf", payload.csrf_token);
      await loadProjects();
      setMessage("Secure session established.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to connect to BrahmaAI Studio API.");
    } finally {
      setBusy(false);
    }
  }

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrfToken) return;
    setBusy(true);
    setMessage("Saving your architectural project…");
    try {
      const payload = {
        name: projectName,
        category,
        plot: width && length ? { shape: "rectangle", width: Number(width), length: Number(length), unit, orientation } : null,
      };
      const response = await fetch(`${API_BASE}/projects`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await apiError(response));
      const created: Project = await response.json();
      setProjects(current => [created, ...current]);
      setProjectName(""); setWidth(""); setLength("");
      setMessage(`Project “${created.name}” saved successfully.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Project could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function archiveProject(id: string) {
    if (!csrfToken || !window.confirm("Archive this project? It will disappear from your active project list.")) return;
    setBusy(true);
    try {
      const response = await fetch(`${API_BASE}/projects/${id}`, {
        method: "DELETE", credentials: "include", headers: { "X-CSRF-Token": csrfToken },
      });
      if (!response.ok) throw new Error(await apiError(response));
      setProjects(current => current.filter(project => project.id !== id));
      setMessage("Project archived. Its data has not been permanently deleted.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to archive project.");
    } finally { setBusy(false); }
  }

  async function logout() {
    if (!csrfToken) return;
    setBusy(true);
    try {
      const response = await fetch(`${API_BASE}/auth/logout`, {
        method: "POST", credentials: "include", headers: { "X-CSRF-Token": csrfToken },
      });
      if (!response.ok) throw new Error(await apiError(response));
      window.sessionStorage.removeItem("brahma_csrf");
      setUser(null); setCsrfToken(null); setProjects([]); setPassword("");
      setMessage("You have signed out securely.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Sign-out failed.");
    } finally { setBusy(false); }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="#home"><span className="brand-mark">B</span><span>BRAHMA<span className="brand-light">AI</span> STUDIO</span></a>
        <span className="topbar-note">ARCHITECTURE · INTELLIGENCE · CREATION</span>
        {user && <button className="text-button" onClick={logout} disabled={busy}>Sign out ↗</button>}
      </header>
      {user ? (
        <section className="workspace" id="home">
          <div className="workspace-heading">
            <div><div className="eyebrow"><span className="pulse"/> YOUR ARCHITECTURAL WORKSPACE</div><h1 className="workspace-title">Good to have you here{user.display_name ? `, ${user.display_name}` : ""}.</h1><p className="lead">Create a project, define your plot, and give your next idea a place to begin.</p></div>
            <div className="workspace-count"><strong>{projects.length.toString().padStart(2, "0")}</strong><span>ACTIVE PROJECTS</span></div>
          </div>
          <div className="workspace-grid">
            <section className="panel create-panel">
              <div className="card-kicker">START SOMETHING NEW</div><h2>New architectural project</h2><p className="muted">Project details can be refined later. Plot dimensions are stored in millimetres for consistent calculations.</p>
              <form onSubmit={createProject} className="form project-form">
                <label>Project name<input required maxLength={160} value={projectName} onChange={e => setProjectName(e.target.value)} placeholder="e.g. East-facing family home"/></label>
                <label>Project category<select value={category} onChange={e => setCategory(e.target.value)}><option value="residential">Residential</option><option value="commercial">Commercial</option><option value="industrial">Industrial</option><option value="other">Other</option></select></label>
                <div className="form-section-label">PLOT CONFIGURATION <span>OPTIONAL</span></div>
                <div className="field-pair"><label>Width<input type="number" min="0.001" step="any" value={width} onChange={e => setWidth(e.target.value)} placeholder="e.g. 30"/></label><label>Length<input type="number" min="0.001" step="any" value={length} onChange={e => setLength(e.target.value)} placeholder="e.g. 50"/></label></div>
                <div className="field-pair"><label>Unit<select value={unit} onChange={e => setUnit(e.target.value)}><option value="ft">Feet</option><option value="in">Inches</option><option value="m">Metres</option><option value="cm">Centimetres</option><option value="mm">Millimetres</option></select></label><label>Orientation<select value={orientation} onChange={e => setOrientation(e.target.value)}><option value="north">North</option><option value="east">East</option><option value="south">South</option><option value="west">West</option><option value="northeast">Northeast</option><option value="southeast">Southeast</option><option value="southwest">Southwest</option><option value="northwest">Northwest</option></select></label></div>
                <button className="button" disabled={busy || (!!width !== !!length)}>{busy ? "Please wait…" : "Create project"}<span>↗</span></button>
                {!!width !== !!length && <p className="field-hint">Enter both plot dimensions, or leave both blank.</p>}
              </form>
            </section>
            <section className="projects-panel">
              <div className="section-heading"><div><div className="card-kicker">YOUR WORK</div><h2>Recent projects</h2></div><span className="project-total">{projects.length} TOTAL</span></div>
              {projects.length === 0 ? <div className="empty-state"><div className="empty-mark">⌂</div><h3>Your canvas is waiting.</h3><p>Create your first project to begin defining its plot and architectural brief.</p></div> : <div className="project-list">{projects.map(project => <article className="project-card" key={project.id}><div className="project-card-top"><span className="project-type">{project.category.toUpperCase()}</span><span className="project-status"><i/> ACTIVE</span></div><h3>{project.name}</h3><div className="project-meta">{project.plot ? <><span>{project.plot.shape === "polygon" ? "Irregular plot" : `${project.plot.width_mm} × ${project.plot.length_mm} mm`}</span><span>{project.plot.area_sq_ft?.toLocaleString()} sq ft</span><span>{project.plot.orientation ?? "Orientation unset"}</span></> : <span>Plot not configured yet</span>}</div><div className="project-card-bottom"><span>Created {new Date(project.created_at).toLocaleDateString()}</span><div className="project-actions"><button className="studio-open-button" onClick={() => setActiveProject(project)} disabled={!project.plot}>Open 2D studio ↗</button><button className="archive-button" onClick={() => archiveProject(project.id)} disabled={busy}>Archive</button></div></div></article>)}</div>}
            </section>
          </div>
          {activeProject && csrfToken && <PlanEditor project={activeProject} csrfToken={csrfToken} onClose={() => setActiveProject(null)} />}
          <p className="notice workspace-notice" role="status">{message}</p>
        </section>
      ) : (
        <section className="hero" id="home">
          <div className="hero-copy"><div className="eyebrow"><span className="pulse"/> THE INTELLIGENT ARCHITECTURAL STUDIO</div><h1>Imagine beyond<br/><em>boundaries.</em></h1><p className="lead">A new foundation for turning architectural ideas into measurable, editable and build-aware design projects.</p><div className="feature-line"><span>01 / PRECISION GEOMETRY</span><span>02 / 2D + 3D DESIGN</span><span>03 / BRAHMA INTELLIGENCE</span></div></div>
          <div className="auth-card"><div className="card-kicker">YOUR DESIGN WORKSPACE</div><h2>{mode === "register" ? "Create your account" : "Welcome back"}</h2><p className="muted">Secure access to your architectural projects.</p><div className="tabs"><button className={mode === "register" ? "tab active" : "tab"} onClick={() => setMode("register")}>Create account</button><button className={mode === "login" ? "tab active" : "tab"} onClick={() => setMode("login")}>Sign in</button></div><form onSubmit={submit} className="form">{mode === "register" && <label>Name<input value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="Your name" maxLength={120}/></label>}<label>Email address<input type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com"/></label><label>Password<input type="password" required minLength={12} value={password} onChange={e => setPassword(e.target.value)} placeholder="At least 12 characters"/></label><button className="button" disabled={busy}>{busy ? "Please wait…" : mode === "register" ? "Create secure account" : "Sign in to studio"}<span>↗</span></button></form><p className="notice" role="status">{message}</p><p className="fineprint">Your password is hashed on the server. Project information is stored in your account.</p></div>
        </section>
      )}
      <footer className="footer"><span>© 2026 BRAHMAAI STUDIO</span><span>IMAGINE BEYOND BOUNDARIES. BUILD WITHIN POSSIBILITIES.</span><span>FOUNDATION RELEASE 0.2</span></footer>
    </main>
  );
}
