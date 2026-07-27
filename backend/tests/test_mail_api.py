import pytest


@pytest.mark.asyncio
async def test_control_plane_is_hidden_from_public_openapi(async_client):
    schema = (await async_client.get("/api/openapi.json")).json()
    assert "/api/state" not in schema["paths"]
    assert "/api/mail/state" not in schema["paths"]
    assert "/api/mail" in schema["paths"]
    assert all(tag.get("name") != "state" for tag in schema.get("tags", []))


@pytest.mark.asyncio
async def test_mailbox(async_client):
    resp = await async_client.get("/api/mail")
    assert resp.status_code == 200
    body = resp.json()
    assert "mail" in body
    assert "emails" in body["mail"]
    assert "labels" in body["mail"]


@pytest.mark.asyncio
async def test_legacy_mail_state_route_remains_compatible(async_client):
    current = await async_client.get("/api/mail")
    legacy = await async_client.get("/api/mail/state")

    assert legacy.status_code == 200
    assert legacy.json()["user_id"] == current.json()["user_id"]
    assert legacy.json()["mail"] == current.json()["mail"]


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
    state_resp = await async_client.get("/api/mail")
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


@pytest.mark.asyncio
async def test_mail_projection_hides_unrelated_control_fields(async_client):
    cookie = "mail-projection"
    await async_client.put(
        "/api/state",
        params={"cookie": cookie},
        json={
            "data": {
                "evaluator_marker": {"keep": True},
                "unrelated_top_level": {"hidden": True},
                "developer_tools_open": False,
            }
        },
    )

    response = await async_client.get("/api/mail", params={"cookie": cookie})

    assert response.status_code == 200
    assert set(response.json()) == {"user_id", "mail", "enable_notifications"}
    assert set(response.json()["mail"]) == {"user", "emails", "labels", "drafts"}
    assert "evaluator_marker" not in response.json()["mail"]
    assert "unrelated_top_level" not in response.json()["mail"]
    assert "developer_tools_open" not in response.json()["mail"]
    final = await async_client.get("/api/state", params={"cookie": cookie})
    assert final.json()["state"]["data"]["evaluator_marker"] == {"keep": True}
    assert final.json()["state"]["data"]["unrelated_top_level"] == {"hidden": True}


@pytest.mark.asyncio
async def test_mail_updates_reject_arbitrary_and_internal_fields(async_client):
    cookie = "mail-strict-updates"
    await async_client.patch(
        "/api/state",
        params={"cookie": cookie},
        json={
            "data": {
                "evaluator_marker": {"keep": True},
                "unrelated_top_level": {"hidden": True},
            }
        },
    )
    state = await async_client.get("/api/mail", params={"cookie": cookie})
    email_id = state.json()["mail"]["emails"][0]["id"]

    for updates in (
        {"developer_tools_open": True},
        {"read": True, "subject": "forged"},
        {"emails": []},
        {"evaluator_marker": True},
        {"folder": "evaluator"},
    ):
        response = await async_client.patch(
            f"/api/mail/email/{email_id}",
            params={"cookie": cookie},
            json={"updates": updates},
        )
        assert response.status_code == 422

    full_state = await async_client.patch(
        f"/api/mail/email/{email_id}",
        params={"cookie": cookie},
        json={"updates": {"read": True}, "state": {"data": {}}},
    )
    assert full_state.status_code == 422

    missing = await async_client.patch(
        "/api/mail/email/missing",
        params={"cookie": cookie},
        json={"updates": {"read": True}},
    )
    assert missing.status_code == 404

    updated = await async_client.patch(
        f"/api/mail/email/{email_id}",
        params={"cookie": cookie},
        json={"updates": {"read": True}},
    )
    assert updated.status_code == 200
    assert next(
        email for email in updated.json()["mail"]["emails"] if email["id"] == email_id
    )["read"] is True
    final = await async_client.get("/api/state", params={"cookie": cookie})
    assert final.json()["state"]["data"]["evaluator_marker"] == {"keep": True}
    assert final.json()["state"]["data"]["unrelated_top_level"] == {"hidden": True}


@pytest.mark.asyncio
async def test_mail_cookie_override_is_isolated(async_client):
    source = await async_client.get("/api/mail", params={"cookie": "mail-a"})
    other = await async_client.get("/api/mail", params={"cookie": "mail-b"})
    source_id = source.json()["mail"]["emails"][0]["id"]
    other_id = other.json()["mail"]["emails"][0]["id"]

    response = await async_client.patch(
        f"/api/mail/email/{source_id}",
        params={"cookie": "mail-a"},
        json={"updates": {"starred": True}},
    )
    assert response.status_code == 200

    untouched = await async_client.get("/api/mail", params={"cookie": "mail-b"})
    assert next(
        email for email in untouched.json()["mail"]["emails"] if email["id"] == other_id
    )["starred"] == next(
        email for email in other.json()["mail"]["emails"] if email["id"] == other_id
    )["starred"]
