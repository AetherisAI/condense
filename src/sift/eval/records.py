"""The harness's own record types — JSON-round-trippable rows for ``results.jsonl``.

Kept separate from ``core`` types on purpose: a run folder must stay readable after ``core``
evolves, so these carry plain fields only (no ``Hit``/``Chunk`` identity), and
:func:`record_from_dict` tolerates missing optional keys from older runs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from sift.core.types import Hit

Surface = Literal["find", "ask"]
SURFACES: tuple[Surface, ...] = ("find", "ask")


@dataclass(slots=True, kw_only=True)
class Passage:
    """One passage the system retrieved, cited, or showed its generator."""

    path: str
    page: int
    text: str
    score: float | None = None
    source_hash: str = ""
    index: int = -1

    @classmethod
    def from_hit(cls, hit: Hit) -> Passage:
        return cls(
            path=hit.source_path,
            page=hit.page,
            text=hit.text,
            score=hit.score,
            source_hash=hit.source_hash,
            index=hit.index,
        )

    def to_hit(self) -> Hit:
        return Hit(
            text=self.text,
            score=self.score or 0.0,
            source_path=self.path,
            page=self.page,
            source_hash=self.source_hash,
            index=self.index,
        )


@dataclass(slots=True, kw_only=True)
class SurfaceResult:
    """One golden item answered by one surface, plus everything scored about it.

    ``retrieved`` is Find's raw vector-search order (empty for Ask). ``ranked`` is Find's
    post-rerank list, or Ask's cited sources (snippet text only). ``contexts`` is exactly what
    the generator saw — the recap passages for Find, every tool-result passage for Ask — and is
    what faithfulness/context utilization are judged against.
    """

    item_id: str
    surface: Surface
    response: str = ""
    contexts: list[Passage] = field(default_factory=list)
    retrieved: list[Passage] = field(default_factory=list)
    ranked: list[Passage] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)
    tool_calls: int = 0
    truncated: bool = False
    error: str | None = None
    scores: dict[str, float | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def record_from_dict(raw: dict[str, Any]) -> SurfaceResult:
    passages = {
        key: [Passage(**p) for p in raw.get(key, [])] for key in ("contexts", "retrieved", "ranked")
    }
    return SurfaceResult(
        item_id=raw["item_id"],
        surface=raw["surface"],
        response=raw.get("response", ""),
        timings_ms=dict(raw.get("timings_ms", {})),
        tool_calls=raw.get("tool_calls", 0),
        truncated=raw.get("truncated", False),
        error=raw.get("error"),
        scores=dict(raw.get("scores", {})),
        **passages,
    )
