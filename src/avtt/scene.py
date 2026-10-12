"""``.uvtt`` -> ``.atlasmap`` conversion — the port.

Spec: README §3.2/§3.3. This is a port of Atlas's ``uvttToScene.ts`` +
``uvttClip.ts`` + ``newSceneFile.ts`` at the pinned release
(``avtt._version.ATLAS_PIN``), which makes it a derivative work of
AGPL code — see README §10 for why the license is declared rather than
dodged. Cited, never vendored (AGENTS.md); re-clone and re-check the
tag before changing a pinned constant.

The whole point of the port is determinism: identical ``.uvtt`` in ->
byte-identical ``.atlasmap`` out (testing discipline 2). The
deterministic id scheme (``wall_uvtt_<n>``, ``chain_uvtt_<n>``,
``light_uvtt_<n>``) reproduces Atlas's exactly. ``schema``/``version``
in the envelope come from the pinned release's ``MapPersistence.ts`` —
the golden fixture is their source of truth, never this docstring,
never the README.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from avtt.uvtt import UvttDocument, UvttPoint

if TYPE_CHECKING:
    from avtt.config import GridDefaults

# --- pinned constants (their home modules at ATLAS_PIN) ----------------------

SCHEMA = "atlas-vtt"     # MapPersistence.ts ATLAS_SCHEMA
SCHEMA_VERSION = 4       # MapPersistence.ts ATLAS_VERSION

MAX_LIGHT_REACH_PX = 8192   # lightingConstants.ts MAX_LIGHT_REACH = MAX_TEXELS * BASE_TEXEL = 4096 * 2
SIDE_TOLERANCE_PX = 2       # uvttToScene.ts SIDE_TOLERANCE: exporters round each side to whole pixels
CELL_PIXELS_LIMIT = 10      # uvttTypes.ts UVTT_LIMITS.cellPixels
IMAGE_PIXELS_LIMIT = 268_435_456  # UVTT_LIMITS.imagePixels: the workers' 1 GiB at four bytes a pixel

HP_RESOURCE_KEY = "hp"       # resources/resourceDefinitions.ts
STRESS_RESOURCE_KEY = "stress"
BAR_WIDGETS = (("hpBar", HP_RESOURCE_KEY), ("stressBar", STRESS_RESOURCE_KEY))  # sceneVisibility.ts


class SceneRefused(Exception):
    """A whole-map refusal after the file parsed: the conversion cannot
    place the scene on its image (Atlas's own import-path refusals,
    ``importUvttFile.ts``)."""


@dataclass(frozen=True)
class CellRect:
    """A rectangle in cells, counted from the image's top-left corner (uvttClip.ts)."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float


# --- JS number semantics the port must reproduce -----------------------------

def _js_round(value: float) -> int:
    """``Math.round``: halves go up (toward +∞); Python's round goes to even."""
    return math.floor(value + 0.5)


def _round_hundredths(value: float) -> float:
    """statedDistance.ts rounded: ``Math.round(value * 100) / 100``."""
    return _js_round(value * 100) / 100


def _js_mod(value: float, period: float) -> float:
    """gridPlacement.ts mod: ``((value % period) + period) % period``."""
    return ((value % period) + period) % period


# --- uvttClip.ts --------------------------------------------------------------

def placeable_rect(size: UvttPoint) -> CellRect:
    """Where a file's walls, doors and lights may lie: on its image and up to
    one cell around it (uvttClip.ts placeableRect)."""
    return CellRect(-1, -1, size.x + 1, size.y + 1)


def is_within(point: UvttPoint, rect: CellRect) -> bool:
    return rect.min_x <= point.x <= rect.max_x and rect.min_y <= point.y <= rect.max_y


def clip_segment(a: UvttPoint, b: UvttPoint,
                 rect: CellRect) -> tuple[UvttPoint, UvttPoint] | None:
    """The part of the segment from ``a`` to ``b`` within ``rect``, or None when
    none of it does (touching the rectangle in one point is none). An end inside
    the rectangle is returned as the very object given, so ends that segments
    share stay shared (uvttClip.ts clipSegment — Liang–Barsky)."""
    if is_within(a, rect) and is_within(b, rect):
        return a, b
    dx = b.x - a.x
    dy = b.y - a.y
    enter, leave = 0.0, 1.0
    # each edge of the rectangle narrows the part of the segment that is inside
    for direction, room in ((-dx, a.x - rect.min_x), (dx, rect.max_x - a.x),
                            (-dy, a.y - rect.min_y), (dy, rect.max_y - a.y)):
        if direction == 0:
            if room < 0:
                return None
        elif direction < 0:
            enter = max(enter, room / direction)
        else:
            leave = min(leave, room / direction)
    if enter >= leave:
        return None

    def at(t: float) -> UvttPoint:
        # Kept inside by clamping: the cut lands on the edge only as exactly as the division allows
        return UvttPoint(min(rect.max_x, max(rect.min_x, a.x + dx * t)),
                         min(rect.max_y, max(rect.min_y, a.y + dy * t)))

    return (at(enter) if enter > 0 else a, at(leave) if leave < 1 else b)


# --- light-unit helpers (lightingUnits/statedDistance/lightRanges/lightEmissionForm) ---

def max_light_range(unit_scale: float, cell_size: float) -> int:
    """The largest bright or dim range a light is given on a map, in whole game
    units (lightRanges.ts maxLightRange): ``floor(MAX_LIGHT_REACH / cellSize *
    unitDistance)``. ``unit_scale`` is the collection's game units per rules
    square (``unitDistance``)."""
    scale_unit_distance = unit_scale if unit_scale > 0 else 5.0   # lightingUnits.ts FALLBACK
    scale_cell_size = cell_size if cell_size > 0 else 70.0
    return math.floor(MAX_LIGHT_REACH_PX / scale_cell_size * scale_unit_distance)


def _emission_of(light_range: float, intensity: float, color: str,
                 unit_scale: float, farthest: float) -> dict:
    """emissionOf: the file's cells are the scene's own, whatever a rules square
    spans — range in cells becomes game units through the collection's distance
    per square; bright is half of where the light ends; both stop at
    ``farthest`` (``maxLightRange``); intensity clamps to 0–2."""
    cells = _round_hundredths(light_range * unit_scale)  # toGameUnits of a distance in squares
    emission = {"bright": 0, "dim": 0, "color": color, "intensity": 1,
                "animation": "none", "kind": "custom"}
    emission = _with_emission_value(emission, "dim", cells, farthest)
    emission = _with_emission_value(emission, "bright", emission["dim"] / 2, farthest)
    return _with_emission_value(emission, "intensity", intensity)


_EMISSION_RANGES = {"bright": (0, math.inf), "dim": (0, math.inf),
                    "intensity": (0, 2)}  # lightEmissionForm.ts RANGES


def _with_emission_value(emission: dict, field: str, value: float,
                         max_range: float = math.inf) -> dict:
    """The emission with one number field set, clamped to its range; bright and
    dim end at ``max_range`` and push each other so dim ≥ bright
    (lightEmissionForm.ts withEmissionValue)."""
    low, high = _EMISSION_RANGES[field]
    cap = max_range if field in ("bright", "dim") else high
    clamped = min(high, cap, max(low, value))
    if clamped == emission[field]:
        return emission
    nxt = dict(emission)
    nxt[field] = clamped
    if field == "bright" and nxt["dim"] < clamped:
        nxt["dim"] = clamped
    if field == "dim" and nxt["bright"] > clamped:
        nxt["bright"] = clamped
    return nxt


def _brightness_of(color: str) -> float:
    """How bright a ``#rrggbb`` colour is, 0 to 1 (Rec. 709 luma), in
    hundredths (uvttToScene.ts brightnessOf)."""
    channel = lambda start: int(color[start:start + 2], 16) / 255  # noqa: E731
    return _js_round((0.2126 * channel(1) + 0.7152 * channel(3)
                      + 0.0722 * channel(5)) * 100) / 100


# --- the conversion (uvttToScene.ts) -----------------------------------------

def cell_size_for(size: UvttPoint, width: int, height: int) -> float | None:
    """World pixels one cell of the file spans on an image of ``width`` ×
    ``height`` pixels, or None when the image does not fit the map size the file
    states: its cells would not be square, and walls would not lie where the
    image shows them (uvttToScene.ts uvttCellSize)."""
    cell_size = width / size.x
    return cell_size if abs(cell_size * size.y - height) <= SIDE_TOLERANCE_PX else None


def checked_cell_size(size: UvttPoint, width: int, height: int) -> float:
    """``cell_size_for`` plus the whole-map refusals the importer layers on it
    (importUvttFile.ts): an image past the decode cap, one that does not fit
    the stated map size, and one too small for its grid."""
    if width * height > IMAGE_PIXELS_LIMIT:
        raise SceneRefused(f"The map image is too large to open: {width} × {height} pixels.")
    cell_size = cell_size_for(size, width, height)
    if cell_size is None:
        raise SceneRefused(f"The map image is {width} × {height} pixels, which does not "
                           f"fit a map of {size.x:g} × {size.y:g} squares.")
    if cell_size < CELL_PIXELS_LIMIT:
        raise SceneRefused(f"The map image is too small for its grid: {width} × {height} "
                           f"pixels for {size.x:g} × {size.y:g} squares.")
    return cell_size


def convert(document: UvttDocument, image_size: tuple[int, int], unit_scale: float,
            max_range: float) -> dict:
    """Convert a validated ``.uvtt`` document to the conversion dict the scene
    file is built from.

    A port of ``uvttToScene.ts``. Reproduces, in order: cell-size math with
    the ±2 px height check (the caller passes it through
    :func:`checked_cell_size`), ``(p - origin) * cellSize`` mapping,
    one-cell-outside clipping, polyline -> wall chains with shared endpoints,
    closed portals -> doors (open portals dropped, counted), light
    dim/bright/intensity with the zero-range drop and the baked-lighting
    hide, and the ambient rule (1 when baked or unnamed, else the Rec. 709
    luma).

    ``image_size`` is the *inline* image's pixel size, read from its own
    header (never the file's claims) — what Atlas measures. ``unit_scale``
    is the collection's game units per rules square;
    ``max_range`` is :func:`max_light_range` for the resulting cell size.

    Deviation from the stub signature: ``image_path`` became
    ``image_size`` — the pipeline measures the image inside the file, not
    the site's PNG (ticket 05 implementation notes).
    """
    cell_size = checked_cell_size(document.size, *image_size)
    rect = placeable_rect(document.size)

    def from_corner(point: UvttPoint) -> UvttPoint:
        return UvttPoint(point.x - document.origin.x, point.y - document.origin.y)

    def to_world(cell: UvttPoint) -> dict:
        return {"x": cell.x * cell_size, "y": cell.y * cell_size}

    walls: dict[str, dict] = {}
    counts = {"walls": 0, "doors": 0, "lights": 0}
    skipped = {"outside": 0, "unlit": 0, "windows": 0}
    on_image = 0
    segments = 0

    def add_wall(from_pt: UvttPoint, to_pt: UvttPoint, rest: dict) -> bool:
        if from_pt.x == to_pt.x and from_pt.y == to_pt.y:
            return False
        nonlocal segments
        segments += 1
        wall_id = f"wall_uvtt_{segments}"
        walls[wall_id] = {"id": wall_id, "kind": "wall",
                          "p1": to_world(from_pt), "p2": to_world(to_pt), **rest}
        return True

    for line_index, line in enumerate(document.polylines):
        cells = [from_corner(point) for point in line]
        for index in range(1, len(cells)):
            inside = clip_segment(cells[index - 1], cells[index], rect)
            if inside is None:
                skipped["outside"] += 1
                continue
            on_image += 1
            if add_wall(inside[0], inside[1],
                        {"type": "solid", "chainId": f"chain_uvtt_{line_index + 1}"}):
                counts["walls"] += 1
    for portal in document.portals:
        from_pt, to_pt = from_corner(portal.bounds[0]), from_corner(portal.bounds[1])
        if not is_within(from_pt, rect) or not is_within(to_pt, rect):
            skipped["outside"] += 1
            continue
        on_image += 1
        if not portal.closed:
            skipped["windows"] += 1  # Dungeondraft's windows: Atlas places nothing
        elif add_wall(from_pt, to_pt, {"type": "door", "closed": True}):
            counts["doors"] += 1

    lights: dict[str, dict] = {}
    for light in document.lights:
        position = from_corner(light.position)
        if not is_within(position, rect):
            skipped["outside"] += 1
            continue
        on_image += 1
        if light.range == 0:
            skipped["unlit"] += 1  # a light without reach lights nothing
            continue
        counts["lights"] += 1
        light_id = f"light_uvtt_{counts['lights']}"
        placed = {"id": light_id, "kind": "light",
                  "x": position.x * cell_size, "y": position.y * cell_size,
                  "emission": _emission_of(light.range, light.intensity, light.color,
                                           unit_scale, max_range)}
        if document.baked_lighting:
            placed["hidden"] = True  # the image shows the glow already
        lights[light_id] = placed

    if document.baked_lighting or document.ambient_light is None:
        ambient: float = 1  # a scene whose image carries its own light is shown as it is
    else:
        ambient = _brightness_of(document.ambient_light)

    offset_x = _js_mod(-document.origin.x * cell_size, cell_size)
    offset_y = _js_mod(-document.origin.y * cell_size, cell_size)
    return {
        "cell_size": cell_size,
        "grid": {"size": cell_size, "offsetX": offset_x, "offsetY": offset_y},
        "walls": walls,
        "lights": lights,
        "lighting": {"enabled": True, "ambient": ambient},
        "counts": counts,
        "skipped": skipped,
        "on_image": on_image,
    }


def check_placement(conversion: dict) -> None:
    """The importer's last whole-map refusal: nothing of the file lies on its
    image means the file's origin is off (importUvttFile.ts)."""
    if conversion["on_image"] == 0 and conversion["skipped"]["outside"] > 0:
        raise SceneRefused("Nothing in the file lies on its map image: its walls, "
                           "doors and lights are all outside it.")


# --- the scene file (newSceneFile.ts + the import's merge) -------------------

def _hidden_on_new_scenes(default_widgets: dict[str, bool] | None) -> list[str]:
    """What a new scene hides of the two bars: those the collection's default
    widgets do not switch on. A collection that never set its default widgets
    shows HP and hides the secondary bar (sceneVisibility.ts
    hiddenOnNewScenes)."""
    if default_widgets is None:
        return [STRESS_RESOURCE_KEY]
    return [key for widget, key in BAR_WIDGETS if not default_widgets.get(widget)]


def scene_file(conversion: dict, background: str | None, *,
               grid_defaults: "GridDefaults | None" = None,
               default_widgets: dict[str, bool] | None = None) -> dict:
    """The content of a ``.atlasmap`` file: the persisted envelope around the
    state, with the conversion's grid, walls, lights and lighting merged in —
    a port of ``newSceneFile.ts`` as ``importUvttFile.ts`` merges it (the
    grid's ``autoDetect`` is dropped: the file states its grid, so there is
    none to detect).

    ``grid_defaults`` is the collection's; when it is None (a fresh
    collection never set any) the grid carries no unit keys, exactly as
    Atlas writes the file for such a collection.
    """
    grid: dict = {
        "enabled": True,
        "visible": True,
        "snapToGrid": True,
        "type": "square",
        "size": conversion["grid"]["size"],
        "offsetX": conversion["grid"]["offsetX"],
        "offsetY": conversion["grid"]["offsetY"],
        "opacity": 0.5,
        "lineType": "solid",
        "lineWidth": 1,
    }
    if grid_defaults is not None:
        grid["unitType"] = grid_defaults.unit_type
        grid["unitDistance"] = grid_defaults.unit_distance
        grid["measurementType"] = ("abstract" if grid_defaults.measurement_mode == "abstract"
                                   else "units")
    hidden = _hidden_on_new_scenes(default_widgets)
    token_settings = {
        "showNameplates": False,
        "hiddenResources": hidden,
        "showInstanceBadges": True,
        "tokenRingSize": 1,
        "showHPBars": HP_RESOURCE_KEY not in hidden,
        "showStressBars": STRESS_RESOURCE_KEY not in hidden,
    }
    state = {
        "schema": SCHEMA,
        "version": SCHEMA_VERSION,
        "background": background,
        "grid": grid,
        "objects": {"tokens": {}, "fog": {}, "pins": {}, "texts": {}, "drawings": {},
                    "walls": conversion["walls"], "lights": conversion["lights"]},
        "camera": {"x": 0, "y": 0, "scale": 1},
        "tokenSettings": token_settings,
        "lighting": conversion["lighting"],
    }
    return {"state": state, "version": SCHEMA_VERSION}


def _js_numbers(value):
    """JSON.stringify prints a whole-number double without a decimal part
    (``20`` where json.dumps writes ``20.0``); the scene file's numbers go
    through cell arithmetic and arrive as doubles. Walks the structure and
    rewrites integral floats as ints so the bytes match Atlas's writer."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer() and abs(value) < 2 ** 53:
        return int(value)
    if isinstance(value, dict):
        return {key: _js_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_js_numbers(item) for item in value]
    return value


def dumps(state: dict) -> bytes:
    """Serialize the envelope deterministically: same state -> same bytes.

    The exact bytes of Atlas's own writer (``JSON.stringify(content,
    null, 2)``): two-space indent, no trailing newline, JS number
    formatting.
    """
    text = json.dumps(_js_numbers(state), indent=2, ensure_ascii=False, allow_nan=False)
    return text.encode("utf-8")
