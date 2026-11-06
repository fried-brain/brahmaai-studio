"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { appendConversationMessage, canPreviewLayoutCandidates, sortLayoutCandidates } from "./assistant-state.mjs";
import type { LayoutCandidateView, LayoutProposal } from "./ProposalPreview";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

type AssistantResult = {
  reply: string;
  intent: string;
  clarifying_questions: string[];
  suggestions: string[];
  proposal: { kind: string; title: string; details: Record<string, unknown>; requires_user_approval: boolean } | null;
  changes_applied: boolean;
  engine: "local_rules" | "local_llm";
  conversation_id: string | null;
  response_type: "clarification" | "answer" | "layout_proposal";
  model?: string | null;
  proposal_id?: string | null;
  proposal_metadata?: { status: "draft" | "needs_revision"; validation_issues: Array<{ path: string; message: string }> } | null;
};
type GenerationResponse = {
  outcome: string;
  reply: string;
  questions: string[];
  suggestions: string[];
  conversation_id: string;
  planner_version: string;
  search_status: "complete" | "budget_exhausted";
  candidates: Array<{ proposal_id: string; candidate_key: string; template: string; score: number; score_breakdown: Record<string, number>; score_version: string; search_status: "complete" | "budget_exhausted"; utilization: LayoutProposal["utilization"]; circulation_components: string[][]; proposal: LayoutProposal; status: LayoutCandidateView["status"]; validation_issues: Array<{ path: string; message: string }> }>;
};
type ChatItem = { role: "user" | "assistant"; text: string; result?: AssistantResult };
type Conversation = { id: string; title: string; floor_number: number; message_count: number };
type AssistantStatus = { enabled: boolean; configured: boolean; reachable: boolean; model_available: boolean; code: string };

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (body.detail?.message) return body.detail.message;
  } catch { /* use fallback */ }
  return "The design assistant could not complete that request.";
}

export default function DesignAssistant({
  projectId, floorNumber, csrfToken, onProposalPreview, onProposalClear,
}: {
  projectId: string;
  floorNumber: number;
  csrfToken: string;
  onProposalPreview: (value: { proposalId: string; proposal: LayoutProposal; status: "draft" | "needs_revision" | "applied" | "rejected"; validationIssues: Array<{ path: string; message: string }>; candidates?: LayoutCandidateView[]; candidateKey?: string }) => void;
  onProposalClear: () => void;
}) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [items, setItems] = useState<ChatItem[]>([{ role: "assistant", text: "I can help design a room layout, ask for missing details, and prepare an editable proposal. Your saved floor plan will not change until you explicitly apply a validated proposal." }]);

  const refreshConversations = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/projects/${projectId}/assistant/conversations?limit=50`, { credentials: "include", cache: "no-store" });
      if (response.ok) setConversations(await response.json());
    } catch { /* transcript remains usable in the current session */ }
  }, [projectId]);

  useEffect(() => {
    setConversationId(null);
    setItems([{ role: "assistant", text: "I can help design a room layout, ask for missing details, and prepare an editable proposal. Your saved floor plan will not change until you explicitly apply a validated proposal." }]);
    onProposalClear();
    void refreshConversations();
    fetch(`${API_BASE}/assistant/status`, { credentials: "include", cache: "no-store" })
      .then(response => response.ok ? response.json() : null)
      .then(value => setStatus(value))
      .catch(() => setStatus(null));
  }, [projectId, floorNumber, refreshConversations, onProposalClear]);

  async function loadConversation(id: string) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/projects/${projectId}/assistant/conversations/${id}`, { credentials: "include", cache: "no-store" });
      if (!response.ok) throw new Error(await responseError(response));
      const transcript = await response.json();
      setConversationId(id);
      setItems(transcript.messages.map((entry: { role: "user" | "assistant"; content: string; proposal_json?: string | null }) => ({ role: entry.role, text: entry.content })));
      onProposalClear();
      const candidatesResponse = await fetch(`${API_BASE}/projects/${projectId}/assistant/conversations/${id}/proposals`, { credentials: "include", cache: "no-store" });
      const candidateRecords = candidatesResponse.ok ? await candidatesResponse.json() : [];
      if (Array.isArray(candidateRecords) && candidateRecords.length > 0) {
        const candidates: LayoutCandidateView[] = sortLayoutCandidates(candidateRecords.map((record: GenerationResponse["candidates"][number]) => ({
          proposalId: record.proposal_id, candidateKey: record.candidate_key, template: record.template,
          score: record.score, scoreBreakdown: record.score_breakdown, scoreVersion: record.score_version,
          searchStatus: record.search_status, utilization: record.utilization,
          circulationComponents: record.circulation_components, proposal: record.proposal,
          status: record.status, validationIssues: record.validation_issues,
        })));
        const first = candidates[0];
        onProposalPreview({ proposalId: first.proposalId, proposal: first.proposal, status: first.status,
          validationIssues: first.validationIssues, candidates, candidateKey: first.candidateKey });
      } else {
        const proposalMessage = [...transcript.messages].reverse().find((entry: { proposal_json?: string | null; proposal_id?: string | null }) => entry.proposal_json && entry.proposal_id);
        if (proposalMessage) {
          const proposalResponse = await fetch(`${API_BASE}/projects/${projectId}/assistant/proposals/${proposalMessage.proposal_id}`, { credentials: "include", cache: "no-store" });
          if (proposalResponse.ok) {
            const record = await proposalResponse.json();
            onProposalPreview({
              proposalId: record.id,
              proposal: JSON.parse(record.proposal_json) as LayoutProposal,
              status: record.status,
              validationIssues: JSON.parse(record.validation_issues_json || "[]"),
            });
          }
        }
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load conversation.");
    } finally { setBusy(false); }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    const value = message.trim();
    if (!value || busy) return;
    setItems(current => appendConversationMessage(current, { role: "user", text: value }));
    setMessage("");
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/projects/${projectId}/assistant/message`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify({ message: value, floor_number: floorNumber, ...(conversationId ? { conversation_id: conversationId } : {}) }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result: AssistantResult = await response.json();
      setConversationId(result.conversation_id);
      setItems(current => appendConversationMessage(current, { role: "assistant", text: result.reply, result }));
      if (result.response_type === "layout_proposal" && result.proposal?.kind === "layout_proposal" && result.proposal_id) {
        onProposalPreview({
          proposalId: result.proposal_id,
          proposal: result.proposal.details as unknown as LayoutProposal,
          status: result.proposal_metadata?.status ?? "draft",
          validationIssues: result.proposal_metadata?.validation_issues ?? [],
        });
      }
      await refreshConversations();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to contact the design assistant.");
    } finally { setBusy(false); }
  }

  async function generateOptions() {
    const value = message.trim();
    if (!value || busy) return;
    setItems(current => appendConversationMessage(current, { role: "user", text: value }));
    setMessage("");
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/projects/${projectId}/assistant/layout-generation`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify({ message: value, floor_number: floorNumber, ...(conversationId ? { conversation_id: conversationId } : {}) }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result: GenerationResponse = await response.json();
      setConversationId(result.conversation_id);
      const assistantResult: AssistantResult = {
        reply: result.reply, intent: "layout_generation", clarifying_questions: result.questions ?? [],
        suggestions: result.suggestions ?? [], proposal: null, changes_applied: false,
        engine: "local_llm", conversation_id: result.conversation_id,
        response_type: result.outcome === "layout_candidates" ? "layout_proposal" : "clarification",
        proposal_id: null, proposal_metadata: null,
      };
      setItems(current => appendConversationMessage(current, { role: "assistant", text: result.reply, result: assistantResult }));
      if (canPreviewLayoutCandidates(result.outcome, result.candidates)) {
        const candidates: LayoutCandidateView[] = sortLayoutCandidates(result.candidates.map(record => ({
          proposalId: record.proposal_id, candidateKey: record.candidate_key, template: record.template,
          score: record.score, scoreBreakdown: record.score_breakdown, scoreVersion: record.score_version,
          searchStatus: record.search_status, utilization: record.utilization,
          circulationComponents: record.circulation_components, proposal: record.proposal,
          status: record.status, validationIssues: record.validation_issues,
        })));
        const first = candidates[0];
        onProposalPreview({ proposalId: first.proposalId, proposal: first.proposal, status: first.status,
          validationIssues: first.validationIssues, candidates, candidateKey: first.candidateKey });
      }
      await refreshConversations();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to generate floor-plan options.");
    } finally { setBusy(false); }
  }

  const engineLabel = status?.code === "ready" ? "LOCAL MODEL READY" : status?.enabled ? "LOCAL MODEL UNAVAILABLE · RULES FALLBACK" : "LOCAL RULES FALLBACK";
  return <section className="design-assistant" aria-label="BrahmaAI design assistant">
    <div className="design-analysis-heading">
      <div><span className="card-kicker">BRAHMAAI · DESIGN ASSISTANT</span><h3>Describe what you have in mind</h3></div>
      <span className="assistant-engine">{engineLabel}</span>
    </div>
    <p className="inspector-help">Chat can use deterministic rules when the local model is unavailable. Generating floor-plan options requires the configured local model; it never switches to cloud AI. Generated layouts remain drafts until you explicitly apply one.</p>
    {conversations.length > 0 && <label className="assistant-conversation-select">Previous conversation<select value={conversationId ?? ""} onChange={event => { if (event.target.value) void loadConversation(event.target.value); else { setConversationId(null); setItems([]); onProposalClear(); } }} disabled={busy}>
      <option value="">New conversation</option>
      {conversations.filter(item => item.floor_number === floorNumber).map(item => <option key={item.id} value={item.id}>{item.title} · {item.message_count} messages</option>)}
    </select></label>}
    <div className="assistant-transcript" aria-live="polite">
      {items.map((item, index) => <article className={`assistant-message ${item.role}`} key={`${item.role}-${index}`}>
        <span className="assistant-role">{item.role === "user" ? "YOU" : "BRAHMAAI"}</span>
        <p>{item.text}</p>
        {item.result && <>
          <small className="assistant-message-engine">{item.result.engine === "local_llm" ? `LOCAL MODEL${item.result.model ? ` · ${item.result.model}` : ""}` : "DETERMINISTIC RULES"}</small>
          {item.result.clarifying_questions.length > 0 && <div className="assistant-detail"><strong>DETAILS NEEDED</strong><ul>{item.result.clarifying_questions.map(question => <li key={question}>{question}</li>)}</ul></div>}
          {item.result.suggestions.length > 0 && <div className="assistant-detail"><strong>SUGGESTIONS</strong><ul>{item.result.suggestions.map(suggestion => <li key={suggestion}>{suggestion}</li>)}</ul></div>}
          {item.result.proposal && <div className="assistant-proposal"><strong>{item.result.proposal.title}</strong><small>{item.result.proposal.kind === "layout_proposal" ? "Editable draft shown below" : "Brief only · User approval required"}</small></div>}
        </>}
      </article>)}
    </div>
    {error && <p className="assistant-error" role="alert">{error}</p>}
    <form className="assistant-compose" onSubmit={send}>
      <label className="sr-only" htmlFor="assistant-message">Message the design assistant</label>
      <textarea id="assistant-message" value={message} maxLength={2000} rows={2} onChange={event => setMessage(event.target.value)} placeholder="e.g. Design a 3 bedroom, 2 bathroom home…" disabled={busy}/>
      <div className="assistant-compose-actions">
        <button className="studio-tool" disabled={busy || !message.trim()}>{busy ? "Thinking…" : "Send ↗"}</button>
        <button type="button" className="studio-tool active" disabled={busy || !message.trim()} onClick={() => void generateOptions()}>{busy ? "Generating…" : "Generate floor-plan options"}</button>
      </div>
    </form>
  </section>;
}
