import asyncio
import copy
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .mail import build_default_mail_state
from .models import UserState

logger = logging.getLogger(__name__)


def _deep_merge(dest: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in src.items():
        if key in dest and isinstance(dest[key], dict) and isinstance(value, dict):
            dest[key] = _deep_merge(dest[key], value)
        else:
            dest[key] = copy.deepcopy(value)
    return dest


class StateStore:
    """Bounded in-memory state store keyed by user id."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 12 * 60 * 60,
        max_entries: int = 1000,
        max_total_bytes: int = 1024 * 1024 * 1024,
        on_evict: Optional[Callable[[str], None]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        if max_entries <= 0:
            raise ValueError("max_entries must be greater than zero")
        if max_total_bytes <= 0:
            raise ValueError("max_total_bytes must be greater than zero")
        self._states: Dict[str, UserState] = {}
        self._accessed_at: Dict[str, float] = {}
        self._sizes: Dict[str, int] = {}
        self._total_bytes = 0
        self._lock = asyncio.Lock()
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._max_total_bytes = max_total_bytes
        self._on_evict = on_evict
        self._clock = clock

    @property
    def entry_count(self) -> int:
        return len(self._states)

    @property
    def total_bytes(self) -> int:
        return self._total_bytes

    @staticmethod
    def _serialized_size(state: UserState) -> int:
        return len(state.model_dump_json().encode("utf-8"))

    def _remove_locked(self, user_id: str) -> bool:
        if self._states.pop(user_id, None) is None:
            return False
        self._accessed_at.pop(user_id, None)
        self._total_bytes -= self._sizes.pop(user_id, 0)
        return True

    def _purge_expired_locked(self, now: float) -> List[str]:
        expired = [
            user_id
            for user_id, accessed_at in self._accessed_at.items()
            if now - accessed_at >= self._ttl_seconds
        ]
        for user_id in expired:
            self._remove_locked(user_id)
        return expired

    def _enforce_limits_locked(self) -> List[str]:
        evicted: List[str] = []
        while len(self._states) > self._max_entries or self._total_bytes > self._max_total_bytes:
            user_id = min(self._accessed_at, key=self._accessed_at.__getitem__)
            self._remove_locked(user_id)
            evicted.append(user_id)
        return evicted

    def _put_locked(self, user_id: str, state: UserState, now: float) -> List[str]:
        if user_id in self._states:
            self._total_bytes -= self._sizes[user_id]
        size = self._serialized_size(state)
        self._states[user_id] = state
        self._accessed_at[user_id] = now
        self._sizes[user_id] = size
        self._total_bytes += size
        return self._enforce_limits_locked()

    def _notify_evictions(self, user_ids: List[str]) -> None:
        if self._on_evict is None:
            return
        for user_id in dict.fromkeys(user_ids):
            try:
                self._on_evict(user_id)
            except Exception:
                logger.exception("State eviction callback failed for user %s", user_id)

    async def get_state(self, user_id: str) -> UserState:
        evicted: List[str]
        async with self._lock:
            now = self._clock()
            evicted = self._purge_expired_locked(now)
            state = self._states.get(user_id)
            if state is None:
                state = UserState(data=build_default_mail_state(user_id))
                evicted.extend(self._put_locked(user_id, state, now))
            else:
                self._accessed_at[user_id] = now
        self._notify_evictions(evicted)
        return state.model_copy(deep=True)

    async def replace_state(self, user_id: str, new_state: Dict[str, Any]) -> UserState:
        async with self._lock:
            now = self._clock()
            evicted = self._purge_expired_locked(now)
            if self._remove_locked(user_id):
                evicted.append(user_id)
            state = UserState(**new_state)
            evicted.extend(self._put_locked(user_id, state, now))
        self._notify_evictions(evicted)
        return state.model_copy(deep=True)

    async def patch_state(
        self, user_id: str, patch: Dict[str, Any], note: Optional[str]
    ) -> UserState:
        async with self._lock:
            now = self._clock()
            evicted = self._purge_expired_locked(now)
            existing = self._states.get(user_id)
            state = (
                existing.model_copy(deep=True)
                if existing is not None
                else UserState(data=build_default_mail_state(user_id))
            )
            updated_data = _deep_merge(copy.deepcopy(state.data), patch)
            state.data = updated_data
            if note is not None:
                state.note = note
            state.touch()
            evicted.extend(self._put_locked(user_id, state, now))
        self._notify_evictions(evicted)
        return state.model_copy(deep=True)

    async def reset_state(self, user_id: str) -> UserState:
        async with self._lock:
            now = self._clock()
            evicted = self._purge_expired_locked(now)
            if self._remove_locked(user_id):
                evicted.append(user_id)
            state = UserState(data=build_default_mail_state(user_id))
            evicted.extend(self._put_locked(user_id, state, now))
        self._notify_evictions(evicted)
        return state.model_copy(deep=True)

    async def delete_state(self, user_id: str) -> None:
        async with self._lock:
            evicted = self._purge_expired_locked(self._clock())
            if self._remove_locked(user_id):
                evicted.append(user_id)
        self._notify_evictions(evicted)

    async def contains_state(self, user_id: str) -> bool:
        async with self._lock:
            evicted = self._purge_expired_locked(self._clock())
            retained = user_id in self._states
        self._notify_evictions(evicted)
        return retained

    async def update_state(
        self,
        user_id: str,
        updater: Callable[[UserState], bool],
        *,
        create_if_missing: bool = True,
    ) -> Optional[UserState]:
        async with self._lock:
            now = self._clock()
            evicted = self._purge_expired_locked(now)
            existing = self._states.get(user_id)
            if existing is None and not create_if_missing:
                state = None
            else:
                state = (
                    existing.model_copy(deep=True)
                    if existing is not None
                    else UserState(data=build_default_mail_state(user_id))
                )
                changed = updater(state)
                if changed:
                    state.touch()
                evicted.extend(self._put_locked(user_id, state, now))
        self._notify_evictions(evicted)
        return state.model_copy(deep=True) if state is not None else None
