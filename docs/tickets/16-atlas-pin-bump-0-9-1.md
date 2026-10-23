# 16 — Atlas pin bump 0.8.0 → 0.9.1 (the third §8 churn)

**Status:** proposed
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

- [ ] `fixtures/golden-0.9.1/sample.atlasmap` committed; the golden
      test green against it via `python run-tests.py --all` (pinned by
      `tests/test_scenes.py::test_golden_file`).
- [ ] The validator accepts a cards-mode `rules.initiative` and the
      new optional fields per the 0.9.1 source, and keeps refusing
      what Atlas refuses — pinned by new cases in
      `tests/test_presets.py` (accept `mode: "cards"`; refuse the old
      vocabulary violations as before; each new optional field either
      accepted or refused, matching the tag's validator, with the
      refusal reasons updated to name the new shape).
- [ ] Pin, fixture, README table and VERSION moved in one tagged change
      — `tests/test_pin.py::test_atlas_pin_matches_fixtures`,
      `::test_readme_table_carries_the_pin`,
      `::test_version_mirrors_pyproject` green at
      `ATLAS_PIN = "0.9.1"`; `git tag` shows `v<VERSION>`.
- [ ] Builtin constants renamed `_0_9_1` with refreshed provenance —
      `tests/test_presets.py::test_builtin_systems_match_the_pinned_release`
      updated and green.
- [ ] The shipped ICRPG pack still validates clean —
      `tests/test_presets.py::test_shipped_icrpg_pack_validates_clean`
      (its `mode: "sides"` initiative is unaffected).
- [ ] README §8 names the weekly cadence; §7 carries the 0.9.1 row
      (checkable by reading).
- [ ] Gates green on the branch: `ruff check src tests run-tests.py`,
      `python run-tests.py`, `python run-tests.py --all`.
- [ ] Live check recorded in Implementation notes (the vault's detected
      version stated plainly; temp copies verified deleted).
- [ ] Any §8 deviation recorded in Implementation notes — never silent.

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
