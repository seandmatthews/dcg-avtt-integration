"""PNG/JPEG/WebP dimension readers on the stdlib only.

Spec: README §4 ("``struct``-based image header reads ... no Pillow").
Needed because ``.uvtt`` geometry is validated against the image's real
pixel size (``cellSize = image.width / size.x``, ±2 px on height —
README §3.3) before anything is converted.
"""

from __future__ import annotations

from pathlib import Path


def pixel_dimensions(path: Path) -> tuple[int, int]:
    """Return (width, height) from the file's header bytes.

    Supports the formats the generator emits (PNG at minimum; JPEG and
    WebP as the format grows). Raises ValueError with a plain-words
    message for a truncated or unrecognized header.
    """
    raise NotImplementedError("lands with the scenes build (ticket 05); README §4")
