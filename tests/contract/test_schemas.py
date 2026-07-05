"""Lock the §8 API contract shapes (pydantic round-trips)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sift.api.schemas import (
    AnswerRequest,
    AnswerResponse,
    DocumentSummary,
    GroundingSegment,
    HealthResponse,
    IngestFileResult,
    IngestResponse,
    IngestStatus,
    ManifestResponse,
    SearchResponse,
    Source,
)


def test_search_response_roundtrip() -> None:
    resp = SearchResponse(
        summary="the sky is blue",
        sources=[Source(path="a.md", page=1, score=0.97, snippet="the sky is blue", index=4)],
    )
    dumped = resp.model_dump()
    assert dumped == {
        "summary": "the sky is blue",
        "sources": [
            {
                "path": "a.md",
                "page": 1,
                "score": 0.97,
                "snippet": "the sky is blue",
                "index": 4,
                "metadata": None,
            }
        ],
    }
    assert SearchResponse.model_validate(dumped) == resp


def test_source_carries_metadata_when_set() -> None:
    source = Source(path="a.md", page=1, score=0.5, metadata={"author": "quentin", "kind": "note"})
    dumped = source.model_dump()
    assert dumped["metadata"] == {"author": "quentin", "kind": "note"}
    assert Source.model_validate(dumped) == source


def test_ingest_response_roundtrip() -> None:
    resp = IngestResponse(
        tenant="default",
        results=[
            IngestFileResult(path="a.md", status=IngestStatus.indexed, content_hash="h1", chunks=3),
            IngestFileResult(path="b.md", status=IngestStatus.skipped_dedup),
        ],
    )
    again = IngestResponse.model_validate(resp.model_dump())
    assert again == resp
    assert again.results[0].status is IngestStatus.indexed


def test_document_summary_roundtrip_includes_temporal_fields() -> None:
    """D44: `modified_at`/`indexed_at` are additive on the shared listing shape used by both
    `GET /documents` and `GET /v1/tools/documents`."""
    doc = DocumentSummary(
        path="a.md",
        source_hash="h1",
        chunks=2,
        modified_at="2026-02-03T04:05:06+00:00",
        indexed_at="2026-02-04T00:00:00+00:00",
    )
    dumped = doc.model_dump()
    assert dumped == {
        "path": "a.md",
        "source_hash": "h1",
        "chunks": 2,
        "modified_at": "2026-02-03T04:05:06+00:00",
        "indexed_at": "2026-02-04T00:00:00+00:00",
    }
    assert DocumentSummary.model_validate(dumped) == doc


def test_document_summary_temporal_fields_default_to_none() -> None:
    doc = DocumentSummary(path="a.md", source_hash="h1", chunks=1)
    assert doc.modified_at is None
    assert doc.indexed_at is None


def test_answer_request_grounding_field_roundtrips_and_defaults_to_none() -> None:
    """D46: `grounding` is optional on the wire — `None` means "use Settings.answer_grounding_
    default"; a caller may pin one of the three modes explicitly."""
    bare = AnswerRequest(message="hi")
    assert bare.grounding is None

    pinned = AnswerRequest(message="hi", grounding="hybrid")
    dumped = pinned.model_dump()
    assert dumped["grounding"] == "hybrid"
    assert AnswerRequest.model_validate(dumped) == pinned


def test_answer_response_grounding_fields_roundtrip() -> None:
    """D46: `grounding_used`/`from_general_knowledge` are the SAME fields the `grounding` SSE
    event carries, surfaced on the non-streaming response too."""
    resp = AnswerResponse(
        answer="Paris.",
        format="text",
        conversation_id="c1",
        trace=[],
        truncated=False,
        grounding_used="hybrid",
        from_general_knowledge=True,
        grounding_segments=[
            GroundingSegment(text="Grounded bit.", kind="grounded"),
            GroundingSegment(text="Paris.", kind="general_knowledge"),
        ],
    )
    dumped = resp.model_dump()
    assert dumped["grounding_used"] == "hybrid"
    assert dumped["from_general_knowledge"] is True
    assert dumped["grounding_segments"] == [
        {"text": "Grounded bit.", "kind": "grounded"},
        {"text": "Paris.", "kind": "general_knowledge"},
    ]
    assert AnswerResponse.model_validate(dumped) == resp


def test_answer_response_grounding_fields_default_to_strict_and_false() -> None:
    resp = AnswerResponse(
        answer="x", format="text", conversation_id="c1", trace=[], truncated=False
    )
    assert resp.grounding_used == "strict"
    assert resp.from_general_knowledge is False
    assert resp.grounding_segments == []


def test_grounding_segment_rejects_unknown_kind() -> None:
    """`kind` is a closed `Literal` — a consumer can exhaustively switch on it without a
    catch-all case, same discipline as `IngestStatus`/`GroundingMode`."""
    with pytest.raises(ValidationError):
        GroundingSegment(text="x", kind="maybe")


def test_manifest_and_health_shapes() -> None:
    manifest = ManifestResponse(tenant="default", hashes=["h1", "h2"])
    assert ManifestResponse.model_validate(manifest.model_dump()) == manifest

    health = HealthResponse(embed_model="bge-m3")
    assert health.status == "ok"
    assert health.embed_model == "bge-m3"
