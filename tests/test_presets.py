"""The presets publisher's pins (ticket 04; discipline 5, README §7.5).

The validator port must refuse every preset Atlas's own loader would
ignore — and every preset Atlas would silently *alter* (a dropped
widget entry, a clamped light radius), because a knob the DM believes
is live but is not is the same failure at the table. The write pins are
contract rule 3: refuse-on-diff, ``--force`` writes a ``-v2`` sibling,
and the built-in-system short-circuit writes nothing at all.
"""

from __future__ import annotations

import json
import os

import pytest

from avtt import _version, presets, publish

# --- helpers ---------------------------------------------------------------


def valid_preset() -> dict:
    """The minimum Atlas accepts: id, name, rules with gridDefaults + conditions."""
    return {
        "id": "pack-test",
        "name": "Test Pack",
        "rules": {
            "gridDefaults": {"unitType": "feet", "unitDistance": 5,
                             "measurementMode": "metric"},
            "conditions": [{"id": "t-blind", "name": "Blinded",
                            "color": "#334155", "icon": "eye"}],
        },
    }


@pytest.fixture
def campaign(tmp_path):
    """A campaign directory that asks for the icrpg pack."""
    (tmp_path / "campaign.yaml").write_text("name: test\ntitle: Test\nsystem: icrpg\n",
                                            encoding="utf-8")
    return tmp_path


def broken(base: dict, **changes) -> dict:
    """A copy of `base` with one deliberate break applied.

    Paths use dots for keys and ``[n]`` for list indices, e.g.
    ``rules.conditions[0].color``.
    """
    preset = json.loads(json.dumps(base))  # deep copy
    for path, value in changes.items():
        parts: list = []
        for part in path.split("."):
            if part.endswith("]"):
                name, index = part[:-1].rsplit("[", 1)
                if name:
                    parts.append(name)
                parts.append(int(index))
            else:
                parts.append(part)
        target = preset
        for key in parts[:-1]:
            target = target[key]
        if value is KeyError:
            target.pop(parts[-1], None)
        else:
            target[parts[-1]] = value
    return preset


# --- the validator port (README §3.4, discipline 5) ------------------------


def test_minimal_valid_preset_passes():
    assert presets.validate_preset(valid_preset()) == []


@pytest.mark.parametrize("broken_preset, fragment", [
    ({}, "Atlas ignores the file"),
    (broken(valid_preset(), id="   "), "id is missing, blank"),
    (broken(valid_preset(), id="builtin:dnd5e"), "builtin:"),
    (broken(valid_preset(), id=KeyError), "id is missing"),
    (broken(valid_preset(), name=""), "name is missing, blank"),
    (broken(valid_preset(), rules=KeyError), "rules is missing"),
    (broken(valid_preset(), **{"rules.gridDefaults": KeyError}), "gridDefaults"),
    (broken(valid_preset(), **{"rules.gridDefaults.unitType": "leagues"}),
     "unitType"),
    (broken(valid_preset(), **{"rules.gridDefaults.unitDistance": 0}),
     "unitDistance"),
    (broken(valid_preset(), **{"rules.gridDefaults.unitDistance": 0.0000001}),
     "between 0.000001 and 1000000"),
    (broken(valid_preset(), **{"rules.gridDefaults.unitDistance": 1_000_000_000}),
     "between 0.000001 and 1000000"),
    (broken(valid_preset(), **{"rules.gridDefaults.measurementMode": "imperial"}),
     "measurementMode"),
    (broken(valid_preset(), **{"rules.conditions": KeyError}), "conditions"),
    (broken(valid_preset(), **{"rules.conditions": "blind"}),
     "conditions is missing or not a list"),
    (broken(valid_preset(), **{"rules.gridDefaults.abstractRangeBands":
                               [{"name": "Close", "maxSquares": 0}]}),
     "abstractRangeBands[0]"),
])
def test_fatal_breaks_are_refused_whole(broken_preset, fragment):
    """Atlas ignores these files entirely; the installer must never write one."""
    failures = presets.validate_preset(broken_preset)
    assert failures, "a deliberately-fatal preset passed the validator"
    assert any(fragment in failure for failure in failures), failures


def test_unit_distance_bounds_are_inclusive():
    """0.7.1 tightened the preset validator: ``gridDefaults.unitDistance``
    is routed through ``isUnitDistance`` (presetValidation.ts:59), which
    accepts exactly [0.000001, 1000000] — the boundaries are in, one step
    outside on either side is fatal (grid/unitDistance.ts
    MIN/MAX_UNIT_DISTANCE; ticket 08)."""
    for inside in (0.000001, 5, 1_000_000):
        preset = broken(valid_preset(), **{"rules.gridDefaults.unitDistance": inside})
        assert presets.validate_preset(preset) == [], inside
    for outside in (0.0000001, 1_000_000_000):
        preset = broken(valid_preset(), **{"rules.gridDefaults.unitDistance": outside})
        failures = presets.validate_preset(preset)
        assert any("between 0.000001 and 1000000" in failure
                   for failure in failures), (outside, failures)


def test_bad_condition_shapes_are_refused():
    """The acceptance criterion names bad condition shapes explicitly."""
    cases = [
        broken(valid_preset(), **{"rules.conditions[0].color": "#fff"}),
        broken(valid_preset(), **{"rules.conditions[0].id": ""}),
        broken(valid_preset(), **{"rules.conditions[0].name": 7}),
        broken(valid_preset(), **{"rules.conditions[0].icon": "halo"}),
        broken(valid_preset(), **{"rules.conditions[0].effect": "jinxed"}),
    ]
    for case in cases:
        failures = presets.validate_preset(case)
        assert failures, case
        assert any("conditions[0]" in failure for failure in failures)


def test_bad_widget_shapes_are_refused():
    cases = [
        ({"id": "w", "label": "W", "value": 0, "type": "stopwatch"}, "usable counter"),
        ({"id": "w", "label": "W", "value": 0, "type": "timer", "duration": 0},
         "usable counter"),
        ({"id": "w", "label": "W", "value": 0, "type": "clock", "segments": 13},
         "usable counter"),
        ({"id": "w", "label": "W", "value": 5, "type": "clock", "segments": 4},
         "usable counter"),
        ({"id": "w", "label": "W", "value": "high", "type": "counter"}, "usable counter"),
    ]
    for widget, fragment in cases:
        preset = broken(valid_preset(), **{"rules.widgets": [widget]})
        failures = presets.validate_preset(preset)
        assert any(fragment in failure for failure in failures), widget


def test_repaired_values_are_refused_not_repaired_silently():
    """Atlas clamps/resets these; the installer refuses so the pack is fixed first."""
    flagged = [
        (broken(valid_preset(), **{"rules.gridDefaults.diagonalRule": "pythagorean"}),
         "diagonalRule"),
        (broken(valid_preset(),
                **{"rules.widgets": [{"id": "w", "label": "W", "value": 0,
                                      "type": "timer", "duration": 60,
                                      "icon": "pocket-watch"}]}),
         "icon"),
        (broken(valid_preset(), **{"rules.dice": {"defaultRoll": "d1", "crit": "natural"}}),
         "rules.dice is not usable"),
        (broken(valid_preset(), **{"rules.dice": {"defaultRoll": "1d20", "crit": "superb"}}),
         "rules.dice is not usable"),
        (broken(valid_preset(), **{"rules.dice": {"defaultRoll": "1d20", "crit": "natural",
                                                  "explode": {"dice": "sometimes"}}}),
         "explode"),
        (broken(valid_preset(), **{"rules.initiative": {"mode": "initiative-of-the-void",
                                                        "roll": "1d20",
                                                        "firstSide": "players"}}),
         "rules.initiative is not usable"),
        (broken(valid_preset(), **{"rules.resources": [
            {"key": "hearts", "name": "Hearts", "field": "hp", "direction": "drains",
             "color": "#e11d48"}] * 2 }),
         "repeats an earlier resource"),
        (broken(valid_preset(), **{"rules.resources": [{"key": "h", "name": "H",
                                                        "field": "hp",
                                                        "direction": "drains",
                                                        "color": "red"}]}),
         "silently drop it"),
        (broken(valid_preset(), **{"rules.lightPresets": [
            {"id": "l", "name": "L", "dim": 0}]}),
         "without reach"),
        (broken(valid_preset(), **{"rules.lightPresets": [
            {"id": "l", "name": "L", "dim": 30, "bright": 60}]}),
         "clamp it to dim"),
        (broken(valid_preset(), **{"rules.lightPresets": [
            {"id": "l", "name": "L", "dim": 30, "bright": "far"}]}),
         "silently reset it to 0"),
        (broken(valid_preset(), **{"rules.lightPresets": [
            {"id": "l", "name": "L", "dim": 30, "bright": -5}]}),
         "silently clamp it to 0"),
        (broken(valid_preset(), **{"rules.senses": [
            {"id": "s", "name": "S", "grants": "see-everything"}]}),
         "only 'see-invisible' is known"),
        (broken(valid_preset(), **{"rules.lightPresets": [
            {"id": "l", "name": "L", "dim": 30, "color": "warm"}]}),
         "replace it with white"),
        (broken(valid_preset(), **{"rules.lightPresets": [
            {"id": "l", "name": "L", "dim": 30, "sourceRadius": 9}]}),
         "silently clamp it"),
        (broken(valid_preset(), **{"rules.defaultTokenVision": {"angle": 400}}),
         "silently drop it"),
        (broken(valid_preset(), **{"rules.senses": [{"id": "sight", "name": "Sight"}]}),
         "reserved for normal sight"),
        (broken(valid_preset(), **{"rules.defaultWidgets": ["icrpg-alarm"]}),
         "defaultWidgets is not an object"),
    ]
    for preset, fragment in flagged:
        failures = presets.validate_preset(preset)
        assert any(fragment in failure for failure in failures), (preset, failures)


def test_valid_rich_preset_passes_clean():
    """A preset exercising every optional section, all inside Atlas's limits."""
    preset = valid_preset()
    preset["rules"].update({
        "dice": {"defaultRoll": "2d12", "crit": "doubles"},
        "initiative": {"mode": "sides", "roll": "1d20", "firstSide": "opponents"},
        "resources": [{"key": "ammo", "name": "Ammo", "field": "ammo",
                       "direction": "drains", "color": "#b45309", "slot": 2}],
        "widgets": [
            {"id": "w-timer", "label": "T", "type": "timer", "value": 0, "duration": 60},
            {"id": "w-clock", "label": "C", "type": "clock", "value": 3, "segments": 6,
             "showCount": True},
            {"id": "w-count", "label": "N", "type": "counter", "value": 1, "min": 0,
             "max": 10},
        ],
        "defaultWidgets": {"w-timer": True},
        "senses": [{"id": "t-darkvision", "name": "Darkvision", "range": "required",
                    "role": "darkvision", "look": "monochrome"}],
        "defaultTokenVision": {"senses": [{"id": "t-darkvision", "range": 6}]},
        "lightPresets": [{"id": "l-torch", "name": "Torch", "unit": "feet",
                          "bright": 20, "dim": 40, "color": "#FF9A3C",
                          "animation": "torch", "kind": "torch",
                          "sourceRadius": 2, "intensity": 2, "angle": 90}],
    })
    assert presets.validate_preset(preset) == []


def test_default_token_vision_legacy_fields_vs_senses_list():
    """A senses list present replaces the legacy darkvision/tremorsense
    fields even when it is empty — an empty JS array is truthy, so
    visionDefaults.ts skips the old fields and the section is ignored
    unless range/angle survive (Atlas's own test, senseValidation.test.ts
    'lets a list of senses, even an empty one, replace the old fields':
    {darkvision, tremorsense, senses: []} -> undefined;
    {darkvision, range, senses: []} -> {range})."""
    def dtv(defaults):
        preset = valid_preset()
        preset["rules"]["defaultTokenVision"] = defaults
        return presets.validate_preset(preset)

    # the reviewer's round-1 repro: passes only if the port wrongly reads
    # the legacy fields beside an empty list
    assert dtv({"senses": [], "darkvision": 30}) != []
    assert any("darkvision is ignored" in failure
               for failure in dtv({"senses": [], "darkvision": 30}))
    # the residual hole: the section survives on range while the authored
    # legacy number is silently dropped
    assert any("darkvision is ignored" in failure
               for failure in dtv({"senses": [], "darkvision": 30, "range": 30}))
    # without a senses list the legacy fields are read as authored
    assert dtv({"darkvision": 30}) == []
    assert dtv({"range": 30}) == []
    # a list with a usable entry is used; a legacy number beside it is ignored
    assert dtv({"senses": [{"id": "darkvision", "range": 6}]}) == []
    assert any("darkvision is ignored" in failure
               for failure in dtv({"senses": [{"id": "darkvision", "range": 6}],
                                   "darkvision": 30}))
    # a senses value that is no list is ignored, and the legacy fields are read
    garbage = dtv({"senses": "darkvision", "darkvision": 30})
    assert garbage == ["rules.defaultTokenVision.senses is not a list — Atlas would "
                       "silently ignore it (the legacy darkvision/tremorsense fields "
                       "are read instead)"]


def test_builtin_systems_match_the_pinned_release():
    """The short-circuit set is Atlas's own built-in ids at 0.7.1
    (builtInPresetId keys, builtInPresets.ts + presets/*.ts) — the same
    nine preset files as at 0.6.0, re-verified 2026-10-13 against tag
    0.7.1 (commit 942514b) in ticket 08's source diff."""
    assert presets.BUILTIN_SYSTEMS_0_7_1 == frozenset({
        "cairn", "coc7e", "cyberpunkred", "daggerheart", "dnd5e",
        "drawsteel", "ose", "pathfinder2e", "shadowdark",
    })
    assert set(presets.BUILTIN_DISPLAY_NAMES_0_7_1) == set(presets.BUILTIN_SYSTEMS_0_7_1)


def test_shipped_icrpg_pack_validates_clean():
    """The pack payload survives the ported validator — the gate it must
    pass before any install writes it."""
    payload = presets.load_pack_preset("icrpg")
    assert presets.validate_preset(payload) == []


# --- refuse-on-diff + --force sibling (contract rule 3) --------------------


@pytest.fixture
def pack_file(tmp_path):
    path = tmp_path / "preset.json"
    path.write_text(json.dumps(valid_preset()), encoding="utf-8")
    return path


def test_install_writes_atlas_canonical_form(tmp_path, pack_file):
    atlas = tmp_path / "atlas-vtt"
    result = presets.install(pack_file, atlas, stem="testpack")
    assert result == atlas / "system-presets" / "testpack.json"
    text = result.read_text(encoding="utf-8")
    assert text.endswith("\n")
    written = json.loads(text)
    assert list(written)[0] == "format" and written["format"] == 1
    assert {k: v for k, v in written.items() if k != "format"} == valid_preset()


def test_install_is_idempotent(tmp_path, pack_file):
    atlas = tmp_path / "atlas-vtt"
    first = presets.install(pack_file, atlas, stem="testpack")
    before = os.stat(first).st_mtime_ns
    again = presets.install(pack_file, atlas, stem="testpack")
    assert again == first
    assert os.stat(first).st_mtime_ns == before, "the identical file was rewritten"


def test_install_refuses_on_diff(tmp_path, pack_file):
    atlas = tmp_path / "atlas-vtt"
    target = atlas / "system-presets" / "testpack.json"
    target.parent.mkdir(parents=True)
    hand_tuned = valid_preset()
    hand_tuned["name"] = "Hand-tuned"
    target.write_text(json.dumps(hand_tuned), encoding="utf-8")
    original = target.read_text(encoding="utf-8")
    with pytest.raises(presets.PresetRefused, match="exists and differs"):
        presets.install(pack_file, atlas, stem="testpack")
    assert target.read_text(encoding="utf-8") == original, "the target was overwritten"


def test_install_force_writes_v2_sibling(tmp_path, pack_file):
    atlas = tmp_path / "atlas-vtt"
    target = atlas / "system-presets" / "testpack.json"
    target.parent.mkdir(parents=True)
    hand_tuned = valid_preset()
    hand_tuned["name"] = "Hand-tuned"
    target.write_text(json.dumps(hand_tuned), encoding="utf-8")
    result = presets.install(pack_file, atlas, stem="testpack", force=True)
    assert result == atlas / "system-presets" / "testpack-v2.json"
    assert json.loads(result.read_text(encoding="utf-8"))["name"] == "Test Pack"
    assert json.loads(target.read_text(encoding="utf-8"))["name"] == "Hand-tuned", \
        "the original was overwritten"


def test_install_force_twice_refuses_instead_of_clobbering(tmp_path, pack_file):
    atlas = tmp_path / "atlas-vtt"
    presets_dir = atlas / "system-presets"
    presets_dir.mkdir(parents=True)
    target = presets_dir / "testpack.json"
    target.write_text(json.dumps({"id": "other", "name": "Other", "rules": {}}),
                      encoding="utf-8")
    sibling = presets_dir / "testpack-v2.json"
    sibling.write_text(json.dumps({"id": "another", "name": "Another", "rules": {}}),
                       encoding="utf-8")
    with pytest.raises(presets.PresetRefused, match="resolve by hand"):
        presets.install(pack_file, atlas, stem="testpack", force=True)
    assert json.loads(target.read_text(encoding="utf-8"))["id"] == "other"
    assert json.loads(sibling.read_text(encoding="utf-8"))["id"] == "another"


def test_install_refuses_a_broken_preset_before_writing(tmp_path, pack_file):
    preset = valid_preset()
    preset["id"] = "builtin:not-ours"
    pack_file.write_text(json.dumps(preset), encoding="utf-8")
    atlas = tmp_path / "atlas-vtt"
    with pytest.raises(presets.PresetRefused, match="builtin:"):
        presets.install(pack_file, atlas, stem="testpack")
    assert not (atlas / "system-presets").exists(), \
        "the refusal still created the target folder"


def test_install_refuses_an_unreadable_target(tmp_path, pack_file):
    atlas = tmp_path / "atlas-vtt"
    target = atlas / "system-presets" / "testpack.json"
    target.parent.mkdir(parents=True)
    target.write_text("{not json", encoding="utf-8")
    with pytest.raises(presets.PresetRefused, match="exists and differs"):
        presets.install(pack_file, atlas, stem="testpack")


# --- the gate + the CLI (README §5.2) --------------------------------------


def test_gate_refuses_a_campaign_that_did_not_ask(tmp_path, capsys):
    (tmp_path / "campaign.yaml").write_text("name: test\n", encoding="utf-8")
    rc = publish.main([str(tmp_path), "presets"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "set `system: icrpg` in `campaign.yaml`" in out
    assert not (tmp_path / "atlas-vtt").exists()


def test_gate_refuses_non_matching_system(tmp_path, capsys):
    (tmp_path / "campaign.yaml").write_text("system: dnd5e\n", encoding="utf-8")
    rc = publish.main([str(tmp_path), "presets"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "found 'dnd5e'" in out
    assert not (tmp_path / "atlas-vtt").exists()


def test_gate_reads_a_yaml_int_as_no_system(tmp_path, capsys):
    """`system: 5` is an int to YAML — the pinned read contract returns None."""
    (tmp_path / "campaign.yaml").write_text("system: 5\n", encoding="utf-8")
    rc = publish.main([str(tmp_path), "presets"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "no system declared" in out


def test_gate_normalizes_mixed_case(tmp_path, capsys):
    """`system: ICRPG` matches the pack — the spine.campaign_system line."""
    (tmp_path / "campaign.yaml").write_text("system: ICRPG\n", encoding="utf-8")
    rc = publish.main([str(tmp_path), "presets"])
    out = capsys.readouterr().out
    assert rc == 0
    target = tmp_path / "atlas-vtt" / "system-presets" / "icrpg.json"
    assert target.is_file()
    assert "wrote" in out


def test_corrupt_campaign_yaml_is_refused_not_defaulted(tmp_path, capsys):
    (tmp_path / "campaign.yaml").write_text("{unclosed: [", encoding="utf-8")
    rc = publish.main([str(tmp_path), "presets"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "does not read" in out


def test_builtin_short_circuit_writes_nothing(tmp_path, capsys):
    """The pinned release ships Shadowdark; the installer advises and
    stops — before the pack is even loaded (no packs/shadowdark/ exists)."""
    (tmp_path / "campaign.yaml").write_text("system: shadowdark\n", encoding="utf-8")
    rc = publish.main([str(tmp_path), "presets", "--pack", "shadowdark"])
    out = capsys.readouterr().out
    assert rc == 0
    assert f"{_version.ATLAS_PIN} has Shadowdark built in — consider using it" in out
    assert not (tmp_path / "atlas-vtt").exists()


def test_dry_run_prints_plan_and_writes_nothing(tmp_path, capsys):
    (tmp_path / "campaign.yaml").write_text("system: icrpg\n", encoding="utf-8")
    rc = publish.main([str(tmp_path), "presets", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "would write" in out
    assert not (tmp_path / "atlas-vtt").exists(), "the dry run wrote the target folder"


def test_dry_run_reports_the_first_divergence(tmp_path, capsys):
    (tmp_path / "campaign.yaml").write_text("system: icrpg\n", encoding="utf-8")
    target = tmp_path / "atlas-vtt" / "system-presets" / "icrpg.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"id": "icrpg-house", "name": "hand-tuned"}', encoding="utf-8")
    rc = publish.main([str(tmp_path), "presets", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "would REFUSE" in out
    assert target.read_text(encoding="utf-8") == '{"id": "icrpg-house", "name": "hand-tuned"}'


def test_dry_run_force_points_at_the_sibling(tmp_path, capsys):
    (tmp_path / "campaign.yaml").write_text("system: icrpg\n", encoding="utf-8")
    target = tmp_path / "atlas-vtt" / "system-presets" / "icrpg.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"id": "icrpg-house", "name": "hand-tuned"}', encoding="utf-8")
    rc = publish.main([str(tmp_path), "presets", "--force", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "icrpg-v2.json" in out
    assert not (tmp_path / "atlas-vtt" / "system-presets" / "icrpg-v2.json").exists()


def test_end_to_end_install_is_idempotent(tmp_path, capsys):
    (tmp_path / "campaign.yaml").write_text("system: icrpg\n", encoding="utf-8")
    assert publish.main([str(tmp_path), "presets"]) == 0
    target = tmp_path / "atlas-vtt" / "system-presets" / "icrpg.json"
    assert json.loads(target.read_text(encoding="utf-8"))["id"] == "icrpg-house"
    rc = publish.main([str(tmp_path), "presets"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "already matches the pack — nothing written" in out


def test_missing_campaign_directory_is_refused(tmp_path, capsys):
    rc = publish.main([str(tmp_path / "nope"), "presets"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "no campaign directory" in out


def test_unknown_pack_is_refused(tmp_path, capsys):
    (tmp_path / "campaign.yaml").write_text("system: nosuch\n", encoding="utf-8")
    rc = publish.main([str(tmp_path), "presets", "--pack", "nosuch"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "no pack 'nosuch'" in out


def test_invalid_pack_is_refused_before_validation(tmp_path, capsys):
    """A broken pack never reaches a disk write (no atlas-vtt/ at all)."""
    (tmp_path / "campaign.yaml").write_text("system: icrpg\n", encoding="utf-8")
    real = presets.pack_preset_path
    presets.pack_preset_path = lambda pack: tmp_path / "bad-pack.json"
    try:
        (tmp_path / "bad-pack.json").write_text(json.dumps({"id": "builtin:x"}))
        rc = publish.main([str(tmp_path), "presets"])
    finally:
        presets.pack_preset_path = real
    out = capsys.readouterr().out
    assert rc == 2
    assert "would not survive Atlas's own loader" in out
    assert not (tmp_path / "atlas-vtt").exists()
