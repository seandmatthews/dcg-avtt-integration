"""The prep-time CLI. No server, no watcher, no runtime at the table.

Spec: README §5. The publishers, in build order:

    publish.py <campaign> presets [--pack icrpg]      (P0, ticket 04 — built)
    publish.py <campaign> scenes [--site <slug>]
                              [--force] [--dry-run]   (P2, ticket 05)

``--dry-run`` prints the exact file plan and the first divergence from
what exists; its exit code mirrors the plan (0 = would succeed,
2 = would refuse). Every write obeys contract rule 3 (stable stems,
refuse-on-diff) and the degrade path (rule: golden test fails -> drop
the ``.uvtt`` in ``atlas-vtt/_inbox/`` with printed instructions
instead of writing ``.atlasmap`` files).

The DM runs the commands (contract rule 4); nothing here runs on its own.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __name__ == "__main__":
    # Run by hand from anywhere: the package lives at src/avtt and the
    # project is never pip-installed (pyproject.toml), so a hand-run needs
    # src/ on the path before the import below.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from avtt import presets  # noqa: E402

_NOT_BUILT = ("publish.py: the '{command}' publisher is not built yet — "
              "this repo is spec-first until the spikes in README §12 land. "
              "See docs/tickets/ for the build queue.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="publish.py",
        description="Publish campaign prep into Atlas VTT's file formats.")
    parser.add_argument("campaign", type=Path,
                        help="path to the campaign directory")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scenes = sub.add_parser("scenes", help="convert + publish site scenes (P2)")
    p_scenes.add_argument("--site", metavar="slug",
                          help="publish one site instead of all")
    p_scenes.add_argument("--force", action="store_true",
                          help="write a <slug>-v2 sibling on divergence "
                               "instead of refusing")
    p_scenes.add_argument("--dry-run", action="store_true",
                          help="print the file plan and the first divergence")

    p_presets = sub.add_parser("presets", help="install a system-preset pack (P0)")
    p_presets.add_argument("--pack", default="icrpg",
                           help="pack name under packs/ (default: icrpg)")
    p_presets.add_argument("--force", action="store_true",
                           help="write a <pack>-v2 sibling on divergence "
                                "instead of refusing")
    p_presets.add_argument("--dry-run", action="store_true",
                           help="print the file plan and the first divergence")
    return parser


def campaign_system(campaign: Path) -> str | None:
    """The campaign's ``system:`` — the pinned read contract (README §5.2,
    core ticket 48): ``str(value).strip().lower()`` for a string; None for
    missing, empty, or a non-string scalar (YAML parses ``system: 5`` as an
    int). Contract rule 4 forbids importing the core's
    ``spine.campaign_system``, so this line IS the shared definition;
    neither side may drift.

    Raises ValueError when campaign.yaml exists but does not parse —
    fed-or-refused, never defaulted silently.
    """
    yaml_path = campaign / "campaign.yaml"
    if not yaml_path.is_file():
        return None
    try:
        doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"{yaml_path} does not read: {exc}") from exc
    value = doc.get("system") if isinstance(doc, dict) else None
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().lower()


def run_presets(campaign: Path, pack: str, force: bool, dry_run: bool) -> int:
    """The ``presets`` publisher: gate, short-circuit, validate, install.

    Order is load-bearing: the campaign must ask for the pack
    (``campaign.yaml`` ``system:``) before anything else happens; a system
    Atlas already ships ends in advice, not a file; only a validated pack
    reaches the refuse-on-diff write (README §3.4/§5.2).
    """
    if not campaign.is_dir():
        print(f"refusing: no campaign directory at {campaign}")
        return 2
    try:
        system = campaign_system(campaign)
    except ValueError as exc:
        print(f"refusing: {exc}")
        return 2
    if system != pack:
        found = f"found {system!r}" if system else "no system declared"
        print(f"refusing: set `system: {pack}` in `campaign.yaml` ({found}) — "
              "never writing a pack into a campaign that did not ask for it")
        return 2

    display = presets.BUILTIN_DISPLAY_NAMES_0_6_0.get(pack)
    if display is not None:
        print(f"0.6.0 has {display} built in — consider using it")
        print("wrote nothing")
        return 0

    try:
        payload = presets.load_pack_preset(pack)
    except presets.PresetRefused as exc:
        print(f"refusing: {exc}")
        return 2
    failures = presets.validate_preset(payload)
    if failures:
        print(f"refusing: packs/{pack}/preset.json would not survive Atlas's own "
              "loader (an invalid preset is silently ignored there):")
        for failure in failures:
            print(f"  - {failure}")
        return 2

    atlas_dir = campaign / "atlas-vtt"
    state = presets.target_state(atlas_dir, pack, payload)
    if dry_run:
        return _dry_run_plan(atlas_dir, pack, payload, force)
    try:
        result = presets.install(presets.pack_preset_path(pack), atlas_dir,
                                 stem=pack, force=force)
    except presets.PresetRefused as exc:
        print(f"refusing: {exc}")
        return 2
    if state == "same":
        print(f"{result} already matches the pack — nothing written")
    else:
        print(f"wrote {result}")
    return 0


def _dry_run_plan(atlas_dir: Path, pack: str, payload: dict, force: bool) -> int:
    """Print the exact file plan and the first divergence; write nothing."""
    target = atlas_dir / presets.SYSTEM_PRESETS_DIRNAME / f"{pack}.json"
    print(f"dry run — file plan for pack '{pack}':")
    print(f"  plan: {target}")
    state = presets.target_state(atlas_dir, pack, payload)
    if state == "missing":
        print("  would write it (the system-presets folder is created if missing)")
        return 0
    if state == "same":
        print("  already matches the pack — would write nothing")
        return 0
    if not force:
        print(f"  would REFUSE: it exists and differs (contract rule 3) — rerun with "
              f"--force to write a '{pack}-v2' sibling beside it")
        return 2
    sibling = atlas_dir / presets.SYSTEM_PRESETS_DIRNAME / f"{pack}-v2.json"
    sibling_state = presets.target_state(atlas_dir, f"{pack}-v2", payload)
    if sibling_state == "missing":
        print(f"  {target.name} differs — would write {sibling.name} instead, "
              "leaving the original untouched")
        return 0
    if sibling_state == "same":
        print(f"  {sibling.name} already matches the pack — would write nothing")
        return 0
    print(f"  would REFUSE: {sibling.name} exists and differs too — resolve by hand")
    return 2


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "presets":
        return run_presets(args.campaign, args.pack, args.force, args.dry_run)
    print(_NOT_BUILT.format(command=args.command))
    return 2


if __name__ == "__main__":
    sys.exit(main())
