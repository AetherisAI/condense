"""Boundary-rule regression: ``pipelines/answer.py`` may act ONLY through ``ToolRegistry.call``
— never a direct store/pipeline call (WP v0.2.0 T3, D40; design §0/§3).

Written FIRST (red, before the loop existed) per the plan: this predates the feature it
constrains, so a future edit that adds a direct ``sift.adapters.*`` import — or a
``store``/``search`` constructor parameter — to this module fails it immediately, without
needing to inspect runtime behavior.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from sift.pipelines.answer import AnswerPipeline

ANSWER_MODULE = Path(__file__).resolve().parents[2] / "src" / "sift" / "pipelines" / "answer.py"


def _imported_modules(tree: ast.Module) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_answer_module_imports_no_adapter() -> None:
    tree = ast.parse(ANSWER_MODULE.read_text(encoding="utf-8"))
    modules = _imported_modules(tree)

    offenders = {m for m in modules if m == "sift.adapters" or m.startswith("sift.adapters.")}

    assert not offenders, f"pipelines/answer.py must never import an adapter; found: {offenders}"


def test_answer_module_never_imports_factory() -> None:
    tree = ast.parse(ANSWER_MODULE.read_text(encoding="utf-8"))
    modules = _imported_modules(tree)

    assert "sift.factory" not in modules


def test_answer_pipeline_constructor_has_no_store_or_search_param() -> None:
    params = set(inspect.signature(AnswerPipeline.__init__).parameters)

    assert "store" not in params
    assert "search" not in params
