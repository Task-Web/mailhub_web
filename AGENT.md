# Agent guidelines

Goal: let an automation agent drive experiments with fully functional UI using the cookie-scoped backend.

## Identity
- The backend issues a `user_id` cookie on first request. Include cookies (`credentials: include` or `-b/-c` in curl/httpie) so each agent run stays scoped.
- No authentication is required; avoid adding auth unless explicitly requested.

## API usage
- Base URL: `http://localhost:8000/api` (override with `VITE_API_BASE` for the frontend or custom base URLs in scripts).
- Preferred endpoints:
  - `GET /state` to read current state.
  - `PUT /state` to fully replace: body `{ "data": {...}, "note": "why" }`.
  - `PATCH /state` to merge into existing state without erasing siblings.
  - `DELETE /state` to reset.
  - `GET /info` to inspect headers, path, and runtime environment.
- Handle non-2xx by reading `{ "detail": "...", "request_id": "..." }`.

## State conventions
- Store experiment inputs under `data`; keep human-readable context in `note`.
- Use structured keys (e.g., `runs`, `config`, `metrics`) to keep merging predictable.
- Prefer PATCH during iterative tuning to avoid losing prior values.

## Operational tips
- When running locally with the frontend, ensure the backend has CORS allowing the origin (`CORS_ORIGINS` env).
- For multiple concurrent agents, isolate with separate cookie jars (e.g., `curl -c jar1 -b jar1 ...`).
- Keep documentation up to date (`API.md`, `docs/EXTENDING.md`, `STATE.md`) after adding endpoints or changing shapes.
- MCP: Streamable HTTP endpoint at `/mcp` exposes tools mirroring the REST API (`get_state`, `replace_state`, `patch_state`, `reset_state`, `info`) plus mail tools (`mail_get_state`, `mail_send`, `mail_reply`, `mail_save_draft`, `mail_delete_draft`, `mail_update_email`, `mail_bulk_update`, `mail_archive`, `mail_delete`, `mail_empty_trash`, `mail_create_label`, `mail_toggle_label`). Pass `user_cookie` to reuse a specific state; omit to create a new cookie-scoped state. Suitable for remote MCP clients that cannot share stdio.
