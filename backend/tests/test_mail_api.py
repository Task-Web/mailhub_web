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
        email.get("subject") == "Hello" and email.get("folder") == "sent"
        for email in body["mail"]["emails"]
    )
