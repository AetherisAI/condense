"""Layering guardrail (CLAUDE.md §3, the dependency rule): every module under ``pipelines/``
and ``adapters/`` respects the architecture's import direction — imports point INWARD only.
``pipelines/`` codes against ports (``sift.core``) and never reaches for ``sift.api`` (the HTTP
surface), ``sift.adapters`` (a concrete implementation), or ``sift.factory`` (the composition
root, which sits above pipelines and wires them together). ``adapters/`` implements a port
behind ``sift.core`` and must never reach UP into ``sift.api``, ``sift.pipelines`` (its own
consumer), or ``sift.factory`` either.

AST-based, not a substring grep: parses each module's own import statements and resolves the
full dotted module path of every one, so an import is caught regardless of how it's written
(``import x``, ``from x import y``, one nested inside a function) and can never be confused with
a forbidden root's name merely appearing as a substring elsewhere in the file (a docstring
mentioning "sift.adapters", a module named "sift.apiary", ...).

Supersedes ``tests/surface/test_search_pipeline.py::test_search_pipeline_imports_no_adapter``,
which only substring-checked for the literal text ``"sift.adapters"`` in ``pipelines/search.py``
— and so entirely missed that module's real, audit-verified defect: a direct ``from sift.api.
schemas import SearchResponse, Source`` (an ``sift.api`` import, not a ``sift.adapters`` one).
This test's pipelines check forbids ``sift.api`` too and would have failed on that pre-fix
module; it also generalizes ``tests/pipelines/test_answer_boundary.py``'s single-module
``sift.adapters``/``sift.factory`` check to every module under ``pipelines/``, and adds the
symmetric guard over ``adapters/``.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src" / "sift"
PIPELINES_DIR = SRC_DIR / "pipelines"
ADAPTERS_DIR = SRC_DIR / "adapters"


def _imported_modules(tree: ast.Module) -> set[str]:
    """Every dotted module path a module imports.

    ``import a.b`` and ``from a.b import c`` both contribute ``"a.b"``; a relative ``from .
    import x`` / ``from ..core import y`` contributes the bare ``"sift"`` root — it can only
    ever resolve to something inside this same package, never to a forbidden external module,
    so collapsing it to the package root is safe and keeps the walk simple.
    """
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                modules.add("sift")
            elif node.module:
                modules.add(node.module)
    return modules


def _forbidden_hits(modules: set[str], forbidden_roots: tuple[str, ...]) -> set[str]:
    """Every imported module that IS one of ``forbidden_roots`` or a sub-module of one.

    A dotted-path check — ``"sift.api"`` matches ``"sift.api.schemas"`` but never a module that
    merely starts with the same characters (e.g. a hypothetical ``"sift.apiary"``) — never a
    bare substring test.
    """
    return {
        m for m in modules if any(m == root or m.startswith(root + ".") for root in forbidden_roots)
    }


def _check_directory(directory: Path, forbidden_roots: tuple[str, ...]) -> dict[str, set[str]]:
    offenders: dict[str, set[str]] = {}
    for path in sorted(directory.rglob("*.py")):
        modules = _imported_modules(ast.parse(path.read_text(encoding="utf-8")))
        bad = _forbidden_hits(modules, forbidden_roots)
        if bad:
            offenders[str(path.relative_to(SRC_DIR))] = bad
    return offenders


def test_pipelines_never_import_api_adapters_or_factory() -> None:
    modules = sorted(PIPELINES_DIR.rglob("*.py"))
    assert modules, f"no modules found under {PIPELINES_DIR}"

    offenders = _check_directory(PIPELINES_DIR, ("sift.api", "sift.adapters", "sift.factory"))

    assert not offenders, (
        f"pipelines/ must code against ports only (sift.core) — never import "
        f"sift.api/sift.adapters/sift.factory; found: {offenders}"
    )


def test_adapters_never_import_api_pipelines_or_factory() -> None:
    modules = sorted(ADAPTERS_DIR.rglob("*.py"))
    assert modules, f"no modules found under {ADAPTERS_DIR}"

    offenders = _check_directory(ADAPTERS_DIR, ("sift.api", "sift.pipelines", "sift.factory"))

    assert not offenders, (
        f"adapters/ must never import sift.api/sift.pipelines/sift.factory; found: {offenders}"
    )
