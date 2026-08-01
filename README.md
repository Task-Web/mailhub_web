# Base Experiment Site

Cookie-scoped experiment playground built with FastAPI (backend) and Vite + React (frontend). Each visitor gets an isolated state slice tracked via a cookie; state can be read, replaced, patched, or reset through well-documented APIs and a MailHub-style mail UI driven entirely from backend state.

## Quick start

Backend (uv):

```bash
cd backend
uv venv
uv pip install -r requirements.txt
uv run uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev -- --host --port 5173
```

Open the frontend at http://localhost:5173. The UI calls the backend at `http://localhost:8000/api` (overridable via `VITE_API_BASE`).

## Docker compose
```bash
docker compose up --build
```
Open http://localhost (nginx reverse proxy). It routes `/api` and `/mcp` to the backend and everything else to the production frontend container.

## Highlights
- Per-user state keyed by cookie; no login required.
- REST endpoints for state lifecycle (`GET/PUT/PATCH/DELETE /api/state`) plus mail actions under `/api/mail/*`.
- MCP server (Streamable HTTP) mounted at `/mcp` mirroring the REST operations; accepts `user_cookie` to target a specific state, plus mail-specific tools.
- You can pin identity via querystring `?cookie=your-id` on any API call; the backend will also set that as the response cookie.
- MailHub-style frontend UI built with Tailwind CSS.
- **New-email notification toasts** – opt-in via `"enable_notifications": "on"` in state data; the frontend polls for inbox changes every 5 seconds and displays a slide-in toast when new mail arrives. Disabled by default for backward compatibility.
- Mail state seeded with sample conversations, labels, and attachments (see `STATE.md`).
- File uploads stored under `backend/files/<user_id>/` and served from `/api/files`.
- Auto-generated OpenAPI docs at `/api/docs` and curated `API.md`.
- Extensible patterns documented in `docs/EXTENDING.md`.

## Repository layout
- `backend/`: FastAPI app, config, and state store.
- `frontend/`: Vite + React UI with API client.
- `docs/`: Guides for extending the backend/frontend and experiments.
- `API.md`: Endpoint reference with examples.
- `AGENT.md`: Notes for automation/agent integrations.
- MCP Streamable HTTP endpoint at `/mcp` (tools: `get_state`, `replace_state`, `patch_state`, `reset_state`, `info`).

## Testing
- Backend (uv): `cd backend && uv pip install -r requirements.txt pytest pytest-asyncio httpx && uv run pytest`
- Frontend: recommended stack `vitest` + Testing Library (see `docs/TESTING.md` for setup).

## Environment variables
- `API_PREFIX` (default `/api`)
- `COOKIE_NAME` (default `user_id`)
- `COOKIE_MAX_AGE` (seconds, default 30d)
- `CORS_ORIGINS` (JSON list, default `["http://localhost:5173"]`)
- `DEBUG` (boolean)
- `FILES_DIR` (default `files`, resolved relative to `backend/`)
- `STATE_TTL_SECONDS` (idle TTL, default `43200` / 12 hours)
- `STATE_MAX_ENTRIES` (default `1000`)
- `STATE_MAX_TOTAL_BYTES` (serialized state budget, default `1073741824` / 1024 MiB)

Set them in `backend/.env` (see `backend/.env.example`).

## Development tips
- Use `ruff`/`black` (optional) for backend formatting; `eslint`/`prettier` for frontend.
- Keep API shapes in sync with `API.md`; run the app and verify Swagger UI after changes.
- When adding state fields, update the Pydantic models and the frontend preview/editor.
