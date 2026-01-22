# Testing strategy

## Backend (FastAPI)
- Framework: `pytest` + `pytest-asyncio`, HTTP client: `httpx.AsyncClient`.
- Location: `backend/tests/`.
  - `conftest.py` sets up an async client mounted on the FastAPI app.
  - `test_state_api.py` covers health, cookie issuance, state CRUD/merge, and info endpoint.
- Run:
```bash
cd backend
uv venv
uv pip install -r requirements.txt pytest pytest-asyncio httpx
uv run pytest
```

## Frontend (Vite + React)
- Framework: `vitest` + `@testing-library/react` + `@testing-library/jest-dom`.
- Location: `frontend/src/__tests__/`.
  - Example: `App.test.jsx` renders the app with mocked `fetch` responses to simulate backend calls.
  - Keep shared test setup in `frontend/src/setupTests.js` (adds jest-dom matchers).
- Run:
```bash
cd frontend
npm install
npm run test
```

### Frontend test checklist
- Mock network calls (`global.fetch`) so tests stay fast and offline.
- Assert visible text and state summaries (e.g., user cookie pill, note/status messages).
- For API helpers, spy on `fetch` to verify HTTP verbs and payloads.
- Prefer `screen.findBy...` to await async state after effects fire.

## Coverage expectations
- Each backend route should have at least one test verifying success, shape, and cookie behavior.
- Each frontend view or helper should have a unit test that exercises its main behavior and error handling paths.
