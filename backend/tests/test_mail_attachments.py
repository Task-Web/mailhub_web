import pytest

from app.config import get_settings

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture(autouse=True)
def isolated_uploads(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "files_dir", str(tmp_path))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename,browser_mime,expected_mime",
    [
        ("Remaining_Course.xlsx", XLSX_MIME, XLSX_MIME),
        ("Remaining_Course.xlsx", "application/wps-office.xlsx", XLSX_MIME),
        ("Remaining Course.xlsx", "application/wps-office.xlsx", XLSX_MIME),
        ("Remaining_Course.xlsx", "application/octet-stream", XLSX_MIME),
        ("Remaining_Course.xlsx", None, XLSX_MIME),
        ("Report.docx", "application/wps-office.docx", DOCX_MIME),
        ("Report.task007unknown", "application/x-custom", "application/octet-stream"),
    ],
)
async def test_uploaded_attachment_round_trip(async_client, filename, browser_mime, expected_mime):
    content = b"attachment round trip\n"
    uploaded = await async_client.post(
        "/api/files", files={"files": (filename, content, browser_mime)}
    )
    assert uploaded.status_code == 200
    attachment = uploaded.json()["files"][0]

    # Submit exactly what the upload endpoint returned, as the UI does.
    draft = await async_client.post(
        "/api/mail/draft",
        json={"to": "advisor@example.com", "attachments": [attachment]},
    )
    assert draft.status_code == 200, draft.text
    sent = await async_client.post(
        "/api/mail/send",
        json={
            "to": "advisor@example.com",
            "subject": "Completed form",
            "body": "Attached is the completed form.",
            "attachments": [attachment],
            "draft_id": draft.json()["draft_id"],
        },
    )
    assert sent.status_code == 200, sent.text
    message = next(
        email
        for email in sent.json()["mail"]["emails"]
        if email["subject"] == "Completed form" and email["folder"] == "sent"
    )
    mail_attachment = {key: value for key, value in attachment.items() if key != "filename"}
    assert message["attachments"] == [mail_attachment]

    replied = await async_client.post(
        "/api/mail/reply",
        json={
            "thread_id": message["threadId"],
            "body": "Here is the form again.",
            "attachments": [attachment],
        },
    )
    assert replied.status_code == 200, replied.text
    assert replied.json()["mail"]["emails"][-1]["attachments"] == [mail_attachment]

    listed = await async_client.get("/api/files")
    assert listed.status_code == 200
    assert listed.json()["files"] == [attachment]
    assert attachment["name"] == filename
    assert attachment["type"] == expected_mime
    downloaded = await async_client.get(attachment["url"])
    assert downloaded.status_code == 200
    assert downloaded.content == content
    assert downloaded.headers["content-type"] == expected_mime


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["send", "draft", "reply"])
@pytest.mark.parametrize("field", ["id", "name", "size", "type", "url", "filename"])
async def test_modified_attachment_metadata_is_rejected(async_client, endpoint, field):
    uploaded = await async_client.post(
        "/api/files", files={"files": ("form.xlsx", b"original", XLSX_MIME)}
    )
    assert uploaded.status_code == 200
    attachment = uploaded.json()["files"][0]
    attachment[field] = "modified"
    payload = {"attachments": [attachment], "body": "Completed form"}
    if endpoint == "reply":
        mailbox = (await async_client.get("/api/mail")).json()["mail"]
        payload["thread_id"] = mailbox["emails"][0]["threadId"]
    else:
        payload["to"] = "advisor@example.com"
    response = await async_client.post(f"/api/mail/{endpoint}", json=payload)
    assert response.status_code == (404 if field == "filename" else 422)


@pytest.mark.asyncio
async def test_other_user_cannot_send_or_download_upload(async_client):
    uploaded = await async_client.post(
        "/api/files",
        params={"cookie": "attachment-owner"},
        files={"files": ("form.xlsx", b"private", XLSX_MIME)},
    )
    assert uploaded.status_code == 200
    attachment = uploaded.json()["files"][0]
    response = await async_client.post(
        "/api/mail/send",
        params={"cookie": "another-user"},
        json={"to": "advisor@example.com", "attachments": [attachment]},
    )
    assert response.status_code == 404
    download = await async_client.get(attachment["url"], params={"cookie": "another-user"})
    assert download.status_code == 404
