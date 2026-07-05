"""The ToolRegistry — the single source of truth for tool definitions (WP v0.2.0 T2, D38).

North star (see ``docs/Quentin/active/machine.md`` §0): the TOOLBOX is the product. Every
deterministic, LLM-free capability Condense exposes — search, list documents, read one
document's chunks — is defined exactly once here and rendered for every consumer: the
``/v1/tools/*`` REST routes call an entry's ``executor`` directly; a future ``/v1/answer``
tool-calling loop and an eventual MCP wrapper render the same registry's
:meth:`ToolRegistry.to_openai_functions`/:meth:`ToolRegistry.to_json_schema_manifest`. If a
future consumer needs a capability, it MUST first exist as a registry tool here — no
side-channel.

Ports + config only (the dependency rule: ``pipelines`` never imports an adapter) — built from
:class:`~sift.core.ports.Embedder`/:class:`~sift.core.ports.VectorStore` by
:func:`build_tool_registry`, which ``factory.py`` (the composition root) calls once per
container. ``PATCH /settings`` is never registered here — see
``tests/pipelines/test_tools_schema.py``.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sift.config import Settings
from sift.core.ports import Embedder, VectorStore
from sift.core.types import Chunk, Hit, SearchFilters
from sift.pipelines.documents import SupportsChunkAccess, SupportsDocumentAdmin

Executor = Callable[[Mapping[str, Any], str], Awaitable[Any]]


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolSpec:
    """One registry entry: identity, its raw-JSON-Schema parameters, and its bound executor.

    ``executor`` takes ``(args, tenant)`` — the tool's arguments as a plain mapping (already
    validated/shaped by whichever consumer called in: a Pydantic request body, a tool-call's
    parsed JSON, ...) plus the resolved tenant, threaded like every other seam in the system.
    """

    name: str
    description: str
    params_json_schema: Mapping[str, Any]
    executor: Executor


class ToolRegistry:
    """An immutable set of :class:`ToolSpec`, addressable by name and renderable as schema."""

    def __init__(self, specs: Sequence[ToolSpec]) -> None:
        self._specs: dict[str, ToolSpec] = {spec.name: spec for spec in specs}

    def tools(self) -> list[ToolSpec]:
        """Every registered tool, in registration order."""
        return list(self._specs.values())

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    async def call(self, name: str, args: Mapping[str, Any], tenant: str) -> Any:
        """Look up ``name`` and run its executor; raises ``KeyError`` for an unknown tool."""
        spec = self._specs.get(name)
        if spec is None:
            raise KeyError(f"unknown tool {name!r}")
        return await spec.executor(args, tenant)

    def to_openai_functions(self) -> list[dict[str, Any]]:
        """The OpenAI function-calling ``tools=[...]`` shape, generated from the registry."""
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": dict(spec.params_json_schema),
                },
            }
            for spec in self._specs.values()
        ]

    def to_json_schema_manifest(self) -> dict[str, Any]:
        """A plain JSON-Schema-flavored manifest of every registered tool."""
        return {
            "tools": [
                {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": dict(spec.params_json_schema),
                }
                for spec in self._specs.values()
            ]
        }


# --- JSON-Schema parameter specs (hand-written once; rendered, never duplicated) --------------

_SEARCH_PARAMS: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "The natural-language search query."},
        "k": {
            "type": "integer",
            "minimum": 1,
            "description": "How many ranked hits to return (defaults to and is capped by "
            "server config; no LLM recap — raw retrieval only).",
        },
        "filters": {
            "type": "object",
            "description": "Narrows the candidate set before ranking.",
            "properties": {
                "metadata": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Equality match: a chunk must carry every given key/value.",
                },
                "since": {
                    "type": "string",
                    "description": "ISO-8601 inclusive lower bound on the source file's "
                    "modified_at.",
                },
                "until": {
                    "type": "string",
                    "description": "ISO-8601 inclusive upper bound on the source file's "
                    "modified_at.",
                },
            },
        },
    },
    "required": ["query"],
}

_LIST_DOCUMENTS_PARAMS: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "limit": {
            "type": "integer",
            "minimum": 1,
            "description": "Page size (default 100).",
        },
        "offset": {
            "type": "integer",
            "minimum": 0,
            "description": "Page offset (default 0).",
        },
        "metadata": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": "Only documents with a chunk matching every given key/value.",
        },
    },
}

_GET_DOCUMENT_CHUNKS_PARAMS: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "source_hash": {
            "type": "string",
            "description": "The document's content hash (see list_documents/ingest results).",
        },
    },
    "required": ["source_hash"],
}


# --- executors (bound onto the wired ports by build_tool_registry) ----------------------------


def _filters_from_args(raw: Mapping[str, Any] | None) -> SearchFilters | None:
    """``None`` when nothing narrows the search; a :class:`SearchFilters` otherwise."""
    if not raw:
        return None
    metadata = raw.get("metadata") or None
    since = raw.get("since")
    until = raw.get("until")
    if metadata is None and since is None and until is None:
        return None
    return SearchFilters(metadata=metadata, since=since, until=until)


async def _search_executor(
    embedder: Embedder,
    store: VectorStore,
    settings: Settings,
    args: Mapping[str, Any],
    tenant: str,
) -> list[Hit]:
    """Embed → ``store.search`` — the toolbox's raw-retrieval primitive. NO recap, NO LLM."""
    query = str(args["query"])
    requested_k = args.get("k")
    k = settings.tools_search_k if requested_k is None else int(requested_k)
    k = min(max(k, 1), settings.tools_search_max_k)
    filters = _filters_from_args(args.get("filters"))
    await store.ensure_ready(settings.embed_model, settings.embed_dim, tenant)
    (vector,) = await embedder.embed([query])
    return await store.search(vector, k, tenant, filters)


async def _list_documents_executor(
    store: VectorStore, settings: Settings, args: Mapping[str, Any], tenant: str
) -> dict[str, Any]:
    """Paginated document listing, optionally narrowed by metadata equality.

    Calls ``ensure_ready`` first — exactly like ``search`` — so the FIRST call on a fresh
    process against a not-yet-migrated store (e.g. a libSQL DB predating the ``metadata``
    column) migrates instead of 500ing (BUG #1, D40 amendment).
    """
    limit = int(args.get("limit") or 100)
    offset = int(args.get("offset") or 0)
    metadata = args.get("metadata") or None
    await store.ensure_ready(settings.embed_model, settings.embed_dim, tenant)
    if not isinstance(store, SupportsDocumentAdmin):
        return {"documents": [], "total": 0, "limit": limit, "offset": offset}
    documents = await store.list_documents(tenant, metadata=metadata)
    total = len(documents)
    page = documents[offset : offset + limit]
    return {"documents": page, "total": total, "limit": limit, "offset": offset}


async def _get_document_chunks_executor(
    store: VectorStore, settings: Settings, args: Mapping[str, Any], tenant: str
) -> list[Chunk]:
    """One document's chunks, ordered by ``index`` — empty when the store can't do chunk access.

    Calls ``ensure_ready`` first — same BUG #1 fix as ``_list_documents_executor`` above.
    """
    source_hash = str(args["source_hash"])
    await store.ensure_ready(settings.embed_model, settings.embed_dim, tenant)
    if not isinstance(store, SupportsChunkAccess):
        return []
    return await store.get_chunks(source_hash, tenant)


def build_tool_registry(embedder: Embedder, store: VectorStore, settings: Settings) -> ToolRegistry:
    """Build the standing registry from the wired ports — called once by ``factory.py``."""
    specs = [
        ToolSpec(
            name="search",
            description=(
                "Semantic search over ingested documents. Returns raw ranked passages "
                "(text, source, page, score) with NO LLM summary — the caller reasons over "
                "the hits itself. Prefer this for CONTENT questions (what does X say, who "
                "would fit Y) over paging through documents one by one. Each hit also carries "
                "modified_at (the source file's last-modified timestamp, ISO-8601 or null if "
                "unknown) and metadata (per-file tags); answer time/recency questions ('when "
                "was this written/updated') from modified_at, NEVER from a date that happens "
                "to appear in a filename."
            ),
            params_json_schema=_SEARCH_PARAMS,
            executor=functools.partial(_search_executor, embedder, store, settings),
        ),
        ToolSpec(
            name="list_documents",
            description=(
                "List ingested documents (paginated), optionally filtered by metadata. "
                "Authoritative and sufficient ALONE for enumeration questions ('what "
                "documents/people/things exist', counts, listings) — its paths and counts "
                "do not need verifying by opening every document's chunks. Each document also "
                "carries modified_at (the source file's last-modified timestamp, ISO-8601 or "
                "null if unknown) — answer time/recency questions from modified_at, NEVER from "
                "a date that happens to appear in a filename."
            ),
            params_json_schema=_LIST_DOCUMENTS_PARAMS,
            executor=functools.partial(_list_documents_executor, store, settings),
        ),
        ToolSpec(
            name="get_document_chunks",
            description=(
                "Fetch the ordered chunks of one ingested document by its content hash. For "
                "drilling into a SMALL number of specific documents already identified by "
                "name — never for iterating over the whole corpus one document at a time "
                "(use list_documents alone for enumeration; that will exhaust the tool-call "
                "budget before finishing). Each chunk also carries modified_at (the source "
                "file's last-modified timestamp) and metadata; answer time/recency questions "
                "from modified_at, NEVER from a date embedded in the filename."
            ),
            params_json_schema=_GET_DOCUMENT_CHUNKS_PARAMS,
            executor=functools.partial(_get_document_chunks_executor, store, settings),
        ),
    ]
    return ToolRegistry(specs)
