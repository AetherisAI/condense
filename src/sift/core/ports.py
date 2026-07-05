"""The ports — the interfaces every component codes against (README §2).

stdlib only. All methods are ``async def`` for one uniform rule: the real adapters do
network/DB I/O behind async FastAPI, and the pure-CPU ones simply never ``await``. Ports
are :class:`typing.Protocol`, so an implementation conforms *structurally* — a fake and a
real adapter satisfy the same port without sharing a base class (and fakes never inherit
a concrete adapter).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from sift.core.types import Chunk, Document, Hit, SearchFilters, ToolCompletion, Vector


@runtime_checkable
class Embedder(Protocol):
    """Text → vector. One shared model across the system (bge-m3)."""

    async def embed(self, texts: Sequence[str]) -> list[Vector]: ...


@runtime_checkable
class Reranker(Protocol):
    """Reorders retrieval candidates by true query↔passage relevance.

    Returns the candidates reordered (and re-scored); the caller keeps the top FINAL_K.
    """

    async def rerank(self, query: str, candidates: list[Hit]) -> list[Hit]: ...


@runtime_checkable
class Completer(Protocol):
    """Chat/completion model used to recap the best chunk into a summary."""

    async def complete(self, system: str, user: str) -> str: ...


@runtime_checkable
class VectorStore(Protocol):
    """Vectors + metadata + dedup behind one port.

    Every method takes ``tenant`` so multi-tenancy is additive, not a refactor; the PoC
    hardcodes ``"default"`` but the parameter exists everywhere from day one.
    """

    async def ensure_ready(self, model: str, dim: int, tenant: str) -> None:
        """Pin the tenant's base to ``(model, dim)`` on first use, or raise
        :class:`~sift.core.errors.ModelPinMismatch` if already pinned to something else."""
        ...

    async def upsert(self, chunks: Sequence[Chunk], tenant: str) -> None:
        """Persist embedded chunks; idempotent on ``(source_hash, index)``."""
        ...

    async def search(
        self, vector: Vector, k: int, tenant: str, filters: SearchFilters | None = None
    ) -> list[Hit]:
        """Return up to ``k`` nearest chunks for the tenant, most relevant first.

        ``filters`` is additive (default ``None`` — every existing call site is unaffected):
        when given, a conforming store narrows the candidate set by it BEFORE applying ``k``
        (WP v0.2.0 T2, D38) — never a post-hoc Python filter on an already-capped top-K.
        """
        ...

    async def known_hashes(self, tenant: str) -> set[str]:
        """The set of ingested file content-hashes — backs the agent's dedup diff."""
        ...


@runtime_checkable
class ToolCompleter(Protocol):
    """Chat model that can drive :class:`~sift.pipelines.tools.ToolRegistry` tool calls.

    The additive port behind the ``/v1/answer`` reference agent (WP v0.2.0 T3, D40) — uniform
    across native OpenAI-style function-calling and a prompted strict-JSON fallback (a model
    with no native tool-calling support), so :mod:`sift.pipelines.answer` codes against ONE
    method regardless of which path a given implementation takes for a given call.

    ``messages`` is the running OpenAI-style chat transcript (the system prompt is message[0];
    the caller threads conversation history and prior tool exchanges the same way any
    OpenAI-compatible chat endpoint expects). ``tools`` is
    :meth:`~sift.pipelines.tools.ToolRegistry.to_openai_functions`'s output verbatim — the
    function-calling ``tools=[...]`` shape — so the SAME registry render drives both a native
    ``tools=`` HTTP param and a prompted implementation's own rendering of it into instructions.
    """

    async def complete_with_tools(
        self, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]
    ) -> ToolCompletion: ...


@runtime_checkable
class Parser(Protocol):
    """Bytes → a page-segmented Document (markitdown in the real adapter)."""

    async def parse(self, data: bytes, filename: str) -> Document: ...


@runtime_checkable
class Chunker(Protocol):
    """Document → embeddable chunks (token-windowed in the real adapter)."""

    async def chunk(self, doc: Document) -> list[Chunk]: ...
