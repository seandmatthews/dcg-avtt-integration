# 09 — Atlas pin bump 0.7.1 → 0.8.0 (the second §8 churn)

**Status:** proposed
**Priority:** P1 — the pin's job is to name the stable release this repo is
verified against (§7); 0.8.0 has been stable since 2026-10-14 and the home
vault's plugin follows stable at an uncontrolled moment (Obsidian's plugin
update) — when it moves, `scenes` silently takes the `_inbox/` degrade path
until this churn lands. The ticket also carries the 0.8.0 re-statement of the
statblock-fence contract (§3.5) that the unwritten ICRPG fence templates
(P1, §1) are waiting on.
**Area:** `src/avtt/_version.py` (ATLAS_PIN, VERSION), `src/avtt/presets.py`
(dice `defaultRoll` groups, builtin-constant rename), `tests/test_presets.py`,
`fixtures/golden-0.8.0/`, `fixtures/README.md`, `README.md` (status line,
§3/§3.5/§3.6 stamps, §7 table), `pyproject.toml` (VERSION),
`packs/icrpg/fences/README.md` (one-line §3.5 sync)
**Found by:** the owner's pin-bump idea; grounded for this ticket in a
0.7.1→0.8.0 re-clone diff re-verified 2026-10-20 (the commands and their
outputs are recorded in Problem — re-runnable as written)

## Problem

**The pin lags current stable.** `ATLAS_PIN = "0.7.1"`
(`src/avtt/_version.py:29`), while upstream's stable is 0.8.0:
`git ls-remote --tags origin` shows `0.8.0` as the highest stable tag
(`3d68221105701e570410e26eb5e34d0d56f8ac86`, commit date
2026-10-14 16:53:53 +0200, matching `changelog/0.8.0.md`'s
`date: 2026-10-14` front matter), with only `0.8.1-beta.0` above it — a
prerelease, not a bump candidate (the pin names stable releases; ticket 08's
discipline). GitHub's releases page agrees: `releases/latest` →
`tag_name: 0.8.0`, carrying the `main.js` / `manifest.json` / `styles.css`
assets `tools/capture-golden.py` installs. Ground truth on the home machine
(2026-10-20): the ember-coast vault's manifest still reads
`"version": "0.7.1"` (`../dnd-campaign-generator/campaign-data/campaigns/
ember-coast/.obsidian/plugins/atlas-vtt/manifest.json`) — the mirror image of
ticket 08's skew. Today pin and vault agree; when Obsidian updates the plugin
the §7 mismatch gate opens with no ticket ready. README §8 prescribes exactly
this ritual.

**The pinned source moved in one way the port must follow.** Verified
2026-10-20: the reference clone at `$TEMP/atlas-vtt` (`git clone --branch
0.8.0 https://github.com/atlas-vtt/atlas-vtt`; `git describe --tags` →
`0.8.0`, commit `3d68221` — the README §7 row to be; `git log -1 0.7.1` →
`942514b`, matching ticket 08's record), and `git diff 0.7.1 0.8.0` was read.
Findings:

- **The one port-worthy delta — `rules.dice.defaultRoll` widens to dice-set
  groups.**
  - 0.7.1 `presetValidation.ts`'s `parseDiceRules` gated on
    `isValidDefaultRoll(raw.defaultRoll)` — one `NdS` group (`diceRules.ts`
    `DEFAULT_ROLL`: 1–99 dice of 2–999 sides).
  - 0.8.0 `presetValidation.ts:126` gates on `parseRollGroups(raw.defaultRoll)`
    (new import from `diceSets.ts`): whitespace stripped, split on `+`,
    **every** part must match the same `NdS` group regex
    (`diceSets.ts:54` — the identical pattern), at least one group
    (`diceSets.ts:60`). So `1d20+1d6` — and any longer sum — is now a usable
    default roll where 0.7.1 refused it. Still fatal on failure: null → Atlas
    omits the whole dice section (unchanged).
  - Our port still implements the 0.7.1 rule — `src/avtt/presets.py:131`
    compiles the single-group `_DEFAULT_ROLL`, and `_default_roll_ok`
    (`presets.py:169-170`) gates `_validate_dice` (`presets.py:344`). A preset
    with `defaultRoll: "1d20+1d6"` passes Atlas 0.8.0 and is refused by our
    installer — a fidelity gap, milder than ticket 08's (we refuse what the
    pin accepts, rather than accepting what it ignores) but not the
    "equivalent strictness" §3.4 demands.
  - **The initiative roll does not widen:** `parseInitiativeRules` still gates
    `roll` through `isValidDefaultRoll` (0.8.0 `initiativeRules.ts:23`) —
    single group. `_validate_initiative` (`presets.py:363-373`) stays as-is;
    the asymmetry is Atlas's and the port keeps it.
  - Everything else in the dice section is unchanged: `CRIT_RULES` and
    `parseExplodeRule` are untouched (the `diceRules.ts` diff only removes
    UI-facing helpers, `isValidDiceRules`/`collectionDiceRules`); the
    `resourceDefinitions.ts` changes are additive (`resourceKey` gains a
    `fallback` param defaulting to the old `'resource'`; a new
    `savedResources` helper) — the parse path the port mirrors is untouched.
- **Everything else port-relevant is unchanged** (each checked in the same
  diff):
  - UVTT import semantics: the whole `src/app/import/uvtt/` diff is
    `runUvttImport.ts` swapping `new Notice(…)` for a themed `showNotice(…)`
    wrapper (the changelog's toast-theming fix). `uvttToScene.ts`,
    `uvttTypes.ts` and `importUvttFile.ts` are not in the diff at all — the
    conversion this repo ports is untouched.
  - Scene schema constants: `ATLAS_SCHEMA = 'atlas-vtt'`,
    `ATLAS_VERSION = 4` at both tags (`MapPersistence.ts:27-28` at 0.7.1 and
    0.8.0) — the existing goldens stay valid and a 0.8.0 capture should match
    the port as it stands.
  - `unitDistance`: `src/app/grid/unitDistance.ts` produces an **empty diff**;
    MIN/MAX are still `0.000001` / `1_000_000` inclusive
    (`unitDistance.ts:7,9,15`). Ticket 08's bounds survive untouched.
  - Built-in systems: the same ten files at both tags
    (`src/app/gameSystems/presets/` — the nine systems plus
    `presetHelpers.ts`), so `BUILTIN_SYSTEMS_0_7_1`'s *set* re-verifies
    against 0.8.0. The preset *contents* gain optional keys: every system adds
    `diceSetId: D20_DICE_SET_ID` and `statblockRoles` (shadowdark:
    `[{id: 'monster', name: 'Monster', templateId: 'builtin:bx-creature'}]`);
    dnd5e also adds `itemRarities` and initiative `modifier`/
    `modifierFallback`. All three are optional `SystemRules` fields
    (`systemPresetTypes.ts`), spread only when present by the new
    `parseSystemRules` — `parseUserPreset` split into a thin wrapper around
    it, with the fatal gates unchanged (non-empty id/name, usable
    `gridDefaults`, a `conditions` array). The port reads only known keys and
    ignores the rest, so a user preset carrying the new keys is judged exactly
    as Atlas judges it, and the shipped pack carries none
    (`packs/icrpg/preset.json:6-7`: `unitDistance: 5`, `defaultRoll: "1d20"`).
    The initiative `modifier` keys flow through the unchanged fatal gates; a
    preset without them parses identically — no port change (scope note).
  - `parseGridDefaults`, `parseCondition`, `parseWidget`,
    `parseSenseDefinitions`, `parseLightPresets`, `parseVisionDefaults`,
    `isValidClockSegments` — no hunks in the validator diff beyond the dice
    gate and the `parseSystemRules` extraction.
- **The statblock-fence contract (§3.5) — the re-read statement the fence
  templates depend on.** 0.8.0's headline is native statblocks ("Atlas draws
  statblocks itself, so they show without the Fantasy Statblocks plugin" —
  `changelog/0.8.0.md`). What the source says:
  - **The fence parser is unchanged in substance.** `parseStatblockFence`
    moved verbatim from `services/statblockNoteSource.ts` (gutted at 0.8.0;
    only `hasBestiaryFrontmatter` left behind) to
    `statblocks/notes/statblockSource.ts`: the same ```statblock / ~~~statblock
    fence regex (byte-identical between tags), YAML body via `parseNoteYaml`,
    a malformed fence still `{}` ("still a statblock fence" — rendered as an
    error, not ignored). `resolveCreatureFromFence`
    (`FantasyStatblocksService.ts`, 0.7.1 line 118 → 0.8.0 line 151) is
    byte-identical: a named bestiary creature underneath, the referenced
    note's frontmatter over that, the fence's own params on top.
  - **The token-link resolution order is preserved.** `linkedCreature.ts` is
    refactored around a classifier (`statblockSourceOf` → kinds `atlas` /
    `fs-frontmatter` / `fs-fence`), but `linkedCreatureAsGiven` keeps the
    order: bestiary-by-path (the plugin parsed the note) → frontmatter →
    fence → bestiary creature of the note's name.
  - **What is new is a second, native surface.** A *native* statblock note is
    frontmatter `statblock: true` plus `atlas-template: <id>` (`TEMPLATE_KEY`,
    `statblockSource.ts`); Atlas's own display fence is a *different fence
    language*, ` ```atlas-statblock ` (`STATBLOCK_FENCE_LANGUAGE`, rendered by
    `statblocks/render/statblockFence.ts:62-63`) whose body is ignored — the
    note's frontmatter is the statblock. The one resolver
    (`statblocks/resolve/resolveStatblock.ts`) states the plugin-less behavior
    in both docstring and code: with Fantasy Statblocks absent, native notes
    render from frontmatter and **inline ```statblock fences render too, with
    the auto template** (`resolveInlineFence`: "its own YAML with the auto
    template"); a fence that only *names* a bestiary creature or another note
    gives null — "only the plugin can read it". The plugin api is
    `window.FantasyStatblocks` (`FantasyStatblocksService.ts:30-32`), so
    fence→creature resolution *for token links* still requires the plugin
    (`resolveCreatureFromFence`'s `if (!api) return null`) — the unchanged
    limitation §3.5 already records, and the reason ICRPG packs lean on the
    preset's token resources by design.
  - **Consequence for the unwritten ICRPG fence templates (P1, §1):** their
    body-only inline fences are *stronger* at 0.8.0 — they display without the
    plugin (auto template) — while the mechanically-live number stays the
    preset's hearts resource. The body-only rule stands: a *native* note would
    put `statblock: true` + `atlas-template:` frontmatter into the spine note,
    which the core's frontmatter parser must never see (§3.5) — if the fences
    ticket ever wants native notes, that is a user ruling, not a silent
    switch. This statement is §3.5's 0.8.0 re-statement; Proposal 5 lands it
    in the README.
- **None of this is announced as a validator change.** The changelog's dice
  line ("Dice formulas support the notation of Foundry and Roll20: keep and
  drop (2d20kh1), …") names the roller feature; `git grep -in 'unitdistance'
  0.8.0 -- changelog/0.8.0.md` finds nothing (nothing needs announcing — the
  bounds did not move). §8 step 1 ("read the changelog") alone would have
  cleared 0.8.0 as safe; only the source diff catches the `defaultRoll`
  widening — the reason §8 mandates the re-clone.
- One §3.6 touch the stamp move forces: 0.8.0 ships opt-in online play (closed
  beta, off until enabled under Experimental features) — Atlas's own feature;
  no contract this repo consumes changes, and `manifest.json` still reads
  `"minAppVersion": "1.8.7"`, `"isDesktopOnly": true`. §3.6's "offline" line
  gains the same-day nuance when the §3 stamp moves (the constitution rule),
  not a new ruling.

## Proposal

1. **Re-capture the golden — no human step (ticket 08's Proposal 1
   machinery):** `uv run --with websocket-client tools/capture-golden.py
   0.8.0` → commit `fixtures/golden-0.8.0/sample.atlasmap`, fill the
   fixtures/README.md table row and note anything capture-specific (as 0.7.1's
   row records the background-format change). The tool installs the 0.8.0
   release assets (verified present — Problem), builds a throwaway vault, and
   its postcondition refuses a capture carrying non-import state keys. The
   diff says the import output is unchanged since 0.7.1 — only the capture
   decides. The optional `sample-lit` second capture stays optional
   (fixtures/README.md), same discipline as ticket 08.
2. **Port the widening** in `src/avtt/presets.py`: add `_roll_groups_ok(value)`
   mirroring `parseRollGroups` — strip *all* whitespace, split on `+`, every
   part fullmatches the existing `_DEFAULT_ROLL` pattern, at least one group,
   **no group-count cap** (`parseRollGroups` has none; `MAX_SET_GROUPS`
   belongs to dice-set editing, not the validator — do not invent one). Use it
   in `_validate_dice` only; `_default_roll_ok` stays for
   `_validate_initiative`. Comment cites `diceSets.ts:54,60` (AGENTS.md:
   cite, never vendor). Update the refusal to name both shapes:
   `"...a defaultRoll like '1d20' or '1d20+1d6' — one or more groups of 1 to
   99 dice of 2 to 999 sides — ..."`. No existing test matches the old
   fragment (grep over `tests/ src/ tools/` for the refusal text and the
   helpers hits only `src/avtt/presets.py`; the only dice-refusal assertions,
   `tests/test_presets.py:170,172`, match the prefix `rules.dice is not
   usable`, which the new text keeps) — nothing breaks; the criterion's new
   cases join `test_fatal_breaks_are_refused_whole`'s parametrized case set
   (`tests/test_presets.py:79-102`), as ticket 08's unitDistance cases did.
3. **Rename `BUILTIN_SYSTEMS_0_7_1` / `BUILTIN_DISPLAY_NAMES_0_7_1` →
   `..._0_8_0`** in the same change, refreshing the provenance comments
   (`presets.py:49-71`) to 0.8.0 / commit `3d68221` ("re-verified 2026-10-20;
   the same ten files as at 0.7.1 — ticket 09's source diff"). Update
   `tests/test_presets.py::test_builtin_systems_match_the_pinned_release`
   (names and docstring); the set itself is unchanged (verified — Problem).
4. **Run the both-goldens gate in this order, before merging:**
   a. With `ATLAS_PIN` still `"0.7.1"` and `golden-0.8.0/` committed:
      `ruff check src tests run-tests.py` and `python run-tests.py --all` —
      `test_golden_file` still reads `golden-0.7.1` (§8 step 3, first half).
   b. Flip `ATLAS_PIN = "0.8.0"` (`src/avtt/_version.py:29`) and bump
      `VERSION` (propose **0.3.0** — the second release carrying a behavior
      change: the validator now accepts `defaultRoll`s 0.2.0 refused; mirrors
      `pyproject.toml`, held together by
      `tests/test_pin.py::test_version_mirrors_pyproject`; final number
      confirmed at merge). Commit the constant, `fixtures/golden-0.8.0/`, the
      README §7 row and the VERSION bump as the one §8-step-5 change,
      git-tagged `v<VERSION>`. `python run-tests.py --all` again —
      `test_golden_file` now reads the 0.8.0 golden.
   - **Contingency (§8 step 4):** if the 0.8.0 golden surprises us — the
     structural comparison is strict on key sets, and the golden is the
     source of truth above any docstring — do not hack the port to pass: keep
     the pin, ship the `_inbox/` degrade path, open the fix as its own
     ticket. The source diff says this should not happen (conversion
     untouched, schema constants unchanged), but only the capture decides.
5. **README moves with the code** (the constitution rule, AGENTS.md): the §7
   table gains `| 0.8.0 | <pin date> | <notes> |` (0.6.0 and 0.7.1's rows
   stay as history); the header's current-state claims move to 0.8.0
   (released 2026-10-14: tag date + changelog front matter) and the status
   line's verified-against sentence gains this ticket's re-read; §3's heading
   stamp gains it too; **§3.5 is re-stated for 0.8.0** with the Problem's
   findings — parser unchanged, resolution order preserved, native
   `statblock: true` + `atlas-template:` notes, the `atlas-statblock` display
   fence as a separate language, inline fences rendering plugin-free with the
   auto template, name-only fences and token-link resolution still needing the
   plugin; §3.6's "offline" line gains the online-play nuance (opt-in, closed
   beta, off by default; `minAppVersion` and desktop-only unchanged).
   `packs/icrpg/fences/README.md`'s one-line §3.5 paraphrase gains the same
   nuance (inline fences display without the plugin; token-link resolution
   needs it). Historical provenance lines elsewhere stay (ticket 07's
   ruling). fixtures/README.md's table fills in step 1.
6. **Live check** (ticket 07/08's discipline), with the ground truth stated
   plainly: the ember-coast vault reads `"version": "0.7.1"` today
   (2026-10-20), so after the flip `publish.py version` on it must print
   `atlas-pin: 0.8.0` / `atlas-detected: 0.7.1`; `presets` on a temp copy must
   print the `atlas-pin-mismatch` line and install anyway; `scenes` on a temp
   copy must take the `_inbox/` degrade path. That is the §7 policy working as
   designed, not a failure: the pin tracks current stable and the vault
   follows when Obsidian updates the plugin. The check is re-run then (pin
   0.8.0 / detected 0.8.0, no mismatch line, `.atlasmap` written, no
   `_inbox/`) as the closing half of the criterion. Temp copies deleted after
   each check (verified gone).

## Acceptance criteria

- [ ] The validator accepts multi-group `defaultRoll`s and keeps refusing
      malformed ones — pinned by `tests/test_presets.py`: new cases accepting
      `1d20+1d6` and whitespace-padded `" 1d20 + 1d6 "`; refusing
      `1d20+sword`, `100d6` (count above 99), `d1000` (sides above 999),
      `1d20++1d6`, and an all-whitespace roll — each with the refusal naming
      both shapes.
- [ ] The initiative roll keeps the single-group rule (the asymmetry is
      Atlas's) — a test pinning that `rules.initiative.roll: "1d20+1d6"` is
      refused while `rules.dice.defaultRoll: "1d20+1d6"` passes.
- [ ] Golden captured and green both ways:
      `fixtures/golden-0.8.0/sample.atlasmap` committed;
      `tests/test_scenes.py::test_golden_file` green with the pin still 0.7.1
      (reading `golden-0.7.1/`) and green after the flip (reading
      `golden-0.8.0/`) — via `python run-tests.py --all`.
- [ ] Pin, fixture and README moved in one change:
      `tests/test_pin.py::test_atlas_pin_matches_fixtures` and
      `::test_readme_table_carries_the_pin` green at `ATLAS_PIN = "0.8.0"`;
      `::test_version_mirrors_pyproject` green at the bumped VERSION; the
      change git-tagged `v<VERSION>` (checkable with `git tag`).
- [ ] Builtin constants renamed `_0_8_0` with refreshed provenance —
      `tests/test_presets.py::test_builtin_systems_match_the_pinned_release`
      updated and green; the constants' comments cite 0.8.0 / commit
      `3d68221` (checkable by reading).
- [ ] The shipped ICRPG pack still validates clean —
      `tests/test_presets.py::test_shipped_icrpg_pack_validates_clean`
      (its `defaultRoll: "1d20"` and `unitDistance: 5`,
      `packs/icrpg/preset.json:6-7`, are unaffected by the widening; no pack
      change).
- [ ] Gates green on the branch: `ruff check src tests run-tests.py` and
      `python run-tests.py` / `python run-tests.py --all` (the integration
      tier runs once a `golden-*/sample.atlasmap` exists — `run-tests.py:60-66`).
- [ ] README moved with the code (checkable by reading): §7 has the 0.8.0 row
      and keeps 0.6.0/0.7.1; the header's "Tested against" names 0.8.0
      (released 2026-10-14); §3 carries the 0.8.0 stamp; §3.5 carries the
      re-statement with the five facts above; §3.6 carries the online-play
      nuance; fixtures/README.md's table has all three rows;
      `packs/icrpg/fences/README.md`'s paraphrase matches §3.5.
- [ ] Live check recorded here: the real ember-coast vault's `version` report
      matches its manifest (expected `pin 0.8.0` / `detected 0.7.1` until the
      plugin updates); `presets` on a temp copy warns and installs; `scenes`
      on a temp copy degrades to `_inbox/`; after the vault's plugin updates,
      the re-run prints no mismatch line and `scenes` writes `.atlasmap` with
      no `_inbox/`. Temp copies deleted after each check (verified gone).
- [ ] Any §8 deviation is recorded in Implementation notes with the reason —
      never silent.

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
