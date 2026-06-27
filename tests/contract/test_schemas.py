"""Lock the §8 API contract shapes (pydantic round-trips)."""

from __future__ import annotations

from sift.api.schemas import (
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
        sources=[Source(path="a.md", page=1, score=0.97)],
    )
    dumped = resp.model_dump()
    assert dumped == {
        "summary": "the sky is blue",
        "sources": [{"path": "a.md", "page": 1, "score": 0.97}],
    }
    assert SearchResponse.model_validate(dumped) == resp


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


def test_manifest_and_health_shapes() -> None:
    manifest = ManifestResponse(tenant="default", hashes=["h1", "h2"])
    assert ManifestResponse.model_validate(manifest.model_dump()) == manifest

    health = HealthResponse(embed_model="bge-m3")
    assert health.status == "ok"
    assert health.embed_model == "bge-m3"
