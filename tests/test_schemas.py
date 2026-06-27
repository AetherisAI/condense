import pytest
from pydantic import ValidationError

from sift.api.schemas import SearchResponse, Source


def test_search_response_ok():
    r = SearchResponse(summary="s", sources=[Source(path="/a.md", page=1, score=0.5)])
    assert r.sources[0].path == "/a.md"


def test_source_rejects_bad_score():
    with pytest.raises(ValidationError):
        Source(path="/a.md", page=1, score="not-a-float")  # pyright: ignore[reportArgumentType]
