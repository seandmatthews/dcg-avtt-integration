"""PNG/JPEG/WebP dimension readers on the stdlib only.

Spec: README §4 ("``struct``-based image header reads ... no Pillow").
Needed because ``.uvtt`` geometry is validated against the image's real
pixel size (``cellSize = image.width / size.x``, ±2 px on height —
README §3.3) before anything is converted.

A port of the readers of Atlas's ``imageProcessing/imageDimensions.ts``
at the pinned release (``avtt._version.ATLAS_PIN``) for the three
formats a ``.uvtt`` may carry (``uvttImage.ts``: PNG, WebP, JPEG) —
cited, never vendored (AGENTS.md). Only header bytes are read; the
image is never decoded.
"""

from __future__ import annotations

import struct
from pathlib import Path

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def dimensions_of_bytes(data: bytes) -> tuple[int, int] | None:
    """``(width, height)`` from the image's header bytes, or ``None``.

    A port of ``imageDimensions.ts``'s readers for PNG, JPEG and WebP
    (the formats ``uvttImage.ts`` accepts). GIF/BMP exist in Atlas's
    reader set but no ``.uvtt`` may carry them, so they are not ported.
    Returns ``None`` for anything unrecognized or truncated — the
    caller turns that into the plain-words refusal.
    """
    if data.startswith(_PNG_SIGNATURE):
        size = _png(data)
    elif data.startswith(b"\xff\xd8\xff"):
        size = _jpeg(data)
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        size = _webp(data)
    else:
        return None
    if size is None or size[0] <= 0 or size[1] <= 0:
        return None
    return size


def pixel_dimensions(path: Path) -> tuple[int, int]:
    """Return (width, height) from the file's header bytes.

    Supports the formats the generator emits (PNG at minimum; JPEG and
    WebP as the format grows). Raises ValueError with a plain-words
    message for a truncated or unrecognized header.
    """
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    size = dimensions_of_bytes(data)
    if size is None:
        raise ValueError(f"{path} does not begin as a PNG, JPEG or WebP "
                         "image (or its header is truncated)")
    return size


def _png(data: bytes) -> tuple[int, int] | None:
    """The IHDR chunk carries the size: big-endian u32 at 16 and 20."""
    if len(data) < 24 or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack_from(">II", data, 16)
    return width, height


def _webp(data: bytes) -> tuple[int, int] | None:
    """The size lives in the first chunk: lossy VP8, lossless VP8L or extended VP8X."""
    if len(data) < 25:
        return None
    chunk = data[12:16]
    if chunk == b"VP8 ":
        if len(data) < 30:
            return None
        width, height = struct.unpack_from("<HH", data, 26)
        return width & 0x3FFF, height & 0x3FFF
    if chunk == b"VP8L":
        bits = struct.unpack_from("<I", data, 21)[0]
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X":
        width = data[24] | (data[25] << 8) | (data[26] << 16)
        height = data[27] | (data[28] << 8) | (data[29] << 16)
        return width + 1, height + 1
    return None


def _jpeg(data: bytes) -> tuple[int, int] | None:
    """Walk the segment chain to the first start-of-frame marker (SOF0–SOF15
    minus DHT/JPG/DAC), whose body carries the size. A frame header beyond
    the first 256 KiB (a huge EXIF block ahead of it) is not found — the
    same read window as Atlas's ``HEADER_BYTES``."""
    if len(data) < 4:
        return None
    offset = 2
    limit = min(len(data), 256 * 1024)
    while offset + 9 <= limit:
        if data[offset] != 0xFF:
            return None
        marker = data[offset + 1]
        if marker == 0xFF:      # a fill byte, not a segment
            offset += 1
        elif 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack_from(">HH", data, offset + 5)
            return width, height
        elif marker == 0x01 or 0xD0 <= marker <= 0xD9:  # standalone, no length field
            offset += 2
        else:
            length = struct.unpack_from(">H", data, offset + 2)[0]
            offset += 2 + length
    return None
