"""Domain exceptions (stdlib only)."""

from __future__ import annotations


class SiftError(Exception):
    """Base class for all Sift domain errors."""


class ParseError(SiftError):
    """A file's declared structure makes it unsafe to parse — reject it explicitly rather than
    attempt a parse that could exhaust memory (see DECISIONS.md D34: a stray far cell inflated
    one real ``.xlsx``'s declared used-range to over a million rows, and markitdown's
    ``pandas.read_excel(engine="openpyxl")`` dutifully materialized the whole declared range,
    climbing past 2GiB RSS for a 38KB file).

    Raised by parser adapters *before* the expensive conversion; the ingest pipeline's per-file
    ``except Exception`` (``pipelines/ingest.py``) turns it into an explicit ``failed``
    :class:`~sift.pipelines.ingest.IngestOutcome` with this exception's message as ``detail`` —
    never a silent truncation, never an unbounded parse attempt.
    """


class ModelPinMismatch(SiftError):
    """The configured embedding model/dim disagrees with a tenant's pinned base.

    The one invariant that keeps a base coherent when the model is just a config string
    (README §6): every ingest and search checks ``EMBED_MODEL`` against the per-tenant
    pin and refuses on mismatch. Pipelines surface this as HTTP 409.

    ``expected`` is what the base is pinned to; ``actual`` is what the request configured.
    """

    def __init__(
        self,
        *,
        tenant: str,
        expected: tuple[str, int],
        actual: tuple[str, int],
    ) -> None:
        self.tenant = tenant
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"model-pin mismatch for tenant {tenant!r}: base pinned to "
            f"{expected[0]!r} (dim {expected[1]}), but request configured "
            f"{actual[0]!r} (dim {actual[1]})"
        )
