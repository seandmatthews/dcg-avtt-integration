"""``.uvtt`` parsing: fields, Atlas's import limits, plain-words refusals.

Spec: README §3.3. The limits are Atlas's own ``UVTT_LIMITS`` at the
pinned release (``avtt._version.ATLAS_PIN``, ``uvttTypes.ts``); a
refused file must get the importer's own reason in plain words, and
nothing may be written on refusal (testing discipline 3, README §7).

A port of ``parseUvtt.ts`` + ``uvttFields.ts`` + ``uvttImage.ts`` —
cited, never vendored (AGENTS.md). The refusal strings are the
importer's own sentences, kept verbatim so a publisher refusal reads
exactly like the Atlas UI's notice for the same file.

The document is cell-coordinate based: every overlay position counts
grid cells, with ``origin`` the cell at the image's top-left and
``size`` the cells the image spans.
"""

from __future__ import annotations

import base64
import binascii
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

# --- UVTT_LIMITS (uvttTypes.ts at the pinned release) ----------------------

FILE_BYTES_LIMIT = 150 * 1024 * 1024   # exports with a large JPEG reach 30 MB; PNG is several times that
WALL_SEGMENTS_LIMIT = 20_000           # wall segments and doors together
LIGHTS_LIMIT = 2_000
MAP_CELLS_LIMIT = 4_096                # cells along one side of the map, and at least one
CELL_PIXELS_LIMIT = 10                 # pixels of the image a cell spans at least
DISTANCE_LIMIT = 1_000_000             # largest coordinate and longest light range, in cells
IMAGE_PIXELS_LIMIT = 268_435_456       # the image workers' decode budget, at four bytes a pixel

_TOO_MANY_WALLS = "The file has more than 20,000 wall segments."
_TOO_MANY_LIGHTS = "The file has more than 2,000 lights."


class UvttRefused(Exception):
    """A ``.uvtt`` file Atlas would refuse, with the plain-words reason."""


@dataclass(frozen=True)
class UvttPoint:
    """A position in grid cells."""

    x: float
    y: float


@dataclass(frozen=True)
class UvttPortal:
    """A door (closed) or a window (not closed): ``bounds`` are its two ends."""

    bounds: tuple[UvttPoint, UvttPoint]
    closed: bool


@dataclass(frozen=True)
class UvttLight:
    position: UvttPoint
    range: float  # how far the light reaches, in cells
    intensity: float
    color: str    # #rrggbb


@dataclass(frozen=True)
class UvttDocument:
    """Parsed ``.uvtt`` payload, still in cell coordinates."""

    raw: dict                 # the untouched JSON, kept for the golden tests
    image_bytes: bytes
    image_type: str           # 'image/png' | 'image/webp' | 'image/jpeg', as the bytes say
    origin: UvttPoint         # the cell at the image's top-left corner
    size: UvttPoint           # cells the image spans
    polylines: tuple[tuple[UvttPoint, ...], ...]  # wall lines, then object outlines, in file order
    portals: tuple[UvttPortal, ...]
    lights: tuple[UvttLight, ...]
    ambient_light: str | None  # #rrggbb, or None when the file names none
    baked_lighting: bool       # the image already shows the lights' glow


# --- the field readers (uvttFields.ts) --------------------------------------
#
# "absent" means the key is missing or null — JSON objects carry nothing
# else that could be absent (uvttFields.ts isAbsent).

def _refuse(problem: str) -> None:
    raise UvttRefused(problem)


def _is_number(value) -> bool:
    """A finite number (a bool is not; TS ``isFiniteNumber``)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _read_record(value, what: str) -> dict:
    if not isinstance(value, dict):
        _refuse(f"{what} is missing or not an object.")
    return value


def _read_list(value, what: str, limit: int, limit_problem: str) -> list:
    """An optional list: absent reads as empty, and it may hold at most ``limit`` entries."""
    if value is None:
        return []
    if not isinstance(value, list):
        _refuse(f"{what} is not a list.")
    if len(value) > limit:
        _refuse(limit_problem)
    return value


def _read_number(value, what: str, minimum: float, maximum: float) -> float:
    if not _is_number(value):
        _refuse(f"{what} is missing or not a number.")
    if value < minimum or value > maximum:  # type: ignore[operator]
        _refuse(f"{what} is out of range.")
    return value  # type: ignore[return-value]


def _read_point(value, what: str) -> UvttPoint:
    """A position in cells, within ``DISTANCE_LIMIT`` of zero on both axes."""
    if not isinstance(value, dict):
        _refuse(f"{what} is missing or not a position.")
    return UvttPoint(
        x=_read_number(value.get("x"), f"{what} (x)", -DISTANCE_LIMIT, DISTANCE_LIMIT),
        y=_read_number(value.get("y"), f"{what} (y)", -DISTANCE_LIMIT, DISTANCE_LIMIT),
    )


def _read_flag(value, fallback: bool) -> bool:
    """A yes or no, however an exporter writes it (uvttFields.ts readFlag)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false")
    return fallback


_COLOR = re.compile(r"^#?(?:[0-9a-f]{2})?([0-9a-f]{6})$", re.IGNORECASE)


def _read_color(value) -> str | None:
    """A colour written as ``aarrggbb`` or ``rrggbb``, as ``#rrggbb`` (the alpha
    is dropped); None for anything else."""
    match = _COLOR.match(value.strip()) if isinstance(value, str) else None
    return f"#{match.group(1).lower()}" if match else None


# --- the image (uvttImage.ts) -----------------------------------------------

_DATA_URL_HEAD = re.compile(r"^\s*data:[^,]{0,100},")
_IS_URL = re.compile(r"^\s*[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_IS_IMAGE_PATH = re.compile(r"\.(?:png|webp|jpe?g|gif|bmp|avif|svg)(?:\?.*)?\s*$", re.IGNORECASE)


def _image_type_of(data: bytes) -> str | None:
    """The image format the bytes begin as, by their signature."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def _is_reference(text: str) -> bool:
    """A file path or an address where the image should be: short, and ending as
    an image file or beginning as an address does."""
    return len(text) <= 2048 and bool(_IS_URL.match(text) or _IS_IMAGE_PATH.search(text))


def _decode_base64(text: str) -> bytes:
    """Base64 in the standard alphabet or, where that fails, in the one written
    for URLs (uvttImage.ts decodeBase64; browsers decode forgiving-base64, so
    stray whitespace is dropped and padding is restored before the strict read)."""
    compact = re.sub(r"[\s]", "", text)
    candidates = (compact, compact.replace("-", "+").replace("_", "/"))
    for candidate in candidates:
        padded = candidate + "=" * (-len(candidate) % 4)
        try:
            return base64.b64decode(padded, validate=True)
        except (binascii.Error, ValueError):
            continue
    _refuse("The map image in the file is damaged (it is not valid base64).")


def _read_image(value) -> tuple[bytes, str]:
    if not isinstance(value, str) or value == "":
        _refuse("The file holds no map image.")
    if _is_reference(value):  # type: ignore[arg-type]
        _refuse("This file refers to its image instead of containing it.")
    data = _decode_base64(_DATA_URL_HEAD.sub("", value))  # type: ignore[arg-type]
    image_type = _image_type_of(data)
    if image_type is None:
        _refuse("The map image in the file is not a PNG, WebP or JPEG image.")
    return data, image_type  # type: ignore[return-value]


# --- the map (parseUvtt.ts readMap) ------------------------------------------

def _capitalized(text: str) -> str:
    return text[:1].upper() + text[1:]


class _SegmentBudget:
    """Wall segments and doors a file may still add; counted as read, so a file
    over the limit costs no more reading than it already has."""

    def __init__(self) -> None:
        self.left = WALL_SEGMENTS_LIMIT

    def spend(self, segments: int) -> None:
        self.left -= segments
        if self.left < 0:
            _refuse(_TOO_MANY_WALLS)


def _read_polylines(value, what: str, budget: _SegmentBudget) -> list[tuple[UvttPoint, ...]]:
    lines = _read_list(value, f"The list of {what}s", WALL_SEGMENTS_LIMIT, _TOO_MANY_WALLS)
    out: list[tuple[UvttPoint, ...]] = []
    for index, line in enumerate(lines):
        label = f"{what} {index + 1}"
        if not isinstance(line, list):
            _refuse(f"{_capitalized(label)} is not a list of positions.")
        budget.spend(max(0, len(line) - 1))
        out.append(tuple(_read_point(point, f"Point {i + 1} of {label}")
                         for i, point in enumerate(line)))
    return out


def _read_portal(value, index: int) -> UvttPortal:
    what = f"door {index + 1}"
    portal = _read_record(value, _capitalized(what))
    bounds = portal.get("bounds")
    if not isinstance(bounds, list) or len(bounds) != 2:
        _refuse(f"{_capitalized(what)} does not have two ends.")
    return UvttPortal(
        bounds=(
            _read_point(bounds[0], f"The first end of {what}"),
            _read_point(bounds[1], f"The second end of {what}"),
        ),
        closed=_read_flag(portal.get("closed"), True),
    )


def _read_light(value, index: int) -> UvttLight:
    what = f"light {index + 1}"
    light = _read_record(value, _capitalized(what))
    intensity = light.get("intensity")
    return UvttLight(
        position=_read_point(light.get("position"), f"The position of {what}"),
        range=_read_number(light.get("range"), f"The range of {what}", 0, DISTANCE_LIMIT),
        # a nonsense intensity reads as nominal, not a refusal
        intensity=intensity if _is_number(intensity) and intensity >= 0 else 1,
        color=_read_color(light.get("color")) or "#ffffff",
    )


def _read_map(root) -> UvttDocument:
    file_data = _read_record(root, "The file's content")
    resolution = _read_record(file_data.get("resolution"), "The map's resolution")
    size_in = _read_record(resolution.get("map_size"), "The map size")
    size = UvttPoint(
        x=_read_number(size_in.get("x"), "The map's width", 1, MAP_CELLS_LIMIT),
        y=_read_number(size_in.get("y"), "The map's height", 1, MAP_CELLS_LIMIT),
    )
    origin_in = resolution.get("map_origin")
    origin = UvttPoint(0, 0) if origin_in is None else _read_point(origin_in, "The map's origin")

    budget = _SegmentBudget()
    polylines = (
        tuple(_read_polylines(file_data.get("line_of_sight"), "wall line", budget))
        + tuple(_read_polylines(file_data.get("objects_line_of_sight"), "object outline", budget))
    )
    doors = _read_list(file_data.get("portals"), "The list of doors",
                       WALL_SEGMENTS_LIMIT, _TOO_MANY_WALLS)
    budget.spend(len(doors))
    portals = tuple(_read_portal(door, index) for index, door in enumerate(doors))
    lights_raw = _read_list(file_data.get("lights"), "The list of lights",
                            LIGHTS_LIMIT, _TOO_MANY_LIGHTS)
    lights = tuple(_read_light(light, index) for index, light in enumerate(lights_raw))

    environment = file_data.get("environment")
    environment = environment if isinstance(environment, dict) else {}
    ambient_light = _read_color(environment.get("ambient_light"))
    baked_lighting = _read_flag(environment.get("baked_lighting"), False)

    # Last: decoding the image is the costly part, and a refused file needs none of it
    image_bytes, image_type = _read_image(file_data.get("image"))
    return UvttDocument(raw=file_data, image_bytes=image_bytes, image_type=image_type,
                        origin=origin, size=size, polylines=polylines, portals=portals,
                        lights=lights, ambient_light=ambient_light,
                        baked_lighting=baked_lighting)


def parse(path: Path) -> UvttDocument:
    """Read and validate a ``.uvtt`` file.

    Raises UvttRefused with a plain-words reason for every limit in
    README §3.3: file > 150 MB, > 20,000 wall segments, > 2,000 lights,
    > 4,096 cells per side, < 10 px per cell (checked by the caller,
    which measures the image), image over the decode cap — plus every
    field-level break the importer refuses. Never writes.
    """
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise UvttRefused(f"cannot read {path}: {exc}") from exc
    if len(data) > FILE_BYTES_LIMIT:
        _refuse(f"The file is larger than {FILE_BYTES_LIMIT // (1024 * 1024)} MB.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        _refuse("The file is not a Universal VTT map (it is not valid JSON).")
    try:
        root = json.loads(text)
    except json.JSONDecodeError:
        _refuse("The file is not a Universal VTT map (it is not valid JSON).")
    try:
        return _read_map(root)
    except UvttRefused:
        raise
