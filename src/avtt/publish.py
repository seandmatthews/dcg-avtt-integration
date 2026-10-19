"""The prep-time CLI. No server, no watcher, no runtime at the table.

Spec: README §5. The publishers, in build order:

    publish.py <campaign> presets [--pack icrpg]      (P0, ticket 04 — built)
    publish.py <campaign> scenes [--site <slug>]
                              [--force] [--dry-run]   (P2, ticket 05 — built)
    publish.py <campaign> version                     (ticket 07 — the pin report)

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
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

if __name__ == "__main__":
    # Run by hand from anywhere: the package lives at src/avtt and the
    # project is never pip-installed (pyproject.toml), so a hand-run needs
    # src/ on the path before the import below.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from avtt import _version, config, image_headers, presets, records, scene, uvtt  # noqa: E402

_NOT_BUILT = ("publish.py: the '{command}' publisher is not built yet — "
              "see docs/tickets/ for the build queue (party is parked, "
              "README §5.3, until a fresh spike says otherwise).")


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

    sub.add_parser("party", help="character + token records (P4 — parked, "
                                 "ticket 06; refuses until built)")
    sub.add_parser("version", help="print companion VERSION, ATLAS_PIN, and "
                                   "the vault's detected Atlas version "
                                   "(ticket 07)")
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
    yaml_path = Path(campaign) / "campaign.yaml"
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


def _warn_pin_mismatch(campaign: Path) -> None:
    """The pin check (ticket 07): report, never refuse.

    Prints the loud machine-readable line when the vault's installed
    Atlas differs from ``_version.ATLAS_PIN`` (unknown counts as
    mismatch) and proceeds — a preset is a watched plain file the DM
    can see and re-edit, so refusing a file copy would trade a visible
    risk for a dead button. Scenes (ticket 05) take the ``_inbox/``
    degrade path on the same condition instead: scene content is where
    schema drift actually bites.
    """
    detected = _version.detect_atlas_version(campaign)
    if detected == _version.ATLAS_PIN:
        return
    print(f"atlas-pin-mismatch: pin={_version.ATLAS_PIN} detected={detected}")
    if detected == "unknown":
        print(f"warning: no readable Atlas plugin manifest "
              f"({_version.MANIFEST_RELPATH.as_posix()}) — treating the pin "
              "as unmatched")
    else:
        print(f"warning: this vault runs Atlas {detected}, the pack targets "
              f"{_version.ATLAS_PIN} — installing anyway (a preset is a plain, "
              "watched file the DM can see and re-edit)")


# --- the scenes publisher (P2, ticket 05) ------------------------------------

_INBOX_DIRNAME = "_inbox"
_ATLASMAP_SUFFIX = ".atlasmap"


@dataclass(frozen=True)
class _Site:
    """One site the maps engine emitted: ``maps/sites/<slug>/{png,uvtt,md}``."""

    slug: str
    directory: Path

    @property
    def image_path(self) -> Path:
        return self.directory / f"{self.slug}.png"

    @property
    def uvtt_path(self) -> Path:
        return self.directory / f"{self.slug}.uvtt"

    @property
    def note_path(self) -> Path:
        return self.directory / f"{self.slug}.md"


@dataclass(frozen=True)
class _SitePlan:
    """What one site publishes: the conversion plus the target set of
    README §5.1, all under one stem (contract rule 3 — the site's slug,
    or ``<slug>-v2`` after ``--force``)."""

    site: _Site
    stem: str
    conversion: dict
    atlasmap_bytes_for: Callable[[str], bytes]
    records_for: Callable[[str], dict]
    note_line_for: Callable[[str], str]


def _discover_sites(sites_dir: Path, only: str | None) -> list[_Site]:
    if not sites_dir.is_dir():
        raise ValueError(f"no {sites_dir} — nothing to publish")
    if only is not None:
        directory = sites_dir / only
        if not directory.is_dir():
            raise ValueError(f"no site '{only}' — expected {directory}")
        return [_Site(only, directory)]
    sites = []
    for entry in sorted(sites_dir.iterdir()):
        if entry.is_dir() and config.COLLECTION_SLUG.match(entry.name):
            sites.append(_Site(entry.name, entry))
    return sites


def _site_files(site: _Site) -> tuple[Path, Path, Path]:
    """The three files the core's maps engine emits per site, or a refusal —
    fed-or-refused: an incomplete site is reported, not guessed around."""
    missing = [path.name for path in (site.image_path, site.uvtt_path, site.note_path)
               if not path.is_file()]
    if missing:
        raise ValueError(f"site '{site.slug}' is incomplete — the generator emits "
                         f"{site.slug}.png, {site.slug}.uvtt and {site.slug}.md "
                         f"together; missing: {', '.join(missing)}")
    return site.image_path, site.uvtt_path, site.note_path


def _convert_site(site: _Site, cfg: config.AvttConfig | None) -> dict:
    """Parse, validate and convert one site's ``.uvtt``.

    Returns the conversion — everything the write stage needs that does
    not depend on the stem. Raises UvttRefused or SceneRefused with the
    importer's plain-words reason; nothing is written on refusal.
    """
    document = uvtt.parse(site.uvtt_path)
    size = image_headers.dimensions_of_bytes(document.image_bytes)
    if size is None:
        raise scene.SceneRefused("The map image in the file could not be read.")
    unit_scale = cfg.grid.unit_scale if cfg is not None and cfg.grid else config.DEFAULT_UNIT_DISTANCE
    farthest = scene.max_light_range(unit_scale, scene.checked_cell_size(document.size, *size))
    conversion = scene.convert(document, size, unit_scale, farthest)
    scene.check_placement(conversion)
    return conversion


def _build_plan(site: _Site, cfg: config.AvttConfig, stem: str,
                conversion: dict) -> _SitePlan:
    """The write plan for one site under ``stem`` (README §5.1): the image
    copy, the map record, the converted ``.atlasmap``, the scene record —
    image before map record and ``.atlasmap`` before scene record, since
    adoption skips a record whose stated file is missing."""

    def atlasmap_bytes(target_stem: str) -> bytes:
        background = (f"atlas-vtt/collections/{cfg.collection_id}"
                      f"/maps/{target_stem}.png")
        return scene.dumps(scene.scene_file(
            conversion, background,
            grid_defaults=cfg.grid, default_widgets=cfg.default_widgets))

    def records_for(target_stem: str) -> dict:
        map_path = f"atlas-vtt/collections/{cfg.collection_id}/maps/{target_stem}.png"
        scene_path = (f"atlas-vtt/collections/{cfg.collection_id}"
                      f"/scenes/{target_stem}{_ATLASMAP_SUFFIX}")
        return {
            "map": records.map_record(target_stem, map_path),
            "scene": records.scene_record(target_stem, scene_path),
        }

    def note_line(target_stem: str) -> str:
        return f"![[{target_stem}{_ATLASMAP_SUFFIX}]]"

    return _SitePlan(site=site, stem=stem, conversion=conversion,
                     atlasmap_bytes_for=atlasmap_bytes, records_for=records_for,
                     note_line_for=note_line)


def _file_state(path: Path, payload: bytes) -> str:
    """``'missing' | 'same' | 'differs'`` for a byte-written target."""
    if not path.exists():
        return "missing"
    try:
        return "same" if path.read_bytes() == payload else "differs"
    except OSError:
        return "differs"


def _atlasmap_state(path: Path, payload: bytes) -> str:
    """State of the ``.atlasmap`` target. Compared as parsed JSON, never
    bytes: the file is hand-tuneable (contract rule 3's moved door,
    tweaked light), and a reformat that means the same thing is not ours
    to overwrite either."""
    if not path.exists():
        return "missing"
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "differs"
    intended = json.loads(payload.decode("utf-8"))
    return "same" if existing == intended else "differs"


def _record_state(path: Path, intended: dict) -> str:
    """State of a record target; the comparison (``records.matches``) accepts
    Atlas's rewritten canonical form as ours unchanged in meaning."""
    if not path.exists():
        return "missing"
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "differs"
    return "same" if records.matches(existing, intended) else "differs"


def _note_has_line(site: _Site, stem: str) -> bool:
    """Whether the companion note already carries a link to this scene's
    ``.atlasmap`` — any link shape (plain, embed, alias, subpath)."""
    try:
        text = site.note_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return f"[[{stem}{_ATLASMAP_SUFFIX}" in text


def _plan_states(plan: _SitePlan, cfg: config.AvttConfig) -> list[tuple[str, Path, str, object]]:
    """The target set with each target's state, in write order."""
    collections = cfg.atlas_dir / "collections" / cfg.collection_id
    png = collections / "maps" / f"{plan.stem}.png"
    atlasmap = collections / "scenes" / f"{plan.stem}{_ATLASMAP_SUFFIX}"
    map_json = collections / "maps" / f"{plan.stem}.json"
    scene_json = collections / "scenes" / f"{plan.stem}.json"
    image_bytes = plan.site.image_path.read_bytes()
    atlasmap_bytes = plan.atlasmap_bytes_for(plan.stem)
    recs = plan.records_for(plan.stem)
    note_state = "same" if _note_has_line(plan.site, plan.stem) else "missing"
    return [
        ("image copy", png, _file_state(png, image_bytes), image_bytes),
        ("scene file", atlasmap, _atlasmap_state(atlasmap, atlasmap_bytes), atlasmap_bytes),
        ("map record", map_json, _record_state(map_json, recs["map"]), recs["map"]),
        ("scene record", scene_json, _record_state(scene_json, recs["scene"]), recs["scene"]),
        ("companion-note link", plan.site.note_path, note_state, plan.note_line_for(plan.stem)),
    ]


def _write_plan(plan: _SitePlan, cfg: config.AvttConfig,
                targets: list[tuple[str, Path, str, object]]) -> None:
    """Write every not-yet-matching target, in the plan's order.

    The companion note is the one licensed exception to "writes only
    inside ``atlas-vtt/``" (contract rule 1) and it is append-only:
    existing note text is kept byte for byte, the embed line is added at
    the end when it is not already there.
    """
    for label, path, state, payload in targets:
        if state == "same":
            continue
        if label == "companion-note link":
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            if text and not text.endswith("\n"):
                text += "\n"
            path.write_text(text + str(payload) + "\n", encoding="utf-8")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, bytes):
            path.write_bytes(payload)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _print_counts(conversion: dict) -> str:
    counts = conversion["counts"]
    line = ", ".join([_plural(counts["walls"], "wall"), _plural(counts["doors"], "door"),
                      _plural(counts["lights"], "light")])
    skipped = conversion["skipped"]
    if any(skipped.values()):
        # "outside" is invariable; "unlit"/"window" pluralize like the nouns they are
        line += (f"; left out: {skipped['outside']} outside, "
                 f"{_plural(skipped['unlit'], 'unlit')}, "
                 f"{_plural(skipped['windows'], 'window')}")
    return line


def _publish_site(plan: _SitePlan, cfg: config.AvttConfig, force: bool,
                  dry_run: bool) -> int:
    """Publish (or plan) one site. Returns 0 when the site would end up
    published, 2 when it would refuse."""
    slug = plan.site.slug
    targets = _plan_states(plan, cfg)

    if all(state == "same" for _l, _p, state, _x in targets):
        if dry_run:
            _print_plan(plan, cfg, targets)
            print("  already matches — would write nothing")
            return 0
        print(f"{slug}: already matches — nothing written")
        return 0

    differs = [(label, path) for label, path, state, _x in targets if state == "differs"]
    if differs and not force:
        first_label, first_path = differs[0]
        if dry_run:
            _print_plan(plan, cfg, targets)
            print(f"  would REFUSE: the {first_label} {first_path} exists and differs "
                  f"(contract rule 3) — rerun with --force to write a "
                  f"'{slug}-v2' sibling")
            return 2
        print(f"refusing {slug}: the {first_label} {first_path} exists and differs "
              f"(contract rule 3) — rerun with --force to write a '{slug}-v2' sibling")
        return 2

    stem = plan.stem
    if differs:  # force: the whole site set republishes as <slug>-v2
        stem = f"{slug}-v2"
        v2_plan = _build_plan(plan.site, cfg, stem, plan.conversion)
        targets = _plan_states(v2_plan, cfg)
        if all(state == "same" for _l, _p, state, _x in targets):
            if dry_run:
                _print_plan(v2_plan, cfg, targets)
                print("  already matches — would write nothing")
                return 0
            print(f"{slug}: {stem} already matches — nothing written")
            return 0
        still_differs = [(label, path) for label, path, state, _x in targets
                         if state == "differs"]
        if still_differs:
            label, path = still_differs[0]
            message = (f"would REFUSE: {stem} exists and differs too — resolve by hand"
                       if dry_run else
                       f"refusing {slug}: {stem} exists and differs too — resolve by hand")
            print(message)
            return 2
        plan = v2_plan

    if dry_run:
        _print_plan(plan, cfg, targets)
        print(f"  would write the set as '{plan.stem}'"
              + (" (the original stays untouched)" if plan.stem != slug else ""))
        return 0

    _write_plan(plan, cfg, targets)
    scene_path = (cfg.atlas_dir / "collections" / cfg.collection_id
                  / "scenes" / f"{plan.stem}{_ATLASMAP_SUFFIX}")
    print(f"{slug}: published {plan.stem} → {scene_path}")
    print(f"  {_print_counts(plan.conversion)}")
    return 0


def _print_plan(plan: _SitePlan, cfg: config.AvttConfig,
                targets: list[tuple[str, Path, str, object]]) -> None:
    print(f"dry run — file plan for site '{plan.site.slug}' (stem '{plan.stem}'):")
    for label, path, state, _payload in targets:
        detail = {"missing": "would write it", "same": "already matches",
                  "differs": "exists and differs"}[state]
        print(f"  plan: {path}  ({label}; {detail})")


def _run_scenes_degraded(campaign: Path, sites: list[_Site], dry_run: bool,
                         detected: str) -> int:
    """The degrade path (README §5.1): the vault does not run the pinned
    Atlas, so no ``.atlasmap`` is written — the ``.uvtt`` drops into
    ``atlas-vtt/_inbox/`` for a hand drag-in. The interchange format
    always works; the adapter is what needs the test. Rule 3 still
    holds in the inbox: an existing copy refuses on diff."""
    print(f"atlas-pin-mismatch: pin={_version.ATLAS_PIN} detected={detected}")
    print("scenes: this vault does not run the pinned Atlas — writing no "
          ".atlasmap files (scene content is where schema drift bites)")
    inbox = campaign / "atlas-vtt" / _INBOX_DIRNAME
    status = 0
    for site in sites:
        try:
            _site_files(site)
            uvtt.parse(site.uvtt_path)  # a file beyond Atlas's limits cannot be dragged in either
        except (ValueError, uvtt.UvttRefused) as exc:
            print(f"refusing {site.slug}: {exc}")
            status = 2
            continue
        target = inbox / f"{site.slug}.uvtt"
        state = _file_state(target, site.uvtt_path.read_bytes())
        if state == "differs":
            print(f"refusing {site.slug}: {target} exists and differs (contract "
                  "rule 3) — resolve by hand; nothing was written")
            status = 2
            continue
        if state == "same":
            print(f"{site.slug}: already in the inbox — nothing written")
            continue
        if dry_run:
            print(f"  plan: {target}  (inbox copy; would write it)")
            continue
        inbox.mkdir(parents=True, exist_ok=True)
        target.write_bytes(site.uvtt_path.read_bytes())
        print(f"{site.slug}: copied {site.uvtt_path} → {target}")
        print("  drag it into Atlas by hand; walls, doors and lights come along")
    if not dry_run and status == 0:
        print(f"inbox: {inbox} — drag the files into Atlas; walls, doors and "
              "lights come along")
    return status


def run_scenes(campaign: Path, site: str | None, force: bool, dry_run: bool) -> int:
    """The ``scenes`` publisher: validate, convert, publish per README §5.1.

    Order is load-bearing: the pin check comes first — a vault that does
    not run the pinned Atlas takes the ``_inbox/`` degrade path (ticket
    07: scene content is where schema drift bites), and the degrade path
    needs no config, only the sites. On the pinned vault the config is
    fed-or-refused before anything else; every site is fully converted
    before any of its files is written, so a refusal writes nothing.
    """
    campaign = Path(campaign)
    if not campaign.is_dir():
        print(f"refusing: no campaign directory at {campaign}")
        return 2

    detected = _version.detect_atlas_version(campaign)
    degrading = detected != _version.ATLAS_PIN
    try:
        sites = _discover_sites(campaign / "maps" / "sites", site)
    except ValueError as exc:
        print(f"refusing: {exc}")
        return 2
    if not sites:
        print(f"refusing: no sites under {campaign / 'maps' / 'sites'} — nothing to publish")
        return 2

    if degrading:
        return _run_scenes_degraded(campaign, sites, dry_run, detected)

    try:
        cfg = config.load(campaign)
    except config.ConfigRefused as exc:
        print(f"refusing: {exc}")
        return 2

    status = 0
    for site in sites:
        try:
            _site_files(site)
            conversion = _convert_site(site, cfg)
        except (ValueError, uvtt.UvttRefused, scene.SceneRefused) as exc:
            print(f"refusing {site.slug}: {exc}")
            status = 2
            continue
        plan = _build_plan(site, cfg, site.slug, conversion)
        if _publish_site(plan, cfg, force, dry_run) != 0:
            status = 2
    return status


# --- the presets publisher (P0, ticket 04) -----------------------------------

def run_presets(campaign: Path, pack: str, force: bool, dry_run: bool) -> int:
    """The ``presets`` publisher: gate, short-circuit, validate, install.

    Order is load-bearing: the campaign must ask for the pack
    (``campaign.yaml`` ``system:``) before anything else happens; a system
    Atlas already ships ends in advice, not a file; only a validated pack
    reaches the refuse-on-diff write (README §3.4/§5.2). The pin check
    (ticket 07) runs once the campaign is known to exist and never
    refuses — it only makes the version skew visible.
    """
    if not Path(campaign).is_dir():
        print(f"refusing: no campaign directory at {campaign}")
        return 2
    _warn_pin_mismatch(campaign)
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

    display = presets.BUILTIN_DISPLAY_NAMES_0_7_1.get(pack)
    if display is not None:
        print(f"{_version.ATLAS_PIN} has {display} built in — consider using it")
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

    atlas_dir = Path(campaign) / "atlas-vtt"
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


def run_version(campaign: Path) -> int:
    """The ``version`` report (ticket 07): the companion version, the
    Atlas pin, and the Atlas version detected in the vault — one
    machine-readable block per value, the line the core's table-setup
    card (core ticket 53) renders. Never refuses: a missing or
    unreadable vault just reports ``unknown``.
    """
    print(f"avtt-version: {_version.VERSION}")
    print(f"atlas-pin: {_version.ATLAS_PIN}")
    print(f"atlas-detected: {_version.detect_atlas_version(campaign)}")
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
    if args.command == "scenes":
        return run_scenes(args.campaign, args.site, args.force, args.dry_run)
    if args.command == "presets":
        return run_presets(args.campaign, args.pack, args.force, args.dry_run)
    if args.command == "version":
        return run_version(args.campaign)
    print(_NOT_BUILT.format(command=args.command))
    return 2

if __name__ == "__main__":
    sys.exit(main())
