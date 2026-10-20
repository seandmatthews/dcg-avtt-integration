"""The version constants and the Atlas detection (ticket 07).

``VERSION`` is this repo's companion version — the thing a consumer
pins. It mirrors ``pyproject.toml``'s ``[project] version`` (the
pin-integrity test keeps the two in step) and every release is
git-tagged ``v<VERSION>``; consumers pin tags, never main (README §8).

``ATLAS_PIN`` is the machine handle for the pinned Atlas release whose
human record is the README §7 table. The fixture directory
``fixtures/golden-{ATLAS_PIN}/`` is the pin's source of truth;
``tests/test_pin.py`` holds constant and fixture together. This module
is the one place the pin lives: docstrings and messages elsewhere cite
it instead of restating a version (the demotion rule of ticket 07), so
a pin bump moves the constant, the golden fixture, the README table
row and ``VERSION`` in one commit.

Detection reads the vault's *Obsidian plugin config*, never
``atlas-vtt/`` state: contract rule 1 allows reading the campaign
directory and rule 2 keeps table state out of reach, and a plugin
manifest is neither — it is which Atlas the vault has installed.
"""

from __future__ import annotations

import json
from pathlib import Path

VERSION = "0.3.0"  # mirrors pyproject.toml [project] version — keep in step
ATLAS_PIN = "0.8.0"  # the pinned-release table, README §7

PLUGIN_ID = "atlas-vtt"
MANIFEST_RELPATH = Path(".obsidian") / "plugins" / PLUGIN_ID / "manifest.json"


def detect_atlas_version(campaign: Path) -> str:
    """The Atlas version installed in the vault at ``campaign``, or
    ``"unknown"``.

    Reads ``<campaign>/.obsidian/plugins/atlas-vtt/manifest.json`` and
    returns its ``version`` (the plugin manifest shape: ``id``,
    ``name``, ``version``, ``minAppVersion``, ...). Missing, unreadable,
    unparseable, not a JSON object, or without a non-blank ``version``
    string → ``"unknown"``. Detection never raises and never writes.

    Only the manifest on disk is read: the plugin being *disabled* in
    Obsidian is not detected, deliberately — the manifest states which
    Atlas wrote this vault's file formats, and that is what the pin is
    about.
    """
    manifest = Path(campaign) / MANIFEST_RELPATH
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        return "unknown"
    if not isinstance(payload, dict):
        return "unknown"
    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        return "unknown"
    return version
