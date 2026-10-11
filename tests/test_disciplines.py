"""The five testing disciplines of README §7, pinned as names before code.

Each test is skip-marked until the build that makes it runnable; the
skip reason names the ticket carrying that build. When a discipline
lands, its test body moves to a real module test file and the skip goes.

Discipline 1 (golden file) additionally needs a fixture only a human can
capture — import ``fixtures/sample.uvtt`` in the Atlas UI at the pinned
version and commit the result under ``fixtures/golden-<version>/``
(README §7, fixtures/README.md).
"""

from __future__ import annotations

import pytest

GOLDEN = pytest.mark.skip(reason="lands with ticket 05 (scenes) + a human-captured golden fixture")


@GOLDEN
def test_golden_file():
    """§7.1: port output matches the captured .atlasmap structurally —
    keys, types, id scheme, math within float tolerance."""


@GOLDEN
def test_round_trip_determinism():
    """§7.2: same .uvtt twice -> byte-identical .atlasmap."""


@GOLDEN
def test_refusals_write_nothing():
    """§7.3: every Atlas limit produces its plain-words reason and the
    atlas-vtt/ tree is untouched."""


@GOLDEN
def test_degrade_path_to_inbox():
    """§7.4: simulated golden mismatch -> the .uvtt lands in
    atlas-vtt/_inbox/ with instructions, nothing else written."""


@GOLDEN
def test_preset_validation_port():
    """§7.5: deliberately-broken presets are refused by the installer
    before Atlas ever sees them."""
