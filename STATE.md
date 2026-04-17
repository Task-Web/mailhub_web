# MailHub State Reference

This document describes the per-user state used by `MailHub`. The backend stores a `UserState`
envelope with a free-form `data` object. The UI uses this to drive the MailHub-style mail demo.

All timestamps are ISO 8601 strings (UTC).

## State envelope (UserState)
- `meta.created_at` (string): When the state was created.
- `meta.updated_at` (string): Last update time (patch/merge).
- `meta.version` (number): Incremented on each patch/merge.
- `meta.type` (string): Currently `"unrestricted"`.
- `data` (object): Free-form container for experiment data and UI features.
- `note` (string or null): Optional human-readable note describing the last change.

## Default data shape
The backend initializes `data` with mail state:
- `user` (object): Mailbox owner profile.
- `emails` (Email[]): Messages across folders.
- `labels` (Label[]): User-defined labels.
- `drafts` (array): Reserved for future draft metadata (currently unused).

### User
- `userId` (string)
- `username` (string)
- `email` (string)
- `avatar` (string): Image URL.

### Email
- `id` (string)
- `threadId` (string)
- `from` (object): Sender (name/email/avatar).
- `to` (Contact[])
- `cc` (Contact[])
- `bcc` (Contact[])
- `subject` (string)
- `body` (string): Email body content.
- `bodyFormat` (string, optional): `text`, `html`, or `markdown`. If omitted, the frontend falls back to content sniffing for backward compatibility.
- `snippet` (string): Text preview.
- `timestamp` (string): ISO timestamp.
- `read` (boolean)
- `starred` (boolean)
- `important` (boolean)
- `labels` (string[]): Label ids.
- `category` (string): `primary`, `social`, or `promotions`.
- `folder` (string): `inbox`, `sent`, `drafts`, `spam`, `trash`, `all-mail`.
- `attachments` (Attachment[])

### Contact
- `name` (string)
- `email` (string)
- `avatar` (string, optional)

### Attachment
- `id` (string)
- `name` (string)
- `size` (string)
- `type` (string)
- `url` (string): Data URL, external link, or `/api/files/<stored_name>` served by the backend.

Supported `type` values for inline previews:
- `image/png`
- `image/jpeg`
- `image/jpg`
- `image/gif`
- `image/webp`
- `image/bmp`
- `image/svg+xml`

All other types render a generic file icon; clicking downloads/opens the file.

### Label
- `id` (string)
- `name` (string)
- `color` (string): Hex color.

## Dynamic events (optional)

When the state is initialized via `PUT /api/state`, two optional top-level keys
in `data` enable dynamic, time-based or action-triggered email delivery.  These
keys are **stripped** from the stored state so the frontend never sees them.

### `time_data` (TimedEmail[])
Emails that arrive automatically after a delay.  Each item is a standard Email
object with one extra field:

- `arrive_after_s` (number): Seconds after state init when this email appears
  in the user's inbox.

### `action_data` (ActionRule[])
Rules that fire *once* when the user sends or replies to an email matching
certain conditions.

- `trigger` (object):
  - `to_email` (string): Recipient email to watch (case-insensitive).
  - `keywords` (string[][]): List of keyword-groups (**OR-of-ANDs**).
    Each group is a list of strings that must ALL appear in subject + body;
    the trigger fires if ANY group is fully matched.
    Example: `[["meeting","schedule"],["45 min"]]` means
    `(meeting AND schedule) OR (45 min)`.
- `delay_s` (number): Seconds to wait after trigger match before injecting.
- `email` (Email): The email to inject into the inbox.

### Backward compatibility
If neither `time_data` nor `action_data` is present in the state, the system
behaves exactly as before — no background tasks are started.


## Full example (UserState)
```json
{
  "meta": {
    "created_at": "2024-04-01T12:00:00+00:00",
    "updated_at": "2024-04-01T12:30:00+00:00",
    "version": 2,
    "type": "unrestricted"
  },
  "data": {
    "user": {
      "userId": "demo",
      "username": "User demo",
      "email": "user-demo@example.com",
      "avatar": "https://picsum.photos/100/100?random=101"
    },
    "emails": [
      {
        "id": "e1",
        "threadId": "t1",
        "from": { "name": "Alice Smith", "email": "alice@company.com", "avatar": "" },
        "to": [{ "name": "User demo", "email": "user-demo@example.com" }],
        "cc": [],
        "bcc": [],
        "subject": "Q4 Project Roadmap Update",
        "body": "Hi everyone, ...",
        "snippet": "Hi everyone, ...",
        "timestamp": "2024-04-01T12:00:00+00:00",
        "read": false,
        "starred": true,
        "important": true,
        "labels": ["l1"],
        "category": "primary",
        "folder": "inbox",
        "attachments": [{
          "id": "a1",
          "name": "roadmap_q4.pdf",
          "size": "2.4 MB",
          "type": "pdf",
          "url": "https://drive.google.com/uc?export=download&id=14NpKKC2atQs1r6hFIy51w6o9PQ_9Xf-G"
        }]
      }
    ],
    "labels": [
      { "id": "l1", "name": "Work", "color": "#ef4444" }
    ],
    "drafts": []
  },
  "note": "Mail: initialized"
}
```
