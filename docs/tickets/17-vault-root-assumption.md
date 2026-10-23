# 17 — state and check the campaign-is-the-vault-root assumption

**Status:** proposed
**Priority:** P2 — a nested campaign silently degrades forever, with a
message that blames the manifest instead of the layout
**Area:** `src/avtt/_version.py`, `src/avtt/publish.py`
(`run_scenes`, `_run_scenes_degraded`), `tests/test_scenes.py`,
README §5.1
**Found by:** full adversarial review, 2026-10-23

## Problem

Version detection reads
`<campaign>/.obsidian/plugins/atlas-vtt/manifest.json`
(`_version.py:32` `MANIFEST_RELPATH`), and every write targets
`<campaign>/atlas-vtt/`. Both only work when the campaign directory
**is** the Obsidian vault root — an assumption the README never states.
If the campaign lives nested inside a vault (say
`<vault>/campaigns/ember-coast/`), detection always returns `"unknown"`
→ pin mismatch → `run_scenes` takes the `_inbox/` degrade path
(`publish.py:486-498`) **on every run**, even though the vault runs the
pinned Atlas; and the mismatch message (`atlas-pin-mismatch:
…detected=unknown`) blames a missing manifest the DM will go looking
for, when the actual problem is the directory layout. The write side is
quietly broken too: `<campaign>/atlas-vtt/` nested inside a vault is
not where Atlas looks.

Nothing detects or explains this; the failure mode is a permanently
degraded publisher and a confused DM.

## Proposal

1. **README §5.1 states the assumption** in the degrade-path paragraph:
   the campaign directory must be the Obsidian vault root — this repo
   reads its plugin manifest and writes its `atlas-vtt/` at the
   campaign's top level (one sentence; the constitution rule makes even
   the undocumented state a same-day fix candidate, but the behavior
   change below rides the same ticket).
2. **Distinguish "no vault here" from "vault runs another version"**:
   when `detect_atlas_version` returns `"unknown"` *and* the campaign
   has no `.obsidian/` directory at all, the degrade message says so in
   plain words — e.g. "no `.obsidian/` under `<campaign>` — scenes
   assumes the campaign directory is the Obsidian vault root; a nested
   campaign cannot publish scenes". Detection stays non-raising and
   never writes (`_version.py`'s contract); `run_scenes` just prints
   the honest line before the degrade behavior. A campaign that *has*
   `.obsidian/` but an unreadable manifest keeps today's message (a
   vault with a broken plugin install is a different problem).
3. No behavior change beyond the message: degrade remains the safe
   action (refusing outright would also be defensible, but the degrade
   path already refuses to write `.atlasmap` files, which is the harm
   being guarded).

## Acceptance criteria

- [ ] A campaign without `.obsidian/` gets the plain-words vault-root
      message (plus the existing mismatch line and `_inbox/` behavior)
      — pinned by a new
      `tests/test_scenes.py::test_degrade_message_names_vault_root_when_no_obsidian_dir`
      (asserting the fragment; the inbox copy still happens).
- [ ] A campaign with `.obsidian/` but an unreadable manifest keeps
      today's unknown-mismatch behavior and message — pinned by the
      existing degrade tests (no change).
- [ ] README §5.1 states the vault-root assumption (checkable by
      reading).

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
