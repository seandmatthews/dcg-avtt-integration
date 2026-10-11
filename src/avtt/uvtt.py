"""``.uvtt`` parsing: fields, Atlas's import limits, plain-words refusals.

Spec: README §3.3. The limits are Atlas's own ``UVTT_LIMITS`` (v0.6.0,
``src/app/import/uvtt/uvttTypes.ts``); a refused file must get the
importer's own reason in plain words, and nothing may be written on refusal
(testing discipline 3, README §7).

The document is cell-coordinate based: every overlay position counts grid
cells, with ``origin`` the cell at the image's top-left and ``size`` the
cells the image spans.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class UvttRefused(Exception):
    """A ``.uvtt`` file Atlas would refuse, with the plain-words reason."""


@dataclass(frozen=True)
class UvttDocument:
    """Parsed ``.uvtt`` payload, still in cell coordinates."""

    raw: dict  # the untouched JSON, kept for the golden tests
    image_bytes: bytes


def parse(path: Path) -> UvttDocument:
    """Read and validate a ``.uvtt`` file.

    Raises UvttRefused with a plain-words reason for every limit in
    README §3.3: file > 150 MB, > 20,000 wall segments, > 2,000 lights,
    > 4,096 cells per side, < 10 px per cell, image over the decode cap.
    """
    raise NotImplementedError("lands with the scenes build (ticket 05); README §3.3")
