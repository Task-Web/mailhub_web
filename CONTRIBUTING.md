# Contributing

- Use feature branches and keep commits focused (one concern per commit).
- Backend: follow FastAPI style in `backend/app`; prefer async endpoints. Run formatters (`ruff`, `black`) if available.
- Frontend: follow the existing API client pattern (`credentials: "include"`). Keep styles purposeful—avoid default system fonts for new panels.
- Update docs (`README.md`, `API.md`, `docs/EXTENDING.md`, `AGENT.md`) when changing API shapes or workflows.
- Add or update tests when touching logic in the state store or API routes.
