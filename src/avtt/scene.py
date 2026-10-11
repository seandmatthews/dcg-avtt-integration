"""``.uvtt`` -> ``.atlasmap`` conversion — the port.

Spec: README §3.2/§3.3. This is a port of Atlas's ``uvttToScene.ts``
(v0.6.0), which makes it a derivative work of AGPL code — see README §10
for why the license is declared rather than dodged.

The whole point of the port is determinism: identical ``.uvtt`` in ->
byte-identical ``.atlasmap`` out (testing discipline 2). The deterministic
id scheme (``wall_uvtt_<n>``, ``chain_uvtt_<n>``, ``light_uvtt_<n>``) must
reproduce Atlas's exactly. ``schema``/``version`` in the envelope come
from the pinned release's ``MapPersistence.ts`` — the golden fixture is
their source of truth, never this docstring, never the README.
"""

from __future__ import annotations

from pathlib import Path

from avtt.uvtt import UvttDocument


def convert(document: UvttDocument, image_path: Path, unit_scale: float,
            max_light_range: float) -> dict:
    """Convert a validated ``.uvtt`` document to the ``.atlasmap`` state dict.

    Reproduces, in order: cell-size math with the ±2 px height check,
    ``(p - origin) * cellSize`` mapping, one-cell-outside clipping,
    polyline -> wall chains with shared endpoints, closed portals ->
    doors (open portals dropped, counted), light dim/bright/intensity
    with the zero-range drop and the baked-lighting hide, ambient from
    the Rec.709 luma, and the normalized grid offset.
    """
    raise NotImplementedError("lands with the scenes build (ticket 05); README §3.3")


def dumps(state: dict) -> bytes:
    """Serialize the envelope deterministically: same state -> same bytes."""
    raise NotImplementedError("lands with the scenes build (ticket 05); README §3.2")
