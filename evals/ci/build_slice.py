"""Rebuild the CI retrieval slice (``golden.jsonl`` + ``corpus/``) from the full MITRE eval set.

Not run in CI: CI only reads the committed output. Re-run it when the selection or the source
corpus changes, then refresh ``baseline/summary.json`` (see README.md).

    python -I evals/ci/build_slice.py \
        --silver ../condense_test_mitre/silver.jsonl \
        --corpus ../condense_test_mitre/corpus \
        --results eval-runs/<full-corpus base run>/results.jsonl \
        --results eval-runs/<full-corpus derivatives run>/results.jsonl

The ``--results`` files are unjudged full-corpus Find runs (bge-m3, no reranker). For every
selected question, the slice keeps its gold documents plus the first ``--negatives`` other
documents that run ranked highest: the near-misses bge-m3 actually confuses with the answer.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Whole families (a base + its English derivatives) wherever derivatives exist, so a base can be
# compared with its rewordings; plus a few standalone bases. Unanswerable items (h09, h10) are
# left out: they carry no gold, so they say nothing about retrieval.
FAMILIES = [f"mitre-vh0{i}" for i in range(1, 6)] + [f"mitre-h0{i}" for i in range(1, 9)]
FAMILIES += [f"mitre-m0{i}" for i in range(1, 8)]
STANDALONE = ["mitre-vh06", "mitre-vh07", "mitre-vh08", "mitre-h12", "mitre-h15", "mitre-h17"]
STANDALONE += ["mitre-h18", "mitre-m10", "mitre-m18"]
ENGLISH_KINDS = {"keywords", "scenario", "reword"}

HEADER = """\
# sift-eval CI retrieval slice: 75 English items from the MITRE ATT&CK 20.1 silver set
# (25 medium, 31 hard, 19 very hard; 29 bases + 46 keywords/scenario/reword derivatives).
# Paths are relative to evals/ci/corpus/. Built by evals/ci/build_slice.py; see evals/ci/README.md.
# ATT&CK content: (c) The MITRE Corporation, see evals/ci/LICENSE-MITRE-ATTACK.txt.
"""


def _selected(item_id: str) -> bool:
    base, _, kind = item_id.partition(".")
    if not kind:
        return base in FAMILIES or base in STANDALONE
    return base in FAMILIES and kind in ENGLISH_KINDS


def _ranked_docs(results: list[Path]) -> dict[str, list[str]]:
    ranked: dict[str, list[str]] = {}
    for path in results:
        for line in path.read_text().splitlines():
            row = json.loads(line)
            docs: list[str] = []
            for passage in row["retrieved"]:
                if passage["path"] not in docs:
                    docs.append(passage["path"])
            ranked[row["item_id"]] = docs
    return ranked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--silver", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--results", type=Path, action="append", required=True)
    parser.add_argument("--negatives", type=int, default=5)
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()

    items = [
        json.loads(line)
        for line in args.silver.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    items = [item for item in items if _selected(item["id"])]
    if any(not item["answerable"] for item in items):
        raise SystemExit("an unanswerable item slipped into the selection")
    ranked = _ranked_docs(args.results)

    docs: set[str] = set()
    for item in items:
        gold = {rel["path"] for rel in item["relevant"]}
        if item["id"] not in ranked:
            raise SystemExit(f"{item['id']}: not in any --results file")
        negatives = [doc for doc in ranked[item["id"]] if doc not in gold][: args.negatives]
        docs |= gold | set(negatives)

    corpus_out = args.out / "corpus"
    if corpus_out.exists():
        shutil.rmtree(corpus_out)
    for doc in sorted(docs):
        target = corpus_out / doc
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.corpus / doc, target)

    order = {"m": 0, "h": 1, "vh": 2}

    def sort_key(item: dict[str, object]) -> tuple[int, str]:
        match = re.match(r"mitre-(m|h|vh)\d+", str(item["id"]))
        assert match, item["id"]
        return order[match.group(1)], str(item["id"])

    lines = [json.dumps(item, ensure_ascii=False) for item in sorted(items, key=sort_key)]
    (args.out / "golden.jsonl").write_text(HEADER + "\n".join(lines) + "\n")
    print(f"{len(items)} items, {len(docs)} documents -> {args.out}")


if __name__ == "__main__":
    main()
