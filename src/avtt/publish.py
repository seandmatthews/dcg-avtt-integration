"""The prep-time CLI. No server, no watcher, no runtime at the table.

Spec: README §5. Two publishers, in build order:

    publish.py <campaign> presets [--pack icrpg]      (P0, ticket 04)
    publish.py <campaign> scenes [--site <slug>]
                              [--force] [--dry-run]   (P2, ticket 05)

``--dry-run`` prints the exact file plan and the first divergence from
what exists. Every write obeys contract rule 3 (stable stems,
refuse-on-diff) and the degrade path (rule: golden test fails -> drop
the ``.uvtt`` in ``atlas-vtt/_inbox/`` with printed instructions
instead of writing ``.atlasmap`` files).

The DM runs the commands (contract rule 4); nothing here runs on its own.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="publish.py",
        description="Publish campaign prep into Atlas VTT's file formats "
                    "(spec-first skeleton — publishers not built yet).")
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
    p_presets.add_argument("--force", action="store_true")
    p_presets.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(f"publish.py: the '{args.command}' publisher is not built yet — "
          "this repo is spec-first until the spikes in README §12 land. "
          "See docs/tickets/ for the build queue.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
