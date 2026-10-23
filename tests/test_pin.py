"""The Atlas version pin: declared, detected, never silent (ticket 07).

The fixture set is the pin's source of truth and ``_version.ATLAS_PIN``
is its machine handle; detection reads the vault's Obsidian plugin
manifest; the mismatch policy is presets-warn-and-proceed (unknown
counts as mismatch) — scenes take the ``_inbox/`` degrade path when
ticket 05 builds them. ``publish.py version`` prints all three values
for the core's table-setup card (core ticket 53).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from avtt import _version, publish

ROOT = Path(__file__).resolve().parents[1]


# --- helpers ----------------------------------------------------------------


def plant_manifest(campaign: Path, version: str) -> Path:
    """Write a plugin manifest in the real shape (the ember-coast vault's,
    per ticket 07's ground truth) at ``campaign``."""
    path = campaign / _version.MANIFEST_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "id": "atlas-vtt",
        "name": "Atlas VTT",
        "version": version,
        "minAppVersion": "1.8.7",
    }), encoding="utf-8")
    return path


def icrpg_campaign(tmp_path: Path) -> Path:
    (tmp_path / "campaign.yaml").write_text("system: icrpg\n", encoding="utf-8")
    return tmp_path


# --- pin integrity: the constant and the fixture set are one pin -------------


def test_atlas_pin_matches_fixtures():
    """The fixture set is the pin's source of truth; the constant is its
    machine handle (ticket 07, proposal 2): the *capture*
    ``golden-{ATLAS_PIN}/sample.atlasmap`` must exist — a README-only
    directory is the documented intermediate shape of a bump, not a pin
    (ticket 12)."""
    golden = ROOT / "fixtures" / f"golden-{_version.ATLAS_PIN}" / "sample.atlasmap"
    assert golden.is_file(), (
        f"ATLAS_PIN={_version.ATLAS_PIN!r} has no captured "
        f"fixtures/golden-{_version.ATLAS_PIN}/sample.atlasmap — a pin "
        "without its golden capture is not a pin; capture it with "
        f"`tools/capture-golden.py {_version.ATLAS_PIN}` "
        "(automated, fixtures/README.md) and commit the fixture in the "
        "same change as the pin")


def test_readme_table_carries_the_pin():
    """The README §7 pinned-release table is the human record; its pinned
    column must agree with the constant (the README is the constitution)."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"| {_version.ATLAS_PIN} |" in text


def test_version_mirrors_pyproject():
    """``VERSION`` mirrors pyproject.toml's ``[project] version`` — two
    spellings of one number (ticket 07, proposal 1), held together here."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version = "([^"]+)"', text)
    assert match, "pyproject.toml lost its [project] version line"
    assert _version.VERSION == match.group(1)


# --- detection (proposal 3) --------------------------------------------------


def test_detect_atlas_version(tmp_path):
    """Present / absent / corrupt manifest, per the acceptance criterion."""
    present = tmp_path / "present"
    plant_manifest(present, "0.7.1")
    assert _version.detect_atlas_version(present) == "0.7.1"

    absent = tmp_path / "absent"  # no .obsidian at all
    assert _version.detect_atlas_version(absent) == "unknown"
    half = tmp_path / "half"  # Obsidian config, but the plugin folder missing
    (half / ".obsidian" / "plugins").mkdir(parents=True)
    assert _version.detect_atlas_version(half) == "unknown"

    corrupt = tmp_path / "corrupt"
    path = corrupt / _version.MANIFEST_RELPATH
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert _version.detect_atlas_version(corrupt) == "unknown"


def test_manifest_without_a_usable_version_is_unknown(tmp_path):
    """A manifest that parses but carries no usable ``version`` string is
    as good as absent."""
    cases = [
        '["atlas-vtt"]',                      # JSON, but not an object
        '{"id": "atlas-vtt"}',                # no version key
        '{"id": "atlas-vtt", "version": ""}',
        '{"id": "atlas-vtt", "version": "   "}',
        '{"id": "atlas-vtt", "version": 7}',  # not a string
    ]
    for i, text in enumerate(cases):
        campaign = tmp_path / f"case{i}"
        path = campaign / _version.MANIFEST_RELPATH
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding="utf-8")
        assert _version.detect_atlas_version(campaign) == "unknown", text


# --- the mismatch policy (proposal 4): presets warn and proceed --------------


def test_preset_mismatch_warns_not_refuses(tmp_path, capsys):
    """installed ≠ pin → the loud machine-readable line, the install still
    happens, exit code 0. (The manifest carries 9.9.9 — a version that is
    not the pin at any pin; it read 0.7.1 while the pin was 0.6.0.)"""
    campaign = icrpg_campaign(tmp_path)
    plant_manifest(campaign, "9.9.9")
    rc = publish.main([str(campaign), "presets"])
    out = capsys.readouterr().out
    assert rc == 0
    assert f"atlas-pin-mismatch: pin={_version.ATLAS_PIN} detected=9.9.9" in out
    target = campaign / "atlas-vtt" / "system-presets" / "icrpg.json"
    assert target.is_file(), "the mismatch warned the install off — it must not"
    assert json.loads(target.read_text(encoding="utf-8"))["id"] == "icrpg-house"


def test_unknown_detection_warns_as_mismatch_and_still_writes(tmp_path, capsys):
    """unknown → treated as mismatch: the line says ``detected=unknown``
    and the install still proceeds."""
    campaign = icrpg_campaign(tmp_path)  # no .obsidian anywhere
    rc = publish.main([str(campaign), "presets"])
    out = capsys.readouterr().out
    assert rc == 0
    assert f"atlas-pin-mismatch: pin={_version.ATLAS_PIN} detected=unknown" in out
    assert (campaign / "atlas-vtt" / "system-presets" / "icrpg.json").is_file()


def test_pin_match_is_quiet(tmp_path, capsys):
    """detected == pin → no mismatch line at all (the warning must fire on
    skew, not always)."""
    campaign = icrpg_campaign(tmp_path)
    plant_manifest(campaign, _version.ATLAS_PIN)
    rc = publish.main([str(campaign), "presets"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "atlas-pin-mismatch" not in out
    assert (campaign / "atlas-vtt" / "system-presets" / "icrpg.json").is_file()


# --- the version report (proposal 5) -----------------------------------------


def test_version_report(tmp_path, capsys):
    """``publish.py version`` prints all three values, machine-readable —
    the line the core's table-setup card (core ticket 53) renders."""
    campaign = tmp_path / "vault"
    plant_manifest(campaign, "0.7.1")
    rc = publish.main([str(campaign), "version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert f"avtt-version: {_version.VERSION}" in out
    assert f"atlas-pin: {_version.ATLAS_PIN}" in out
    assert "atlas-detected: 0.7.1" in out


def test_version_report_never_refuses(tmp_path, capsys):
    """A missing campaign reports ``unknown`` instead of failing — the
    table-setup card calls this before anything else exists."""
    rc = publish.main([str(tmp_path / "nope"), "version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert f"avtt-version: {_version.VERSION}" in out
    assert f"atlas-pin: {_version.ATLAS_PIN}" in out
    assert "atlas-detected: unknown" in out
