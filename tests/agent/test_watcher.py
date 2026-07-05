"""Offline regression tests for the watcher's event filter (A5 / DECISIONS D29, D32).

Pure stdlib: stub event objects carrying only the attributes ``_Handler`` reads
(``.event_type``/``.is_directory``/``.src_path``/``.dest_path``) so the filter is exercised
without a live ``watchdog`` ``Observer`` or a real filesystem. This is the most safety-critical
change in the branch (it's what stops the agent's own file-hashing from re-triggering itself
forever, see D29) and previously had zero automated coverage.
"""

from __future__ import annotations

from agent.watcher import _CHANGE_EVENTS, _Handler
from watchdog.events import FileSystemEvent

READ_EVENTS = ("opened", "closed_no_write", "accessed", "closed")
CHANGE_EVENTS = ("created", "modified", "moved", "deleted")


class _Ev(FileSystemEvent):
    """Minimal stand-in for a ``watchdog`` ``FileSystemEvent``.

    A real subclass (not just a duck-typed look-alike) so it satisfies ``_Handler.on_any_event``'s
    ``FileSystemEvent`` parameter type; ``event_type``/``is_directory`` are set post-``__init__``
    since the real dataclass declares them ``init=False`` (concrete watchdog subclasses like
    ``FileCreatedEvent`` fix them as class attributes instead of taking them as constructor args).
    """

    def __init__(
        self,
        event_type: str,
        *,
        is_directory: bool = False,
        src: str = "/x/a.pdf",
        dest: str = "",
    ) -> None:
        super().__init__(src, dest)
        self.event_type = event_type
        self.is_directory = is_directory


def _handler(only: str | None = None) -> tuple[list[int], _Handler]:
    """A fresh ``_Handler`` wired to a call counter, so tests assert exact arm counts."""
    calls = [0]
    handler = _Handler(lambda: calls.__setitem__(0, calls[0] + 1), only)
    return calls, handler


def test_change_events_constant_matches_expected_set() -> None:
    # Pin the exact set the filter reacts to, so a future edit that silently narrows/widens it
    # (e.g. dropping "moved") is caught here instead of live, in production.
    assert _CHANGE_EVENTS == frozenset({"created", "modified", "moved", "deleted"})


def test_read_events_do_not_arm_a_sync() -> None:
    """opened/closed_no_write/accessed/closed are the agent's own hashing reads — must be inert."""
    calls, handler = _handler()
    for et in READ_EVENTS:
        handler.on_any_event(_Ev(et))
    assert calls[0] == 0


def test_real_changes_each_arm_a_sync() -> None:
    """created/modified/moved/deleted are genuine edits — every one must arm the debounce."""
    calls, handler = _handler()
    for et in CHANGE_EVENTS:
        handler.on_any_event(_Ev(et))
    assert calls[0] == len(CHANGE_EVENTS)


def test_directory_events_are_always_ignored() -> None:
    """A directory-level event (even a real change type) must never arm — only files matter."""
    calls, handler = _handler()
    for et in (*CHANGE_EVENTS, *READ_EVENTS):
        handler.on_any_event(_Ev(et, is_directory=True))
    assert calls[0] == 0


def test_only_filter_ignores_sibling_files() -> None:
    """Watching a single file (``only`` set) must ignore a change event for a sibling path."""
    calls, handler = _handler("/x/a.pdf")
    handler.on_any_event(_Ev("modified", src="/x/sibling.pdf"))
    assert calls[0] == 0


def test_only_filter_fires_for_the_watched_file() -> None:
    """The scoped file's own change (matched by absolute path) must still arm the debounce."""
    calls, handler = _handler("/x/a.pdf")
    handler.on_any_event(_Ev("modified", src="/x/a.pdf"))
    assert calls[0] == 1


def test_only_filter_matches_via_dest_path_on_move() -> None:
    """A move event that renames *into* the watched file (via dest_path) must still arm it."""
    calls, handler = _handler("/x/a.pdf")
    handler.on_any_event(_Ev("moved", src="/x/old-name.pdf", dest="/x/a.pdf"))
    assert calls[0] == 1
