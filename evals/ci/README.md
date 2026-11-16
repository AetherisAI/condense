# CI retrieval gate

A fixed, committed retrieval benchmark that the **Retrieval eval** workflow
(`.github/workflows/eval-retrieval.yml`, manual trigger) runs on a plain GitHub runner. It
ingests `corpus/` with bge-m3 on CPU, runs Find over `golden.jsonl` without a judge, reranker or
recap, and fails if retrieval got worse than `baseline/summary.json` beyond a tolerance. Decision:
D87 in `docs/Quentin/DECISIONS.md`.

| File | What it is |
| --- | --- |
| `golden.jsonl` | 75 English questions from the MITRE ATT&CK 20.1 silver set: 25 medium, 31 hard, 19 very hard; 29 bases + 46 keywords / scenario / reword derivatives |
| `corpus/` | 263 ATT&CK pages (2.5 MB, 1,389 chunks): every gold page plus each question's 5 highest-ranked wrong pages from a full-corpus run |
| `baseline/summary.json` | The reference run the gate compares against |
| `ingest.py` | Ingests a folder through the real parse → chunk → embed → store path |
| `build_slice.py` | Rebuilds `golden.jsonl` + `corpus/` from the full MITRE set (not run in CI) |
| `LICENSE-MITRE-ATTACK.txt` | MITRE's license for the ATT&CK content in `corpus/` and the questions |

## Why these questions and pages

- **Questions:** whole families (a base with its English rewordings) for vh01–vh05, h01–h08 and
  m01–m07, plus standalone bases vh06–vh08, h12, h15, h17, h18, m10, m18. German variants and
  the two unanswerable hard items are left out: unanswerable items carry no gold, so they say
  nothing about retrieval.
- **Pages:** the near-misses bge-m3 ranked above or just below the answer on the full
  2,298-page corpus. That keeps the slice as hard as the full corpus: on these 75 questions,
  top-1 is 0.533 on both, and MRR 0.661 vs 0.656. A random sample of pages would make
  retrieval look easy and miss regressions.

## The gate

`sift-eval compare evals/ci/baseline <run> --fail-on METRIC:TOLERANCE` exits 1 when a metric got
worse by more than its tolerance (direction-aware; improvements always pass) and 2 when a metric
is missing or the two runs used different golden sets. The workflow gates the final doc-level
`hit@1`, `recall@10` and `mrr` at 0.03 each: one question is 1/75 ≈ 0.013 of hit@1, so two
questions may slip and a third fails the run. It also fails if any question errored
(`find.errors:0`).

## Run it locally

```bash
docker run -d --name condense-ci-ollama -p 127.0.0.1:11435:11434 \
  ollama/ollama:0.31.1@sha256:f1a705f2bd113fb8d15f85f7c217f0dc5f6bebda6b0cc42b82c3ad165ffcb9dc
curl -s http://127.0.0.1:11435/api/pull -d '{"model": "bge-m3", "stream": false}'
export STORE_BACKEND=libsql TURSO_DATABASE_URL=file:eval-ci.db \
  EMBED_BASE_URL=http://127.0.0.1:11435/v1 EMBED_MODEL=bge-m3 \
  RERANK_STRATEGY=none RECAP_ENABLED=false
python evals/ci/ingest.py evals/ci/corpus --env-file /dev/null
sift-eval --env-file /dev/null run --golden evals/ci/golden.jsonl --surfaces find --skip-judge \
  --label ci-retrieval
sift-eval compare evals/ci/baseline eval-runs/*-ci-retrieval \
  --fail-on find.retrieval.final.doc.hit@1:0.03
```

`--env-file /dev/null` keeps your `.env` out of both, as on the runner. Delete `eval-ci.db` before
re-ingesting.

## Updating the baseline

Update it when a change makes retrieval better on purpose, or when the slice, the Ollama image
or the model changes. Run the workflow with **update_baseline** ticked: it skips the gate and
uploads the run folder as the `retrieval-run` artifact. Commit that run's `summary.json` as
`baseline/summary.json` in the same PR as the change, so the new numbers get reviewed. Editing
`golden.jsonl` without a new baseline fails the gate on purpose (different golden sets).
