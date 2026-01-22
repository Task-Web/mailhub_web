# API Reference

Base path: `/api`

All endpoints assume cookie-based user identification. A new `user_id` cookie is issued on first request. Include credentials on cross-site calls.

## Health
- `GET /health` — simple liveness probe. Response: `{"status":"ok"}`.

## State
- `GET /state` — fetch current state for this cookie.
  - Response `200`: `{ "user_id": "uuid", "state": { "meta": {...}, "data": {...}, "note": "..." } }`
- `PUT /state` — replace the entire state payload.
  - Body: `{ "data": { ... }, "note": "optional string" }`
  - Response: same shape as GET.
- `PATCH /state` — deep-merge into the existing `data` field.
  - Body: `{ "data": { ... }, "note": "optional string" }`
  - Response: merged state.
- `DELETE /state` — reset state to a new blank object and fresh metadata.
  - Response: `{ "user_id": "...", "state": { "meta": {...}, "data": {}, "note": null } }`

Notes:
- `meta.version` increments on patch/merge operations; resets on replace/reset.
- `meta.created_at` and `updated_at` are UTC ISO timestamps.
- Default state includes the MailHub-style mail dataset under `data` (see `STATE.md`).

## Info
- `GET /info` — return runtime and request context for debugging.
  - Response example:
    ```json
    {
      "app_name": "Base Experiment Backend",
      "python_version": "3.11.7",
      "env": { "python_version": "3.11.7", "platform": "Linux-...", "env_mode": "dev" },
      "request": { "client": "127.0.0.1", "headers": {...}, "path": "/api/info", "method": "GET", "user_id": "..." }
    }
    ```

## Proxy
- `GET /proxy?url=https://...` - fetch a remote asset and return it from the same origin.
  - Intended for rendering cross-origin images/styles inside email HTML.

## Usage examples

`curl` (remember cookies):
```bash
curl -i -c cookies.txt http://localhost:8000/api/state
curl -b cookies.txt -X PATCH http://localhost:8000/api/state \
  -H "Content-Type: application/json" \
  -d '{"data": {"step": 2, "parameters": {"alpha": 0.1}}, "note": "patched via curl"}'
curl -b cookies.txt http://localhost:8000/api/info
```

`httpie`:
```bash
http --print=HBhb GET :8000/api/state
http --print=HBhb PATCH :8000/api/state data:='{"foo": "bar"}'
http DELETE :8000/api/state
```

## Mail
Mail endpoints operate on the `data` envelope and return `{ "user_id": "...", "mail": { ... } }`.

- `GET /mail/state` — fetch mail state for this cookie.
- `POST /mail/send` — send a new message.
  - Body: `{ "to": "...", "cc": "...", "bcc": "...", "subject": "...", "body": "...", "attachments": [], "draft_id": "optional" }`
- `POST /mail/reply` — reply to an existing thread.
  - Body: `{ "thread_id": "...", "body": "...", "reply_all": false, "reply_to_id": "optional", "attachments": [] }`
- `POST /mail/draft` — create or update a draft.
  - Body: `{ "draft_id": "optional", "to": "...", "cc": "...", "bcc": "...", "subject": "...", "body": "...", "attachments": [] }`
  - Response: includes `draft_id` when created.
- `DELETE /mail/draft/{draft_id}` — delete a draft.
- `PATCH /mail/email/{email_id}` — update a single email.
  - Body: `{ "updates": { "read": true, "starred": false, "folder": "trash" } }`
- `POST /mail/bulk` — update multiple emails.
  - Body: `{ "email_ids": ["..."], "updates": { "read": true } }`
- `POST /mail/archive` — move emails to `all-mail`.
  - Body: `{ "email_ids": ["..."] }`
- `POST /mail/delete` — move to trash (or delete permanently if already in trash).
  - Body: `{ "email_ids": ["..."] }`
- `POST /mail/empty-trash` — delete all trash.
- `POST /mail/labels` — create a label.
  - Body: `{ "name": "New label", "color": "#9ca3af" }`
- `POST /mail/email/{email_id}/labels` — add/remove/toggle labels.
  - Body: `{ "label_id": "...", "action": "toggle" }`

## Files
File endpoints are cookie-scoped and map to `backend/files/<user_id>/`.

- `POST /files` — upload files (multipart/form-data).
  - Field name: `files` (repeatable).
  - Response:
    ```json
    {
      "user_id": "uuid",
      "files": [
        {
          "id": "abc123",
          "name": "notes.pdf",
          "size": "1.2 MB",
          "type": "application/pdf",
          "url": "/api/files/abc123__notes.pdf",
          "filename": "abc123__notes.pdf"
        }
      ]
    }
    ```
- `GET /files` — list files for the current user (same response shape as upload).
- `GET /files/{filename}` — fetch a file by stored filename for the current user.

## Error shape
- HTTP errors return `{ "detail": "message", "request_id": "<uuid>" }`.
- Non-2xx responses keep the `user_id` cookie intact.
