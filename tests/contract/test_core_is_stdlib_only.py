"""Guardrail: ``src/sift/core/`` imports only the standard library (the dependency rule).

Parses each core module's AST and asserts every import resolves to a stdlib module or to
the project's own ``sift`` package (intra-core imports) — never a third-party dependency.
This is what keeps pydantic/httpx/libsql/torch out of the pure domain layer.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parents[2] / "src" / "sift" / "core"
ALLOWED = set(sys.stdlib_module_names) | {"sift"}


def _top_level(module: str) -> str:
    return module.split(".", 1)[0]


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(_top_level(alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import within the package
                roots.add("sift")
            elif node.module:
                roots.add(_top_level(node.module))
    return roots


def test_core_modules_import_stdlib_only() -> None:
    modules = sorted(CORE_DIR.glob("*.py"))
    assert modules, f"no core modules found under {CORE_DIR}"

    offenders: dict[str, set[str]] = {}
    for path in modules:
        roots = _imported_roots(ast.parse(path.read_text(encoding="utf-8")))
        bad = {root for root in roots if root not in ALLOWED}
        if bad:
            offenders[path.name] = bad

    assert not offenders, f"core/ may import only stdlib + sift; found: {offenders}"
