# 11 — presets: refuse the shadowed write when another file owns the preset id

**Status:** completed (implemented + reviewer-signed-off 2026-10-23, this commit, branch `feature/11-presets-id-shadowing`)
**Priority:** P1 — breaks the documented DM edit-loop on the home table:
the installer reports success for a file Atlas will never read
**Area:** `src/avtt/presets.py` (`install`/`target_state`),
`src/avtt/publish.py` (`run_presets`), `tests/test_presets.py`,
`packs/icrpg/PACK.md` (one-line sync)
**Found by:** full adversarial review, 2026-10-23 — reproduced live (below)

## Problem

Atlas keys system presets by the `id` inside the file, never the path,
and keeps the **first** file per id (`presetFiles.ts`; recorded in the
`presets.py` module docstring, lines 32-37). The ICRPG pack preset is a
verbatim transcription of the DM's hand-made `icrpg-house.json` — **same
id** — and `icrpg-house.json` sorts before `icrpg.json`, so on the home
vault the hand-made file wins forever (`packs/icrpg/PACK.md:32-40`
documents the ordering, framing it as "one preset to Atlas").

The consequence PACK.md misses: the documented workflow "the DM edits
values **here** (in the pack) from now on; the installer is the only
writer" cannot work on that vault. The DM edits the pack, reruns
`presets`, is told `wrote …icrpg.json` — and the table never changes,
because Atlas keeps reading `icrpg-house.json`. That is verbatim this
repo's own definition of the worst failure mode (`presets.py:23-30`: "a
knob the DM believes is live but is not").

**Live repro (2026-10-23, temp campaign, deleted after):** planted
`atlas-vtt/system-presets/icrpg-house.json` (same id as the pack, a
stale-name variant) beside nothing; ran `publish.py <campaign> presets`
→ `wrote …system-presets\icrpg.json`, exit 0, no warning. Two files,
one id; the stale one keeps winning by sort order; the installer's
refuse-on-diff checks only `<stem>.json` (`presets.py:760-767`
`target_state`), so it cannot notice.

## Proposal

After validation, before writing, scan the target
`system-presets/` directory (when it exists) for **other** `.json`
files whose parsed `id` equals the pack's id:

- If another same-id file **sorts before** the intended target: this is
  the shadowed write — the pack file would be inert. **Refuse** with
  plain words naming both files: e.g. "not writing `icrpg.json`:
  `icrpg-house.json` already carries id `icrpg-house` and sorts first,
  so Atlas would keep reading it — delete or rename the old file, or
  edit it by hand". Exit 2, nothing written. This matches the repo's
  strictness contract: never write something Atlas will not use exactly
  as authored.
- If another same-id file sorts **after** the target: our file is the
  live one but the other is dead weight that will resurface if ours is
  ever removed — print a one-line **warning** (not a refusal) naming it.

Sort order is the byte order of file names, the order `presetFiles.ts`
enumerates — the same fact PACK.md already records. Keep the check
cheap: it runs once over the (small) directory, only at install time.

PACK.md's shadowing paragraph gains the operational sentence: the
installer refuses the shadowed write, so the stale hand-made file must
be deleted once — then the pack is the single source. README §5.2 needs
no change (the refusal *is* §5.2's "never write a pack into a campaign
that did not ask for it" spirit extended to "never write a preset Atlas
cannot use").

## Acceptance criteria

- [x] A same-id sibling sorting before the target is refused with a
      plain-words message naming both files; nothing is written — pinned
      by `tests/test_presets.py::test_shadowed_write_is_refused`.
- [x] A same-id sibling sorting after the target installs with a
      one-line warning naming the dead-weight file — pinned by
      `tests/test_presets.py::test_shadowing_write_warns`.
- [x] The live repro from Problem now refuses (recorded in
      Implementation notes; temp deleted).
- [x] `packs/icrpg/PACK.md` states the one-time deletion of the stale
      hand-made file (checkable by reading).

## Implementation notes (2026-10-23)

Landed as the branch's single feat(11) commit on
`feature/11-presets-id-shadowing` (this commit — the completed status
flip and the `archive/` move are folded into it after reviewer
sign-off). `presets.same_id_siblings`
scans `system-presets/` for other files carrying the pack's id and
splits them by sort order; `presets.install(..., warnings=[...])`
raises `PresetRefused` on a file sorting before the effective target
(plain stem, or the `-v2` sibling after `--force`) and appends one
plain-words line per dead-weight file; `publish.run_presets` prints the
notes after the outcome line, `_dry_run_plan` mirrors the refusal ("would
REFUSE", exit 2). `target_state` itself is unchanged — its stem-only
view is correct for its job; the neighborhood scan is the new function.

Source re-verified before implementing (AGENTS.md rule; fresh clone of
tag 0.8.0): `RecordFiles.ts` `entries()` keeps "the first file per id
by path" and `holders()` is a plain path sort (UTF-16 code units; the
presets layout sets no `namedHolds` — `RecordFolderFiles.ts`
`folderLayout`); `recordFolder.ts` `isRecordPath` admits `.json` files
case-insensitively in subfolders too and `readFolder` recurses;
`readRecordText`/`isStoredRecord` define "carries an id": a JSON object
with a non-blank `id` outside `builtin:`.

Deliberate decisions beyond the proposal's letter, each pinned by a
test:

- **The scan recurses** into subfolders of `system-presets/`: Atlas
  reads them (`isRecordPath` + `readFolder`), so a same-id file below a
  subfolder shadows by full-path order the same way —
  `test_same_id_file_in_a_subfolder_is_seen`.
- **The refusal also covers the already-matching target**: a rerun that
  would report "already matches — nothing written" beside an
  earlier-sorting same-id file is the same lie (the pack file is
  inert), so the shadow check runs before any success return —
  `test_shadowed_write_refuses_even_when_target_already_matches`.
- **Rule 3 fires first**: a differing target refuses on diff before the
  shadow check; after `--force` moves the write to the sibling, the
  shadow check applies to the sibling (a shadowed `-v2` is refused
  too).
- **Docstring corrected**: the module docstring claimed "a `-v2`
  sibling never overrides the original" — wrong at this pin. The path
  sort includes the extension, and hyphen (0x2D) sorts before dot
  (0x2E), so `icrpg-v2.json` sorts *before* `icrpg.json`: with the same
  id in both, the sibling is the live one. `--force` over a same-id
  differing original therefore installs, the original becoming dead
  weight (warned) — `test_force_sibling_is_dead_weight_not_shadow_when_ids_match`.
  The README makes no such claim (§2 rule 3 and §5.2 unaffected).
- **Foreign files never crash the scan**: broken JSON, non-UTF-8 bytes,
  a missing id and a `builtin:` id all carry no preset and do not
  shadow — `test_foreign_files_do_not_shadow`.

Live repro rerun (2026-10-23, temp campaign under `%TEMP%`, deleted
after, deletion verified): planted
`atlas-vtt/system-presets/icrpg-house.json` (same id as the pack) →
`refusing: not writing icrpg.json: icrpg-house.json already carries id
icrpg-house and sorts first, so Atlas would keep reading it — delete or
rename the old file, or edit it by hand`, exit 2, `icrpg.json` not
written. After deleting the stale file once: `wrote
…\atlas-vtt\system-presets\icrpg.json`, exit 0.

`packs/icrpg/PACK.md`'s shadowing paragraph now states the refusal and
the one-time deletion (its old "leaves both in place" sentence
described the pre-ticket behavior and was rewritten in the same
change). Gates: `ruff check src tests run-tests.py` — all checks
passed; `run-tests.py --all` — fast tier 161 passed + 1 skipped,
golden tier passed.
