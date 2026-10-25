"""Ticket 05's pins: the scenes publisher, the uvttToScene port, and the
testing disciplines of README §7 that land with it (1–4; discipline 5
lives in tests/test_presets.py).

The golden-file test (discipline 1) reads the capture under
``fixtures/golden-<version>/`` (fixtures/README.md). Its absence is a
failure, never a skip (ticket 12): the capture is automated
(``tools/capture-golden.py``) and lands in the same change as the pin,
so the only state in which a skip could fire is the broken one. Only
the optional lit variant keeps its skip — that capture is genuinely
optional (fixtures/README.md).
"""

from __future__ import annotations

import base64
import json
import os
import struct
import zlib
from pathlib import Path

import pytest

from avtt import _version, config, image_headers, publish, records, scene, uvtt

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
GOLDEN_VERSION_ENV = "AVTT_GOLDEN_VERSION"

SAMPLE = FIXTURES / "sample.uvtt"


# --- helpers -----------------------------------------------------------------


def golden_version() -> str:
    """The golden version under test: the ``AVTT_GOLDEN_VERSION``
    override when set, else the pin — README §8 step 3's pre-flip
    handle, so a bump can prove the new capture green *before* the pin
    flips (ticket 12)."""
    return os.environ.get(GOLDEN_VERSION_ENV) or _version.ATLAS_PIN


def golden_dir() -> Path:
    """The golden fixture directory the golden tests read (the override
    above decides which; the pin's own by default)."""
    return FIXTURES / f"golden-{golden_version()}"


def sample_png_bytes() -> bytes:
    """The image inside the sample fixtures — the site PNG the campaign
    fixture needs (the generator writes both from one render)."""
    raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return base64.b64decode(raw["image"])


def sample_doc() -> dict:
    """The sample fixture's JSON with the image swapped for a fresh PNG
    (variants reuse the design and change one thing)."""
    doc = json.loads(SAMPLE.read_text(encoding="utf-8"))
    doc["image"] = base64.b64encode(png(64, 32)).decode("ascii")
    return doc


def png(width: int, height: int, *, header_only: bool = False) -> bytes:
    """A minimal valid 8-bit RGBA PNG with deterministic pixels. With
    ``header_only`` the IDAT is left out — enough header for the
    dimension reader, not decodable (used for the oversized-image
    refusal, which reads the header only)."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    data = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
    if header_only:
        return data
    rows = b"".join(b"\x00" + bytes((x * 7 + y * 11) % 256
                                    for x in range(width)
                                    for _ in range(4))
                    for y in range(height))
    return data + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def write_uvtt(path: Path, doc) -> Path:
    """Write a ``.uvtt``; ``doc`` may be raw text (for malformed files)."""
    if isinstance(doc, str):
        path.write_text(doc, encoding="utf-8")
    else:
        path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def variant_doc(**changes) -> dict:
    """The sample design with one change applied (deep-merged one level)."""
    doc = sample_doc()
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(doc.get(key), dict):
            doc[key].update(value)
        else:
            doc[key] = value
    return doc


def make_campaign(tmp_path: Path, *, manifest: str | None = None,
                  doc=None, avtt_yaml: str | None = None,
                  note_text: str = "Site briefing from the core.\n",
                  slug: str = "demo", site_png: bytes | None = None) -> Path:
    """A campaign the scenes publisher accepts: campaign.yaml, avtt.yaml,
    and the complete site triple under maps/sites/<slug>/. ``site_png``
    overrides the site image's bytes (the boundary tests need geometries
    the sample PNG does not have; header-only bytes suffice — the
    pipeline reads image headers only)."""
    tmp_path = Path(tmp_path)
    (tmp_path / "campaign.yaml").write_text("system: icrpg\n", encoding="utf-8")
    (tmp_path / "avtt.yaml").write_text(
        avtt_yaml if avtt_yaml is not None else "collection: demo\n",
        encoding="utf-8")
    site = tmp_path / "maps" / "sites" / slug
    site.mkdir(parents=True)
    (site / f"{slug}.png").write_bytes(
        site_png if site_png is not None else sample_png_bytes())
    write_uvtt(site / f"{slug}.uvtt", sample_doc() if doc is None else doc)
    (site / f"{slug}.md").write_text(note_text, encoding="utf-8")
    if manifest is not None:
        (tmp_path / ".obsidian" / "plugins" / "atlas-vtt").mkdir(parents=True)
        (tmp_path / ".obsidian" / "plugins" / "atlas-vtt" / "manifest.json").write_text(
            json.dumps({"id": "atlas-vtt", "name": "Atlas VTT", "version": manifest}),
            encoding="utf-8")
    return tmp_path


def collections_dir(campaign: Path) -> Path:
    return Path(campaign) / "atlas-vtt" / "collections" / "demo"


def note_bytes(campaign: Path, slug: str = "demo") -> bytes:
    """The site's companion note, byte for byte. Read before a publish,
    compare after (ticket 15): a refusal must leave the note untouched —
    the note is the one write the system makes outside ``atlas-vtt/``
    (contract rule 1's licensed exception) and the highest-blast-radius
    write it makes, so every refusal test pins it, not just the
    ``atlas-vtt/`` tree's absence."""
    return (Path(campaign) / "maps" / "sites" / slug / f"{slug}.md").read_bytes()


def boundary_doc(cells: tuple[int, int], image_px: tuple[int, int], *,
                 polylines: list | None = None) -> dict:
    """A minimal valid ``.uvtt`` at an exact geometry: ``cells`` squares
    spanning ``image_px`` pixels (ticket 15's limit-boundary cases sit the
    geometry *exactly at* a §3.3 limit). The embedded image is a
    header-only PNG — enough header for the dimension reader, and the
    pipeline reads image headers only (README §4): a full 16384 × 16384
    image would be a quarter-gigabyte of pixels no test ever decodes."""
    return {
        "format": 0.2,
        "resolution": {"map_size": {"x": cells[0], "y": cells[1]},
                       "map_origin": {"x": 0, "y": 0}},
        "line_of_sight": polylines or [],
        "portals": [],
        "lights": [],
        "environment": {"baked_lighting": False},
        "image": base64.b64encode(png(*image_px, header_only=True)).decode("ascii"),
    }


def parse_sample() -> uvtt.UvttDocument:
    return uvtt.parse(SAMPLE)


def convert_sample(document: uvtt.UvttDocument | None = None) -> dict:
    document = document or parse_sample()
    size = image_headers.dimensions_of_bytes(document.image_bytes)
    cell = scene.checked_cell_size(document.size, *size)
    farthest = scene.max_light_range(5.0, cell)
    return scene.convert(document, size, 5.0, farthest)


# --- the port, rule by rule (README §3.3) ------------------------------------


def test_image_headers_reads_png_jpeg_webp(tmp_path):
    (tmp_path / "a.png").write_bytes(png(64, 32))
    assert image_headers.pixel_dimensions(tmp_path / "a.png") == (64, 32)

    body = (b"\x30\x01\x00" + b"\x9d\x01\x2a"          # frame tag + sync code
            + struct.pack("<HH", 64, 32))              # W at byte 26, H at 28
    webp = (b"RIFF" + struct.pack("<I", 4 + 8 + len(body)) + b"WEBP"
            + b"VP8 " + struct.pack("<I", len(body)) + body)
    (tmp_path / "b.webp").write_bytes(webp)
    assert image_headers.pixel_dimensions(tmp_path / "b.webp") == (64, 32)

    jpeg = (b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 16)   # APP0, 16 incl. its length
            + b"JFIF\0" + b"\x01\x02" + b"\x00"
            + struct.pack(">HH", 1, 1) + b"\x00\x00"
            + b"\xff\xc0" + struct.pack(">H", 17) + b"\x08"     # SOF0
            + struct.pack(">HH", 32, 64) + b"\x01\x11\x00")
    (tmp_path / "c.jpg").write_bytes(jpeg)
    assert image_headers.pixel_dimensions(tmp_path / "c.jpg") == (64, 32)

    (tmp_path / "d.png").write_bytes(b"\x89PNG\r\n\x1a\ntrunc")
    with pytest.raises(ValueError, match="does not begin"):
        image_headers.pixel_dimensions(tmp_path / "d.png")
    (tmp_path / "e.bin").write_bytes(b"not an image at all")
    with pytest.raises(ValueError, match="does not begin"):
        image_headers.pixel_dimensions(tmp_path / "e.bin")


def test_dimensions_of_bytes_is_the_uvtt_pipeline_reader():
    assert image_headers.dimensions_of_bytes(parse_sample().image_bytes) == (64, 32)
    assert image_headers.dimensions_of_bytes(b"GIF89a") is None
    assert image_headers.dimensions_of_bytes(png(16385, 16384, header_only=True)) \
        == (16385, 16384)


def test_cell_size_math_with_side_tolerance():
    from avtt.uvtt import UvttPoint
    assert scene.cell_size_for(UvttPoint(4, 2), 64, 32) == 16.0
    # exporters round each side to whole pixels: ±2 px on the height
    assert scene.cell_size_for(UvttPoint(4, 2), 64, 30) == 16.0
    assert scene.cell_size_for(UvttPoint(4, 2), 64, 34) == 16.0
    assert scene.cell_size_for(UvttPoint(4, 2), 64, 29) is None
    assert scene.cell_size_for(UvttPoint(4, 2), 64, 35) is None
    assert scene.cell_size_for(UvttPoint(4, 3), 64, 32) is None  # the nonsquare fixture


def test_sample_conversion_pins_ids_chains_counts():
    """The deterministic id scheme and the skip counters, on the fixture the
    golden capture imports (fixtures/README.md's table)."""
    conversion = convert_sample()
    assert list(conversion["walls"]) == [
        "wall_uvtt_1", "wall_uvtt_2", "wall_uvtt_3", "wall_uvtt_4", "wall_uvtt_5"]
    assert [w.get("chainId") for w in conversion["walls"].values()] == [
        "chain_uvtt_1", "chain_uvtt_1", "chain_uvtt_2", "chain_uvtt_4", None]
    assert [w["type"] for w in conversion["walls"].values()] == \
        ["solid", "solid", "solid", "solid", "door"]
    assert conversion["walls"]["wall_uvtt_5"]["closed"] is True
    assert list(conversion["lights"]) == ["light_uvtt_1"]
    assert conversion["counts"] == {"walls": 4, "doors": 1, "lights": 1}
    assert conversion["skipped"] == {"outside": 3, "unlit": 1, "windows": 1}
    # the importer counts a zero-range light (and the window) as on-image
    # before dropping them: 4 walls + 2 portals + 2 lights
    assert conversion["on_image"] == 8


def test_convert_maps_cells_to_world_pixels_with_origin():
    conversion = convert_sample()
    # origin (1,1), cellSize 16: cell (0,0) of the file is world (0,0)
    door = conversion["walls"]["wall_uvtt_5"]
    assert door["p1"] == {"x": 0.0, "y": 0.0}
    assert door["p2"] == {"x": 16.0, "y": 0.0}
    # clipping keeps shared endpoints exactly (line 1's two segments)
    assert conversion["walls"]["wall_uvtt_1"]["p2"] \
        == conversion["walls"]["wall_uvtt_2"]["p1"]
    # the edge-crossing line is cut at the placeable rect (cell 5 = one past the edge)
    clipped = conversion["walls"]["wall_uvtt_3"]
    assert clipped["p1"] == {"x": -16.0, "y": 0.0}
    assert clipped["p2"] == {"x": 80.0, "y": 0.0}


def test_light_math_cells_to_game_units_and_hidden_when_baked():
    light = convert_sample()["lights"]["light_uvtt_1"]
    # feet-based collection, 5 ft squares: range 2 cells = 10 units, bright half
    assert light["emission"] == {"bright": 5, "dim": 10, "color": "#ff8800",
                                 "intensity": 1.5, "animation": "none",
                                 "kind": "custom"}
    assert light["hidden"] is True  # baked lighting: the image shows the glow
    assert light["x"] == 16 and light["y"] == 16


def test_light_clamped_to_max_light_range(tmp_path):
    raw = variant_doc(environment={"baked_lighting": False, "ambient_light": None},
                      lights=[{"position": {"x": 2, "y": 2}, "range": 1_000_000,
                               "intensity": 9, "color": "#ffffff"}])
    conversion = convert_sample(uvtt.parse(write_uvtt(tmp_path / "big.uvtt", raw)))
    light = conversion["lights"]["light_uvtt_1"]
    # maxLightRange = floor(8192 / cellSize * unitDistance) = 2560 at cellSize 16
    assert scene.max_light_range(5.0, 16.0) == 2560
    assert light["emission"]["dim"] == 2560
    assert light["emission"]["bright"] == 1280
    assert light["emission"]["intensity"] == 2  # clamped to the 0–2 slider range
    assert "hidden" not in light


def test_ambient_rules(tmp_path):
    # baked wins even when a color is named (the sample proves precedence)
    assert convert_sample()["lighting"] == {"enabled": True, "ambient": 1}
    # the lit variant takes the luma branch: Rec. 709 luma of #334455
    conversion = convert_sample(uvtt.parse(FIXTURES / "sample-lit.uvtt"))
    assert conversion["lighting"]["ambient"] == 0.26
    assert list(conversion["lights"].values())[0].get("hidden") is None
    # no ambient named at all: daylight
    raw = variant_doc(environment={"baked_lighting": False, "ambient_light": None})
    none_doc = convert_sample(uvtt.parse(write_uvtt(tmp_path / "none.uvtt", raw)))
    assert none_doc["lighting"]["ambient"] == 1


def test_grid_offset_normalized():
    # -origin * cellSize is a whole-cell multiple, so the normalized offset is 0
    grid = convert_sample()["grid"]
    assert grid["size"] == 16.0
    assert grid["offsetX"] == 0.0 and grid["offsetY"] == 0.0


def test_dumps_is_deterministic_and_js_shaped():
    envelope = scene.scene_file(convert_sample(), "atlas-vtt/collections/demo/maps/demo.png")
    assert scene.dumps(envelope) == scene.dumps(envelope)
    text = scene.dumps(envelope).decode("utf-8")
    assert text.startswith('{\n  "state": {')  # two-space indent like JSON.stringify
    assert not text.endswith("\n")             # no trailing newline
    assert '"size": 16,' in text               # whole-number doubles print bare
    assert '"intensity": 1.5' in text
    parsed = json.loads(text)
    assert parsed["state"]["schema"] == "atlas-vtt"
    assert parsed["state"]["version"] == 4
    assert parsed["version"] == 4


def test_scene_file_envelope_fresh_collection_vs_grid_defaults():
    conversion = convert_sample()
    bare = scene.scene_file(conversion, None)
    grid = bare["state"]["grid"]
    assert grid["enabled"] is True and grid["type"] == "square" and grid["size"] == 16.0
    assert "unitType" not in grid and "unitDistance" not in grid \
        and "measurementType" not in grid  # a fresh collection never set gridDefaults
    assert "autoDetect" not in grid  # the import drops it: the file states its grid
    assert bare["state"]["tokenSettings"] == {
        "showNameplates": False, "hiddenResources": ["stress"],
        "showInstanceBadges": True, "tokenRingSize": 1,
        "showHPBars": True, "showStressBars": False,
    }
    assert bare["state"]["objects"] == {
        "tokens": {}, "fog": {}, "pins": {}, "texts": {}, "drawings": {},
        "walls": conversion["walls"], "lights": conversion["lights"]}
    assert bare["state"]["camera"] == {"x": 0, "y": 0, "scale": 1}
    assert list(bare) == ["state", "version"]

    fed = scene.scene_file(
        conversion, None,
        grid_defaults=config.GridDefaults("feet", 5.0, "metric"),
        default_widgets={"hpBar": True, "stressBar": True})
    grid = fed["state"]["grid"]
    assert grid["unitType"] == "feet" and grid["unitDistance"] == 5.0
    assert grid["measurementType"] == "units"
    assert fed["state"]["tokenSettings"]["hiddenResources"] == []
    abstract = scene.scene_file(
        conversion, None,
        grid_defaults=config.GridDefaults("units", 1.0, "abstract"))
    assert abstract["state"]["grid"]["measurementType"] == "abstract"


# --- records (README §3.1, tickets 01/02) -------------------------------------


def test_record_shapes():
    assert records.map_record("demo", "atlas-vtt/collections/demo/maps/demo.png") == {
        "name": "demo", "tags": [], "type": "map",
        "mapFilePath": "atlas-vtt/collections/demo/maps/demo.png"}
    assert records.scene_record("demo", "atlas-vtt/collections/demo/scenes/demo.atlasmap") == {
        "name": "demo", "tags": [], "type": "scene",
        "mapPath": "atlas-vtt/collections/demo/scenes/demo.atlasmap"}
    # ids are left for Atlas to recover; timestamps fall back to adoption time;
    # collection comes from the folder — none of them is ours to write
    for payload in (records.map_record("demo", "x.png"),
                    records.scene_record("demo", "x.atlasmap")):
        for field in ("id", "collection", "createdAt", "modifiedAt"):
            assert field not in payload


def test_record_matches_accepts_atlas_canonical_rewrite():
    """Atlas rewrites adopted records in place (ticket 01): payload beside an
    ``atlasRecord`` envelope, with Atlas-owned fields filled in. That form
    still means what we intended — refuse-on-diff must accept it."""
    intended = records.scene_record("demo", "atlas-vtt/collections/demo/scenes/demo.atlasmap")
    assert records.matches(dict(intended), intended)
    rewritten = {
        "mapPath": intended["mapPath"], "name": "demo", "tags": [], "type": "scene",
        "atlasRecord": {"format": 1, "id": "demo", "name": "demo", "tags": [],
                        "collection": "demo", "createdAt": 1, "modifiedAt": 2,
                        "type": "scene"},
    }
    assert records.matches(rewritten, intended)
    # a rename in the UI is the DM's: refuse
    renamed = json.loads(json.dumps(rewritten))
    renamed["name"] = "Hand-renamed"
    renamed["atlasRecord"]["name"] = "Hand-renamed"
    assert not records.matches(renamed, intended)
    # a different stated path is a different scene: refuse
    moved = json.loads(json.dumps(rewritten))
    moved["mapPath"] = "atlas-vtt/collections/demo/scenes/other.atlasmap"
    assert not records.matches(moved, intended)

    intended_map = records.map_record("demo", "atlas-vtt/collections/demo/maps/demo.png")
    # Atlas's map rewrite carries type only in the envelope (legacyMapFields payload)
    canonical_map = {
        "id": "demo", "name": "demo",
        "mapFilePath": "atlas-vtt/collections/demo/maps/demo.png",
        "tags": [], "collection": "demo", "createdAt": 1, "modifiedAt": 2,
        "atlasRecord": {"format": 1, "id": "demo", "name": "demo", "tags": [],
                        "collection": "demo", "createdAt": 1, "modifiedAt": 2,
                        "type": "map",
                        "mapFilePath": "atlas-vtt/collections/demo/maps/demo.png"},
    }
    assert records.matches(canonical_map, intended_map)
    relinked = json.loads(json.dumps(canonical_map))
    relinked["mapFilePath"] = "atlas-vtt/assets/moved.webp"
    relinked["atlasRecord"]["mapFilePath"] = "atlas-vtt/assets/moved.webp"
    assert not records.matches(relinked, intended_map)


# --- discipline 1: the golden file (needs the human capture) -------------------


def _assert_structurally_equal(golden, ours, path="$", tolerance=1e-9):
    """README §7.1: keys, types, id scheme, math within float tolerance.
    Everything matches exactly except floats (compared within tolerance)
    and the ``background`` path (capture-specific: the UI import renames
    the image into ``assets/`` as a timestamped webp)."""
    if isinstance(golden, dict):
        assert isinstance(ours, dict), path
        assert set(golden) == set(ours), f"{path}: keys differ: {set(golden) ^ set(ours)}"
        for key in golden:
            if key == "background":
                assert isinstance(golden[key], str) and golden[key], path
                assert isinstance(ours[key], str) and ours[key], path
                continue
            _assert_structurally_equal(golden[key], ours[key], f"{path}.{key}", tolerance)
    elif isinstance(golden, list):
        assert isinstance(ours, list) and len(golden) == len(ours), path
        for index, (g, o) in enumerate(zip(golden, ours)):
            _assert_structurally_equal(g, o, f"{path}[{index}]", tolerance)
    elif isinstance(golden, bool) or golden is None:
        assert golden is ours, f"{path}: {golden!r} != {ours!r}"
    elif isinstance(golden, (int, float)):
        assert isinstance(ours, (int, float)) and not isinstance(ours, bool), \
            f"{path}: {ours!r} is not a number"
        assert golden == pytest.approx(ours, abs=tolerance), f"{path}: {golden!r} != {ours!r}"
    else:
        assert golden == ours, f"{path}: {golden!r} != {ours!r}"


@pytest.mark.integration
def test_golden_file():
    """§7.1: the port's output matches the captured .atlasmap
    structurally. The fixture is required (ticket 12): a missing capture
    fails here naming the capture command — never a skip, which is how a
    pin bump could merge with zero golden verification."""
    golden = golden_dir() / "sample.atlasmap"
    assert golden.is_file(), (
        f"missing golden fixture: {golden} — a pin without its capture is "
        f"not a pin; capture it with `tools/capture-golden.py "
        f"{golden_version()}` (automated, fixtures/README.md) and commit "
        "the fixture in the same change as the pin")
    payload = json.loads(golden.read_text(encoding="utf-8"))
    envelope = scene.scene_file(convert_sample(),
                                "atlas-vtt/collections/demo/maps/demo.png")
    _assert_structurally_equal(payload, envelope)


@pytest.mark.integration
@pytest.mark.skipif(not golden_dir().joinpath("sample-lit.atlasmap").is_file(),
                    reason="optional second capture (sample-lit.uvtt) not "
                           "present — genuinely optional (fixtures/README.md)")
def test_golden_file_lit_variant():
    """The luma branch against the real app, when the optional capture exists."""
    golden = golden_dir() / "sample-lit.atlasmap"
    payload = json.loads(golden.read_text(encoding="utf-8"))
    envelope = scene.scene_file(convert_sample(uvtt.parse(FIXTURES / "sample-lit.uvtt")),
                                "atlas-vtt/collections/demo/maps/demo.png")
    _assert_structurally_equal(payload, envelope)


def test_golden_override(monkeypatch):
    """Ticket 12 / README §8 step 3: ``AVTT_GOLDEN_VERSION`` resolves the
    fixture directory the golden tests read, so a pin bump can prove the
    new capture green *before* the pin flips. Unset, the resolution is
    the pin's own directory (the default run)."""
    monkeypatch.delenv(GOLDEN_VERSION_ENV, raising=False)
    assert golden_version() == _version.ATLAS_PIN
    assert golden_dir() == FIXTURES / f"golden-{_version.ATLAS_PIN}"

    # any other committed capture stands in for "the new golden"
    others = sorted(path.name for path in FIXTURES.glob("golden-*")
                    if path.name != f"golden-{_version.ATLAS_PIN}"
                    and (path / "sample.atlasmap").is_file())
    assert others, "no second committed golden to prove the override against"
    version = others[0].removeprefix("golden-")
    monkeypatch.setenv(GOLDEN_VERSION_ENV, version)
    assert golden_version() == version
    assert golden_dir() == FIXTURES / f"golden-{version}"


# --- discipline 2: round-trip determinism --------------------------------------


def test_round_trip_determinism(tmp_path, capsys):
    """§7.2: same .uvtt twice -> byte-identical .atlasmap (unit and CLI)."""
    first = scene.dumps(scene.scene_file(convert_sample(), "bg.png"))
    second = scene.dumps(scene.scene_file(convert_sample(uvtt.parse(SAMPLE)), "bg.png"))
    assert first == second

    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    assert publish.main([str(campaign), "scenes"]) == 0
    atlasmap = collections_dir(campaign) / "scenes" / "demo.atlasmap"
    written = atlasmap.read_bytes()
    assert written == scene.dumps(scene.scene_file(
        convert_sample(), "atlas-vtt/collections/demo/maps/demo.png"))
    before = os.stat(atlasmap).st_mtime_ns
    assert publish.main([str(campaign), "scenes"]) == 0
    assert "already matches — nothing written" in capsys.readouterr().out
    assert atlasmap.read_bytes() == written
    assert os.stat(atlasmap).st_mtime_ns == before, "the identical file was rewritten"


# --- discipline 3: refusals write nothing --------------------------------------


def _refusal_cases() -> list[tuple[str, object, str]]:
    """(name, uvtt document/text, reason fragment) — every Atlas limit and
    the field breaks the importer refuses, one per plain-words reason.
    The one-past cases of ticket 15 sit exactly one over each countable
    limit, so an off-by-one on the refuse side ships red."""
    oversized = sample_doc()  # header claims 16385×16384 (> 268,435,456 px), body truncated
    oversized["image"] = base64.b64encode(png(16385, 16384, header_only=True)).decode("ascii")
    tiny = variant_doc(image=base64.b64encode(png(32, 16)).decode("ascii"))  # cellSize 8 < 10
    wall_hog = variant_doc(line_of_sight=[[{"x": 0, "y": 0}] + [{"x": 0, "y": 0}] * 20002])
    # 20,002 points = 20,001 segments: the first count past 20,000 that must refuse
    one_past_walls = variant_doc(line_of_sight=[[{"x": x, "y": 0} for x in range(20_002)]],
                                 objects_line_of_sight=[], portals=[], lights=[])
    # 39 × 20 over 4 × 2 squares: cellSize 9.75 — fits within the ±2 px
    # height tolerance yet is under the 10 px-per-cell floor
    small_cell = boundary_doc((4, 2), (39, 20))
    light_hog = variant_doc(lights=[{"position": {"x": 1, "y": 1}, "range": 1,
                                     "intensity": 1, "color": "#ffffff"}] * 2001)
    bad_range = variant_doc(lights=[{"position": {"x": 1, "y": 1}, "range": -1,
                                     "intensity": 1, "color": "#ffffff"}])
    no_ends = variant_doc(portals=[{"bounds": [{"x": 1, "y": 1}], "closed": True}])
    all_outside = variant_doc(line_of_sight=[[{"x": 50, "y": 50}, {"x": 60, "y": 50}]],
                              objects_line_of_sight=[], portals=[], lights=[])
    nonsquare = json.loads((FIXTURES / "sample-nonsquare.uvtt").read_text(encoding="utf-8"))
    nonsquare["image"] = base64.b64encode(png(64, 32)).decode("ascii")
    return [
        ("not-json", "{nope", "not valid JSON"),
        ("width-over-4096-cells",
         variant_doc(resolution={"map_size": {"x": 4097, "y": 2}}), "out of range"),
        ("width-not-a-number",
         variant_doc(resolution={"map_size": {"x": "wide", "y": 2}}),
         "missing or not a number"),
        ("origin-not-a-position",
         variant_doc(resolution={"map_size": {"x": 4, "y": 2},
                                 "map_origin": "up and left"}),
         "missing or not a position"),
        ("over-20000-wall-segments", wall_hog, "more than 20,000 wall segments"),
        ("one-past-20000-wall-segments", one_past_walls, "more than 20,000 wall segments"),
        ("over-2000-lights", light_hog, "more than 2,000 lights"),
        ("light-range-negative", bad_range, "out of range"),
        ("door-without-two-ends", no_ends, "does not have two ends"),
        ("no-image", variant_doc(image=""), "holds no map image"),
        ("image-reference", variant_doc(image="map.png"), "refers to its image"),
        ("image-not-base64", variant_doc(image="!!!not-base64!!!"), "not valid base64"),
        ("image-wrong-format",
         variant_doc(image=base64.b64encode(b"GIF89a0102").decode("ascii")),
         "not a PNG, WebP or JPEG"),
        ("image-too-large", oversized, "too large to open"),
        ("image-unreadable-header",
         variant_doc(image=base64.b64encode(b"\xff\xd8\xfftrunc").decode("ascii")),
         "could not be read"),
        ("nonsquare-cells", nonsquare, "does not fit a map of 4 × 3 squares"),
        ("grid-too-small", tiny, "too small for its grid"),
        ("cell-just-under-10-px", small_cell, "too small for its grid"),
        ("nothing-lies-on-image", all_outside,
         "Nothing in the file lies on its map image"),
    ]


@pytest.mark.parametrize("name,doc,fragment", _refusal_cases(),
                         ids=[case[0] for case in _refusal_cases()])
def test_refusals_write_nothing(tmp_path, capsys, name, doc, fragment):
    """§7.3: every limit produces its plain-words reason, the atlas-vtt/
    tree is untouched, and so is the companion note (ticket 15 — the note
    is the one write outside atlas-vtt/, contract rule 1)."""
    campaign = make_campaign(tmp_path, doc=doc, manifest=_version.ATLAS_PIN)
    note_before = note_bytes(campaign)
    atlas = campaign / "atlas-vtt"
    assert publish.main([str(campaign), "scenes", "--site", "demo"]) == 2
    out = capsys.readouterr().out
    assert fragment in out, (name, out)
    assert not atlas.exists(), f"{name}: the refusal wrote into atlas-vtt/"
    assert note_bytes(campaign) == note_before, \
        f"{name}: the refusal edited the companion note"


def test_refusal_of_a_150mb_file_writes_nothing(tmp_path, capsys):
    """The file-size limit fires on the byte count, before any parse; the
    companion note is untouched with the rest (ticket 15)."""
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    note_before = note_bytes(campaign)
    uvtt_path = campaign / "maps" / "sites" / "demo" / "demo.uvtt"
    with open(uvtt_path, "wb") as handle:
        handle.write(b"{")
        handle.truncate(uvtt.FILE_BYTES_LIMIT + 1)
    assert publish.main([str(campaign), "scenes", "--site", "demo"]) == 2
    out = capsys.readouterr().out
    assert "larger than 150 MB" in out
    assert not (campaign / "atlas-vtt").exists()
    assert note_bytes(campaign) == note_before, "the refusal edited the companion note"


def test_incomplete_site_is_refused(tmp_path, capsys):
    """The generator emits png + uvtt + md together; a missing file is
    reported, not guessed around; the note that does exist is untouched
    (ticket 15)."""
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    note_before = note_bytes(campaign)
    (campaign / "maps" / "sites" / "demo" / "demo.png").unlink()
    assert publish.main([str(campaign), "scenes"]) == 2
    out = capsys.readouterr().out
    assert "incomplete" in out and "demo.png" in out
    assert not (campaign / "atlas-vtt").exists()
    assert note_bytes(campaign) == note_before, "the refusal edited the companion note"


def test_site_png_disagreeing_with_uvtt_is_refused(tmp_path, capsys):
    """Ticket 10: the grid/wall math comes from the image embedded in the
    .uvtt, but the scene's background is the site PNG — a disagreeing pair
    would publish misaligned walls, so it is refused naming both sizes."""
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    (campaign / "maps" / "sites" / "demo" / "demo.png").write_bytes(png(128, 32))
    assert publish.main([str(campaign), "scenes", "--site", "demo"]) == 2
    out = capsys.readouterr().out
    assert "refusing demo" in out
    assert "the site image demo.png is 128 × 32 but the .uvtt embeds 64 × 32" in out
    assert "regenerate the site" in out
    assert not (campaign / "atlas-vtt").exists()


def test_site_png_unreadable_is_refused(tmp_path, capsys):
    """Ticket 10: a site PNG no header reader can parse is refused with
    the plain-words header message (image_headers.pixel_dimensions)."""
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    (campaign / "maps" / "sites" / "demo" / "demo.png").write_bytes(b"not a png at all")
    assert publish.main([str(campaign), "scenes", "--site", "demo"]) == 2
    out = capsys.readouterr().out
    assert "refusing demo" in out
    assert "does not begin as a PNG, JPEG or WebP" in out
    assert not (campaign / "atlas-vtt").exists()


def test_unknown_site_is_refused(tmp_path, capsys):
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    assert publish.main([str(campaign), "scenes", "--site", "nosuch"]) == 2
    assert "no site 'nosuch'" in capsys.readouterr().out


def test_missing_config_is_refused_on_the_pinned_vault(tmp_path, capsys):
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    (campaign / "avtt.yaml").unlink()
    assert publish.main([str(campaign), "scenes"]) == 2
    assert "avtt.yaml" in capsys.readouterr().out
    assert not (campaign / "atlas-vtt").exists()


@pytest.mark.parametrize("yaml_text,fragment", [
    ("collection: ../escape\n", "stable slug"),
    ("collection: ''\n", "stable slug"),
    ("collection: demo\ngrid:\n  unit_type: leagues\n  unit_distance: 5\n"
     "  measurement_mode: metric\n", "unit_type"),
    ("collection: demo\ngrid:\n  unit_type: feet\n  unit_distance: 0\n"
     "  measurement_mode: metric\n", "unit_distance"),
    ("collection: demo\ngrid:\n  unit_type: feet\n  unit_distance: 5\n"
     "  measurement_mode: imperial\n", "measurement_mode"),
    ("collection: demo\ndefault_widgets: [hpBar]\n", "default_widgets"),
])
def test_bad_config_values_are_refused(tmp_path, capsys, yaml_text, fragment):
    campaign = make_campaign(tmp_path, avtt_yaml=yaml_text, manifest=_version.ATLAS_PIN)
    with pytest.raises(config.ConfigRefused, match=fragment.replace("(", "\\(")):
        config.load(campaign)
    assert publish.main([str(campaign), "scenes"]) == 2
    assert fragment in capsys.readouterr().out
    assert not (campaign / "atlas-vtt").exists()


# --- the inclusive limit boundaries (ticket 15) --------------------------------
#
# §3.3's limits are `>` comparisons: a file sitting exactly at a limit is
# accepted, one past it refuses (the refuse side lives in the refusal
# table above). The exactly-at side is what an off-by-one would break, so
# each of the six limits gets its file-at-the-limit publish here. The
# image geometries ride header-only PNGs: the pipeline reads image
# headers only (README §4), and a full 16384 × 16384 image would be a
# quarter-gigabyte of pixels no test ever decodes.


def test_boundary_exactly_20000_wall_segments_publishes(tmp_path, capsys):
    """One line of 20,001 points = 20,000 segments — the whole budget, and
    everything else in the file empty, so the total is exactly the limit."""
    line = [{"x": x, "y": 0} for x in range(20_001)]
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN,
                             doc=variant_doc(line_of_sight=[line],
                                             objects_line_of_sight=[],
                                             portals=[], lights=[]))
    assert publish.main([str(campaign), "scenes", "--site", "demo"]) == 0
    out = capsys.readouterr().out
    assert "demo: published" in out and "walls" in out
    assert (collections_dir(campaign) / "scenes" / "demo.atlasmap").is_file()


def test_boundary_exactly_2000_lights_publishes(tmp_path, capsys):
    """Exactly 2,000 lights is the whole budget: the lights limit refuses
    only the 2,001st."""
    lights = [{"position": {"x": 1, "y": 1}, "range": 1,
               "intensity": 1, "color": "#ffffff"}] * 2_000
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN,
                             doc=variant_doc(lights=lights))
    assert publish.main([str(campaign), "scenes", "--site", "demo"]) == 0
    out = capsys.readouterr().out
    assert "demo: published" in out and "2000 lights" in out
    assert (collections_dir(campaign) / "scenes" / "demo.atlasmap").is_file()


def test_boundary_exactly_4096_cells_per_side_publishes(tmp_path):
    """4,096 squares on a side is the whole budget; with 10 px cells that
    means a 40,960 × 10 image (the cell-pixels floor is what sizes it)."""
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN,
                             doc=boundary_doc((4_096, 1), (40_960, 10)),
                             site_png=png(40_960, 10, header_only=True))
    assert publish.main([str(campaign), "scenes"]) == 0
    assert (collections_dir(campaign) / "scenes" / "demo.atlasmap").is_file()


def test_boundary_exactly_10px_per_cell_publishes(tmp_path, capsys):
    """A cell of exactly 10.0 world pixels is the floor: 40 × 20 px over
    4 × 2 squares must publish where 9.75 px refuses."""
    line = [{"x": 0, "y": 0}, {"x": 2, "y": 0}]
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN,
                             doc=boundary_doc((4, 2), (40, 20),
                                              polylines=[line]),
                             site_png=png(40, 20))
    assert publish.main([str(campaign), "scenes"]) == 0
    assert "1 wall" in capsys.readouterr().out
    assert (collections_dir(campaign) / "scenes" / "demo.atlasmap").is_file()


def test_boundary_exactly_268435456_image_pixels_publishes(tmp_path):
    """268,435,456 px (16384 × 16384) is the decode budget exactly: at four
    bytes a pixel it is the last image size the importer opens."""
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN,
                             doc=boundary_doc((1_024, 1_024), (16_384, 16_384)),
                             site_png=png(16_384, 16_384, header_only=True))
    assert publish.main([str(campaign), "scenes"]) == 0
    assert (collections_dir(campaign) / "scenes" / "demo.atlasmap").is_file()


def test_boundary_file_of_exactly_the_size_limit_publishes(tmp_path, monkeypatch):
    """A file of exactly the size limit parses instead of refusing: the
    check is ``len(data) > FILE_BYTES_LIMIT``. The real 150 MB constant is
    not rebuilt here — 150 MB of JSON is slow to construct and slow to
    parse — so the limit is patched to 1 MiB and the file padded to
    exactly that many bytes with trailing JSON whitespace. That pins the
    comparison at its boundary; that the constant is 150 MB, and that one
    byte over it refuses, stay with
    ``test_refusal_of_a_150mb_file_writes_nothing`` (the unusual
    construction the ticket asks to have documented)."""
    limit = 1024 * 1024
    monkeypatch.setattr(uvtt, "FILE_BYTES_LIMIT", limit)
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    text = json.dumps(sample_doc())
    padding = limit - len(text.encode("utf-8"))
    assert padding > 0
    uvtt_path = campaign / "maps" / "sites" / "demo" / "demo.uvtt"
    uvtt_path.write_text(text + " " * padding, encoding="utf-8")
    assert uvtt_path.stat().st_size == limit
    assert publish.main([str(campaign), "scenes", "--site", "demo"]) == 0
    assert (collections_dir(campaign) / "scenes" / "demo.atlasmap").is_file()


# --- the non-PNG images inside a real .uvtt (ticket 15) -------------------------


@pytest.mark.parametrize("fixture_name,image_type", [
    ("sample-webp.uvtt", "image/webp"),   # VP8L: the lossless reader, least covered
    ("sample-jpeg.uvtt", "image/jpeg"),   # the SOF segment walk
], ids=["webp-vp8l", "jpeg"])
def test_webp_and_jpeg_uvtt_convert_end_to_end(tmp_path, capsys, fixture_name, image_type):
    """A ``.uvtt`` whose embedded image is not a PNG walks the real
    conversion path green (ticket 15): the header readers behind
    ``dimensions_of_bytes`` are reached by a publish, not only by the
    unit test above. The variants carry the sample design — same
    geometry — so the published scene is byte-identical to the PNG
    sample's, which is what proves the readers agree."""
    path = FIXTURES / fixture_name
    document = uvtt.parse(path)
    assert document.image_type == image_type
    assert image_headers.dimensions_of_bytes(document.image_bytes) == (64, 32)
    campaign = make_campaign(
        tmp_path, manifest=_version.ATLAS_PIN,
        doc=json.loads(path.read_text(encoding="utf-8")))
    assert publish.main([str(campaign), "scenes"]) == 0
    assert "4 walls, 1 door, 1 light" in capsys.readouterr().out
    atlasmap = collections_dir(campaign) / "scenes" / "demo.atlasmap"
    assert atlasmap.read_bytes() == scene.dumps(scene.scene_file(
        convert_sample(), "atlas-vtt/collections/demo/maps/demo.png"))


# --- discipline 4: the degrade path ---------------------------------------------


def test_degrade_path_to_inbox(tmp_path, capsys):
    """§7.4: golden mismatch (a vault not running the pinned Atlas) -> the
    .uvtt lands in atlas-vtt/_inbox/ with instructions, nothing else written."""
    campaign = make_campaign(tmp_path, manifest="9.9.9")
    note_before = (campaign / "maps" / "sites" / "demo" / "demo.md").read_bytes()
    assert publish.main([str(campaign), "scenes"]) == 0
    out = capsys.readouterr().out
    assert f"atlas-pin-mismatch: pin={_version.ATLAS_PIN} detected=9.9.9" in out
    assert "writing no .atlasmap" in out
    assert "drag it into Atlas" in out and "walls, doors and lights come along" in out
    inbox_copy = campaign / "atlas-vtt" / "_inbox" / "demo.uvtt"
    assert inbox_copy.read_bytes() == (campaign / "maps" / "sites" / "demo"
                                       / "demo.uvtt").read_bytes()
    # _inbox/ only: no collections, no records, no scene files, no note edit
    assert list((campaign / "atlas-vtt").iterdir()) == [campaign / "atlas-vtt" / "_inbox"]
    assert (campaign / "maps" / "sites" / "demo" / "demo.md").read_bytes() == note_before


def test_degrade_is_unknown_detection_too(tmp_path, capsys):
    campaign = make_campaign(tmp_path)  # no .obsidian anywhere
    assert publish.main([str(campaign), "scenes"]) == 0
    out = capsys.readouterr().out
    assert f"atlas-pin-mismatch: pin={_version.ATLAS_PIN} detected=unknown" in out
    assert (campaign / "atlas-vtt" / "_inbox" / "demo.uvtt").is_file()


def test_degrade_message_names_vault_root_when_no_obsidian_dir(tmp_path, capsys):
    """Ticket 17: with no .obsidian/ under the campaign at all, the layout —
    not a missing manifest — is the problem: the tool assumes the campaign
    directory *is* the Obsidian vault root (README §5.1), so a nested
    campaign degrades on every run. The degrade says so in plain words,
    on top of the usual mismatch line, and the _inbox/ copy still happens."""
    campaign = make_campaign(tmp_path)  # no .obsidian anywhere
    assert publish.main([str(campaign), "scenes"]) == 0
    out = capsys.readouterr().out
    assert f"atlas-pin-mismatch: pin={_version.ATLAS_PIN} detected=unknown" in out
    assert "no .obsidian/" in out
    assert "campaign directory is the Obsidian vault root" in out
    assert (campaign / "atlas-vtt" / "_inbox" / "demo.uvtt").is_file()


def test_degrade_keeps_todays_message_when_obsidian_dir_exists(tmp_path, capsys):
    """Ticket 17: the plain-words vault-root message is for "no .obsidian/ at
    all" — a vault that HAS .obsidian/ but an unreadable plugin manifest is
    a different problem (a broken plugin install) and keeps today's
    unknown-mismatch behavior and message unchanged."""
    campaign = make_campaign(tmp_path)
    plugin_dir = campaign / ".obsidian" / "plugins" / "atlas-vtt"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "manifest.json").write_text("not json at all", encoding="utf-8")
    assert publish.main([str(campaign), "scenes"]) == 0
    out = capsys.readouterr().out
    assert f"atlas-pin-mismatch: pin={_version.ATLAS_PIN} detected=unknown" in out
    assert "vault root" not in out
    assert (campaign / "atlas-vtt" / "_inbox" / "demo.uvtt").is_file()


def test_degrade_is_idempotent_and_refuses_on_diff(tmp_path, capsys):
    campaign = make_campaign(tmp_path, manifest="9.9.9")  # not the pin, at any pin
    assert publish.main([str(campaign), "scenes"]) == 0
    inbox_copy = campaign / "atlas-vtt" / "_inbox" / "demo.uvtt"
    before = os.stat(inbox_copy).st_mtime_ns
    assert publish.main([str(campaign), "scenes"]) == 0
    assert "already in the inbox" in capsys.readouterr().out
    assert os.stat(inbox_copy).st_mtime_ns == before

    inbox_copy.write_bytes(b"different bytes entirely")  # a hand-edited inbox copy
    assert publish.main([str(campaign), "scenes", "--site", "demo"]) == 2
    assert "exists and differs" in capsys.readouterr().out
    assert inbox_copy.read_bytes() == b"different bytes entirely"


def test_degrade_refuses_an_invalid_uvtt_without_copying(tmp_path, capsys):
    campaign = make_campaign(tmp_path, manifest="9.9.9",  # not the pin, at any pin
                             doc=variant_doc(image=""))
    assert publish.main([str(campaign), "scenes"]) == 2
    assert "holds no map image" in capsys.readouterr().out
    assert not (campaign / "atlas-vtt").exists(), "the degrade copied an invalid file"


def test_degrade_dry_run_writes_nothing(tmp_path, capsys):
    campaign = make_campaign(tmp_path, manifest="9.9.9")  # not the pin, at any pin
    assert publish.main([str(campaign), "scenes", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "_inbox" in out and "would write it" in out
    assert not (campaign / "atlas-vtt").exists()


# --- --dry-run on the pinned path (acceptance criterion 5) -----------------------


def test_dry_run_prints_plan_and_writes_nothing(tmp_path, capsys):
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    assert publish.main([str(campaign), "scenes", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "dry run — file plan for site 'demo'" in out
    for name in ("demo.png", "demo.json", "demo.atlasmap", "companion-note link"):
        assert name in out, name
    assert out.count("maps") >= 2 and out.count("scenes") >= 2  # both records' folders
    assert "would write it" in out
    assert not (campaign / "atlas-vtt").exists(), "the dry run wrote files"


def test_dry_run_reports_the_first_divergence(tmp_path, capsys):
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    atlasmap = collections_dir(campaign) / "scenes" / "demo.atlasmap"
    atlasmap.parent.mkdir(parents=True)
    atlasmap.write_text('{"state": {"schema": "hand-tuned"}}', encoding="utf-8")
    before = atlasmap.read_bytes()
    assert publish.main([str(campaign), "scenes", "--dry-run"]) == 2
    out = capsys.readouterr().out
    assert "would REFUSE" in out and "exists and differs" in out and "--force" in out
    assert atlasmap.read_bytes() == before
    assert not (collections_dir(campaign) / "maps" / "demo.png").exists()


def test_dry_run_force_points_at_the_v2_sibling(tmp_path, capsys):
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    atlasmap = collections_dir(campaign) / "scenes" / "demo.atlasmap"
    atlasmap.parent.mkdir(parents=True)
    atlasmap.write_text('{"state": {"schema": "hand-tuned"}}', encoding="utf-8")
    assert publish.main([str(campaign), "scenes", "--dry-run", "--force"]) == 0
    out = capsys.readouterr().out
    assert "demo-v2" in out
    assert not (collections_dir(campaign) / "scenes" / "demo-v2.atlasmap").exists()


# --- the companion note (acceptance criterion 6, contract rule 1) -----------------


def test_companion_note_append_is_idempotent(tmp_path, capsys):
    original = "Site briefing from the core.\nSecond line.\n"
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN,
                             note_text=original)
    assert publish.main([str(campaign), "scenes"]) == 0
    note = campaign / "maps" / "sites" / "demo" / "demo.md"
    after_first = note.read_text(encoding="utf-8")
    assert after_first == original + "![[demo.atlasmap]]\n"

    assert publish.main([str(campaign), "scenes"]) == 0
    assert "already matches" in capsys.readouterr().out
    assert note.read_text(encoding="utf-8") == after_first, "republish rewrote the note"


def test_companion_note_preserves_content_without_trailing_newline(tmp_path):
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN,
                             note_text="no trailing newline")
    assert publish.main([str(campaign), "scenes"]) == 0
    note = campaign / "maps" / "sites" / "demo" / "demo.md"
    assert note.read_text(encoding="utf-8") == "no trailing newline\n![[demo.atlasmap]]\n"


@pytest.mark.parametrize("note_text", [
    "See [[demo.atlasmap]] here.\n",
    "Embedded: ![[demo.atlasmap|the keep]]\n",
    "Snapshot link [[demo.atlasmap#gate]]\n",
])
def test_companion_note_recognizes_any_link_shape(tmp_path, note_text):
    """A note that already links the scene (plain, alias, embed, subpath)
    gains no second line."""
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN,
                             note_text=note_text)
    assert publish.main([str(campaign), "scenes"]) == 0
    note = campaign / "maps" / "sites" / "demo" / "demo.md"
    assert note.read_text(encoding="utf-8") == note_text


@pytest.mark.parametrize("note_text,carries", [
    ("A different file: [[demo.atlasmap-old]] is not this scene.\n", False),
    ("A different file: [[demo.atlasmaps]] is not this scene either.\n", False),
    ("Plain [[demo.atlasmap]] counts.\n", True),
    ("Alias ![[demo.atlasmap|Scene]] counts.\n", True),
    ("Subpath [[demo.atlasmap#fog]] counts.\n", True),
])
def test_note_link_detection_is_anchored(tmp_path, note_text, carries):
    """Ticket 18: the note-link idempotency check is anchored — the target
    name must be followed by a link terminator (``]``, ``|`` alias, ``#``
    subpath), so a link whose target merely *starts with*
    ``<slug>.atlasmap`` (``-old``, plural) does not count and the real
    embed line is still appended; the plain/alias/subpath shapes that do
    count still gain no second line."""
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN,
                             note_text=note_text)
    assert publish.main([str(campaign), "scenes"]) == 0
    note = campaign / "maps" / "sites" / "demo" / "demo.md"
    expected = note_text if carries else note_text + "![[demo.atlasmap]]\n"
    assert note.read_text(encoding="utf-8") == expected


# --- the write path end to end ----------------------------------------------------


def test_publish_writes_the_plan_in_order(tmp_path):
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    assert publish.main([str(campaign), "scenes"]) == 0
    collections = collections_dir(campaign)
    assert (collections / "maps" / "demo.png").read_bytes() == sample_png_bytes()
    atlasmap = json.loads((collections / "scenes" / "demo.atlasmap").read_text(encoding="utf-8"))
    assert atlasmap["state"]["background"] == "atlas-vtt/collections/demo/maps/demo.png"
    map_record = json.loads((collections / "maps" / "demo.json").read_text(encoding="utf-8"))
    assert map_record["mapFilePath"] == "atlas-vtt/collections/demo/maps/demo.png"
    scene_record = json.loads((collections / "scenes" / "demo.json").read_text(encoding="utf-8"))
    assert scene_record["mapPath"] == "atlas-vtt/collections/demo/scenes/demo.atlasmap"


def test_publish_reports_counts_refuse_on_diff_and_force_v2(tmp_path, capsys):
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    assert publish.main([str(campaign), "scenes"]) == 0
    assert "4 walls, 1 door, 1 light" in capsys.readouterr().out

    # a hand-tuned scene (contract rule 3's moved door) is never overwritten
    atlasmap = collections_dir(campaign) / "scenes" / "demo.atlasmap"
    tuned = json.loads(atlasmap.read_text(encoding="utf-8"))
    tuned["state"]["objects"]["walls"]["wall_uvtt_1"]["p1"] = {"x": 1.0, "y": 2.0}
    tuned_bytes = scene.dumps(tuned)
    atlasmap.write_bytes(tuned_bytes)
    assert publish.main([str(campaign), "scenes", "--site", "demo"]) == 2
    out = capsys.readouterr().out
    assert "exists and differs" in out and "--force" in out
    assert atlasmap.read_bytes() == tuned_bytes

    # --force republishes the whole site set as demo-v2, original untouched
    assert publish.main([str(campaign), "scenes", "--site", "demo", "--force"]) == 0
    collections = collections_dir(campaign)
    assert (collections / "scenes" / "demo-v2.atlasmap").is_file()
    assert (collections / "scenes" / "demo-v2.json").is_file()
    assert (collections / "maps" / "demo-v2.png").is_file()
    assert (collections / "maps" / "demo-v2.json").is_file()
    assert json.loads((collections / "scenes" / "demo-v2.json").read_text(
        encoding="utf-8"))["mapPath"].endswith("demo-v2.atlasmap")
    note = (campaign / "maps" / "sites" / "demo" / "demo.md").read_text(encoding="utf-8")
    assert note.endswith("![[demo.atlasmap]]\n![[demo-v2.atlasmap]]\n")
    assert json.loads(atlasmap.read_text(encoding="utf-8")) == tuned, \
        "the hand-tuned scene was overwritten"

    # --force again: the v2 set matches already, nothing written
    assert publish.main([str(campaign), "scenes", "--site", "demo", "--force"]) == 0
    assert "demo-v2 already matches — nothing written" in capsys.readouterr().out


def test_publish_counts_line_reports_skips(tmp_path, capsys):
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    assert publish.main([str(campaign), "scenes"]) == 0
    assert "left out: 3 outside, 1 unlit, 1 window" in capsys.readouterr().out


def test_publish_refuses_a_renamed_record(tmp_path, capsys):
    """A record the DM renamed in Atlas is the DM's — republishing refuses
    instead of stomping the rename (contract rule 3)."""
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    assert publish.main([str(campaign), "scenes"]) == 0
    record_path = collections_dir(campaign) / "scenes" / "demo.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["name"] = "Hand-renamed"
    record["atlasRecord"] = {"format": 1, "id": "demo", "name": "Hand-renamed",
                             "tags": [], "collection": "demo", "createdAt": 1,
                             "modifiedAt": 2, "type": "scene"}
    record_path.write_text(json.dumps(record), encoding="utf-8")
    assert publish.main([str(campaign), "scenes", "--site", "demo"]) == 2
    assert "exists and differs" in capsys.readouterr().out
    assert json.loads(record_path.read_text(encoding="utf-8"))["name"] == "Hand-renamed"


def test_publish_accepts_an_atlas_rewritten_record_as_same(tmp_path, capsys):
    """The canonical rewrite of our own record means the same: republishing
    writes nothing (ticket 01's corollary for rule 3)."""
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    assert publish.main([str(campaign), "scenes"]) == 0
    record_path = collections_dir(campaign) / "scenes" / "demo.json"
    intended = json.loads(record_path.read_text(encoding="utf-8"))
    rewritten = {"mapPath": intended["mapPath"], "name": "demo", "tags": [],
                 "type": "scene",
                 "atlasRecord": {"format": 1, "id": "demo", "name": "demo",
                                 "tags": [], "collection": "demo", "createdAt": 1,
                                 "modifiedAt": 2, "type": "scene"}}
    record_path.write_text(json.dumps(rewritten, indent=2), encoding="utf-8")
    assert publish.main([str(campaign), "scenes", "--site", "demo"]) == 0
    assert "already matches" in capsys.readouterr().out


def test_atlasmap_refuse_on_diff_is_semantic_not_bytes(tmp_path, capsys):
    """A reformatted-but-equal .atlasmap is not a divergence: the file is
    compared as parsed JSON, never as bytes."""
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    assert publish.main([str(campaign), "scenes"]) == 0
    atlasmap = collections_dir(campaign) / "scenes" / "demo.atlasmap"
    payload = json.loads(atlasmap.read_text(encoding="utf-8"))
    atlasmap.write_text(json.dumps(payload, separators=(",", ":")))  # same meaning, other bytes
    assert publish.main([str(campaign), "scenes", "--site", "demo"]) == 0
    assert "already matches" in capsys.readouterr().out


def test_multiple_sites_publish_and_partial_refusal(tmp_path, capsys):
    campaign = make_campaign(tmp_path, manifest=_version.ATLAS_PIN)
    sites = campaign / "maps" / "sites"
    for slug in ("alpha", "beta"):
        site = sites / slug
        site.mkdir()
        (site / f"{slug}.png").write_bytes(sample_png_bytes())
        write_uvtt(site / f"{slug}.uvtt", sample_doc())
        (site / f"{slug}.md").write_text(f"{slug} briefing.\n", encoding="utf-8")
    # gamma is broken: the run reports it and still publishes the others
    gamma = sites / "gamma"
    gamma.mkdir()
    (gamma / "gamma.png").write_bytes(sample_png_bytes())
    write_uvtt(gamma / "gamma.uvtt", variant_doc(image=""))
    (gamma / "gamma.md").write_text("gamma\n", encoding="utf-8")
    note_bytes_before = {slug: note_bytes(campaign, slug)
                         for slug in ("demo", "alpha", "beta", "gamma")}
    assert publish.main([str(campaign), "scenes"]) == 2
    out = capsys.readouterr().out
    for slug in ("alpha", "beta", "demo"):
        assert f"{slug}: published" in out, slug
    assert "refusing gamma" in out and "holds no map image" in out
    for slug in ("alpha", "beta", "demo"):
        assert (collections_dir(campaign) / "scenes" / f"{slug}.atlasmap").is_file()
    # the published notes gained exactly their embed line (compared as
    # text, both sides through universal newlines: the append rewrites
    # through Python text mode, so on-disk line endings are the
    # platform's); the refused gamma's note is byte-identical (ticket 15)
    for slug in ("demo", "alpha", "beta"):
        note = sites / slug / f"{slug}.md"
        assert note.read_text(encoding="utf-8") \
            == note_bytes_before[slug].decode("utf-8").replace("\r\n", "\n") \
            + f"![[{slug}.atlasmap]]\n", slug
    assert note_bytes(campaign, "gamma") == note_bytes_before["gamma"], \
        "the refusal edited gamma's companion note"
