"""``sift-eval bootstrap``: verified drafts only, never overwriting, valid golden output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sift.adapters.llm.fake import FakeCompleter
from sift.eval.bootstrap import bootstrap, parse_draft
from sift.eval.config import EvalSettings
from sift.eval.golden import load_golden
from sift.factory import Container


class _PassageQuoter:
    """Quotes the first five words of whatever passage it's shown — always verbatim."""

    async def complete(self, system: str, user: str) -> str:
        passage = user.split("\n", 1)[1]
        quote = " ".join(passage.split()[:5])
        return json.dumps(
            {"question": f"What about {quote}?", "answer": passage, "evidence": quote}
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            '{"question": "q?", "answer": "a", "evidence": "e"}',
            {"question": "q?", "answer": "a", "evidence": "e"},
        ),
        (
            '```json\n{"question": "q?", "answer": "a", "evidence": "e"}\n```',
            {"question": "q?", "answer": "a", "evidence": "e"},
        ),
        ('{"skip": true}', None),
        ('{"question": "q?", "answer": ""}', None),
        ("not json", None),
    ],
)
def test_parse_draft(raw: str, expected: dict[str, str] | None) -> None:
    assert parse_draft(raw) == expected


async def test_bootstrap_writes_curatable_golden_items(
    container: Container, tmp_path: Path
) -> None:
    out = tmp_path / "draft.jsonl"
    es = EvalSettings(bootstrap_min_chars=10)

    written = await bootstrap(
        out, container.settings, es, n=3, container=container, completer=_PassageQuoter()
    )

    assert written == 3
    items = load_golden(out)  # the drafts are a valid golden set as-is
    assert [i.id for i in items] == ["draft-001", "draft-002", "draft-003"]
    assert all(i.tags == ("bootstrap",) for i in items)
    assert len({i.relevant[0].path for i in items}) == 3  # round-robin across documents
    assert '"review": "todo"' in out.read_text()


async def test_bootstrap_drops_non_verbatim_evidence(container: Container, tmp_path: Path) -> None:
    invented = FakeCompleter(json.dumps({"question": "q?", "answer": "a", "evidence": "not in it"}))

    written = await bootstrap(
        tmp_path / "d.jsonl",
        container.settings,
        EvalSettings(bootstrap_min_chars=10),
        container=container,
        completer=invented,
    )

    assert written == 0


async def test_bootstrap_refuses_to_overwrite(container: Container, tmp_path: Path) -> None:
    out = tmp_path / "golden.jsonl"
    out.write_text("# my curated set\n")

    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        await bootstrap(out, container.settings, EvalSettings(), completer=FakeCompleter())

    assert out.read_text() == "# my curated set\n"


async def test_bootstrap_needs_an_llm(container: Container, tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="needs an LLM"):
        await bootstrap(
            tmp_path / "d.jsonl", container.settings, EvalSettings(), container=container
        )
