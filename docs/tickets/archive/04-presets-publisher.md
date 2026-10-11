# 04 — P0: the presets publisher (pack installer)

**Status:** completed (2026-10-11 — reviewer signed off on round 1 of
`8ede78d` after the vision-defaults fix; archived in the same change)
**Priority:** P1 (first code build, after the spikes)
**Area:** `src/avtt/presets.py`, `src/avtt/publish.py` (presets
subcommand), `packs/icrpg/`
**Found by:** spec §5.2, 2026-10-10

## Problem

The ICRPG preset is the repo's system-specific payload (README §1) and
the pack installer is its delivery mechanism — the first build item
once spikes 01–03 land. Nothing exists yet; `presets.py` is a stub.

## Proposal

Implement per README §3.4/§5.2:

1. Port the validator checks from Atlas's `presetValidation.ts` at the
   pinned version — exactly as strict as Atlas's own loader, since an
   invalid preset is silently ignored there (the worst failure mode).
2. `install()`: refuse-on-diff write to
   `atlas-vtt/system-presets/<pack>.json`; `--force` writes a
   `<pack>-v2` sibling (contract rule 3).
3. Built-in short-circuit: if the pack's system is one Atlas ships
   (`BUILTIN_SYSTEMS_0_6_0` — re-verify against the pinned release),
   write nothing and print "0.6.0 has Shadowdark built in — consider
   using it".
4. CLI: `publish.py <campaign> presets [--pack icrpg] [--force]
   [--dry-run]`.
5. Author `packs/icrpg/preset.json` — **values come from the table's
   house rules only** (icrpg DESIGN §13 checklist: dice, TN ladder,
   heart conventions, milestone cadence). No value is invented here;
   each knob's provenance goes in PACK.md.

## Acceptance criteria

- [x] Ported validator refuses deliberately-broken presets (wrong id
      prefix `builtin:`, missing rules keys, bad condition shapes) —
      pinned by `tests/test_presets.py` (discipline 5, README §7.5).
- [x] Refuse-on-diff and `--force` sibling semantics — pinned by
      `tests/test_presets.py`.
- [x] Built-in-system short-circuit writes nothing, message printed —
      pinned by `tests/test_presets.py`.
- [x] `preset.json` ships only when its values have PACK.md provenance
      lines (checkable by reading).

## Implementation notes (2026-10-11)

Landed on `feature/04-presets-publisher` (round 1: `9b2df20`, amended to
`8ede78d` with the review fix). All four criteria proven by the runs below.

**The validator port is stricter than Atlas's loader by design, in one
direction only.** Atlas either ignores a whole preset (fatal: bad
top-level shape, `builtin:` id, bad `gridDefaults`, `conditions` not a
list) or *silently drops/repairs* individual knobs (a bad widget entry
vanishes, `bright` past `dim` is clamped, an unknown icon falls back to
'star'). Both end the same way at the table — a knob the DM believes is
live but is not — so `validate_preset` refuses both, and never rejects
anything Atlas would use verbatim. Ported from `presetValidation.ts`
plus everything it reads through. The port was re-cloned fresh at the
pinned tag on 2026-10-11 (commit
`c5a9983003f40054caff8d6f394a09816ababa31`); the module docstring of
`src/avtt/presets.py` lists every file read. Cross-checked against
Atlas's own `senseValidation.test.ts` expectations.

**`BUILTIN_SYSTEMS_0_6_0` was corrected against the pinned release** —
the stub's guessed slugs were wrong. Atlas's built-in ids (the
`builtInPresetId(key)` keys, `builtInPresets.ts` + `presets/*.ts`) are
`cairn, coc7e, cyberpunkred, daggerheart, dnd5e, drawsteel, ose,
pathfinder2e, shadowdark`; the short-circuit matches the normalized
`campaign.yaml` `system:` against these, and the message uses each
preset's own display name.

**`preset.json` ships: it is a verbatim transcription of the table's
own hand-authored preset** — no value invented, satisfying the
"values come from the house rules only" gate. Source:
`dnd-campaign-generator/campaign-data/campaigns/ember-coast/atlas-vtt/
system-presets/icrpg-house.json` ("ICRPG (house)", no `builtIn` field —
hand-written by the DM into their live vault, recorded at campaigns-repo
commit `674043c`, 2026-10-10). Machine-checked JSON-value-identical to
the source; provenance for every knob (and for the two *by-absence*
checklist items — TN ladder and milestone cadence are not Atlas preset
knobs) is in `packs/icrpg/PACK.md`. Consequence of keeping the
table's id `icrpg-house`: in a vault that already carries the DM's
hand-made file, Atlas sees one preset (same id), and per
`SystemPresetFiles.entries()` the lower path (`icrpg-house.json`) wins —
the pack never clobbers the hand-made artifact.

**Install semantics** (contract rule 3): refuse-on-diff compares the
parsed preset body, ignoring the `format` envelope (Atlas does not
rewrite preset files behind us — unlike adopted records, ticket 01);
`--force` writes `<pack>-v2.json` and refuses again if *that* exists
and differs, so `--force` twice on a moved table ends in a refusal, not
a clobber. Written files match Atlas's own writer (`presetFiles.ts
presetText`): `format` first, 2-space JSON, trailing newline.

**Deviations from the proposal text:** none material. The gate (README
§5.2, core ticket 48) landed as pinned — `str(value).strip().lower()`
re-implemented in `publish.py campaign_system` (contract rule 4: this
line IS the shared definition), corrupt `campaign.yaml` refused rather
than defaulted, and the built-in short-circuit runs *after* the gate and
*before* the pack is loaded (no `packs/shadowdark/` needs to exist).

**Also in this change:** `publish.py` gained a hand-run bootstrap
(`python src/avtt/publish.py …` works from anywhere; the project is
never pip-installed); the smoke test's stub pins for `presets` moved to
`tests/test_presets.py` per its documented convention; the §7.5
discipline placeholder in `tests/test_disciplines.py` moved to its real
body; README §intro status line updated (first build landed).

**Verification.** Gates run in the worktree: `ruff check src tests
run-tests.py` — all checks passed; `run-tests.py --all` — 67 passed,
4 skipped (the four remaining golden-discipline placeholders, ticket 05
+ human fixture; the integration tier correctly skips with no captured
golden). Live CLI smoke outside pytest: dry-run plan → install (writes
`atlas-vtt/system-presets/icrpg.json`, format-first) → rerun
("already matches — nothing written") → `--pack shadowdark` in an
`icrpg` campaign refused with the pinned gate message.

**Left for the human:** nothing blocking. Two optional reviews: (a) the
transcribed values are the table's as of `674043c` — if any value has
since changed at the table, edit `packs/icrpg/preset.json` and note the
ruling in PACK.md; (b) the source's `measurementMode: "metric"` +
`unitType: "feet"` pairing and `bright == dim` lights were carried over
untouched and are valid per the 0.6.0 validator — flagged in PACK.md in
case the DM wants them revisited.

## Implementation notes (2026-10-11) — round-1 review fix

Reviewer found a real hole in `_validate_vision_defaults`, and the
original notes above over-claimed: the cross-check against Atlas's own
`senseValidation.test.ts` missed the line that pins the exact behavior
that leaked (its 'lets a list of senses, even an empty one, replace the
old fields' test, lines 129–135 of the pinned clone). Reproduced before
fixing: `validate_preset` passed
`defaultTokenVision: {senses: [], darkvision: 30}` with no failures,
while at the pinned release an empty `senses` list replaces the legacy
darkvision/tremorsense fields (an empty JS array is truthy, so
`visionDefaults.ts`'s `senses ? [] : OLD_SENSE_FIELDS` skips them) and
the whole section is ignored unless range/angle survive — the exact
knob-believed-live-but-not failure the ticket forbids. The residual
sibling (`{senses: [], darkvision: 30, range: 30}` — section survives on
`range`, `darkvision` silently dropped, per the same test's
`{darkvision: 60, range: 120, senses: []} → {range: 120}`) passed too.

Fix: the legacy fields are read/validated only when no `senses` list is
present at all (absent, or a value that is no list — a non-list reads
the old fields per `parseTokenSenses` returning undefined, pinned by the
same Atlas test with `senses: 'none'`); any present list, empty or not,
flags authored legacy numbers as ignored. Pinned by
`tests/test_presets.py::test_default_token_vision_legacy_fields_vs_senses_list`.
The shipped pack is unaffected (no `defaultTokenVision` at all).
Gates re-run after the fix: ruff all checks passed; `run-tests.py
--all` 68 passed, 4 skipped. **Accepted on reviewer sign-off 2026-10-11**;
status flipped to `completed` and the file moved to `archive/` in the
same change (this commit).
