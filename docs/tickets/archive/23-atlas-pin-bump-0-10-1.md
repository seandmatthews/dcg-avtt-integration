# 23 — Atlas pin bump 0.9.1 → 0.10.1 (the fourth §8 churn)

**Status:** completed (implemented and verified 2026-10-26, single §8-step-5
commit, tagged `v0.5.0`; run directly rather than through the
implementer workflow — recorded as a deviation, none of §8's order
relaxed)
**Priority:** P1 — two stables shipped the same day the pin was checked
(0.10.0 and 0.10.1, both 2026-10-26, the fastest cadence yet; a
`0.10.2-beta.0` prerelease is also out). 0.10.0's headline is map
layers — the scene surface — so it counted as breaking until the
golden said otherwise (§8 step 1).
**Area:** `src/avtt/_version.py` (ATLAS_PIN, VERSION), `src/avtt/presets.py`
(difficultTerrain, light animations, builtin-constant rename),
`src/avtt/publish.py` (constant name), `tests/test_presets.py`,
`tests/test_smoke.py`, `fixtures/golden-0.10.1/`, `fixtures/README.md`,
`README.md` (status line, §3 stamps, §3.3, §3.6, §7 table, §8 cadence),
`pyproject.toml` (VERSION)
**Found by:** the weekly-cadence drift check, 2026-10-26. Grounded
against a fresh clone diff 0.9.1→0.10.1 recorded in Problem.

## Problem

**The pin lags two stables.** `ATLAS_PIN = "0.9.1"`. Upstream releases
(GitHub /releases, pre-releases included — checked, not just /latest):

| release | date | kind |
|---|---|---|
| 0.10.0 | 2026-10-26 | stable — dungeon generator, map layers, random encounters |
| 0.10.1-beta.0 | 2026-10-26 | prerelease |
| 0.10.1 | 2026-10-26 | stable, current latest — "fix for black maps on Windows" |
| 0.10.2-beta.0 | 2026-10-26 | prerelease |

Two stables in one day — the record so far was one every 2–6 days.
**The 0.9.1→0.10.1 clone diff (2026-10-26, tag `0.10.1` = commit
`af9ccc974024089788a26ab69eb3f224c0462631`), surface by surface:**

- **The import surface grew a second path — the map-layers feature.**
  `importUvttFloors.ts`, `runUvttFloorsImport.ts`, `runUvttGroupImport.ts`,
  `uvttFloors.ts`, `uvttFloorNames.ts`, `uvttSource.ts` are new: several
  `.uvtt` files imported together become the floors of one multi-level
  scene. `uvttToScene.ts` (the ported conversion) changes only for that
  path: a new optional `UvttTarget` gains `at` (cell offset of a floor,
  default `{0,0}`) and `level` (tags ids `wall_${'uvtt_<floor#>'}_<n>`,
  `chain_…`, `light_…` and stamps each placed wall/light with the level
  id). With both unset — every single-file import — the math, ids and
  keys are unchanged. `uvttTypes.ts` adds group-only limits (`floors:
  32` files, `floorsBytes: 400 MB` together); the single-file limits are
  untouched. `MapPersistence.ts`: `ATLAS_VERSION` stays 4; a scene of
  several levels is written at the new `LEVELS_FILE_VERSION = 5`
  (`levels/levelFile.ts`, `SINGLE_LEVEL_FILE_VERSION = 4`); `parseSceneFile`
  now refuses files newer than 5; new optional `MapFile` fields
  (`levels`, `objects.levelLinks/levelSurfaces/mapFeatures/liquids`,
  all "absent until a map has some") and an in-memory `audios` kind that
  the file writer still omits when empty. `importUvttFile.ts` is
  restructured around `importUvttSource` (the single-file path
  preserved); `runUvttImport.ts`'s user-visible diff is i18n'd notices.
- **The whole `services/vault-sync/` tree (adoption) is untouched** —
  0 diff lines.
- **The one port-worthy delta — two validator widenings.**
  `presetValidation.ts`'s `parseGridDefaults` now reads
  `gridDefaults.difficultTerrain`, valid values `'double'`/`'none'`
  (new `DIFFICULT_TERRAIN_RULES`), written only when valid — any other
  value is silently left out of the parsed preset. And
  `lightPresetValidation.ts`'s `ANIMATIONS` gains `'smoulder'`. Our port
  at 0.9.1 would **falsely refuse** a 0.10.1-valid preset carrying
  either: the mild fidelity gap, refuse-what-the-pin-accepts — not
  §3.4's "equivalent strictness".
- **Data-only:** the dnd5e, drawSteel and pathfinder2e built-in presets
  each gained `difficultTerrain: 'double'` in `gridDefaults`;
  `builtInPresets.ts` itself is unchanged, so the nine-id set
  re-verifies as-is.
- **manifest.json at 0.10.1:** `minAppVersion "1.8.7"`,
  `isDesktopOnly: true` — both confirmed, unchanged.

## Proposal

Ticket 16's ritual, adjusted for what changed:

1. **Re-capture both goldens, no human step:**
   `uv run --with websocket-client tools/capture-golden.py 0.10.1` and
   the same with `--fixture sample-lit.uvtt` (ticket 15: the pin's
   directory carries the lit variant, the lit test runs there, not
   skips) → commit `fixtures/golden-0.10.1/`, fill the fixtures/README.md
   rows. Prove both green **before** the flip via
   `AVTT_GOLDEN_VERSION=0.10.1 python run-tests.py --all` (ticket 12's
   mechanism).
2. **Port the two widenings** in `presets.py`: accept
   `difficultTerrain: 'double'|'none'` and refuse every other spelling
   with the silently-dropped phrasing (the coneAngle/diagonalRule
   pattern); add `'smoulder'` to `LIGHT_ANIMATIONS`. Rename
   `BUILTIN_SYSTEMS_0_9_1` / `BUILTIN_DISPLAY_NAMES_0_9_1` → `…_0_10_1`
   with refreshed provenance comments (set unchanged — Problem).
3. **The both-goldens gate, in order:** new fixtures committed, pin
   still 0.9.1 → `ruff check src tests run-tests.py` +
   `run-tests.py --all` (old golden green), then
   `AVTT_GOLDEN_VERSION=0.10.1 run-tests.py --all` (new golden green);
   flip `ATLAS_PIN = "0.10.1"`, bump `VERSION` to **0.5.0** (validator
   behavior change rides a minor, mirroring 09's 0.3.0 and 16's 0.4.0),
   re-run `--all` (new golden green at the pin); one §8-step-5 commit,
   git-tagged `v0.5.0`. Contingency unchanged (§8 step 4): a surprising
   capture keeps the pin and ships the degrade path with a fix ticket,
   never a hacked port.
4. **README moves with the code**: §7 table row for 0.10.1; the header's
   verified-against and §3 stamps; §3.3 gains the group-import note (a
   surface this repo never takes, documented because the limits and the
   version-5 files are part of the format contract); §3.6's
   minAppVersion stamp; §8's cadence list gains 0.10.0 → 0.10.1;
   fixtures/README.md rows for both captures.
5. **Live check** (ticket 07/08/09/16 discipline): `publish.py version`
   on the real ember-coast vault; `presets` and `scenes` on temp copies;
   temp copies deleted, verified gone.

## Acceptance criteria

- [x] `fixtures/golden-0.10.1/sample.atlasmap` and
      `fixtures/golden-0.10.1/sample-lit.atlasmap` committed; both golden
      tests green against them via `python run-tests.py --all`
      (`tests/test_scenes.py::test_golden_file`,
      `::test_golden_file_lit_variant`).
- [x] The validator accepts `rules.gridDefaults.difficultTerrain` of
      `'double'`/`'none'` and `lightPresets[].animation: 'smoulder'`,
      and keeps refusing what Atlas silently drops — pinned by new cases
      in `tests/test_presets.py::test_grid_defaults_rules`
      (`triple`/`Double`/`2` refused; `double`/`none` accepted) and
      `::test_light_preset_rules` (`smoulder` accepted; the `flicker`
      refusal stays).
- [x] Pin, fixture, README table and VERSION moved in one tagged change
      — `tests/test_pin.py::test_atlas_pin_matches_fixtures`,
      `::test_readme_table_carries_the_pin`,
      `::test_version_mirrors_pyproject` green at `ATLAS_PIN = "0.10.1"`;
      `git tag` shows `v0.5.0`.
- [x] Builtin constants renamed `…_0_10_1` with refreshed provenance —
      `tests/test_smoke.py::test_public_surface_exists` and
      `tests/test_presets.py::test_builtin_systems_match_the_pinned_release`
      updated and green.
- [x] The shipped ICRPG pack still validates clean —
      `tests/test_presets.py::test_shipped_icrpg_pack_validates_clean`
      (the pack carries no `difficultTerrain`; its animations are
      torch/lantern presets, unaffected by `'smoulder'`).
- [x] README §7 carries the 0.10.1 row; the header and §3 stamps name
      the 2026-10-26 re-read; §3.3 documents the group-import path
      (checkable by reading).
- [x] Gates green on the branch: `ruff check src tests run-tests.py`,
      `python run-tests.py`, `python run-tests.py --all` (old golden
      pre-flip, new golden pre-flip via `AVTT_GOLDEN_VERSION`, new
      golden post-flip).
- [x] Live check recorded in Implementation notes (the vault's detected
      version stated plainly; temp copies verified deleted).
- [x] Any §8 deviation recorded in Implementation notes — never silent.

## Implementation notes (2026-10-26)

- **Re-clone re-verified** (AGENTS.md): fresh clone at tag `0.10.1` =
  commit `af9ccc974024089788a26ab69eb3f224c0462631`, diffed against tag
  `0.9.1` (`5499fd8`). Surface by surface as in Problem. The one
  surprise the diff settled: `MapPersistence.ts` grew 74 lines but
  `ATLAS_VERSION` stayed 4 — the multi-level version lives in
  `levels/levelFile.ts` (`LEVELS_FILE_VERSION = 5`,
  `SINGLE_LEVEL_FILE_VERSION = 4`), so single-level files (everything
  this repo writes) keep the version-4 envelope.
- **The two widenings' exact line**: `parseGridDefaults` destructures
  `difficultTerrain` beside `diagonalRule`/`coneAngle` and spreads it in
  only when `isOneOf(DIFFICULT_TERRAIN_RULES, …)` — `('double', 'none')`
  — so a valid value is used as written and anything else is silently
  absent from the parsed preset; the port refuses it instead (the
  `test_repaired_values_are_refused_not_repaired_silently` doctrine).
  `systemRules.ts`'s `sameGridDefaults` treats a preset without the knob
  as compatible with `'none'` — repair-comparison semantics, not
  validation, nothing for the port to mirror. `lightPresetValidation.ts`:
  `ANIMATIONS` gains `'smoulder'` between `magic` and the closing
  bracket; `lightAnimation`'s type widened to match
  (`types/lightingTypes.ts`).
- **Capture, no surprises in the artifact**: both captures
  (`sample.uvtt`, `sample-lit.uvtt`) landed; the 0.10.1 goldens are
  structurally identical to 0.9.1's apart from the timestamped asset
  name — 2787 = 2921 − 134 bytes, the byte delta exactly the line
  endings, because **0.10.1's writer emits LF where 0.9.1's wrote CRLF**
  (fixtures/README.md says so). Envelope `schema='atlas-vtt' version=4`
  in both. One harness observation, recorded not silently: the drop
  step logged `{'__error__': 'exception'}` in both captures (it did not
  in ticket 16's), yet the import ran and each scene materialized with
  the pure-import envelope — the poisoned-keys postcondition (the
  auto-open-rewrite detector) is what certifies these captures, and it
  passed. If it repeats at the next bump, that is a
  capture-harness ticket (the 0.10.x Electron may reject the
  synthesized `DragEvent` differently); the artifact checks stood in
  here, honestly noted.
- **Both-goldens order held**: pin still 0.9.1 with the new fixtures in
  the tree — ruff clean, `run-tests.py` green, `--all` green on the old
  golden, `AVTT_GOLDEN_VERSION=0.10.1 --all` green on the new one
  (ticket 12's mechanism — the pre-flip proof). Then the flip
  (`ATLAS_PIN = "0.10.1"`, `VERSION = "0.5.0"` in `_version.py` +
  pyproject, README status line/§3 stamp/§3.3/§3.6/§7 row/§8 cadence,
  fixtures/README rows) and the full gate re-run green at the new pin:
  ruff clean, both suites PASS. One §8-step-5 commit, tagged `v0.5.0`.
  §8 step 4's contingency never fired.
- **Live check**: `publish.py version` on the real ember-coast vault →
  `avtt-version: 0.5.0`, `atlas-pin: 0.10.1`, `atlas-detected: 0.7.1`
  (the manifest read directly agrees: 0.7.1 — Obsidian has not updated
  it; the expectation carried forward from 16 still stands: the
  pin-match behavior shows at the table only once Obsidian updates the
  vault's Atlas). `presets` on a temp copy, as found: mismatch warns,
  install proceeds, then ticket 11's shadowed-write refusal fires — the
  vault's `icrpg-house.json` still shadows `icrpg.json` (the live
  shadow state; the one-time delete remains pending at the vault). With
  the shadow removed in the copy: "already matches the pack — nothing
  written" (the vault's `icrpg.json` equals the pack payload
  byte-for-byte — refuse-on-diff pass). `scenes` on a second temp copy:
  mismatch → "writing no .atlasmap files", `the-drowned-crypt.uvtt`
  dropped into `atlas-vtt/_inbox/` with the drag-it-in instruction,
  rc 0. Both temp copies deleted, verified gone; no Obsidian process
  left running (tasklist checked); the real vault was never written
  (the `version` run reads only, the rest ran on copies).
- **§8 deviations: none of the procedure — one of the runner.** The
  bump was implemented and verified directly in a ticket worktree
  branch (`23-atlas-pin-bump-0-10-1`, the implementer workflow's
  worktree convention) rather than through
  `avtt-ticket-implementer`, at the user's go-ahead in session; every
  §8 step and gate ran in the documented order, and this ticket's
  completed flip + archive move ride the same single commit. VERSION
  0.5.0 as proposed — the validator behavior change rides a minor
  bump, mirroring 09 and 16.

**Sign-off (2026-10-26).** Every acceptance criterion is ticked on
evidence recorded above, none left for a human. The ticket's status
flip to `completed` and its move to `docs/tickets/archive/` are folded
into the branch's single §8-step-5 commit (ticket 16's bookkeeping
pattern).
