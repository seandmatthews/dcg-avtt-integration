# 08 — Atlas pin bump 0.6.0 → 0.7.1 (the first §8 churn)

**Status:** completed (implemented + signed off 2026-10-18; this flip and
the `archive/` move are folded into the branch's single `feat(08)` commit)
**Priority:** P1 — the machine this repo serves runs Atlas 0.7.1 against the
0.6.0 pin (ticket 07's ground truth), so every real `scenes` run there takes
the `_inbox/` degrade path until the pin moves; and the validator port now
accepts presets the pinned release refuses
**Area:** `src/avtt/_version.py` (ATLAS_PIN, VERSION), `src/avtt/presets.py`
(unitDistance bounds, builtin-constant rename), `tests/test_presets.py`,
`fixtures/golden-0.6.0/`, `fixtures/golden-0.7.1/`, `fixtures/README.md`,
`README.md` (status line, §3 stamp, §7 table), `pyproject.toml` (VERSION);
`tools/capture-golden.py` + both goldens already landed 2026-10-18 (Proposal 1)
**Found by:** the owner's pin-bump idea; grounded for this ticket in a
0.6.0→0.7.1 re-clone diff re-verified 2026-10-13 (the commands and their
outputs are recorded in Problem — re-runnable as written)

## Problem

**The pin lags the only Atlas installed where this repo is used.** Ticket 07
recorded the ember-coast vault's plugin manifest reading `"version": "0.7.1"`
(ground truth, 2026-10-12) while `ATLAS_PIN = "0.6.0"`
(`src/avtt/_version.py:29`). Under the §7 mismatch policy that means `scenes`
refuses to write `.atlasmap` files there and drops every `.uvtt` into
`atlas-vtt/_inbox/` — the adapter path is dead on the home machine until the
pin moves. README §8 prescribes exactly this ritual for it.

**The pinned source moved in a way the port must follow.** Verified
2026-10-13: the reference clone at `$TEMP/atlas-vtt` (`git describe --tags`
→ `0.6.0`, commit `c5a99830` — matches the README §7 row) had the `0.7.1`
tag fetched (`git log -1 0.7.1` → commit `942514b`, commit date
2026-10-10 14:41 +0200, matching `changelog/0.7.1.md`'s `date: 2026-10-10`
front matter), and `git diff 0.6.0 0.7.1` was read. Findings:

- **The one port-worthy delta — `unitDistance` bounds in the preset
  validator.**
  - 0.6.0, `src/app/gameSystems/presetValidation.ts:58`:
    `if (typeof unitDistance !== 'number' || !(unitDistance > 0)) return null;`
  - 0.7.1, same file line 59:
    `if (!isUnitDistance(unitDistance)) return null;` (import added at
    line 9: `import { isUnitDistance } from '../grid/unitDistance';`)
  - `isUnitDistance` (0.7.1 `src/app/grid/unitDistance.ts:14`):
    `typeof value === 'number' && value >= MIN_UNIT_DISTANCE && value <= MAX_UNIT_DISTANCE`
    with `MIN_UNIT_DISTANCE = 0.000001` (the source comment: below a
    millionth JavaScript writes the number as a power of ten — `"1e-7"` —
    which no field reads back) and `MAX_UNIT_DISTANCE = 1_000_000`. The
    bounds are **inclusive**. Still fatal: `parseGridDefaults` returns null
    and Atlas ignores the whole preset file.
  - Our port still implements the 0.6.0 rule — `src/avtt/presets.py:222-224`
    accepts any finite number above 0. A preset with
    `unitDistance: 2000000000` or `0.0000001` passes our installer and is
    silently ignored by Atlas 0.7.1 — the exact worst failure mode README
    §3.4 names.
- **Everything else port-relevant is unchanged** (each checked in the same
  diff):
  - UVTT import semantics: the whole `src/app/import/uvtt/` diff is 4 files,
    +5−3 — guard imports moved (`assetMetadataGuards` → `utils/guards`), the
    `GridState` type import re-pointed (see below), and one UI-side
    `prebuildMapImageAt` call added in `importUvttFile.ts` (image prebuild
    after import, not conversion). `uvttToScene.ts`'s conversion logic is
    untouched.
  - Scene schema constants: `ATLAS_SCHEMA = 'atlas-vtt'`,
    `ATLAS_VERSION = 4` at both tags (0.6.0 `MapPersistence.ts:64-65`;
    0.7.1 `MapPersistence.ts:27-28`).
  - GridState: 0.6.0's interface (in `MapPersistence.ts`) already carried
    `unitDistanceOverride`, `cellNumbers`, `cellNumberOpacity`, `autoDetect`;
    0.7.1's version (the interface moved to the new
    `src/app/types/gridTypes.ts`) adds exactly `mapStretch?: MapStretch` —
    optional, and absent from the uvtt import path
    (`git grep mapStretch 0.7.1 -- src/app/import/uvtt/` → no hits), so a
    captured golden should not carry it.
  - Validator satellites: `lightPresetValidation.ts`, `senseValidation.ts`,
    `measurementFormat.ts` — import moves only; `visionDefaults.ts` — a
    type-level decoupling (a local `VisionDefaultsSource` interface replaces
    the `AssetService` type; no behavior change); `visionCone.ts` — a
    geometry-indexing performance refactor (`outlineAt` moved to a new
    `outlineIndex.ts`, precomputed bearing arrays); the cone-angle logic the
    port mirrors (the file's lines 8–68) is untouched.
    `diceRules.ts`, `initiativeRules.ts`, `resources/resourceDefinitions.ts`
    do not appear in the diff at all.
  - Built-in systems: the same nine preset files at both tags
    (`src/app/gameSystems/presets/`: cairn, callOfCthulhu, cyberpunkRed,
    daggerheart, dnd5e, drawSteel, oldSchoolEssentials, pathfinder2e,
    shadowdark) — `BUILTIN_SYSTEMS_0_6_0` re-verified against 0.7.1.
- **None of this is announced:** `git grep -in 'unitdistance' 0.7.1 -- changelog/`
  finds nothing. §8 step 1 ("read the changelog") alone would have cleared
  0.7.1 as safe; only the source diff catches the validator tightening —
  the reason §8 mandates the re-clone.
- **0.7.1 is the right target:** `git ls-remote --tags origin` shows `0.7.1`
  as the highest stable tag and `0.7.2-beta.0` as a prerelease — not a bump
  candidate (the pin names stable releases).

**The both-goldens gate cannot run today.** `fixtures/golden-0.6.0/` holds
only the README placeholder (fixtures/README.md's table row is unfilled) and
no `golden-0.7.1/` exists, so `tests/test_scenes.py::test_golden_file` and
the whole integration tier skip (`run-tests.py:60-66` prints its skip note
until a `golden-*/sample.atlasmap` exists). Ticket 05's acceptance list was
signed off with exactly this criterion left open: the human capture.
**Update 2026-10-18:** both goldens now exist — captured by
`tools/capture-golden.py` (Proposal 1 below) and green against the port at
both pins (`run-tests.py --all` with the pin still 0.6.0, then
`tests/test_scenes.py::test_golden_file` with the pin flipped to 0.7.1).
The gate runs; what remains is the code work of Proposals 2–6.

## Proposal

1. **The golden capture — DONE 2026-10-18, no human step needed.** The
   original plan reserved this for a human at the Atlas UI; it proved
   automatable end to end, so it was done before implementation started.
   `tools/capture-golden.py` (committed alongside the goldens) builds a
   throwaway vault per version, installs the plugin from the version's
   GitHub release assets, drives an isolated Obsidian instance over CDP
   (own `--user-data-dir`; the owner's running Obsidian is untouched), and
   synthesizes the asset-manager drop — the real import code path — with
   `WorkspaceLeaf.openFile` suppressed so the file stays the pure import
   output (`newSceneFile`'s envelope) rather than the auto-open's runtime
   rewrite; a postcondition refuses any capture carrying non-import state
   keys (the first attempt caught exactly that poisoning). Both goldens are
   committed and green against the port at both pins (Problem, update).
   fixtures/README.md records the method and one capture finding the source
   diff had missed: 0.7.1 keeps the imported image's source format
   (background `.png`) where 0.6.0 re-encoded it as `.webp` — the
   structural check treats the background path as a capture-specific
   string, so it does not bite the port.
   - The "0.6.0 can no longer be installed" ruling is moot: the 0.6.0
     release assets install fine and both goldens are captured.
2. **Port the bounds** in `src/avtt/presets.py::_validate_grid_defaults`:
   replace the `> 0` check with the inclusive range — a module-level
   `MIN_UNIT_DISTANCE = 0.000001` / `MAX_UNIT_DISTANCE = 1_000_000` mirroring
   Atlas's `grid/unitDistance.ts` constants (comment cites the source file;
   AGENTS.md: cite, never vendor), keeping the existing `_number` finiteness
   gate. Keep the *fatal* wording — 0.7.1 still refuses the whole preset
   over this — but name the range:
   `"...unitDistance {value!r} is not a number between 0.000001 and 1000000 — Atlas refuses the whole preset"`.
   The existing test case (`unitDistance: 0`,
   `tests/test_presets.py:89-90`) matches on the `unitDistance` fragment and
   keeps passing.
   - Scope note, grounded: only the *preset* validator tightens. At 0.7.1
     the *scene* grid's `unitDistance` is not routed through
     `isUnitDistance` (no hits in `MapPersistence.ts` or `uvttToScene.ts` —
     the import path reads it only for the cells→units arithmetic), so
     `config.py`'s `> 0` rule for `avtt.yaml` `grid.unit_distance`
     (`src/avtt/config.py:153-156`) stays faithful to Atlas and is not
     touched.
3. **Rename `BUILTIN_SYSTEMS_0_6_0` / `BUILTIN_DISPLAY_NAMES_0_6_0` →
   `..._0_7_1`** in the same change, refreshing their "re-verified" comments
   to 0.7.1 / commit `942514b`. Ticket 07's implementation notes kept the
   0.6.0 names "until the pin moves" — this is that move. Update
   `tests/test_presets.py::test_builtin_systems_match_the_pinned_release`
   (names and docstring) to match; the set itself is unchanged (verified —
   Problem).
4. **Run the both-goldens gate in this order, before merging:**
   a. With `ATLAS_PIN` still `"0.6.0"` and `golden-0.6.0/` committed:
      `python run-tests.py --all` — `test_golden_file` reads
      `golden-{ATLAS_PIN}`, i.e. the 0.6.0 golden (§8 step 3, first half).
   b. Flip `ATLAS_PIN = "0.7.1"` (`src/avtt/_version.py`) and bump `VERSION`
      (propose **0.2.0** — the repo's first release carrying a behavior
      change: the validator now refuses presets 0.6.0's accepted; mirrors
      `pyproject.toml`, held together by
      `tests/test_pin.py::test_version_mirrors_pyproject`; final number
      confirmed at merge). Commit the constant, `fixtures/golden-0.7.1/`,
      the README §7 row and the VERSION bump as the one §8-step-5 change,
      git-tagged `v<VERSION>`. Run `python run-tests.py --all` again —
      `test_golden_file` now reads the 0.7.1 golden.
   - **Contingency (§8 step 4):** if the 0.7.1 golden surprises us — the
     structural comparison is strict on key sets
     (`tests/test_scenes.py:374`), and the golden is the source of truth
     above any docstring — do not hack the port to pass: keep the pin,
     ship the `_inbox/` degrade path, and open the fix as its own ticket.
     The source diff says this should not happen (mapStretch is not written
     by the import path), but only the capture decides.
5. **README moves with the code** (the constitution rule, AGENTS.md): the
   §7 table gains a `| 0.7.1 | <pin date> | <notes> |` row (0.6.0's row
   stays as history); the header's two current-state claims —
   "Everything below was verified against Atlas VTT v0.6.0 source on
   2026-10-09" and "**Tested against: Atlas VTT 0.6.0** (released
   2026-10-05)" — move to 0.7.1 (released 2026-10-10: tag date + changelog
   front matter); §3's "(source-read 2026-10-09, v0.6.0)" stamp gains this
   ticket's 0.7.1 re-read. Historical provenance lines elsewhere stay
   (ticket 07's ruling). fixtures/README.md's table fills in step 1.
6. **Live check** (ticket 07's discipline): `publish.py version` against the
   real ember-coast vault (read-only) must print
   `atlas-pin: 0.7.1` / `atlas-detected: 0.7.1` and no mismatch line; then a
   full `scenes` run on a temp copy of that vault must write `.atlasmap`
   files (not `_inbox/`) — the adapter path is back on the home machine.
   The temp copy is deleted after the check.

## Acceptance criteria

- [x] The validator refuses `unitDistance` outside [0.000001, 1000000] and
      accepts the boundaries — pinned by `tests/test_presets.py`: new cases
      in `test_fatal_breaks_are_refused_whole` (e.g. `0.0000001` and
      `1_000_000_000`, refused with the range named) plus a boundary test
      that exactly `0.000001` and exactly `1_000_000` yield no failures.
- [x] Golden captures committed and green both ways:
      `fixtures/golden-0.6.0/sample.atlasmap` green with the pin still 0.6.0,
      `fixtures/golden-0.7.1/sample.atlasmap` green after the flip —
      `tests/test_scenes.py::test_golden_file` (integration tier, via
      `python run-tests.py --all`); ticket 05's open criterion closes with
      it.
- [x] Pin, fixture and README moved in one change:
      `tests/test_pin.py::test_atlas_pin_matches_fixtures` and
      `::test_readme_table_carries_the_pin` green at `ATLAS_PIN = "0.7.1"`;
      `::test_version_mirrors_pyproject` green at the bumped VERSION; the
      change git-tagged `v<VERSION>` (checkable with `git tag`).
- [x] Builtin constants renamed `_0_7_1` with refreshed provenance —
      `tests/test_presets.py::test_builtin_systems_match_the_pinned_release`
      updated and green; the constants' comments must cite 0.7.1 / commit
      `942514b` (checkable by reading).
- [x] The shipped ICRPG pack still validates clean —
      `tests/test_presets.py::test_shipped_icrpg_pack_validates_clean`
      (its `unitDistance: 5`, `packs/icrpg/preset.json:6`, is inside the
      bounds; no pack change).
- [x] Gates green on the branch: `python run-tests.py` and
      `python run-tests.py --all` (the integration tier runs once a golden
      exists — `run-tests.py:60-66`).
- [x] README moved with the code (checkable by reading): §7 table has the
      0.7.1 row and keeps 0.6.0's; the header's "Tested against" names 0.7.1
      (released 2026-10-10); §3 carries the 0.7.1 source-read stamp;
      fixtures/README.md's table has both rows.
- [x] Live check recorded here: real ember-coast vault reports pin 0.7.1 /
      detected 0.7.1 with no mismatch line via `publish.py version`; a
      scenes run on a temp copy writes `.atlasmap` and no `_inbox/`; the
      temp copy deleted after. (The adapter-path proof ran with one
      fixture-built site added to the copy — the vault's only real site is
      Atlas-refused on content; see Implementation notes, 2026-10-18.)
- [x] Any §8 deviation (the single-golden fallback of Proposal 1) is
      recorded in Implementation notes with the reason — never silent.
      (No fallback happened: both goldens ran green at their pins. The
      live-check site substitution is recorded in Implementation notes.)

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._

### 2026-10-18

Landed as the branch's single `feat(08)` commit on
`feature/08-atlas-pin-bump-0-7-1` (the status flip and these notes folded
in). The `v0.2.0` tag sits on it; §8 step 5's constant + §7 row + VERSION
move together here — the `golden-0.7.1/` bytes themselves landed with
Proposal 1 (caf7ab8) by design, before implementation started.

Gates, run in the ticket's order:

- Pin still `0.6.0` (§8 step 3, first half): `ruff check src tests
  run-tests.py` clean; `python run-tests.py --all` green — fast tier
  143 passed, 1 skipped; integration tier `test_golden_file` passed
  against `golden-0.6.0/` (the 1 skip is the optional `sample-lit`
  golden, fixtures/README.md — not a §8 fallback).
- After the flip (`ATLAS_PIN = "0.7.1"`, `VERSION = "0.2.0"`): ruff
  clean; `python run-tests.py --all` green — fast tier 146 passed,
  1 skipped; integration tier `test_golden_file` passed against
  `golden-0.7.1/` (no contingency: the source diff held, mapStretch is
  not in the capture). Plain `python run-tests.py` (fast tier) also run:
  green.

The code moves, all in the one commit per §8 step 5:

- `presets.py`: module-level `MIN_UNIT_DISTANCE = 0.000001` /
  `MAX_UNIT_DISTANCE = 1_000_000` citing `grid/unitDistance.ts`
  (AGENTS.md: cited, never vendored); `_validate_grid_defaults` enforces
  the inclusive range and the refusal names it ("not a number between
  0.000001 and 1000000 — Atlas refuses the whole preset"). The
  `config.py` `> 0` rule for `avtt.yaml` `grid.unit_distance` is
  untouched (scope note — the scene path never routes through
  `isUnitDistance` at 0.7.1).
- `BUILTIN_SYSTEMS_0_6_0` / `BUILTIN_DISPLAY_NAMES_0_6_0` renamed
  `..._0_7_1` (usages: `publish.py`, `test_smoke.py`,
  `test_presets.py`); comments re-verified 2026-10-13 against tag 0.7.1,
  commit `942514b` — and re-checked first-hand today against the
  reference clone (`$TEMP/atlas-vtt`: `git log -1 0.7.1` → `942514b`,
  2026-10-10 14:41 +0200; `presetValidation.ts` routes gridDefaults
  through `isUnitDistance`; `unitDistance.ts` MIN/MAX inclusive; the
  same nine `presets/*.ts` files at both tags; `git grep mapStretch
  0.7.1 -- src/app/import/uvtt/` → no hits; `ATLAS_SCHEMA`/`ATLAS_VERSION`
  at `services/MapPersistence.ts:27-28`).
- `tests/test_presets.py`: two new fatal cases (`0.0000001`,
  `1_000_000_000`) matched on the range text, plus
  `test_unit_distance_bounds_are_inclusive` (exactly the boundaries pass;
  one step outside on either side is refused with the range named);
  `test_builtin_short_circuit_writes_nothing` now interpolates
  `_version.ATLAS_PIN` — the short-circuit message was already dynamic
  (ticket 07), the test literal was not.
- Four fixtures planted `manifest="0.7.1"` to mean "a version that is
  not the pin"; at the new pin that reads as a match. They now plant
  `"9.9.9"` (the convention `test_degrade_path_to_inbox` already used),
  so they keep testing mismatch/degrade behavior; no assertion was
  weakened. Note `test_degrade_refuses_an_invalid_uvtt_without_copying`
  had been passing *by accident* after the flip (its refusal fired on
  the pinned path instead) — re-pointed to the degrade path it names.
- README: header claims moved to v0.7.1 (source-read 2026-10-13, first
  read 2026-10-09; tested against 0.7.1, released 2026-10-10); §3
  heading carries both stamps; §7 table gains the 0.7.1 row (0.6.0
  stays); the repo-map line that still said "empty until the human
  capture" now lists both captured goldens. fixtures/README.md's table
  was already filled by Proposal 1.

Live check (2026-10-18, ticket 07's discipline):

- `publish.py version` on the real ember-coast vault (read-only):
  `avtt-version: 0.2.0` / `atlas-pin: 0.7.1` / `atlas-detected: 0.7.1`,
  rc 0, no mismatch line. The adapter path's pin gate is open on the
  home machine.
- Scenes on a temp copy — with a recorded deviation. The vault's only
  real site (`maps/sites/the-drowned-crypt`) is refused by the ported
  importer on content: "The map image is too small for its grid:
  2940 × 1960 pixels for 2940 × 1960 squares". Verified faithful, not a
  port bug: the export declares `map_size` 2940 × 1960 *squares* at
  `pixels_per_grid: 70` while the image is 2940 × 1960 *pixels* (42 × 28
  squares) — and Atlas 0.7.1 itself refuses the same file
  (`importUvttFile.ts:58`, `cellSize < UVTT_LIMITS.cellPixels`; cellSize
  here is 2940/2940 = 1). That is a `dnd-mapping` export finding, out of
  this repo's scope — route it to the mapping engine's owner. To prove
  the adapter path end-to-end anyway, the temp copy (real
  `manifest.json` bytes verbatim, real `campaign.yaml`, real
  `atlas-vtt/`) carried one extra site built from the repo's own
  `fixtures/sample.uvtt` (`demo.png`/`demo.uvtt`/`demo.md`) and a
  hand-authored `avtt.yaml` (`collection: ember-coast` — the config the
  real vault does not have yet; the same feed-the-copy precedent as
  ticket 07's `system: icrpg`). `scenes --site demo` → rc 0: wrote
  `atlas-vtt/collections/ember-coast/scenes/demo.atlasmap` +
  `maps/demo.json` + `maps/demo.png`, appended `![[demo.atlasmap]]` to
  the site note, created no `_inbox/` anywhere in the copy (find: no
  matches), and touched nothing else (`library.json`,
  `collections/Default/`, `system-presets/` are the vault's own bytes).
  The full run (all sites) on the same copy refuses the real site with
  rc 2 and writes nothing for it — fed-or-refused on real data. The
  temp copy was deleted after the check (verified gone).

Signed off 2026-10-18 (reviewer accepted; nothing left for a human —
every criterion above is pinned by a run recorded in these notes). The
status flip and this `archive/` move are folded into the branch's single
`feat(08)` commit (CONVENTIONS.md), and the `v0.2.0` tag is re-pointed at
the amended commit so it stays on the change it names.
