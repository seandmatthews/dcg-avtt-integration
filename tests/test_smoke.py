"""The skeleton's own smoke test: the public surface exists and is honest.

Every module imports, every documented entry point is present, and the
CLI admits it is not built instead of pretending. When a stub grows real
code, its pin moves out of here into the discipline tests (README §7).
"""

from __future__ import annotations

import pytest

from avtt import (_version, config, image_headers, presets, publish,
                  records, scene, uvtt)

MODULES = (uvtt, image_headers, scene, records, presets, config, publish,
           _version)


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__)
def test_module_imports(module):
    assert module.__doc__, f"{module.__name__} lost its spec docstring"


@pytest.mark.parametrize("entry", [
    (uvtt, "parse"), (uvtt, "UvttRefused"), (uvtt, "UvttDocument"),
    (image_headers, "pixel_dimensions"),
    (scene, "convert"), (scene, "dumps"),
    (records, "map_record"), (records, "scene_record"),
    (presets, "validate_preset"), (presets, "install"),
    (presets, "load_pack_preset"), (presets, "BUILTIN_SYSTEMS_0_9_1"),
    (config, "AvttConfig"), (config, "load"),
    (_version, "VERSION"), (_version, "ATLAS_PIN"),
    (_version, "detect_atlas_version"),
])
def test_public_surface_exists(entry):
    module, name = entry
    assert hasattr(module, name), f"{module.__name__}.{name} missing"


def test_cli_admits_party_not_built(capsys):
    """The unbuilt publishers refuse loudly (rc 2), pointing at the queue.
    (The presets pin moved to tests/test_presets.py when ticket 04 built
    it; the scenes pin moved to tests/test_scenes.py at ticket 05. What
    is still spec-first — party, ticket 06 — keeps the pin here.)"""
    rc = publish.main(["some-campaign", "party"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "not built yet" in out
    assert "docs/tickets" in out


def test_cli_parses_publisher_flags():
    """The flag surface of README §5 exists even before the publishers do."""
    args = publish.build_parser().parse_args(
        ["camp", "scenes", "--site", "ruravaqan-keep", "--force", "--dry-run"])
    assert (args.command, args.site, args.force, args.dry_run) == (
        "scenes", "ruravaqan-keep", True, True)
    args = publish.build_parser().parse_args(["camp", "presets", "--pack", "icrpg"])
    assert (args.command, args.pack) == ("presets", "icrpg")
