"""The collect phase on the default fakes: Find via ``trace()``, Ask via the event stream."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from sift.adapters.conversation.fake import FakeConversationStore
from sift.adapters.llm.fake import FakeToolCompleter
from sift.core.types import ToolCall, ToolCompletion
from sift.eval.collect import collect, collect_ask, collect_find
from sift.eval.config import EvalSettings, load_settings
from sift.eval.golden import GoldenItem, GoldRef
from sift.factory import Container
from sift.pipelines.answer import AnswerPipeline

REFUNDS = GoldenItem(
    id="refunds",
    question="refunds take two to three business days after approval",
    reference="Two to three business days.",
    relevant=(GoldRef(path="refunds.md", evidence="two to three business days"),),
)


async def test_collect_find_records_every_stage(container: Container) -> None:
    row = await collect_find(container, REFUNDS, EvalSettings())

    assert row.error is None
    assert row.retrieved[0].path == "policies/refunds.md"  # exact-text query → cosine 1.0
    assert len(row.retrieved) == 4  # the whole tiny corpus, wider than FINAL_K=1
    assert [p.path for p in row.contexts] == [p.path for p in row.ranked[:2]]  # recap_context_k
    assert row.response.startswith("Question: ")  # NullCompleter echoes the recap prompt
    assert {"embed", "retrieve", "rerank", "recap", "total"} <= set(row.timings_ms)


async def test_collect_find_captures_errors(container: Container) -> None:
    class Boom:
        async def trace(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("store down")

    broken = replace(container, search=Boom())  # pyright: ignore[reportArgumentType]

    row = await collect_find(broken, REFUNDS, EvalSettings())

    assert row.error == "RuntimeError: store down"


def _with_scripted_agent(container: Container, script: list[ToolCompletion]) -> Container:
    answer = AnswerPipeline(
        FakeToolCompleter(script), container.tools, FakeConversationStore(), container.settings
    )
    return replace(container, answer=answer)


async def test_collect_ask_gathers_tool_contexts_sources_and_answer(container: Container) -> None:
    agent = _with_scripted_agent(
        container,
        [
            ToolCompletion(
                tool_calls=(
                    ToolCall(name="search", arguments={"query": REFUNDS.question}, id="c1"),
                )
            ),
            ToolCompletion(content="Refunds take two to three business days."),
        ],
    )

    row = await collect_ask(agent, REFUNDS, EvalSettings())

    assert row.error is None
    assert row.response == "Refunds take two to three business days."
    assert row.tool_calls == 1
    assert row.truncated is False
    assert row.contexts and row.contexts[0].path == "policies/refunds.md"
    assert row.contexts[0].text.startswith("refunds take")  # full text, not the 200-char snippet
    assert row.ranked[0].path == "policies/refunds.md"  # the `sources` event
    assert set(row.timings_ms) == {"total", "tools", "model"}


async def test_collect_ask_caps_contexts(container: Container) -> None:
    agent = _with_scripted_agent(
        container,
        [
            ToolCompletion(
                tool_calls=(ToolCall(name="search", arguments={"query": "shipping"}, id="c1"),)
            ),
            ToolCompletion(content="done"),
        ],
    )

    row = await collect_ask(agent, REFUNDS, EvalSettings(ask_max_contexts=2))

    assert len(row.contexts) == 2


async def test_collect_runs_warmup_then_every_item_per_surface(container: Container) -> None:
    other = replace(REFUNDS, id="shipping", question="shipping is free for orders above")
    messages: list[str] = []

    rows = await collect(
        container, [REFUNDS, other], EvalSettings(warmup=1), ["find", "ask"], messages.append
    )

    assert [(r.surface, r.item_id) for r in rows] == [
        ("find", "refunds"),
        ("find", "shipping"),
        ("ask", "refunds"),
        ("ask", "shipping"),
    ]
    assert messages[0].startswith("[find 1/2] refunds: ")


def test_load_settings_tolerates_missing_ingest_token(tmp_path: Path) -> None:
    env = tmp_path / "eval.env"
    env.write_text("RETRIEVE_K=7\nEVAL_K_VALUES=5,1\nEVAL_JUDGE_MODEL=big-judge\n")

    app, es = load_settings(env)

    assert app.retrieve_k == 7
    assert es.ks == [1, 5]
    assert es.judge_model_name(app) == "big-judge"


def test_judge_settings_fall_back_to_app_llm() -> None:
    app, _ = load_settings(None)
    app = app.model_copy(update={"llm_base_url": "http://gen/v1", "llm_model": "gen"})

    judge = EvalSettings(judge_base_url="http://judge/v1").judge_settings(app)

    assert (judge.llm_base_url, judge.llm_model) == ("http://judge/v1", "gen")


@pytest.mark.parametrize(("key", "value"), [("k_values", "0,5"), ("noise_ratios", "0,1.0")])
def test_eval_settings_reject_bad_lists(key: str, value: str) -> None:
    with pytest.raises(ValueError):
        EvalSettings(**{key: value})  # pyright: ignore[reportArgumentType]
