"""Continuous, debounced file watching via ``watchdog`` (cross-platform).

``watchdog`` picks the native backend per OS — FSEvents (macOS), ReadDirectoryChangesW
(Windows), inotify (Linux) — and falls back to polling where none is available. Raw change
events arrive in bursts (an editor save can fire several within milliseconds), so we don't
sync per event: every event (re)arms a single shared timer, and only after a quiet ``debounce``
window do we fire one ``on_change`` callback. One :class:`Watcher` covers *several* folders/files
at once (one ``Observer``, many schedules) with that single global debounce, so a burst spread
across folders still collapses to one sync. The callback runs on the timer thread, off the UI.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

# Only true content changes should trigger a sync. watchdog's inotify backend also emits
# read-only events — ``opened``, ``closed_no_write``, ``accessed`` — and a sync's own hashing
# *opens and reads* every watched file, firing exactly those events, which would re-arm the
# debounce and re-sync forever: a self-feeding loop that pins CPU + disk and (via the server)
# piles up ingests until OOM. Reacting only to create/modify/move/delete breaks the loop while
# still catching every real edit, new file, rename, and deletion. See DECISIONS.md D29.
_CHANGE_EVENTS = frozenset({"created", "modified", "moved", "deleted"})


class _Handler(FileSystemEventHandler):
    """Forwards non-directory events to the shared debouncer; ``only`` pins it to one file."""

    def __init__(self, arm: Callable[[], None], only: str | None) -> None:
        self._arm = arm
        self._only = only  # set when watching a single file — ignore its siblings

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if event.event_type not in _CHANGE_EVENTS:
            return  # ignore opened/closed_no_write/accessed — our own reads must not self-trigger
        if self._only is not None:
            paths = (getattr(event, "src_path", ""), getattr(event, "dest_path", ""))
            if not any(os.path.abspath(p) == self._only for p in paths if p):
                return
        self._arm()


class Watcher:
    """Watches several folders (recursive) and/or files, firing ``on_change`` after each burst."""

    def __init__(
        self,
        paths: list[str],
        on_change: Callable[[], None],
        *,
        recursive: bool = True,
        debounce: float = 1.5,
    ) -> None:
        self._paths = [os.path.abspath(p) for p in paths]
        self._on_change = on_change
        self._recursive = recursive
        self._debounce = debounce
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._observer = Observer()

    # --- shared debounce ----------------------------------------------------------

    def _arm(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        with self._lock:
            self._timer = None
        self._on_change()

    # --- lifecycle ----------------------------------------------------------------

    def start(self) -> None:
        for path in self._paths:
            if os.path.isfile(path):
                # A single file: watch its parent dir, filter events down to that file.
                self._observer.schedule(_Handler(self._arm, path), os.path.dirname(path))
            elif os.path.isdir(path):
                self._observer.schedule(_Handler(self._arm, None), path, recursive=self._recursive)
        self._observer.start()

    def stop(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self._observer.stop()
        self._observer.join(timeout=5)
