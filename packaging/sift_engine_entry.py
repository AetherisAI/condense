"""PyInstaller entry point for the frozen Sift **engine** (the FastAPI API, D62).

A thin wrapper so PyInstaller has a concrete script to analyze; the real app lives in
``sift.api.main``. Kept out of ``src/sift/`` so it never ships as part of the importable
package — mirrors ``sift_agent_entry.py``'s / ``sift_agent_cli_entry.py``'s convention.

Deliberately imports the ``app`` object directly and calls ``uvicorn.run(app, ...)`` rather
than the string form ``uvicorn.run("sift.api.main:app", ...)`` that ``api.Dockerfile``'s CMD
uses: the string form makes uvicorn re-import the module by dotted path at runtime (needed
for ``--reload``/multi-worker, irrelevant here), which does not work once frozen — a
PyInstaller onedir bundle has no real package/module tree on disk for uvicorn to resolve a
dotted import against, only the bundled bytecode already loaded once by the bootloader. The
object form runs the already-imported ASGI app directly and has no such requirement.

``host``/``port`` come from ``Settings`` (``api_bind``/``api_port``, D62) via the same cached
``get_settings()`` accessor every adapter uses — no new config surface, no ``os.environ``
reads here (P2).
"""

import uvicorn

from sift.api.main import app
from sift.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(app, host=settings.api_bind, port=settings.api_port)


if __name__ == "__main__":
    main()
