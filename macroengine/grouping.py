"""Display-only grouping for the event timeline.

A held key produces hundreds of repeated ``key_down`` events (OS key-repeat) and
mouse motion produces thousands of ``mouse_move`` samples — yet the macro is
"simple". Compact view collapses each *run of consecutive same-kind events* into a
single display row. This is purely cosmetic: the underlying events are untouched,
so playback is byte-for-byte identical.

A group is a ``(start, length)`` span into the events list. In detailed mode every
event is its own length-1 group.
"""

from __future__ import annotations

from typing import List, Tuple

from .models.event import KEY_DOWN, MOUSE_MOVE, MOUSE_SCROLL, Event

Group = Tuple[int, int]  # (start_index, length)


def build_groups(events: List[Event], compact: bool) -> List[Group]:
    if not compact:
        return [(i, 1) for i in range(len(events))]

    groups: List[Group] = []
    i, n = 0, len(events)
    while i < n:
        ev = events[i]
        j = i + 1
        if ev.type == MOUSE_MOVE:
            while j < n and events[j].type == MOUSE_MOVE:
                j += 1
        elif ev.type == KEY_DOWN:  # auto-repeat of a held key
            key = ev.data.get("key")
            while j < n and events[j].type == KEY_DOWN and events[j].data.get("key") == key:
                j += 1
        elif ev.type == MOUSE_SCROLL:
            while j < n and events[j].type == MOUSE_SCROLL:
                j += 1
        groups.append((i, j - i))
        i = j
    return groups


def group_span_delay(events: List[Event], start: int, length: int) -> float:
    return sum(events[k].delay for k in range(start, start + length))


def group_describe(events: List[Event], start: int, length: int) -> str:
    ev = events[start]
    if length == 1:
        return ev.describe()
    total = group_span_delay(events, start, length)
    if ev.type == MOUSE_MOVE:
        last = events[start + length - 1]
        return f"Mouse move ×{length} → ({last.data.get('x', '?')}, {last.data.get('y', '?')})  [{total:.2f}s]"
    if ev.type == KEY_DOWN:
        return f"Hold key '{ev.data.get('key', '?')}' ×{length}  [{total:.2f}s]"
    if ev.type == MOUSE_SCROLL:
        return f"Scroll ×{length}  [{total:.2f}s]"
    return f"{ev.type} ×{length}  [{total:.2f}s]"
