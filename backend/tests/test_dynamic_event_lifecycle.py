import asyncio

import pytest
import pytest_asyncio

from app import dynamic_events
from app.main import mcp_reset_state, store


@pytest_asyncio.fixture(autouse=True)
async def clean_dynamic_events():
    dynamic_events.shutdown_dynamic_events()
    yield
    dynamic_events.shutdown_dynamic_events()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_rest_replace_with_empty_arrays_cancels_old_events(async_client):
    user_id = "mail-replace-cleanup"
    scheduled = {
        "id": "later",
        "arrive_after_s": 3600,
        "from": {"email": "sender@example.com"},
        "to": [],
        "subject": "Later",
        "body": "Later",
    }
    await async_client.put(
        "/api/state",
        params={"cookie": user_id},
        json={"data": {"time_data": [scheduled]}},
    )
    old_task = next(iter(dynamic_events._timers[user_id]))

    await async_client.put(
        "/api/state",
        params={"cookie": user_id},
        json={"data": {"time_data": [], "action_data": []}},
    )
    await asyncio.sleep(0)

    assert old_task.cancelled()
    assert user_id not in dynamic_events._timers
    assert user_id not in dynamic_events._actions


@pytest.mark.asyncio
async def test_mcp_reset_cancels_dynamic_events():
    user_id = "mail-mcp-reset"
    await store.replace_state(user_id, {"data": {"marker": True}})
    dynamic_events.start_dynamic_events(
        user_id,
        [{"id": "later", "arrive_after_s": 3600}],
        [],
    )
    task = next(iter(dynamic_events._timers[user_id]))

    await mcp_reset_state(user_cookie=user_id)
    await asyncio.sleep(0)

    assert task.cancelled()
    assert user_id not in dynamic_events._timers


@pytest.mark.asyncio
async def test_rest_delete_cancels_dynamic_events(async_client):
    user_id = "mail-rest-delete"
    await async_client.put(
        "/api/state",
        params={"cookie": user_id},
        json={"data": {"time_data": [{"id": "later", "arrive_after_s": 3600}]}},
    )
    task = next(iter(dynamic_events._timers[user_id]))

    await async_client.delete("/api/state", params={"cookie": user_id})
    await asyncio.sleep(0)

    assert task.cancelled()
    assert user_id not in dynamic_events._timers


@pytest.mark.asyncio
async def test_action_tasks_are_tracked_and_cancelled(monkeypatch):
    release = asyncio.Event()

    async def hold_delivery(*args, **kwargs):
        await release.wait()

    monkeypatch.setattr(dynamic_events, "_deliver_timed_email", hold_delivery)
    user_id = "mail-action"
    dynamic_events.start_dynamic_events(
        user_id,
        [],
        [
            {
                "trigger": {"to_email": "recipient@example.com"},
                "email": {"id": "reply"},
            }
        ],
    )

    await dynamic_events.check_action_triggers(
        user_id,
        {"to": [{"email": "recipient@example.com"}], "subject": "", "body": ""},
    )
    task = next(iter(dynamic_events._timers[user_id]))
    assert dynamic_events._registered_event_count() == 1
    dynamic_events.cancel_dynamic_events(user_id)
    await asyncio.sleep(0)

    assert task.cancelled()
    assert user_id not in dynamic_events._timers


@pytest.mark.asyncio
async def test_completed_tasks_are_removed(monkeypatch):
    async def finish_immediately(*args, **kwargs):
        return None

    monkeypatch.setattr(dynamic_events, "_deliver_timed_email", finish_immediately)
    user_id = "mail-complete"
    dynamic_events.start_dynamic_events(user_id, [{"id": "now"}], [])
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert user_id not in dynamic_events._timers
    assert user_id not in dynamic_events._actions
    assert user_id not in dynamic_events._fired
    assert user_id not in dynamic_events._start_ts
    assert user_id not in dynamic_events._notif_enabled


@pytest.mark.asyncio
async def test_shutdown_cancels_all_users():
    dynamic_events.start_dynamic_events("one", [{"id": "one", "arrive_after_s": 3600}], [])
    dynamic_events.start_dynamic_events("two", [], [{"trigger": {"to_email": "x@y.z"}}])
    task = next(iter(dynamic_events._timers["one"]))

    dynamic_events.shutdown_dynamic_events()
    await asyncio.sleep(0)

    assert task.cancelled()
    assert not dynamic_events._timers
    assert not dynamic_events._actions
    assert not dynamic_events._fired
    assert not dynamic_events._start_ts
    assert not dynamic_events._notif_enabled


def test_dynamic_event_count_and_delay_are_bounded():
    user_id = "mail-bounds"
    rules = [{"trigger": {"to_email": "nobody@example.com"}}] * 1001
    dynamic_events.start_dynamic_events(user_id, [], rules)

    assert len(dynamic_events._actions[user_id]) == dynamic_events.MAX_DYNAMIC_EVENTS_PER_USER
    assert dynamic_events._bounded_delay(float("inf")) == 0
    assert dynamic_events._bounded_delay(10**9) == dynamic_events.MAX_DYNAMIC_EVENT_DELAY_SECONDS


def test_dynamic_event_count_is_bounded_across_users():
    rules = [{"trigger": {"to_email": "nobody@example.com"}}] * 100
    for index in range(10):
        dynamic_events.start_dynamic_events(f"mail-global-{index}", [], rules)

    dynamic_events.start_dynamic_events("mail-global-overflow", [], rules)

    assert dynamic_events._registered_event_count() == 1000
    assert "mail-global-overflow" not in dynamic_events._actions
