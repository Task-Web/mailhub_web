# File Storage Migration Guide

This guide explains how to move from base64 attachments to backend file storage.
The goal: upload files once, store them under `backend/files/<user_id>/`, and
reference them by URL in mail state.

## Target behavior
- Uploads go to `POST /api/files` (multipart/form-data).
- Files are stored under `backend/files/<user_id>/`.
- File metadata is returned with a stable URL (`/api/files/<stored_name>`).
- Mail attachments store that URL, not base64 data.
- Files can be listed with `GET /api/files` and fetched via `GET /api/files/{filename}`.

## Backend changes (FastAPI)
1. Add a files root in config (default `FILES_DIR=files`).
2. Implement a file store helper:
   - Create `backend/files/<user_id>/` on demand.
   - Save uploads as `<id>__<original_name>` to avoid collisions.
   - Return metadata: `id`, `name`, `size`, `type`, `url`, `filename`.
3. Add endpoints:
   - `POST /api/files` accepts `files` (repeatable) and returns metadata.
   - `GET /api/files` lists user files.
   - `GET /api/files/{filename}` serves a file scoped by cookie.
4. Keep `get_user_id` for cookie scoping and guard against path traversal.

## Frontend changes (Vite + React)
1. Update the API client:
   - Detect `FormData` and skip `Content-Type: application/json`.
   - Add `uploadFiles(files)` that posts to `/files` with `FormData`.
2. Update compose/reply flows:
   - Replace `FileReader` base64 logic with `uploadFiles`.
   - Store returned metadata in `attachments`.
3. Resolve file URLs at render time:
   - If `url` is relative (e.g., `/api/files/...`), prepend the API origin.
   - Leave `http(s)` and `data:` URLs unchanged.

## Checklist for other sites
- [ ] Add `/api/files` upload, list, and fetch endpoints.
- [ ] Store files under `files/<user_id>/` with safe names.
- [ ] Return `url` values that the frontend can resolve.
- [ ] Switch frontend attachments to upload-first, then reference URLs.
- [ ] Confirm cookies are sent (`credentials: "include"` on fetch).
- [ ] Verify Nginx/client upload limits (`client_max_body_size`).
- [ ] Update documentation (`API.md`, state references, README).

## Notes
- Existing base64 attachments still render; only new uploads use file URLs.
- File cleanup is optional and can be added later (e.g., delete unused files).
