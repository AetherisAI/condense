"""The collect phase: run every golden question through Find and/or Ask, record everything.

Sequential on purpose — one question at a time, judge calls deferred to their own phase — so
the recorded latency is the system's, not contention with the harness. The first
``EVAL_WARMUP`` questions run once per surface and are discarded (cold model loads, connection
setup). A failing question is recorded with its ``error`` and the run carries on.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from sift.eval.config import EvalSettings
from sift.eval.golden import GoldenItem
from sift.eval.records import Passage, Surface, SurfaceResult
from sift.factory import Container

Progress = Callable[[str], None]


def _error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


async def collect_find(container: Container, item: GoldenItem, es: EvalSettings) -> SurfaceResult:
    try:
        trace = await container.search.trace(item.question, es.tenant)
    except Exception as exc:  # noqa: BLE001 — one bad question must not sink the whole run
        return SurfaceResult(item_id=item.id, surface="find", error=_error(exc))
    return SurfaceResult(
        item_id=item.id,
        surface="find",
        response=trace.outcome.summary,
        contexts=[Passage.from_hit(h) for h in trace.context],
        retrieved=[Passage.from_hit(h) for h in trace.retrieved],
        ranked=[Passage.from_hit(h) for h in trace.ranked],
        timings_ms=dict(trace.timings_ms),
    )


def _tool_passages(detail: Any) -> list[Passage]:
    """Passages from a ``search``/``get_document_chunks`` result (``list_documents`` has none)."""
    if not isinstance(detail, list):
        return []
    passages: list[Passage] = []
    for row in detail:
        if not isinstance(row, Mapping):
            continue
        text, path = row.get("text"), row.get("source_path")
        if not isinstance(text, str) or not isinstance(path, str):
            continue
        score, page, index = row.get("score"), row.get("page"), row.get("index")
        passages.append(
            Passage(
                path=path,
                page=page if isinstance(page, int) else 0,
                text=text,
                score=float(score) if isinstance(score, (int, float)) else None,
                source_hash=str(row.get("source_hash", "")),
                index=index if isinstance(index, int) else -1,
            )
        )
    return passages


async def collect_ask(container: Container, item: GoldenItem, es: EvalSettings) -> SurfaceResult:
    result = SurfaceResult(item_id=item.id, surface="ask")
    contexts: dict[tuple[str, str, int, str], Passage] = {}
    parts: list[str] = []
    tool_ms = 0.0
    start = time.perf_counter()
    call_started: float | None = None
    try:
        async for event in container.answer.run(item.question, es.tenant, grounding=es.grounding):
            if event.type == "tool_call":
                result.tool_calls += 1
                call_started = time.perf_counter()
            elif event.type == "tool_result":
                if call_started is not None:
                    tool_ms += (time.perf_counter() - call_started) * 1000
                    call_started = None
                for passage in _tool_passages(event.data.get("detail")):
                    key = (passage.path, passage.source_hash, passage.index, passage.text[:64])
                    contexts.setdefault(key, passage)
            elif event.type == "answer_delta":
                parts.append(str(event.data.get("text", "")))
            elif event.type == "sources":
                result.ranked = [
                    Passage(
                        path=str(s.get("path", "")),
                        page=int(s.get("page", 0)),
                        text=str(s.get("snippet", "")),
                        score=s.get("score"),
                    )
                    for s in event.data.get("items", [])
                ]
            elif event.type == "done":
                result.truncated = bool(event.data.get("truncated"))
    except Exception as exc:  # noqa: BLE001 — run() degrades gracefully; this is belt-and-braces
        result.error = _error(exc)
    total = (time.perf_counter() - start) * 1000
    result.response = "".join(parts)
    result.contexts = list(contexts.values())[: es.ask_max_contexts]
    result.timings_ms = {"total": total, "tools": tool_ms, "model": max(total - tool_ms, 0.0)}
    return result


_COLLECTORS = {"find": collect_find, "ask": collect_ask}


async def collect(
    container: Container,
    items: Sequence[GoldenItem],
    es: EvalSettings,
    surfaces: Sequence[Surface],
    progress: Progress | None = None,
) -> list[SurfaceResult]:
    """Every item × surface, in golden-set order, after ``es.warmup`` discarded warmup runs."""
    say = progress or (lambda _msg: None)
    results: list[SurfaceResult] = []
    for surface in surfaces:
        run_one = _COLLECTORS[surface]
        for item in items[: es.warmup]:
            await run_one(container, item, es)
        for n, item in enumerate(items, start=1):
            row = await run_one(container, item, es)
            status = f"ERROR {row.error}" if row.error else f"{row.timings_ms['total']:.0f} ms"
            say(f"[{surface} {n}/{len(items)}] {item.id}: {status}")
            results.append(row)
    return results
