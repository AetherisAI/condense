"""Domain exceptions (stdlib only)."""

from __future__ import annotations


class SiftError(Exception):
    """Base class for all Sift domain errors."""


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
