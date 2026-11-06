# Local LLM Gateway and Design Assistant (WP5B)

BrahmaAI Studio supports an **optional, local-only Ollama-compatible runtime**. The FastAPI backend is the only component that contacts the model endpoint. The browser cannot select a model, change the endpoint, issue runtime tool calls, or invoke a cloud fallback.

## Runtime prerequisites

1. Install and start a compatible local model runtime separately.
2. Install a model in that runtime separately; this package does not install Ollama, download model weights or manage model lifecycle.
3. Configure the backend environment:

```dotenv
LOCAL_LLM_ENABLED=true
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434
LOCAL_LLM_MODEL=qwen2.5:7b
LOCAL_LLM_CONNECT_TIMEOUT_SECONDS=3
LOCAL_LLM_READ_TIMEOUT_SECONDS=45
LOCAL_LLM_MAX_RESPONSE_BYTES=1000000
LOCAL_LLM_MAX_HISTORY_MESSAGES=12
LOCAL_LLM_MAX_HISTORY_CHARACTERS=12000
```

`LOCAL_LLM_ENABLED` defaults to `false`; no model is assumed by default. The endpoint must use `http` or `https`, must not contain URL user-info credentials, and must be reachable from the API process. The endpoint and model identifier are server-side settings and are not accepted from API request bodies.

### Docker networking

Inside a container, `127.0.0.1` refers to that same container. If the model runtime is another Compose service, set `LOCAL_LLM_BASE_URL` to its service hostname and port. If the model runtime runs on the host, configure a host-reachable address supported by the deployment environment. Do not expose an unauthenticated model endpoint to untrusted networks.

## Readiness

`GET /api/v1/assistant/status` requires an authenticated session and returns only:

```json
{
  "enabled": true,
  "configured": true,
  "reachable": true,
  "model_available": true,
  "code": "ready"
}
```

Stable status codes are `disabled`, `model_not_configured`, `model_unavailable`, and `ready`. The response intentionally does not disclose the configured URL, hostname, port, internal network topology or filesystem paths. The backend checks the runtime's `/api/tags` response for the configured model.

## Conversations

All endpoints are authenticated and project-owner-scoped.

- `POST /api/v1/projects/{project_id}/assistant/message` — send a message; requires `X-CSRF-Token`.
- `GET /api/v1/projects/{project_id}/assistant/conversations?limit=20` — list up to 100 conversations for the project.
- `GET /api/v1/projects/{project_id}/assistant/conversations/{conversation_id}` — load a transcript.

A conversation is bound to one floor. Reusing it with another floor returns HTTP 409 with `conversation_floor_mismatch`; select or create a conversation for the target floor. Message input is limited to 2,000 characters. Model context uses at most the newest 12 messages and 12,000 characters by default. Assistant transcript content is limited to 12,000 characters.

If local inference is disabled, unconfigured, unreachable, or returns malformed output, the existing deterministic WP5A rules engine is used and the response is labeled `engine=local_rules`. A successful model response is labeled `engine=local_llm` and includes the configured model name. No cloud provider is contacted.

## Layout proposals and approval

A model-generated layout proposal is stored as a separate record with one of four states:

- `draft` — passes schema and deterministic preflight geometry checks.
- `needs_revision` — schema or geometry issues must be corrected.
- `applied` — the user explicitly applied the proposal after fresh server-side validation.
- `rejected` — the user explicitly rejected the proposal.

Proposal endpoints:

- `GET /api/v1/projects/{project_id}/assistant/proposals/{proposal_id}` — retrieve an owned proposal.
- `POST /api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/apply` — submit edited proposal JSON for fresh validation and atomic application; requires CSRF.
- `POST /api/v1/projects/{project_id}/assistant/proposals/{proposal_id}/reject` — reject a pending proposal; requires CSRF.

Apply rechecks project ownership, pending state, the current plot/floor fingerprint, room polygon validity, plot containment, room overlap, room-name uniqueness and opening edge/overlap rules. If the plot or saved floor changed since generation, Apply returns HTTP 409 `proposal_stale`; the record becomes `needs_revision` and saved rooms remain untouched. Invalid edited geometry returns HTTP 422 `proposal_invalid` and does not replace saved rooms. Repeated actions return HTTP 409 `proposal_not_pending`. Apply updates the floor rooms and proposal state in one database transaction. Reject changes proposal state only.

The frontend proposal preview is independent of the editor's saved-room state and never participates in autosave. Only the Apply endpoint can replace saved floor geometry.

## Privacy and architectural boundary

Only the selected project's plot and selected-floor room geometry/openings plus bounded conversation history are sent to the configured local model. Prompt bodies and transcripts are not written to application logs. Model output is untrusted JSON: it cannot execute code, SQL, shell commands, URLs, tools or filesystem actions. All geometry calculations and validation are deterministic backend operations.

BrahmaAI Studio remains a conceptual architectural planning aid. It does not certify structural safety, MEP design, accessibility, fire/egress safety, building-code compliance or construction readiness. Generated dimensions and layouts require qualified professional review before construction.
