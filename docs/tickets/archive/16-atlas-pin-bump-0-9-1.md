# 16 — Atlas pin bump 0.8.0 → 0.9.1 (the third §8 churn)

**Status:** completed (implemented + signed off 2026-10-23, after one
review round; this flip and the `archive/` move are folded into the
branch's single §8-step-5 commit by amending — tagged `v0.4.0`,
re-pointed at the amended commit; pre-amend hash `a9d5006`)
**Priority:** P1 — two stables have shipped since the pin (0.9.0 on
2026-10-20, 0.9.1 on 2026-10-22, the current latest); the ember-coast
vault (still 0.7.1) follows stable at Obsidian's pace, and every vault
that updates past 0.8.0 silently takes the `_inbox/` degrade path until
this churn lands. Also carries the first substantive validator delta
since the repo started (initiative, below).
**Area:** `src/avtt/_version.py` (ATLAS_PIN, VERSION), `src/avtt/presets.py`
(initiative rules, builtin-constant rename), `tests/test_presets.py`,
`tests/test_pin.py`, `fixtures/golden-0.9.1/`, `fixtures/README.md`,
`README.md` (status line, §3 stamps, §7 table, §8 cadence line),
`pyproject.toml` (VERSION)
**Found by:** full adversarial review (upstream drift check), 2026-10-23.
Grounded against a fresh clone diff 0.8.0→0.9.1 recorded in Problem —
re-run the re-clone before implementing (AGENTS.md; the ticket's facts
are the 2026-10-23 state).

## Problem

**The pin lags two stables.** `ATLAS_PIN = "0.8.0"`
(`src/avtt/_version.py:29`). Upstream releases (GitHub /releases, which
includes pre-releases — checked, not just /latest):

| release | date | kind |
|---|---|---|
| 0.8.1-beta.0 | 2026-10-14 | prerelease only — **no stable 0.8.1 ever shipped** |
| 0.9.0 | 2026-10-20 | stable |
| 0.9.1-beta.0 | 2026-10-20 | prerelease |
| 0.9.1 | 2026-10-22 | stable, current latest |

Stable cadence is **~weekly** (0.7.0 Oct 9 → 0.7.1 Oct 10 → 0.8.0 Oct
14 → 0.9.0 Oct 20 → 0.9.1 Oct 22); README §8's "assume monthly
breakage" understates it and its first line should say weekly.

**The 0.8.0→0.9.1 clone diff (2026-10-23), surface by surface:**

- **Untouched (byte-identical)**: `src/app/import/uvtt/uvttToScene.ts`
  (the ported conversion), `src/app/services/MapPersistence.ts`
  (`ATLAS_SCHEMA`/`ATLAS_VERSION` still `atlas-vtt`/4), the whole
  `src/app/services/vault-sync/` directory (adoption),
  `presetValidation.ts`, `diceSets.ts`, `builtInPresets.ts`,
  `statblocks/render/statblockFence.ts`. So the existing goldens should
  hold and the capture should match the port as it stands — but only
  the capture decides (§8).
- **The one port-worthy delta — initiative widens.** 0.9.0's
  card-based initiative adds a `'cards'` mode to `InitiativeRules` plus
  optional fields (`sides`, `sideRoll`, `deck`, `dealEachRound`,
  `lookAlikesShare`, `rollHitPoints`; one field's source comment reads
  "Older versions ignore it"). `firstSide` stays required. Our port
  (`presets.py:383-393` `_validate_initiative`) accepts only
  `("turn-order", "sides")` — at the new pin it would **falsely refuse**
  a cards-mode preset Atlas accepts: a fidelity gap of the mild kind
  (refuse-what-the-pin-accepts), but not §3.4's "equivalent strictness".
  The implementer re-checks at the tag which new fields are validated
  versus silently dropped, and ports each side of that line exactly.
- **Data-only**: the OSE built-in preset gained an `initiative` block;
  the nine `builtInPresetId` keys and `builtInPresets.ts` are unchanged,
  so `BUILTIN_SYSTEMS_0_8_0`'s set re-verifies as-is.
- **0.9.0/0.9.1 changelog highlights** (encounter builder, statblock
  rest actions and counters, card initiative, Dice Chrome extension,
  dynamic lighting out of experimental, Atlas Online expansion) touch
  no consumed surface per the diff; `minAppVersion`/desktop-only not
  re-verified at 0.9.1 — the implementer confirms both in the manifest
  while there.

## Proposal

Ticket 09's ritual, adjusted for what changed:

1. **Re-capture the golden, no human step:**
   `uv run --with websocket-client tools/capture-golden.py 0.9.1` →
   commit `fixtures/golden-0.9.1/sample.atlasmap`, fill the
   fixtures/README.md row. Given ticket 12's mechanism exists, prove
   the new capture green **before** the flip (its whole point); if 12
   has not landed, land it first or follow ticket 09's two-commit
   order with the same honest note.
2. **Port the initiative widening** in `presets.py`: add `'cards'` to
   `INITIATIVE_MODES`; accept the new optional fields exactly as the
   0.9.1 validator treats them (used-as-written or refused — never
   silently dropped). Rename `BUILTIN_SYSTEMS_0_8_0` /
   `BUILTIN_DISPLAY_NAMES_0_8_0` → `..._0_9_1` with refreshed
   provenance comments (set unchanged — Problem).
3. **The both-goldens gate, in order** (ticket 09 Proposal 4's shape):
   new fixture committed, pin still 0.8.0 → `ruff check src tests
   run-tests.py` + `python run-tests.py --all` (old golden green);
   flip `ATLAS_PIN = "0.9.1"`, bump `VERSION` (propose **0.4.0** — it
   carries a validator behavior change, mirroring how 09 proposed
   0.3.0; final number at merge), re-run `--all` (new golden green);
   one §8-step-5 commit, git-tagged `v<VERSION>`. Contingency unchanged
   (§8 step 4): a surprising capture keeps the pin and ships the
   degrade path with a fix ticket, never a hacked port.
4. **README moves with the code**: §7 table row for 0.9.1 (notes: the
   initiative widening is the port delta; import semantics, scene
   schema, adoption, unitDistance bounds, builtin set unchanged); the
   header's verified-against and §3 stamps; **§8's cadence sentence
   says weekly, not monthly** (three-days→weekly is the observed
   record); fixtures/README.md row.
5. **Live check** (ticket 07/08/09 discipline): `publish.py version` on
   the ember-coast vault (expected `pin 0.9.1` / `detected 0.7.1` until
   Obsidian updates it); `presets` on a temp copy warns and installs;
   `scenes` on a temp copy degrades. Temp copies deleted, verified
   gone.

## Acceptance criteria

- [x] `fixtures/golden-0.9.1/sample.atlasmap` committed; the golden
      test green against it via `python run-tests.py --all` (pinned by
      `tests/test_scenes.py::test_golden_file`).
- [x] The validator accepts a cards-mode `rules.initiative` and the
      new optional fields per the 0.9.1 source, and keeps refusing
      what Atlas refuses — pinned by new cases in
      `tests/test_presets.py` (accept `mode: "cards"`; refuse the old
      vocabulary violations as before; each new optional field either
      accepted or refused, matching the tag's validator, with the
      refusal reasons updated to name the new shape).
- [x] Pin, fixture, README table and VERSION moved in one tagged change
      — `tests/test_pin.py::test_atlas_pin_matches_fixtures`,
      `::test_readme_table_carries_the_pin`,
      `::test_version_mirrors_pyproject` green at
      `ATLAS_PIN = "0.9.1"`; `git tag` shows `v<VERSION>`.
- [x] Builtin constants renamed `_0_9_1` with refreshed provenance —
      `tests/test_presets.py::test_builtin_systems_match_the_pinned_release`
      updated and green.
- [x] The shipped ICRPG pack still validates clean —
      `tests/test_presets.py::test_shipped_icrpg_pack_validates_clean`
      (its `mode: "sides"` initiative is unaffected).
- [x] README §8 names the weekly cadence; §7 carries the 0.9.1 row
      (checkable by reading).
- [x] Gates green on the branch: `ruff check src tests run-tests.py`,
      `python run-tests.py`, `python run-tests.py --all`.
- [x] Live check recorded in Implementation notes (the vault's detected
      version stated plainly; temp copies verified deleted).
- [x] Any §8 deviation recorded in Implementation notes — never silent.

## Implementation notes (2026-10-23)

- **Re-clone re-verified** (AGENTS.md): tag `0.9.1` = commit
  `5499fd8710c38dc04d359a141b8c03ce4db54c92`, diffed against fetched
  tag `0.8.0`. Surface by surface: `presetValidation.ts`,
  `diceSets.ts`, `builtInPresets.ts`, `MapPersistence.ts`, the whole
  `services/vault-sync/` tree, `import/uvtt/uvttToScene.ts`,
  `statblocks/render/statblockFence.ts` and
  `statblocks/notes/statblockSource.ts` all byte-identical (0 diff
  lines). The one import-dir delta is `runUvttImport.ts` — notice text
  only (the "switch on dynamic lighting" sentence left with the
  feature's move out of Experimental); the import write path is
  untouched. `manifest.json` at 0.9.1: `minAppVersion "1.8.7"`,
  `isDesktopOnly true` — both confirmed, unchanged. The nine
  `builtInPresetId` keys re-verified one by one (`presets/*.ts`); OSE
  gained only its data `initiative` block
  (`{mode: 'sides', roll: '1d20', firstSide: 'players', sideRoll:
  '1d6'}` — the exact shape the port's sides-mode accept case pins).
- **Release record re-checked** via the GitHub API: 0.9.0 stable
  2026-10-20, 0.9.1 stable 2026-10-22, exactly as the Problem table.
  One fact newer than the ticket: a `0.9.2-beta.0` **prerelease** also
  shipped 2026-10-22 — 0.9.1 remains the latest stable, so the pin
  target stands; noted here, not silently.
- **The initiative port's exact line** (initiativeRules.ts
  `parseInitiativeRules` reading the new initiativeSideRules.ts /
  initiativeCardRules.ts): whole-section refusal unchanged (mode ∈
  turn-order/sides/cards — the widening; firstSide ∈ players/opponents,
  still required; roll still one dice group — the asymmetry with
  `dice.defaultRoll` groups is Atlas's and stays). Per knob:
  `sides` must survive `parseSideList` unchanged — every entry an
  object with a non-blank unique id ≤ 64 chars and no key but id/name,
  `name` only on named sides (a named built-in's name is dropped),
  named names already trimmed and ≤ 40 chars, both built-in sides
  present (missing ones are appended), ≤ 6 named sides beside them —
  and a list's first built-in side must equal `firstSide` (`sideParts`
  takes the order from the list, silently overriding a disagreeing
  `firstSide`). `sideRoll`: one dice group or refused (silently
  dropped there). `deck`: whole number 2–50 — 10 is the default
  kept-equivalent and accepted; anything else is silently dropped for
  10 and refused. `dealEachRound`/`lookAlikesShare`/`rollHitPoints`:
  booleans — `true` stored, `false` reads as the unset off, every
  other spelling is silently read as off and refused. `null` follows
  the module-wide absent-equals-absent convention (as `diagonalRule`
  always has). `modifierSources` (unchanged between the tags) reads
  only `modifier`/`modifierFallback` — outside this delta, untouched.
- **Capture, no surprises**: `uv run --with websocket-client
  tools/capture-golden.py 0.9.1` green first try (drop step clean,
  envelope `schema='atlas-vtt' version=4`); the 0.9.1 golden is
  byte-identical to 0.8.0's apart from the timestamped asset name —
  fixtures/README.md says so now. §8 step 4's contingency never fired.
- **Both-goldens order held**: with the pin still 0.8.0 and the new
  fixture in the tree — `ruff check src tests run-tests.py` clean,
  `run-tests.py` green, `run-tests.py --all` green on
  the old golden, then `AVTT_GOLDEN_VERSION=0.9.1 run-tests.py --all`
  green on the new one (ticket 12's mechanism — the pre-flip proof).
  Then the flip (`ATLAS_PIN = "0.9.1"`, `VERSION = "0.4.0"` in
  `_version.py` + pyproject, README status/§3 stamps/§3.6/§4/§7 row/§8
  weekly cadence, fixtures/README row) and the full gates re-run green
  at the new pin: ruff clean, `run-tests.py` 163 passed/1 skipped,
  `--all` both suites PASS. Committed once, tagged `v0.4.0` (§8 step 5).
- **Round 1 (reviewer)**: the edit inserting the new initiative test
  accidentally consumed the `def test_unit_distance_bounds_are_inclusive():`
  line — the ticket-08 test's docstring and body dangled as dead
  statements inside the new test, so its assertions still ran but the
  named test no longer existed (the pass count sat at 162 either way,
  masking the loss; ruff's E4/E7/E9/F never flags an orphaned
  docstring). Restored the def line — the test is byte-identical to
  main's again (`pytest --collect-only` lists it; diff against
  `git show main:tests/test_presets.py` empty), and the suite now
  reads 163 passed/1 skipped. Amended into the same commit, tag
  `v0.4.0` re-pointed at the amended one (nothing was pushed).
- **Live check**: `publish.py version` on the real ember-coast vault →
  `avtt-version: 0.4.0`, `atlas-pin: 0.9.1`, `atlas-detected: 0.7.1`
  (the manifest read directly agrees: 0.7.1 — Obsidian has not
  updated it). `presets` on a temp copy: mismatch warns and the
  install proceeds — with the copy as found it also hit ticket 11's
  shadowed-write refusal (the vault's `icrpg-house.json` carries the
  pack's own id and sorts first — the live shadow state); with the
  shadow removed in the copy: "already matches the pack — nothing
  written"; with the target also removed: "wrote …icrpg.json"
  (installed id `icrpg-house`, initiative `mode: sides` — the pack
  payload itself is unchanged this ticket). `scenes` on a second temp
  copy: mismatch → "writing no .atlasmap files",
  `the-drowned-crypt.uvtt` dropped into `atlas-vtt/_inbox/` with the
  drag-it-in instruction, rc 0. Both temp copies deleted, verified
  gone; no Obsidian process left running (tasklist checked). Nothing
  was written outside `atlas-vtt/` in any vault (the `version` run
  reads only).
- **§8 deviations: none.** VERSION 0.4.0 as proposed — the validator
  behavior change rides a minor bump, mirroring 09's 0.3.0.

**Sign-off and flip (2026-10-23).** The reviewer accepted the ticket
after round 1 (the consumed `test_unit_distance_bounds_are_inclusive`
def line — restored, recorded above); every acceptance criterion is
ticked on evidence recorded above, none left for a human. One
expectation carried forward, mirroring 09's closing note: the vault's
plugin still reads 0.7.1, so the pin-match behavior (no mismatch line,
`scenes` writing `.atlasmap` instead of `_inbox/`) will first show at
the table once Obsidian updates the vault's Atlas — re-run Proposal 5's
commands then; the criterion as written (the detected version stated
plainly, temp copies verified deleted) is met and recorded. Bookkeeping:
status → completed, file moved `docs/tickets/` → `docs/tickets/archive/`
in the same change, both folded into the branch's LAST commit by
amending the §8-step-5 commit (`a9d5006` pre-amend); the `v0.4.0` tag
was re-pointed at the amended commit so §8 step 5's "the change
git-tagged v<VERSION>" stays true of the final commit (nothing was
pushed; the tag existed only locally).
