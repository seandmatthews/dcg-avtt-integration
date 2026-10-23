# 11 — presets: refuse the shadowed write when another file owns the preset id

**Status:** proposed
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

- [ ] A same-id sibling sorting before the target is refused with a
      plain-words message naming both files; nothing is written — pinned
      by `tests/test_presets.py::test_shadowed_write_is_refused`.
- [ ] A same-id sibling sorting after the target installs with a
      one-line warning naming the dead-weight file — pinned by
      `tests/test_presets.py::test_shadowing_write_warns`.
- [ ] The live repro from Problem now refuses (recorded in
      Implementation notes; temp deleted).
- [ ] `packs/icrpg/PACK.md` states the one-time deletion of the stale
      hand-made file (checkable by reading).

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
