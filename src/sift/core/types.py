"""Pure domain types — the shared vocabulary every layer codes against.

stdlib only (the dependency rule: ``core`` imports nothing external), so any adapter or
pipeline can depend on these without dragging in pydantic, httpx, libsql, or torch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

type Vector = tuple[float, ...]
"""An embedding: an ordered, immutable sequence of floats.

Its length is the embedding model's dimension (1024 for bge-m3) — a *config* value,
never baked into the type. ``tuple`` (not ``list``) keeps it immutable and hashable so
it nests cleanly inside the frozen dataclasses below.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class Page:
    """One page (or the sole page of a non-paged file) of a parsed document."""

    number: int  # 1-based; the citation unit. Non-paged formats emit a single Page(number=1).
    text: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Document:
    """A parsed source file: its identity, dedup hash, and page-segmented text."""

    path: str  # source path → becomes Source.path
    content_hash: str  # sha256 hex of the raw bytes → manifest + dedup; set by the Parser
    pages: tuple[Page, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Chunk:
    """An embeddable unit of a document.

    Carries everything the store needs to persist and later cite it. ``vector`` is None
    until the ingest pipeline fills it after embedding (via ``dataclasses.replace``).
    """

    text: str  # embedded; carried into Hit; summarized by the recap
    source_path: str  # denormalized from Document.path (chunks travel detached from their doc)
    page: int  # citation page
    source_hash: str  # parent file hash → known_hashes / manifest
    index: int  # 0-based ordinal within the document; (source_hash, index) is a stable PK
    vector: Vector | None = None  # None pre-embed; asserted non-None at upsert
    modified_at: str | None = None  # source file's last-modified time (ISO-8601); recency signal
    metadata: dict[str, str] | None = None  # per-file tags threaded in at ingest; None = none set


@dataclass(frozen=True, slots=True, kw_only=True)
class Hit:
    """A retrieval result: a chunk's text plus its relevance score and citation.

    ``score`` holds cosine similarity after vector search and is replaced by the
    cross-encoder score after reranking. ``text`` is required so the reranker can score
    the (query, passage) pair and the recap can summarize it.
    """

    text: str
    score: float
    source_path: str  # → Source.path
    page: int  # → Source.page
    source_hash: str = ""
    index: int = -1
    modified_at: str | None = None  # source file's last-modified time (ISO-8601); primary recency
    indexed_at: str | None = None  # when the store indexed it; recency fallback when mtime absent
    metadata: dict[str, str] | None = None  # from Chunk.metadata; carried through for filtering


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentInfo:
    """One ingested source file, aggregated from its chunks (one row per source_hash).

    ``modified_at``/``indexed_at`` (D44, additive) mirror ``Hit``'s own pair — the source
    file's true last-modified time (``None`` when never provided at ingest) and when the
    store indexed it, so a tool consumer can answer "when was this written/modified" from
    real timestamps instead of guessing from a filename.
    """

    source_path: str
    source_hash: str
    chunks: int
    modified_at: str | None = None
    indexed_at: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchSource:
    """One search-result citation — the domain sibling of the API's ``api.schemas.Source``.

    Mirrors that pydantic schema's fields exactly (``pipelines/search.py`` builds this, never
    the API schema directly — the dependency rule: pipelines never import ``sift.api``); ``api/
    routes.py``'s search handler maps this 1:1 onto ``Source`` for the HTTP response, so the
    wire shape is unchanged even though the pipeline no longer constructs it.
    """

    path: str
    page: int
    score: float
    snippet: str = ""
    index: int | None = None
    metadata: dict[str, str] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchOutcome:
    """The search pipeline's result: the recap plus its source citations.

    The domain sibling of ``api.schemas.SearchResponse`` — :class:`~sift.pipelines.search.
    SearchPipeline` returns this (stdlib-only, no pydantic), and ``api/routes.py``'s search
    handler maps it 1:1 onto ``SearchResponse`` for the HTTP response.
    """

    summary: str
    sources: list[SearchSource]


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchFilters:
    """Narrows a :meth:`~sift.core.ports.VectorStore.search` candidate set (WP v0.2.0 T2, D38).

    Every field is optional and additive — ``None``/empty means "no constraint on that axis".
    A conforming store applies these BEFORE its ``k`` ranking limit (a narrowed candidate set,
    not a post-hoc filter on an already-capped top-K): ``metadata`` is equality on every given
    key (a chunk matches only if all keys are present with the exact given value); ``since``/
    ``until`` bound ``modified_at`` (inclusive), compared as raw ISO-8601 strings — consistent
    zero-padded ISO-8601 sorts lexicographically the same as chronologically, so no datetime
    parsing is needed store-side.
    """

    metadata: dict[str, str] | None = None
    since: str | None = None
    until: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCall:
    """One tool invocation a :class:`~sift.core.ports.ToolCompleter` wants executed.

    Uniform across native OpenAI-style function-calling and the prompted-JSON fallback (WP
    v0.2.0 T3, D40) — whichever path produced it, the answer loop drives it through
    :class:`~sift.pipelines.tools.ToolRegistry` the same way. ``id`` mirrors a native
    provider's call id when one exists (echoed back in the ``tool`` message so multi-call
    turns stay attributable); the prompted fallback, which has no such id, synthesizes one.
    """

    name: str
    arguments: dict[str, Any]
    id: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCompletion:
    """A :class:`~sift.core.ports.ToolCompleter` turn: tool call(s) to run, or a final message.

    Exactly one of the two is meaningful per turn: non-empty ``tool_calls`` means "run these
    and give me the results"; an empty ``tool_calls`` means ``content`` is the model's final
    answer for this loop.
    """

    tool_calls: tuple[ToolCall, ...] = ()
    content: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ConversationTurn:
    """One stored turn of a ``/v1/answer`` conversation (WP v0.2.0 T3, D40).

    Only ``"user"``/``"assistant"`` turns are persisted here — the intra-turn tool-call/
    tool-result exchange stays local to that one request's transcript (see
    ``pipelines/answer.py``); this is conversational continuity across separate ``/v1/answer``
    calls, never the reasoning trace. ``turn`` is a 0-based ordinal within the conversation.
    ``sources`` (WP v0.2.0 T6, D42) is set only on an assistant turn that cited retrieved
    passages — the same compact ``{path, page, score, snippet}`` shape the ``sources`` SSE
    event carries, persisted so ``GET /v1/conversations/{id}`` can render a reopened
    conversation's citations without re-running the tool loop.

    ``grounding_used``/``from_general_knowledge``/``grounding_segments`` (D51) are the SAME
    trust-boundary fields the ``grounding`` SSE event carries for the live turn (D46/D48), set
    only on an assistant turn — persisted so a reopened conversation (History, a tab switch, a
    page reload) renders THIS turn's own recorded grounding, never re-derived from whatever mode
    happens to be selected live. Motivating bug: before this field existed, a remount reset
    every turn's grounding to "unknown", and the purple general-knowledge marking silently
    vanished from a message that legitimately had it.
    """

    role: str  # "user" | "assistant"
    content: str
    turn: int
    created_at: str  # ISO-8601, set by the store
    sources: list[dict[str, Any]] | None = None
    grounding_used: str | None = None  # "strict" | "hybrid" | "open" | None (user turns, legacy)
    from_general_knowledge: bool = False
    grounding_segments: list[dict[str, Any]] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ConversationMeta:
    """One conversation's metadata row (WP v0.2.0 T6, D42) — ``GET /v1/conversations`` listing
    shape and the header of ``GET /v1/conversations/{id}``.

    ``title`` is ``None`` until the auto-title pass fires after the first assistant answer
    (or ``Settings.answer_autotitle_enabled`` is off); ``turn_count`` is every stored turn
    (user + assistant), not exchange pairs.
    """

    conversation_id: str
    title: str | None
    created_at: str
    updated_at: str
    turn_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ConversationDetail:
    """A full conversation: its metadata plus every stored turn, oldest first."""

    meta: ConversationMeta
    turns: list[ConversationTurn]
