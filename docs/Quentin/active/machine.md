# WP0 — Contracts & Fakes — Machine Doc

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax. TDD, commit per task.

**Status:** planned (ready to implement) · **Branch:** `feat/contracts` · **Updated:** 2026-06-27 · Paired with [`human.md`](./human.md).

## 1. Overview
The first, unblocking work package. Freeze the interfaces Dev B builds against (`core/` types + ports, `api/schemas.py`) and ship the three fakes (`FakeEmbedder`, `FakeVectorStore`, `NullReranker`) that let every later slice be tested with no Turso/Ollama/TEI. `core/` is co-owned — this is our **proposal**, flagged for Arthur's sign-off.

**Goal:** importable contracts + green fakes + compose skeleton.
**Tech:** Python 3.12, stdlib-only `core/`, pydantic for schemas, pytest/ruff/pyright.

## 2. Design
- **Package root:** `sift/` (README §2 module map; placeholder codename — see `DECISIONS.md` D11, rename-later is a config/import sweep).
- **Dependency rule:** `core/` imports **nothing external** (dataclasses, not pydantic). `adapters/` import `core` only. `api/schemas.py` may use pydantic (it's the HTTP boundary, not `core`).
- **Ports** are `typing.Protocol` (structural — adapters need not inherit). Signatures verbatim from README §66–74.
- **Fakes** are deterministic and in-memory so tests are stable and offline.

**Files:**
```
pyproject.toml                         (Create — deps + tool config)
sift/__init__.py  sift/core/__init__.py  sift/adapters/__init__.py
  sift/adapters/embedding/__init__.py  sift/adapters/store/__init__.py
  sift/adapters/rerank/__init__.py  sift/api/__init__.py            (Create — packages)
sift/core/types.py                     (Create — Vector, Page, Document, Chunk, Hit, EMBED_DIM)
sift/core/ports.py                     (Create — Embedder, Reranker, Completer, VectorStore, Parser, Chunker)
sift/api/schemas.py                    (Create — Source, SearchResponse, FileStatus, IngestResponse, ManifestResponse, HealthResponse)
sift/adapters/rerank/null.py           (Create — NullReranker)
sift/adapters/embedding/fake.py        (Create — FakeEmbedder)
sift/adapters/store/fake.py            (Create — FakeVectorStore)
tests/test_types.py  tests/test_ports.py  tests/test_schemas.py
  tests/test_null_reranker.py  tests/test_fake_embedder.py  tests/test_fake_store.py   (Create)
docker-compose.yml  .env.example       (Create — skeleton)
```

## 3. Plan (TDD tasks)

### Task 1: Project bootstrap + `core/types.py`
**Files:** Create `pyproject.toml`, `sift/**/__init__.py`, `sift/core/types.py`, `tests/test_types.py`
**Interfaces:** Produces `Vector=list[float]`, `EMBED_DIM=1024`, `Page`, `Document`, `Chunk`, `Hit`.

- [ ] **Step 1: `pyproject.toml`**
```toml
[project]
name = "sift"
version = "0.0.0"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.9", "pydantic-settings>=2.14", "fastapi>=0.128",
                "uvicorn[standard]>=0.34", "httpx>=0.27", "openai>=1.50"]
[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.6", "pyright>=1.1"]
[tool.pytest.ini_options]
pythonpath = ["."]
[tool.ruff]
line-length = 100
```
- [ ] **Step 2: package `__init__.py` files** (empty): `sift/`, `sift/core/`, `sift/adapters/`, `sift/adapters/{embedding,store,rerank}/`, `sift/api/`.
- [ ] **Step 3: write the failing test** `tests/test_types.py`
```python
from sift.core.types import Vector, EMBED_DIM, Page, Document, Chunk, Hit

def test_embed_dim_is_1024():
    assert EMBED_DIM == 1024

def test_hit_and_chunk_construct():
    h = Hit(id="1", text="x", path="/a.md", page=2, score=0.9)
    assert h.path == "/a.md" and h.page == 2
    c = Chunk(id="1", text="x", path="/a.md", page=2, content_hash="ab", tenant="default")
    assert c.embedding is None and c.tenant == "default"

def test_document_holds_pages():
    d = Document(path="/a.md", pages=[Page(number=1, text="hi")], content_hash="ab")
    assert d.pages[0].text == "hi"
```
- [ ] **Step 4: run, expect FAIL** — `pytest tests/test_types.py -v` → `ModuleNotFoundError: sift.core.types`
- [ ] **Step 5: implement** `sift/core/types.py`
```python
"""Pure domain types — ZERO external deps (dependency rule: core imports nothing)."""
from __future__ import annotations
from dataclasses import dataclass

Vector = list[float]          # dense embedding; bge-m3 => length 1024
EMBED_DIM = 1024

@dataclass(frozen=True)
class Page:
    number: int
    text: str

@dataclass(frozen=True)
class Document:
    path: str
    pages: list[Page]
    content_hash: str

@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    path: str
    page: int | None
    content_hash: str
    tenant: str
    embedding: Vector | None = None

@dataclass(frozen=True)
class Hit:
    id: str
    text: str
    path: str
    page: int | None
    score: float
```
- [ ] **Step 6: run, expect PASS** — `pytest tests/test_types.py -v`
- [ ] **Step 7: commit** — `git add -A && git commit -m "feat(core): types + project bootstrap"`

### Task 2: `core/ports.py`
**Files:** Create `sift/core/ports.py`, `tests/test_ports.py`
**Interfaces:** Produces Protocols `Embedder`, `Reranker`, `Completer`, `VectorStore`, `Parser`, `Chunker`.

- [ ] **Step 1: failing test** `tests/test_ports.py` — a structural stub satisfies the port
```python
from sift.core.ports import Embedder
from sift.core.types import Vector

class _Stub:
    def embed(self, texts: list[str]) -> list[Vector]:
        return [[0.0] for _ in texts]

def test_stub_is_structural_embedder():
    e: Embedder = _Stub()          # passes pyright structurally
    assert e.embed(["a", "b"]) == [[0.0], [0.0]]
```
- [ ] **Step 2: run, expect FAIL** (`ModuleNotFoundError: sift.core.ports`)
- [ ] **Step 3: implement** `sift/core/ports.py`
```python
"""Ports — the interfaces everything codes against. Stdlib only."""
from __future__ import annotations
from typing import Protocol
from .types import Vector, Hit, Chunk, Document

class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[Vector]: ...

class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[Hit]) -> list[Hit]: ...

class Completer(Protocol):
    def complete(self, system: str, user: str) -> str: ...

class VectorStore(Protocol):
    def ensure_ready(self, model: str, dim: int) -> None: ...
    def upsert(self, chunks: list[Chunk]) -> None: ...
    def search(self, vector: Vector, k: int, tenant: str) -> list[Hit]: ...
    def known_hashes(self, tenant: str) -> set[str]: ...

class Parser(Protocol):
    def parse(self, data: bytes, filename: str) -> Document: ...

class Chunker(Protocol):
    def chunk(self, doc: Document) -> list[Chunk]: ...
```
- [ ] **Step 4: run, expect PASS**; **Step 5: commit** — `feat(core): ports (Embedder/Reranker/Completer/VectorStore/Parser/Chunker)`

### Task 3: `api/schemas.py`
**Files:** Create `sift/api/schemas.py`, `tests/test_schemas.py`
**Interfaces:** Produces `Source`, `SearchResponse`, `IngestStatus`, `IngestFileResult`, `IngestResponse`, `ManifestResponse`, `HealthResponse`. *(names aligned to Arthur — D17)*

- [ ] **Step 1: failing test** `tests/test_schemas.py`
```python
import pytest
from pydantic import ValidationError
from sift.api.schemas import SearchResponse, Source

def test_search_response_ok():
    r = SearchResponse(summary="s", sources=[Source(path="/a.md", page=1, score=0.5)])
    assert r.sources[0].path == "/a.md"

def test_source_rejects_bad_score():
    with pytest.raises(ValidationError):
        Source(path="/a.md", page=1, score="not-a-float")
```
- [ ] **Step 2: run, expect FAIL**
- [ ] **Step 3: implement** `sift/api/schemas.py`
```python
"""API request/response schemas (pydantic) — the HTTP boundary contract."""
from __future__ import annotations
from pydantic import BaseModel

class Source(BaseModel):
    path: str
    page: int | None = None
    score: float

class SearchResponse(BaseModel):
    summary: str
    sources: list[Source]

class IngestStatus(str, Enum):           # add `from enum import Enum` at top
    indexed = "indexed"
    skipped = "skipped"
    failed = "failed"

class IngestFileResult(BaseModel):
    filename: str
    status: IngestStatus
    detail: str | None = None

class IngestResponse(BaseModel):
    files: list[IngestFileResult]

class ManifestResponse(BaseModel):
    tenant: str
    hashes: list[str]

class HealthResponse(BaseModel):
    status: str
    embed_model: str
```
- [ ] **Step 4: run, expect PASS**; **Step 5: commit** — `feat(api): response schemas`

### Task 4: `adapters/rerank/null.py` (NullReranker)
**Files:** Create `sift/adapters/rerank/null.py`, `tests/test_null_reranker.py`
**Interfaces:** Consumes `Hit`. Produces `NullReranker.rerank(query, candidates)->list[Hit]` (identity).

- [ ] **Step 1: failing test**
```python
from sift.adapters.rerank.null import NullReranker
from sift.core.types import Hit

def test_null_reranker_preserves_order():
    hits = [Hit(id=str(i), text="t", path="/p", page=None, score=1.0 - i/10) for i in range(3)]
    assert NullReranker().rerank("q", hits) == hits
```
- [ ] **Step 2: run, expect FAIL**
- [ ] **Step 3: implement**
```python
"""Identity reranker — keeps vector-search order (RERANK_STRATEGY=none)."""
from __future__ import annotations
from ...core.types import Hit

class NullReranker:
    def rerank(self, query: str, candidates: list[Hit]) -> list[Hit]:
        return list(candidates)
```
- [ ] **Step 4: run, expect PASS**; **Step 5: commit** — `feat(rerank): null/identity reranker`

### Task 5: `adapters/embedding/fake.py` (FakeEmbedder)
**Files:** Create `sift/adapters/embedding/fake.py`, `tests/test_fake_embedder.py`
**Interfaces:** Produces `FakeEmbedder.embed(texts)->list[Vector]` — deterministic unit vectors of length `EMBED_DIM`.

- [ ] **Step 1: failing test**
```python
import math
from sift.adapters.embedding.fake import FakeEmbedder
from sift.core.types import EMBED_DIM

def test_deterministic_and_dim():
    e = FakeEmbedder()
    a1, a2 = e.embed(["alpha"])[0], e.embed(["alpha"])[0]
    assert a1 == a2 and len(a1) == EMBED_DIM

def test_unit_norm_and_distinct():
    e = FakeEmbedder()
    a, b = e.embed(["alpha"])[0], e.embed(["beta"])[0]
    assert abs(math.sqrt(sum(x*x for x in a)) - 1.0) < 1e-9
    assert a != b
```
- [ ] **Step 2: run, expect FAIL**
- [ ] **Step 3: implement**
```python
"""Deterministic, offline fake embedder for tests — no network."""
from __future__ import annotations
import hashlib, math
from ...core.types import Vector, EMBED_DIM

class FakeEmbedder:
    """Same text -> same unit vector of length `dim`; different text -> different vector."""
    def __init__(self, dim: int = EMBED_DIM) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[Vector]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> Vector:
        vals: list[float] = []
        counter = 0
        while len(vals) < self.dim:
            digest = hashlib.sha256(f"{text}:{counter}".encode()).digest()
            for i in range(0, len(digest), 4):
                if len(vals) >= self.dim:
                    break
                n = int.from_bytes(digest[i:i+4], "big")
                vals.append((n / 2**32) * 2 - 1)      # [-1, 1)
            counter += 1
        norm = math.sqrt(sum(v*v for v in vals)) or 1.0
        return [v / norm for v in vals]
```
- [ ] **Step 4: run, expect PASS**; **Step 5: commit** — `feat(embedding): deterministic fake embedder`

### Task 6: `adapters/store/fake.py` (FakeVectorStore)
**Files:** Create `sift/adapters/store/fake.py`, `tests/test_fake_store.py`
**Interfaces:** Consumes `Chunk`, `Hit`, `Vector`. Produces `FakeVectorStore` implementing the `VectorStore` port (in-memory cosine).

- [ ] **Step 1: failing test**
```python
from sift.adapters.store.fake import FakeVectorStore
from sift.adapters.embedding.fake import FakeEmbedder
from sift.core.types import Chunk

def _chunk(cid, text, emb, tenant="default"):
    return Chunk(id=cid, text=text, path=f"/{cid}.md", page=None,
                 content_hash=cid, tenant=tenant, embedding=emb)

def test_search_ranks_by_cosine_and_filters_tenant():
    e = FakeEmbedder()
    store = FakeVectorStore()
    store.ensure_ready("bge-m3", 1024)
    store.upsert([
        _chunk("a", "apple", e.embed(["apple"])[0]),
        _chunk("b", "banana", e.embed(["banana"])[0]),
        _chunk("c", "other", e.embed(["apple"])[0], tenant="t2"),  # different tenant
    ])
    hits = store.search(e.embed(["apple"])[0], k=2, tenant="default")
    assert hits[0].id == "a"                       # best match first
    assert all(h.id != "c" for h in hits)          # tenant filtered out

def test_known_hashes():
    store = FakeVectorStore()
    store.upsert([_chunk("a", "x", [0.0]*1024)])
    assert store.known_hashes("default") == {"a"}
```
- [ ] **Step 2: run, expect FAIL**
- [ ] **Step 3: implement**
```python
"""In-memory fake VectorStore — brute-force cosine search. Tests only."""
from __future__ import annotations
import math
from ...core.types import Vector, Hit, Chunk

def _cosine(a: Vector, b: Vector) -> float:
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)) or 1.0
    nb = math.sqrt(sum(y*y for y in b)) or 1.0
    return dot / (na * nb)

class FakeVectorStore:
    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._model: str | None = None
        self._dim: int | None = None

    def ensure_ready(self, model: str, dim: int) -> None:
        self._model, self._dim = model, dim

    def upsert(self, chunks: list[Chunk]) -> None:
        self._chunks.extend(c for c in chunks if c.embedding is not None)

    def search(self, vector: Vector, k: int, tenant: str) -> list[Hit]:
        scored = [(_cosine(vector, c.embedding), c) for c in self._chunks
                  if c.tenant == tenant and c.embedding is not None]
        scored.sort(key=lambda s: s[0], reverse=True)
        return [Hit(id=c.id, text=c.text, path=c.path, page=c.page, score=score)
                for score, c in scored[:k]]

    def known_hashes(self, tenant: str) -> set[str]:
        return {c.content_hash for c in self._chunks if c.tenant == tenant}
```
- [ ] **Step 4: run, expect PASS**; **Step 5: commit** — `feat(store): in-memory fake vector store`

### Task 7: `docker-compose.yml` skeleton + `.env.example`
**Files:** Create `docker-compose.yml`, `.env.example`
**Interfaces:** none (infra). Acceptance via `docker compose config`.

- [ ] **Step 1: write `docker-compose.yml`**
```yaml
# Skeleton — api + web; tei (cross-encoder) added behind a profile in WP9.
services:
  api:
    build: .
    environment:
      INGEST_TOKEN: ${INGEST_TOKEN:-dev-token}
      EMBED_BASE_URL: ${EMBED_BASE_URL:-http://host.docker.internal:11434/v1}
      EMBED_MODEL: ${EMBED_MODEL:-bge-m3}
      RERANK_STRATEGY: ${RERANK_STRATEGY:-llm}
      LLM_BASE_URL: ${LLM_BASE_URL:-}
      LLM_MODEL: ${LLM_MODEL:-}
    ports: ["8000:8000"]
    extra_hosts: ["host.docker.internal:host-gateway"]   # reach host inference (Linux)
  web:
    build: ./web
    ports: ["8080:80"]
    depends_on: [api]
```
- [ ] **Step 2: write `.env.example`** (all README §8 keys, blank/defaulted).
- [ ] **Step 3: validate** — `docker compose config -q` (expected: no error). *Note: `build` targets (`Dockerfile`, `web/`) are created in WP8; until then validate with `docker compose config` which doesn't build.*
- [ ] **Step 4: full suite** — `pytest -q` (all green) + `ruff check .`
- [ ] **Step 5: commit** — `chore(docker): compose skeleton + .env.example`

## 4. Test strategy
Pure-unit, offline. Fakes are the product of this WP and the test scaffolding for every later WP. No HTTP, no Turso. `pytest -q` must be green; `ruff` + `pyright` clean.

## 5. Implementation log
| Date | Commit | Change |
|------|--------|--------|
| _pending_ | | |

## 6. Decisions
- D2 (Turso native vectors — fake mirrors cosine semantics) · D3 (build against fakes) · D6 (config-driven) · **D11** (package name `sift/` placeholder — confirm with Arthur). See `DECISIONS.md`.

## 7. Changelog
- _unreleased_ — WP0 contracts & fakes.
