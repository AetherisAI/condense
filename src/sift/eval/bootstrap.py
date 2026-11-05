"""``sift-eval bootstrap`` — draft golden items from the index, for a human to curate.

Samples passages round-robin across documents (seeded), asks the judge LLM for one realistic
question each plus a short answer and a verbatim evidence quote, and keeps a draft only when that
quote really is in the passage. Every draft is tagged ``bootstrap`` with ``"review": "todo"``.

Drafts are a starting point, not a golden set: each question was written while looking at its
answer, so it tends to reuse the passage's wording and makes retrieval look easier than real
user questions. Rewrite them in your users' words, delete weak ones, and add multi-document and
unanswerable questions by hand (see ``docs/evaluation.md``).
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from pathlib import Path
from typing import Any

from sift.config import Settings
from sift.core.ports import Completer
from sift.eval.collect import Progress
from sift.eval.config import EvalSettings
from sift.eval.corpus import Doc, document_passages, list_documents
from sift.eval.matching import evidence_matches
from sift.eval.records import Passage
from sift.factory import Container, build_completer, build_container

_SYSTEM = (
    "You write evaluation questions for a document search system. You are given one passage. "
    "Write ONE question a real user might ask that this passage answers, the correct answer in "
    "one or two sentences, and a short quote (5 to 25 words) copied EXACTLY from the passage "
    "that proves the answer. The question must make sense on its own: never refer to 'the "
    "passage', 'the text' or 'the document'. If the passage has no answerable fact (a table of "
    'contents, boilerplate, a fragment), reply {"skip": true}. Otherwise reply with JSON only: '
    '{"question": "...", "answer": "...", "evidence": "..."}'
)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_draft(raw: str) -> dict[str, str] | None:
    """The model's JSON reply as ``{question, answer, evidence}``, or ``None`` if unusable."""
    try:
        data: Any = json.loads(_FENCE.sub("", raw.strip()))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("skip"):
        return None
    fields = {k: data.get(k) for k in ("question", "answer", "evidence")}
    if not all(isinstance(v, str) and v.strip() for v in fields.values()):
        return None
    return {k: str(v).strip() for k, v in fields.items()}


async def _sample(
    container: Container, docs: list[Doc], es: EvalSettings, want: int, rng: random.Random
) -> list[Passage]:
    """Up to ``want`` passages, round-robin across shuffled documents, long enough to ask about."""
    order = list(docs)
    rng.shuffle(order)
    pools: list[list[Passage]] = []
    for doc in order:
        passages = [
            p
            for p in await document_passages(container, doc.source_hash, es.tenant)
            if len(p.text) >= es.bootstrap_min_chars
        ]
        rng.shuffle(passages)
        if passages:
            pools.append(passages)
    picked: list[Passage] = []
    while pools and len(picked) < want:
        for pool in list(pools):
            picked.append(pool.pop())
            if not pool:
                pools.remove(pool)
            if len(picked) >= want:
                break
    return picked


async def bootstrap(
    out: Path,
    app: Settings,
    es: EvalSettings,
    *,
    n: int = 30,
    container: Container | None = None,
    completer: Completer | None = None,
    progress: Progress | None = None,
) -> int:
    """Write up to ``n`` verified drafts to ``out`` (never overwrites); returns how many."""
    say = progress or (lambda _msg: None)
    if out.exists():
        raise RuntimeError(f"{out} already exists — refusing to overwrite; pick another --out")
    if completer is None:
        judge_app = es.judge_settings(app)
        if not judge_app.llm_base_url:
            raise RuntimeError("bootstrap needs an LLM — set EVAL_JUDGE_* (or LLM_*)")
        completer = build_completer(judge_app)
    container = container or build_container(app, ephemeral_conversations=True)
    docs = await list_documents(container, es.tenant)
    if not docs:
        raise RuntimeError("the index is empty — ingest documents before bootstrapping")

    # Oversample: some passages are boilerplate (the model skips them) or yield a quote that
    # isn't really verbatim (dropped below).
    passages = await _sample(container, docs, es, n * 2, random.Random(es.seed))
    gate = asyncio.Semaphore(es.judge_concurrency)

    async def draft(passage: Passage) -> dict[str, str] | None:
        async with gate:
            try:
                raw = await completer.complete(
                    _SYSTEM, f"Passage (from {passage.path}, page {passage.page}):\n{passage.text}"
                )
            except Exception:  # noqa: BLE001 — one failed draft is just one fewer draft
                return None
        parsed = parse_draft(raw)
        if parsed is None or not evidence_matches(parsed["evidence"], passage.text, 1.0):
            return None
        return parsed

    say(f"drafting from {len(passages)} sampled passage(s) across {len(docs)} document(s)")
    drafts = await asyncio.gather(*(draft(p) for p in passages))
    lines: list[str] = []
    for passage, parsed in zip(passages, drafts, strict=True):
        if parsed is None or len(lines) >= n:
            continue
        item = {
            "id": f"draft-{len(lines) + 1:03d}",
            "question": parsed["question"],
            "reference": parsed["answer"],
            "relevant": [
                {"path": passage.path, "page": passage.page, "evidence": parsed["evidence"]}
            ],
            "tags": ["bootstrap"],
            "review": "todo",
        }
        lines.append(json.dumps(item, ensure_ascii=False))
    out.parent.mkdir(parents=True, exist_ok=True)
    header = "# sift-eval bootstrap drafts — rewrite in your users' words, then delete `review`\n"
    out.write_text(header + "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)
