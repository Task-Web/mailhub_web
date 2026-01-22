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
- `body` (string): HTML allowed.
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
