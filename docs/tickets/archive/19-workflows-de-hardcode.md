# 19 — the ticket workflows must not hardcode one machine's paths

**Status:** completed (implemented + reviewer sign-off 2026-10-24 on
pre-flip commit `3d84f13`; this flip and the `archive/` move are folded
into the branch's single commit by amending)
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

- [x] `git grep -n "C:/Users" -- .zcode/workflows/` returns nothing
      after the change (checkable claim).
- [x] `ROOT`/`WT_BASE` are derived from the script's own location /
      the repo's parent, with the derivation visible in the two files
      (checkable by reading).
- [x] The forge's campaign-generator grounding step checks existence
      and degrades to in-repo grounding with a stated reason
      (checkable by reading).
- [x] A dry confirmation run of each workflow (or the implementer's
      plan stage) from the current machine behaves exactly as before —
      same repo, same worktree base (recorded in Implementation notes).

## Implementation notes (2026-10-24)

Landed on `feature/19-workflows-de-hardcode` (worktree
`19-workflows-de-hardcode`) as one commit, `3d84f13` pre-amend;
reviewer sign-off 2026-10-24 — this status flip and the `archive/` move
are amended into that same commit. One lane, paths only. No criterion
was left for a human: all four are pinned by the recorded evidence
below (criterion 4 by the plan-stage confirmation, with its honesty
caveat stated where it is recorded).

**The mechanism (both scripts).** `ROOT` is derived at runtime from the
run's workspace: `await world.run("git", ["rev-parse", "--show-toplevel"])`
(no `-C`; the facade's `world.run` executes with its cwd at the workspace —
the repo root the run was started from), trimmed and backslash-normalized.
If the probe fails, the script aborts before any work with the probe's
exit code and stderr in the report — a loud stop, not an operation on a
wrong path. In the implementer, `WT_BASE` is then `ROOT`'s parent +
`/dcg-avtt-wt` (`ROOT.slice(0, parentSlash) + "/dcg-avtt-wt"`), matching
the documented sibling layout (AGENTS.md: `../dcg-avtt-wt/`). The forge
derives `CG_DIR` the same way for the grounding sibling.

**The forge's grounding leg.** Before the writer is ever pointed at the
campaign-generator repo, the script probes it (`git -C <CG_DIR>
rev-parse --show-toplevel`). When the probe fails, the writer prompt
degrades: ground ONLY in-repo claims, make no campaign-generator claim,
and write the campaign-generator side as something the ticket must
establish on a machine that has the repo ("named explicitly there as
unverified here"); the run log states the degradation. When the probe
succeeds, the prompt is as before, now with the absolute derived path.
The reviewer's independent ATLAS/campaign-generator check is untouched —
it stays strict, so an ungrounded claim still blocks.

**Confirmation (criterion 4 — the plan stage, recorded here).** From the
main-checkout cwd a run starts from (`C:/Users/matth/Documents/
dcg-avtt-integration`), 2026-10-24: `git rev-parse --show-toplevel` →
`C:/Users/matth/Documents/dcg-avtt-integration` — identical to the
formerly hardcoded `ROOT`; its parent + `/dcg-avtt-wt` →
`C:/Users/matth/Documents/dcg-avtt-wt` — identical to the formerly
hardcoded `WT_BASE`; the sibling probe `git -C ../dnd-campaign-generator
rev-parse --show-toplevel` exits 0 (`C:/Users/matth/Documents/
dnd-campaign-generator`), so a forge run on this machine grounds
campaign-generator claims exactly as before. Honesty note: the
dynamic-workflows snippet bench (`EvalWorkflowSnippet`) was unavailable
inside the implementer session (the `dynamic-workflows` skill is not
loadable there), so the implementer did not execute `world.run` itself;
the world.run-cwd-is-the-workspace fact is the ticket's own mechanism
hint (added 2026-10-24 from prior implementer runs' observed behavior),
corroborated by this run's workspace-relative `files.glob`/`files.read`
calls. The derivation failure guard converts any environment where that
assumption breaks into the loud abort described above. Neither script
was compiled standalone (no tsc in the sandbox; the facade compiles both
scripts when the next run is created) — the syntax follows the proven
`world.run`/`satisfies` patterns already in these files.

**Verification added.** `tests/test_workflows.py` (house text-pin
discipline): runs the criterion's exact grep; asserts no `C:/Users` and
no `const ROOT|WT_BASE = "C:` literal in either script; asserts the
`rev-parse` derivation and the `ROOT === ""` abort guard in both;
asserts the implementer's parent-slice WT_BASE derivation; asserts the
forge probes the sibling before the grounding instruction and that the
degraded path states the reason, restricts grounding to in-repo claims,
and names the gap. Gates run in the worktree 2026-10-24: ruff "All
checks passed"; `run-tests.py --all` — ruff PASS, avtt 272 passed (6 of
them the new tests, run individually with `-v`), avtt-golden 2 passed.

**Not changed, deliberately.** The lock discipline, gates and merge flow
(ticket 20's lane); the reviewer's grounding check (kept strict); AGENTS.md
(its only path mention is the relative `../dcg-avtt-wt/`, which matches
the new derivation — no correction needed); `docs/tickets/19-*` quoting
the old literals in its Problem block (a ticket's evidence stays true of
the past).
