import hashlib
import html
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_LABELS = [
    {"id": "l1", "name": "Work", "color": "#ef4444"},
    {"id": "l2", "name": "Personal", "color": "#3b82f6"},
    {"id": "l3", "name": "Travel", "color": "#22c55e"},
    {"id": "l4", "name": "Finance", "color": "#eab308"},
]

_TAG_RE = re.compile(r"<[^>]+>")
_KNOWN_HTML_TAG_RE = re.compile(
    r"<(?:!doctype|/?(?:a|article|aside|b|blockquote|body|br|code|del|details|div|em|figcaption|figure|footer|h[1-6]|head|header|hr|html|i|iframe|img|li|main|nav|ol|p|pre|section|span|strong|style|summary|table|tbody|td|th|thead|tr|u|ul)\b)",
    re.IGNORECASE,
)

_BODY_FORMAT_ALIASES = {
    "html": "html",
    "text/html": "html",
    "text": "text",
    "plain": "text",
    "plaintext": "text",
    "plain-text": "text",
    "text/plain": "text",
    "markdown": "markdown",
    "md": "markdown",
    "text/markdown": "markdown",
}


def _seed_from_user_id(user_id: str) -> int:
    digest = hashlib.md5(user_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % 1000


def generate_id() -> str:
    return uuid.uuid4().hex[:8]


def build_snippet(body: str, limit: int = 100) -> str:
    text = body or ""
    # Strip quoted reply section before extracting snippet.
    text = re.sub(
        r'<div\s+class="gmail_quote".*',
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    cleaned = _TAG_RE.sub("", text)
    cleaned = re.sub(r"&[a-zA-Z0-9#]+;", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit]


def build_user_profile(user_id: str) -> Dict[str, str]:
    short_id = user_id.split("-")[0][:8]
    seed = _seed_from_user_id(user_id)
    return {
        "userId": short_id,
        "username": f"User {short_id}",
        "email": f"user-{short_id}@example.com",
        "avatar": f"https://picsum.photos/100/100?random={seed}",
    }


def normalize_recipients(value: Any) -> List[Dict[str, str]]:
    if isinstance(value, list):
        recipients = []
        for item in value:
            if isinstance(item, dict) and item.get("email"):
                recipients.append(
                    {
                        "name": item.get("name") or item["email"],
                        "email": item["email"],
                        "avatar": item.get("avatar"),
                    }
                )
            elif isinstance(item, str) and item.strip():
                recipients.append({"name": item.strip(), "email": item.strip()})
        return recipients
    if not value:
        return []
    recipients = []
    for part in str(value).split(","):
        trimmed = part.strip()
        if trimmed:
            recipients.append({"name": trimmed, "email": trimmed})
    return recipients


def normalize_attachments(value: Any) -> List[Dict[str, Any]]:
    attachments: List[Dict[str, Any]] = []
    if not isinstance(value, list):
        return attachments
    for attachment in value:
        if not isinstance(attachment, dict):
            continue
        attachment_id = attachment.get("id") or generate_id()
        url = attachment.get("url") or attachment.get("content_base64") or ""
        attachments.append(
            {
                "id": attachment_id,
                "name": attachment.get("name") or "attachment",
                "size": attachment.get("size") or "",
                "type": attachment.get("type") or attachment.get("content_type") or "",
                "url": url,
            }
        )
    return attachments


def normalize_body_format(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    return _BODY_FORMAT_ALIASES.get(value.strip().lower())


def body_looks_like_html(body: Any) -> bool:
    if not isinstance(body, str) or not body:
        return False
    return bool(_KNOWN_HTML_TAG_RE.search(body))


def infer_body_format(body: Any, body_format: Optional[str] = None) -> str:
    normalized = normalize_body_format(body_format)
    if normalized:
        return normalized
    return "html" if body_looks_like_html(body) else "text"


def text_to_html_fragment(body: Any) -> str:
    normalized = str(body or "").replace("\r\n", "\n").replace("\r", "\n")
    escaped = html.escape(normalized)
    return escaped.replace("\n", "<br>")


def body_to_html_fragment(body: Any, body_format: Optional[str] = None) -> str:
    resolved = infer_body_format(body, body_format)
    if resolved == "html":
        return str(body or "")
    return text_to_html_fragment(body)


def build_email(
    *,
    email_id: str,
    thread_id: str,
    from_contact: Dict[str, Any],
    to: List[Dict[str, Any]],
    cc: Optional[List[Dict[str, Any]]] = None,
    bcc: Optional[List[Dict[str, Any]]] = None,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    read: bool = False,
    starred: bool = False,
    important: bool = False,
    labels: Optional[List[str]] = None,
    category: str = "primary",
    folder: str = "inbox",
    attachments: Optional[List[Dict[str, Any]]] = None,
    body_format: Optional[str] = None,
) -> Dict[str, Any]:
    created_at = timestamp or datetime.now(timezone.utc)
    email_body = body or ""
    resolved_body_format = infer_body_format(email_body, body_format)
    return {
        "id": email_id,
        "threadId": thread_id,
        "from": from_contact,
        "to": to,
        "cc": cc or [],
        "bcc": bcc or [],
        "subject": subject or "(no subject)",
        "body": email_body,
        "bodyFormat": resolved_body_format,
        "snippet": build_snippet(email_body),
        "timestamp": created_at.isoformat(),
        "read": read,
        "starred": starred,
        "important": important,
        "labels": labels or [],
        "category": category,
        "folder": folder,
        "attachments": attachments or [],
    }


def build_seed_emails(user: Dict[str, str]) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    emails: List[Dict[str, Any]] = []

    thread1 = generate_id()
    emails.append(
        build_email(
            email_id=generate_id(),
            thread_id=thread1,
            from_contact={
                "name": "Alice Smith",
                "email": "alice@company.com",
                "avatar": "https://picsum.photos/100/100?random=2",
            },
            to=[{"name": user["username"], "email": user["email"], "avatar": user["avatar"]}],
            subject="Q4 Project Roadmap Update",
            body=(
                "Hi everyone, <br><br>Here is the updated roadmap for Q4. "
                "Please review the attached document.<br><br>Best,<br>Alice"
            ),
            timestamp=now - timedelta(minutes=30),
            read=False,
            starred=True,
            important=True,
            labels=["l1"],
            category="primary",
            folder="inbox",
            attachments=[
                {
                    "id": generate_id(),
                    "name": "img.png",
                    "size": "2.4 MB",
                    "type": "image/png",
                    "url": "https://picsum.photos/400/300?random=attach1",
                }
            ],
        )
    )

    thread2 = generate_id()
    emails.append(
        build_email(
            email_id=generate_id(),
            thread_id=thread2,
            from_contact={
                "name": "Bob Jones",
                "email": "bob@friends.com",
                "avatar": "https://picsum.photos/100/100?random=3",
            },
            to=[{"name": user["username"], "email": user["email"]}],
            subject="Lunch tomorrow?",
            body="Hey! Are we still on for lunch tomorrow at 12?",
            timestamp=now - timedelta(days=1),
            read=True,
            labels=["l2"],
            category="primary",
            folder="inbox",
            attachments=[
                {
                    "id": generate_id(),
                    "name": "roadmap_q4.pdf",
                    "size": "2.4 MB",
                    "type": "pdf",
                    "url": "https://drive.google.com/uc?export=download&id=14NpKKC2atQs1r6hFIy51w6o9PQ_9Xf-G",
                }
            ]
        )
    )
    emails.append(
        build_email(
            email_id=generate_id(),
            thread_id=thread2,
            from_contact={
                "name": user["username"],
                "email": user["email"],
                "avatar": user["avatar"],
            },
            to=[{"name": "Bob Jones", "email": "bob@friends.com"}],
            subject="Re: Lunch tomorrow?",
            body="Yes! Let's go to that new burger place.",
            timestamp=now - timedelta(hours=23),
            read=True,
            labels=["l2"],
            category="primary",
            folder="sent",
        )
    )
    emails.append(
        build_email(
            email_id=generate_id(),
            thread_id=thread2,
            from_contact={
                "name": "Bob Jones",
                "email": "bob@friends.com",
                "avatar": "https://picsum.photos/100/100?random=3",
            },
            to=[{"name": user["username"], "email": user["email"]}],
            subject="Re: Lunch tomorrow?",
            body="Perfect. See you there!",
            timestamp=now - timedelta(hours=2),
            read=False,
            labels=["l2"],
            category="primary",
            folder="inbox",
        )
    )

    emails.append(
        build_email(
            email_id=generate_id(),
            thread_id=generate_id(),
            from_contact={
                "name": "LinkedIn",
                "email": "notifications@linkedin.com",
                "avatar": "https://picsum.photos/100/100?random=4",
            },
            to=[{"name": user["username"], "email": user["email"]}],
            subject="You appeared in 5 searches this week",
            body="People are looking for you. See who viewed your profile.",
            timestamp=now - timedelta(hours=5),
            read=False,
            category="social",
            folder="inbox",
        )
    )

    emails.append(
        build_email(
            email_id=generate_id(),
            thread_id=generate_id(),
            from_contact={
                "name": "Amazon",
                "email": "store-news@amazon.com",
                "avatar": "https://picsum.photos/100/100?random=5",
            },
            to=[{"name": user["username"], "email": user["email"]}],
            subject="Your order has shipped",
            body="Your package is on the way. Track your package here.",
            timestamp=now - timedelta(hours=48),
            read=True,
            category="promotions",
            folder="inbox",
        )
    )

    emails.append(
        build_email(
            email_id=generate_id(),
            thread_id=generate_id(),
            from_contact={
                "name": "Prince Henry",
                "email": "money@rich.com",
                "avatar": "https://picsum.photos/100/100?random=6",
            },
            to=[{"name": user["username"], "email": user["email"]}],
            subject="URGENT BUSINESS PROPOSAL",
            body="I have 50 million dollars for you...",
            timestamp=now - timedelta(hours=100),
            read=False,
            category="primary",
            folder="spam",
        )
    )

    emails.append(
        build_email(
            email_id=generate_id(),
            thread_id=generate_id(),
            from_contact={
                "name": "Newsletter",
                "email": "news@letter.com",
                "avatar": "https://picsum.photos/100/100?random=7",
            },
            to=[{"name": user["username"], "email": user["email"]}],
            subject="Weekly Digest",
            body="Here is your weekly digest...",
            timestamp=now - timedelta(hours=200),
            read=True,
            category="promotions",
            folder="trash",
        )
    )

    return emails


def build_default_mail_state(user_id: Optional[str] = None) -> Dict[str, Any]:
    resolved_user = user_id or "demo-user"
    user = build_user_profile(resolved_user)
    return {
        "user": user,
        "emails": build_seed_emails(user),
        "labels": [label.copy() for label in DEFAULT_LABELS],
        "drafts": [],
    }


def ensure_mail_state(data: Any, user_id: str) -> Tuple[Dict[str, Any], bool]:
    changed = False
    if not isinstance(data, dict):
        data = {}
        changed = True

    if not isinstance(data.get("user"), dict):
        data["user"] = build_user_profile(user_id)
        changed = True

    if not isinstance(data.get("labels"), list):
        data["labels"] = [label.copy() for label in DEFAULT_LABELS]
        changed = True

    if not isinstance(data.get("emails"), list):
        data["emails"] = build_seed_emails(data["user"])
        changed = True

    if not isinstance(data.get("drafts"), list):
        data["drafts"] = []
        changed = True

    return data, changed


def find_email(emails: List[Dict[str, Any]], email_id: str) -> Optional[Dict[str, Any]]:
    for email in emails:
        if email.get("id") == email_id:
            return email
    return None


def update_email_fields(email: Dict[str, Any], updates: Dict[str, Any]) -> None:
    allowed = {"read", "starred", "important", "folder", "labels", "category"}
    for key, value in updates.items():
        if key in allowed:
            email[key] = value


def apply_bulk_update(
    emails: List[Dict[str, Any]], email_ids: List[str], updates: Dict[str, Any]
) -> bool:
    changed = False
    targets = set(email_ids)
    for email in emails:
        if email.get("id") in targets:
            update_email_fields(email, updates)
            changed = True
    return changed


def apply_delete(emails: List[Dict[str, Any]], email_ids: List[str]) -> Tuple[List[Dict[str, Any]], bool]:
    changed = False
    targets = set(email_ids)
    trash_ids = {email["id"] for email in emails if email.get("id") in targets and email.get("folder") == "trash"}
    move_ids = {email["id"] for email in emails if email.get("id") in targets and email.get("folder") != "trash"}

    if trash_ids:
        emails = [email for email in emails if email.get("id") not in trash_ids]
        changed = True

    if move_ids:
        for email in emails:
            if email.get("id") in move_ids:
                email["folder"] = "trash"
        changed = True

    return emails, changed


def apply_empty_trash(emails: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    filtered = [email for email in emails if email.get("folder") != "trash"]
    return filtered, len(filtered) != len(emails)


def apply_label_toggle(
    emails: List[Dict[str, Any]], email_id: str, label_id: str, action: str
) -> bool:
    email = find_email(emails, email_id)
    if not email:
        return False
    labels = list(email.get("labels", []))
    if action == "add" and label_id not in labels:
        labels.append(label_id)
    elif action == "remove" and label_id in labels:
        labels = [label for label in labels if label != label_id]
    elif action == "toggle":
        if label_id in labels:
            labels = [label for label in labels if label != label_id]
        else:
            labels.append(label_id)
    else:
        return False
    email["labels"] = labels
    return True


def build_outgoing_email(
    user: Dict[str, str], payload: Dict[str, Any], thread_id: Optional[str] = None
) -> Dict[str, Any]:
    attachments = normalize_attachments(payload.get("attachments"))
    return build_email(
        email_id=generate_id(),
        thread_id=thread_id or generate_id(),
        from_contact={"name": user["username"], "email": user["email"], "avatar": user["avatar"]},
        to=normalize_recipients(payload.get("to")),
        cc=normalize_recipients(payload.get("cc")),
        bcc=normalize_recipients(payload.get("bcc")),
        subject=payload.get("subject") or "(no subject)",
        body=payload.get("body") or "",
        read=True,
        starred=False,
        important=False,
        labels=[],
        category="primary",
        folder=payload.get("folder") or "sent",
        attachments=attachments,
        body_format="text",
    )


_QUOTE_RE = re.compile(
    r'<div\s+class="gmail_quote".*?</div>\s*$',
    re.DOTALL | re.IGNORECASE,
)


def _strip_existing_quote(html: str) -> str:
    """Remove the trailing gmail_quote block so quotes don't nest."""
    return _QUOTE_RE.sub("", html).rstrip()


def _build_body_with_quote(body: str, source_email: Dict[str, Any]) -> str:
    """Wrap the user's reply with a collapsed quote of the source email."""
    source_from = source_email.get("from") or {}
    sender_name = source_from.get("name", "")
    sender_email = source_from.get("email", "")
    raw_ts = source_email.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(raw_ts)
        timestamp = dt.strftime("%a, %b %d, %Y at %I:%M %p")
    except (ValueError, TypeError):
        timestamp = raw_ts
    reply_body = text_to_html_fragment(body)
    source_body = source_email.get("body") or ""
    source_body_format = source_email.get("bodyFormat")
    if infer_body_format(source_body, source_body_format) == "html":
        source_body = _strip_existing_quote(source_body)
    source_body = body_to_html_fragment(source_body, source_body_format)

    if not source_body:
        return reply_body

    quote_prefix = "<br><br>" if reply_body else ""

    return (
        f"{reply_body}"
        f"{quote_prefix}"
        f'<div class="gmail_quote">'
        f"<details>"
        f'<summary style="cursor:pointer;list-style:none;display:inline-block;'
        f'margin:4px 0 8px;user-select:none">'
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:36px;height:18px;border:1px solid #ddd;border-radius:8px;'
        f'background:#f1f3f4;font-size:11px;letter-spacing:2px;color:#5f6368;'
        f'line-height:1;transition:background .15s"'
        f' onmouseover="this.style.background=\'#e0e0e0\'"'
        f' onmouseout="this.style.background=\'#f1f3f4\'">'
        f"&bull;&bull;&bull;</span></summary>"
        f'<div style="margin-top:8px;color:#5f6368;font-size:13px">'
        f"On {timestamp} {sender_name} &lt;{sender_email}&gt; wrote:</div>"
        f'<blockquote style="margin:0 0 0 .8ex;border-left:1px solid #ccc;padding-left:1ex">'
        f"{source_body}"
        f"</blockquote>"
        f"</details>"
        f"</div>"
    )


def build_reply_email(
    user: Dict[str, str],
    source_email: Dict[str, Any],
    body: str,
    reply_all: bool = False,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    to_recipients = [source_email.get("from")] if source_email.get("from") else []
    if reply_all:
        to_recipients.extend(source_email.get("to") or [])
        to_recipients.extend(source_email.get("cc") or [])

    filtered = [
        recipient
        for recipient in to_recipients
        if recipient and recipient.get("email") != user.get("email")
    ]

    subject = source_email.get("subject") or "(no subject)"
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    reply_body = _build_body_with_quote(body, source_email)

    return build_email(
        email_id=generate_id(),
        thread_id=source_email.get("threadId") or generate_id(),
        from_contact={"name": user["username"], "email": user["email"], "avatar": user["avatar"]},
        to=filtered,
        cc=[],
        bcc=[],
        subject=subject,
        body=reply_body,
        read=True,
        starred=False,
        important=False,
        labels=[],
        category="primary",
        folder="sent",
        attachments=normalize_attachments(attachments),
        body_format="html",
    )
