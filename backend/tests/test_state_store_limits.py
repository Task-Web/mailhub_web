import pytest

from app.models import UserState
from app.state_store import StateStore


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float = 1.0) -> None:
        self.value += seconds


@pytest.mark.asyncio
async def test_idle_ttl_refreshes_on_access_and_evicts_at_boundary():
    clock = FakeClock()
    evicted = []
    store = StateStore(ttl_seconds=10, on_evict=evicted.append, clock=clock)
    await store.replace_state("user", {"data": {"marker": True}})

    clock.advance(9)
    assert (await store.get_state("user")).data == {"marker": True}
    clock.advance(9)
    assert (await store.get_state("user")).data == {"marker": True}
    clock.advance(10)
    refreshed = await store.get_state("user")

    assert "marker" not in refreshed.data
    assert evicted == ["user"]


@pytest.mark.asyncio
async def test_entry_limit_uses_least_recently_used_order():
    clock = FakeClock()
    evicted = []
    store = StateStore(max_entries=2, on_evict=evicted.append, clock=clock)

    await store.get_state("old")
    clock.advance()
    await store.get_state("recent")
    clock.advance()
    await store.get_state("old")
    clock.advance()
    await store.get_state("new")

    assert set(store._states) == {"old", "new"}
    assert evicted == ["recent"]


@pytest.mark.asyncio
async def test_total_byte_limit_and_overwrite_accounting():
    small = UserState(data={"payload": "x" * 10})
    large = UserState(data={"payload": "x" * 100})
    large_size = StateStore._serialized_size(large)
    clock = FakeClock()
    evicted = []
    store = StateStore(
        max_total_bytes=large_size + 8,
        on_evict=evicted.append,
        clock=clock,
    )

    await store.replace_state("a", {"data": small.data})
    clock.advance()
    await store.replace_state("b", {"data": small.data})
    clock.advance()
    updated = await store.replace_state("a", {"data": large.data})

    assert set(store._states) == {"a"}
    assert store.total_bytes == StateStore._serialized_size(updated)
    assert store.total_bytes <= large_size + 8
    assert "b" in evicted


@pytest.mark.asyncio
async def test_state_larger_than_total_budget_is_accepted_but_not_retained():
    store = StateStore(max_total_bytes=1)

    returned = await store.replace_state("large", {"data": {"payload": "x" * 1000}})

    assert returned.data["payload"] == "x" * 1000
    assert store.entry_count == 0
    assert store.total_bytes == 0
