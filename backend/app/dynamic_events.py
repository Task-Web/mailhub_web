"""
Dynamic events engine for MailHub.

Supports two new optional keys in ``state.data``:

* **time_data**  list of emails that arrive after a delay (seconds since
  state init).  Each item is a normal Email dict with an extra
  ``"arrive_after_s"`` field.

* **action_data**  list of rules that fire *once* when a sent/replied
  email matches certain conditions.  Each rule has:
    - ``trigger.to_email``    recipient email to watch (case-insensitive)
    - ``trigger.keywords``    list of keyword-groups (OR-of-ANDs).
    - ``delay_s``             seconds to wait after match before injecting
    - ``email``               the Email dict to inject (folder ``"inbox"``)

"""

from __future__ import annotations

import asyncio
import copy
import math
import re
import time
from typing import Any, Dict, List, Set

from .mail import ensure_mail_state, generate_id

# ── per-user registries ────────────────────────────────────────────────
# _timers[user_id]   = set of asyncio.Task (timed and action delivery)
# _actions[user_id]  = list of action-rule dicts (pending triggers)
# _fired[user_id]    = set of rule indices already fired
# _start_ts[user_id] = monotonic timestamp when dynamic events started
_timers: Dict[str, Set[asyncio.Task]] = {}
_actions: Dict[str, List[Dict[str, Any]]] = {}
_fired: Dict[str, Set[int]] = {}
_start_ts: Dict[str, float] = {}
_notif_enabled: Dict[str, bool] = {}  # per-user notification toggle

# back-reference so timer tasks can mutate state
_store_ref: Any = None  # will be set to the StateStore instance

MAX_DYNAMIC_EVENTS_PER_USER = 100
MAX_DYNAMIC_EVENTS_TOTAL = 1000
MAX_DYNAMIC_EVENT_DELAY_SECONDS = 12 * 60 * 60


def set_store(store: Any) -> None:
    """Call once at startup to give this module access to the state store."""
    global _store_ref
    _store_ref = store


# ── helpers ─────────────────────────────────────────────────────────────
_NON_ALNUM = re.compile(r"[^a-z0-9]")


def _norm(text: str) -> str:
    """Strip all whitespace & punctuation, lowercase."""
    return _NON_ALNUM.sub("", text.lower())


def _bounded_delay(value: Any) -> float:
    try:
        delay = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(delay):
        return 0.0
    return min(max(delay, 0.0), MAX_DYNAMIC_EVENT_DELAY_SECONDS)


def _discard_task(user_id: str, task: asyncio.Task) -> None:
    tasks = _timers.get(user_id)
    if tasks is not None:
        tasks.discard(task)
        if not tasks:
            _timers.pop(user_id, None)
    if not task.cancelled():
        task.exception()
    if user_id not in _timers and not _actions.get(user_id):
        _actions.pop(user_id, None)
        _fired.pop(user_id, None)
        _start_ts.pop(user_id, None)
        _notif_enabled.pop(user_id, None)


def _track_task(user_id: str, task: asyncio.Task) -> None:
    _timers.setdefault(user_id, set()).add(task)
    task.add_done_callback(lambda completed: _discard_task(user_id, completed))


def _registered_event_count() -> int:
    return sum(len(tasks) for tasks in _timers.values()) + sum(
        max(0, len(rules) - len(_fired.get(user_id, set())))
        for user_id, rules in _actions.items()
    )


def _email_matches_trigger(email_data: Dict[str, Any], trigger: Dict[str, Any]) -> bool:
    """Check if an outgoing email satisfies a trigger rule."""
    # 1. recipient check
    target_email = _norm(trigger.get("to_email", ""))
    if not target_email:
        return False
    recipients: List[Dict[str, Any]] = (
        (email_data.get("to") or []) + (email_data.get("cc") or []) + (email_data.get("bcc") or [])
    )
    matched_recipient = any(_norm(r.get("email", "")) == target_email for r in recipients)
    if not matched_recipient:
        return False

    # 2. keyword check in subject + body  (OR-of-ANDs)
    raw_keywords = trigger.get("keywords", [])
    if not raw_keywords:
        return True  # no keyword requirement

    haystack = _norm((email_data.get("subject") or "") + " " + (email_data.get("body") or ""))

    if raw_keywords and isinstance(raw_keywords[0], list):
        keyword_sets: List[List[str]] = raw_keywords
    else:
        # legacy flat list
        match_all = trigger.get("match_all", False)
        if match_all:
            keyword_sets = [raw_keywords]
        else:
            keyword_sets = [[kw] for kw in raw_keywords]

    # OR-of-ANDs: any group where ALL keywords match → True
    return any(all(_norm(kw) in haystack for kw in group) for group in keyword_sets)


# ── lifecycle hooks ─────────────────────────────────────────────────────


def extract_dynamic_fields(data: Dict[str, Any]) -> tuple:
    """Pop time_data, action_data and enable_notifications from *data* (in-place)."""
    time_data = data.pop("time_data", None) or []
    action_data = data.pop("action_data", None) or []
    enable_notif = str(data.pop("enable_notifications", "")).lower() == "on"
    return time_data, action_data, enable_notif


async def _deliver_timed_email(user_id: str, email: Dict[str, Any], delay: float) -> None:
    """Sleep *delay* seconds then inject *email* into the user's inbox."""
    await asyncio.sleep(delay)
    if _store_ref is None:
        return

    injected_email = copy.deepcopy(email)
    # Ensure it has required fields
    injected_email.setdefault("id", generate_id())
    injected_email.setdefault("threadId", injected_email.get("threadId") or generate_id())
    injected_email.setdefault("folder", "inbox")
    injected_email.setdefault("read", False)
    injected_email.setdefault("starred", False)
    injected_email.setdefault("important", False)
    injected_email.setdefault("labels", [])
    injected_email.setdefault("category", "primary")
    injected_email.setdefault("cc", [])
    injected_email.setdefault("bcc", [])
    injected_email.setdefault("attachments", [])
    # Remove the scheduling field
    injected_email.pop("arrive_after_s", None)

    def updater(existing_state):
        mail_state, _ = ensure_mail_state(existing_state.data, user_id)
        mail_state["emails"].insert(0, injected_email)
        existing_state.data = mail_state
        existing_state.note = f"Mail: timed delivery ({injected_email.get('id')})"
        return True

    await _store_ref.update_state(user_id, updater, create_if_missing=False)


def is_notifications_enabled(user_id: str) -> bool:
    """Return whether notifications are enabled for *user_id*."""
    return _notif_enabled.get(user_id, False)


def start_dynamic_events(
    user_id: str, time_data: List[Dict], action_data: List[Dict], enable_notifications: bool = False
) -> None:
    """Start background tasks for timed emails; register action rules."""
    cancel_dynamic_events(user_id)

    available = min(
        MAX_DYNAMIC_EVENTS_PER_USER,
        max(0, MAX_DYNAMIC_EVENTS_TOTAL - _registered_event_count()),
    )
    time_data = (
        [item for item in time_data[:available] if isinstance(item, dict)]
        if isinstance(time_data, list)
        else []
    )
    remaining = available - len(time_data)
    action_data = (
        [item for item in action_data[:remaining] if isinstance(item, dict)]
        if isinstance(action_data, list)
        else []
    )
    if not time_data and not action_data:
        return

    _start_ts[user_id] = time.monotonic()
    _fired[user_id] = set()
    _notif_enabled[user_id] = enable_notifications

    # ── schedule timed emails ──
    for item in time_data:
        delay = _bounded_delay(item.get("arrive_after_s", 0))
        email = {k: v for k, v in item.items() if k != "arrive_after_s"}
        task = asyncio.create_task(
            _deliver_timed_email(user_id, email, delay),
            name=f"time_event_{user_id}_{email.get('id', '?')}",
        )
        _track_task(user_id, task)

    # ── register action rules ──
    if action_data:
        _actions[user_id] = list(action_data)


def cancel_dynamic_events(user_id: str) -> None:
    """Cancel all pending events for a user (e.g. on state reset)."""
    for task in _timers.pop(user_id, set()):
        task.cancel()
    _actions.pop(user_id, None)
    _fired.pop(user_id, None)
    _start_ts.pop(user_id, None)
    _notif_enabled.pop(user_id, None)


def shutdown_dynamic_events() -> None:
    """Cancel all tasks and clear every per-user registry."""
    user_ids = set(_timers) | set(_actions) | set(_fired) | set(_start_ts) | set(_notif_enabled)
    for user_id in user_ids:
        cancel_dynamic_events(user_id)


async def check_action_triggers(user_id: str, outgoing_email: Dict[str, Any]) -> None:
    """Called after a mail send or reply.  Check each unfired action rule."""
    rules = _actions.get(user_id)
    if not rules:
        return

    fired = _fired.setdefault(user_id, set())
    for idx, rule in enumerate(rules):
        if idx in fired:
            continue
        trigger = rule.get("trigger", {})
        if _email_matches_trigger(outgoing_email, trigger):
            fired.add(idx)
            delay = _bounded_delay(rule.get("delay_s", 0))
            reply_email = rule.get("email", {})
            if reply_email:
                task = asyncio.create_task(
                    _deliver_timed_email(user_id, reply_email, delay),
                    name=f"action_event_{user_id}_{idx}",
                )
                _track_task(user_id, task)
    if len(fired) >= len(rules):
        _actions.pop(user_id, None)
        _fired.pop(user_id, None)
        if user_id not in _timers:
            _start_ts.pop(user_id, None)
            _notif_enabled.pop(user_id, None)
