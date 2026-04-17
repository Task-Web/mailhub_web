import pytest


@pytest.mark.asyncio
async def test_mail_state(async_client):
    resp = await async_client.get("/api/mail/state")
    assert resp.status_code == 200
    body = resp.json()
    assert "mail" in body
    assert "emails" in body["mail"]
    assert "labels" in body["mail"]


@pytest.mark.asyncio
async def test_send_mail(async_client):
    payload = {
        "to": "team@example.com",
        "subject": "Hello",
        "body": "Testing the outbound path",
    }
    resp = await async_client.post("/api/mail/send", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert any(
        email.get("subject") == "Hello"
        and email.get("folder") == "sent"
        and email.get("bodyFormat") == "text"
        for email in body["mail"]["emails"]
    )


@pytest.mark.asyncio
async def test_reply_mail_preserves_multiline_reply_text(async_client):
    state_resp = await async_client.get("/api/mail/state")
    thread_id = state_resp.json()["mail"]["emails"][0]["threadId"]

    resp = await async_client.post(
        "/api/mail/reply",
        json={
            "thread_id": thread_id,
            "body": "First line\nSecond line",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    reply = next(
        email
        for email in reversed(body["mail"]["emails"])
        if email.get("threadId") == thread_id and email.get("folder") == "sent"
    )
    assert reply["bodyFormat"] == "html"
    assert "First line<br>Second line" in reply["body"]
    assert 'class="gmail_quote"' in reply["body"]


@pytest.mark.asyncio
async def test_reply_mail_preserves_multiline_plain_text_quotes(async_client):
    payload = {
        "data": {
            "user": {
                "userId": "demo",
                "username": "Demo User",
                "email": "demo@example.com",
                "avatar": "https://example.com/avatar.png",
            },
            "emails": [
                {
                    "id": "email-1",
                    "threadId": "thread-1",
                    "from": {
                        "name": "Alice",
                        "email": "alice@example.com",
                        "avatar": "https://example.com/alice.png",
                    },
                    "to": [{"name": "Demo User", "email": "demo@example.com"}],
                    "cc": [],
                    "bcc": [],
                    "subject": "Plain text thread",
                    "body": "Original line 1\nOriginal line 2",
                    "snippet": "Original line 1 Original line 2",
                    "timestamp": "2024-01-01T00:00:00+00:00",
                    "read": False,
                    "starred": False,
                    "important": False,
                    "labels": [],
                    "category": "primary",
                    "folder": "inbox",
                    "attachments": [],
                }
            ],
            "labels": [],
            "drafts": [],
        },
        "note": "seed multiline plain text",
    }
    put_resp = await async_client.put("/api/state", json=payload)
    assert put_resp.status_code == 200

    resp = await async_client.post(
        "/api/mail/reply",
        json={
            "thread_id": "thread-1",
            "body": "Reply line 1\nReply line 2",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    reply = next(
        email
        for email in reversed(body["mail"]["emails"])
        if email.get("threadId") == "thread-1" and email.get("folder") == "sent"
    )
    assert "Reply line 1<br>Reply line 2" in reply["body"]
    assert "Original line 1<br>Original line 2" in reply["body"]
