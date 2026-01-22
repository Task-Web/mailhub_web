import pytest


@pytest.mark.asyncio
async def test_health(async_client):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_cookie_and_default_state(async_client):
    resp = await async_client.get("/api/state")
    assert resp.status_code == 200
    assert "user_id" in resp.cookies
    body = resp.json()
    assert "user" in body["state"]["data"]
    assert "emails" in body["state"]["data"]
    assert "labels" in body["state"]["data"]
    assert "drafts" in body["state"]["data"]
    assert body["state"]["note"] is None


@pytest.mark.asyncio
async def test_cookie_override_via_query(async_client):
    resp = await async_client.get("/api/state", params={"cookie": "custom-cookie"})
    assert resp.status_code == 200
    assert resp.cookies.get("user_id") == "custom-cookie"
    assert resp.json()["user_id"] == "custom-cookie"


@pytest.mark.asyncio
async def test_put_replaces_state(async_client):
    payload = {"data": {"a": 1, "b": {"x": 2}}, "note": "full replace"}
    resp = await async_client.put("/api/state", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"]["data"] == payload["data"]
    assert body["state"]["note"] == "full replace"


@pytest.mark.asyncio
async def test_patch_merges_state(async_client):
    await async_client.put("/api/state", json={"data": {"a": 1, "b": {"x": 2}}})

    patch_payload = {"data": {"b": {"y": 3}, "c": 4}, "note": "patched"}
    resp = await async_client.patch("/api/state", json=patch_payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"]["data"] == {"a": 1, "b": {"x": 2, "y": 3}, "c": 4}
    assert body["state"]["note"] == "patched"


@pytest.mark.asyncio
async def test_delete_resets_state(async_client):
    await async_client.put("/api/state", json={"data": {"temp": True}})
    resp = await async_client.delete("/api/state")
    assert resp.status_code == 200
    body = resp.json()
    assert "user" in body["state"]["data"]
    assert "emails" in body["state"]["data"]
    assert "labels" in body["state"]["data"]
    assert "drafts" in body["state"]["data"]
    assert body["state"]["note"] is None


@pytest.mark.asyncio
async def test_info_includes_user_id(async_client):
    state_resp = await async_client.get("/api/state")
    user_id = state_resp.cookies.get("user_id")

    info_resp = await async_client.get("/api/info")
    assert info_resp.status_code == 200
    body = info_resp.json()
    assert body["request"]["user_id"] == user_id
