"""``sift-eval`` — the quality-evaluation harness (D73–D75).

A separate dev-tool application (the same pattern as ``agent/``): it builds the real system
under test through :func:`sift.factory.build_container` and drives the Find
(:class:`~sift.pipelines.search.SearchPipeline`) and Ask (:class:`~sift.pipelines.answer.
AnswerPipeline`) surfaces in-process against a golden question set, then scores retrieval
(recall/precision/hit@k, MRR), answers (RAGAS, behind :class:`~sift.eval.judge.Judge`), noise
robustness and latency. The product never imports this package (``tests/contract/
test_layering.py``).
"""
