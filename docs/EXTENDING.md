# Extending the base site

## Backend (FastAPI)
- **Add new state fields**: extend `app/models.py` (`UserState.data` can stay free-form). For stronger typing, introduce specific Pydantic models and update `StateRequest`/`StatePatchRequest` in `app/schemas.py`.
- **New endpoints**: add route functions in `app/main.py` or a dedicated router module. Reuse `get_user_id` to stay cookie-scoped. Tag endpoints for OpenAPI and update `API.md`.
- **Persistence**: swap `StateStore` with a different implementation (e.g., Redis, file-backed). Keep the async interface (`get_state`, `replace_state`, `patch_state`, `reset_state`, `delete_state`).
- **Middleware**: add logging/metrics in `app/main.py`. The `x-request-id` middleware is a placeholder; extend it to integrate tracing if needed.
- **Validation**: enforce schemas in `StateRequest`/`StatePatchRequest` to constrain experiment inputs.

## Frontend (Vite + React)
- **API base**: set `VITE_API_BASE` in `.env` to point to the backend.
- **New panels**: create components under `src/` and wire them into `App.jsx`. Use `apiClient.js` for calls and keep `credentials: "include"` so cookies flow through.
- **State visualizers**: replace the `<pre>` blocks with custom renderers (tables, charts) that consume the state payload.
- **Styling**: styles live in `src/App.css` and `src/index.css`. Keep the purposeful typography and background; feel free to introduce theme tokens if growing.

## Experiments workflow
- Use the PATCH endpoint to iteratively merge experiment parameters without wiping the entire state.
- Use the `note` field to annotate why a state change occurred (frontends can surface it prominently).
- Use `/api/info` to confirm which headers/cookies are reaching the backend and to debug CORS.

## Testing
- Backend: add `pytest` cases under `backend/tests/` (not included yet) using `httpx.AsyncClient` against the FastAPI app.
- Frontend: add React Testing Library tests under `frontend/src/__tests__/`.

## Documentation
- Keep `API.md` aligned with actual routes and update examples when shapes change.
- Summarize user-facing interactions in `README.md`; deeper engineering detail here in `docs/`.
