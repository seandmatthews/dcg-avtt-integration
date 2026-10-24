# 19 — the ticket workflows must not hardcode one machine's paths

**Status:** proposed
**Priority:** P2 — the repo is public (since 2026-10-21); the documented
ticket loop points at one physical machine, or worse at whatever lives
at that path on a stranger's machine
**Area:** `.zcode/workflows/avtt-ticket-forge.dwf.ts`,
`.zcode/workflows/avtt-ticket-implementer.dwf.ts`, `AGENTS.md` (only if
its description of the workflows needs the same correction)
**Found by:** pre-publication audit 2026-10-20 (left open); re-found
with blast-radius analysis by the full adversarial review, 2026-10-23

## Problem

Both saved workflows hardcode the owner's machine:

- `avtt-ticket-forge.dwf.ts:40` and
  `avtt-ticket-implementer.dwf.ts:44`:
  `const ROOT = "C:/Users/matth/Documents/dcg-avtt-integration"` — the
  only three tracked `git grep -n "matth"` hits.
- `avtt-ticket-implementer.dwf.ts:45`:
  `const WT_BASE = "C:/Users/matth/Documents/dcg-avtt-wt"`.

Consequences for anyone else (and for the owner after any path change):
every run of the loop AGENTS.md presents as *the* way tickets happen
operates on a nonexistent directory — or on whatever happens to exist
at that path, which for an agent-driven merge pipeline is not a
graceful failure mode. The forge additionally assumes the **private**
sibling `../dnd-campaign-generator` exists (`avtt-ticket-forge.dwf.ts:132`:
a grounding step reads it for campaign-generator claims) with no
existence check or fallback — on a stranger's machine the grounding
step either blocks or invites fabrication.

## Proposal

1. Derive `ROOT` from the environment instead of a literal. Mechanism
   hint (added 2026-10-24, from the implementer runs' observed behavior):
   the dynamic-workflows `world.run` executes with its cwd at the
   *workspace* — the repo root this run was started from — so
   `git rev-parse --show-toplevel` (no `-C`) yields `ROOT` at runtime;
   deriving from the script file's own path may not be possible inside
   the facade (the running script lives in a session draft directory,
   not necessarily in the repo). `WT_BASE` then derives from `ROOT`'s
   parent: `<ROOT-parent>/dcg-avtt-wt` (sibling of the repo, matching
   the current layout). If the implementer finds a cleaner mechanism
   the facade supports, land it — the criterion is no hardcoded
   per-user path, not a specific derivation.
2. The forge's grounding step checks the sibling exists before reading
   it; when absent it grounds only in-repo claims and says so in its
   output (a stranger's forge run must not fabricate grounding for a
   repo it cannot read).
3. Keep everything else untouched — the lock discipline, gates and
   merge flow are ticket 20's concern, not this one. One lane, one
   change: paths only.

## Acceptance criteria

- [ ] `git grep -n "C:/Users" -- .zcode/workflows/` returns nothing
      after the change (checkable claim).
- [ ] `ROOT`/`WT_BASE` are derived from the script's own location /
      the repo's parent, with the derivation visible in the two files
      (checkable by reading).
- [ ] The forge's campaign-generator grounding step checks existence
      and degrades to in-repo grounding with a stated reason
      (checkable by reading).
- [ ] A dry confirmation run of each workflow (or the implementer's
      plan stage) from the current machine behaves exactly as before —
      same repo, same worktree base (recorded in Implementation notes).

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
