# 20 — checkout-lock staleness and same-ticket worktree collisions

**Status:** proposed
**Priority:** P2 — the automation loop AGENTS.md depends on has failure
modes that need human surgery exactly when it is meant to run unattended
**Area:** `.zcode/tools/checkout-lock.ps1`,
`.zcode/workflows/avtt-ticket-implementer.dwf.ts`
**Found by:** full adversarial review, 2026-10-23

## Problem

**1. A crashed run poisons the loop for up to an hour.** The lock's
steal threshold is `maxAgeSec = 3600` (`checkout-lock.ps1:31`) but the
implementer only waits 1800s to acquire
(`avtt-ticket-implementer.dwf.ts:146`, `"acquire", "main", "1800"`).
A waiter may steal a lock only once its age crosses 3600s
(`checkout-lock.ps1:57`) — past its own give-up point. So a lock left
behind by a crashed run simply cannot be stolen until it is an hour
old, and every implementer run in that window burns its full 30-minute
timeout and fails ("could not acquire the shared main-checkout lock
within 30 min"). Worse, `Get-AgeSeconds` returns 0 on any parse
failure (`checkout-lock.ps1:40-42`), so a corrupt or unreadable lock
file never goes stale — a permanent block until someone hand-deletes
`.zcode/tools/locks/main.lock`.

**2. Two runs of the same ticket destroy each other's worktrees.** The
implementer serializes only its main-checkout sections under the lock;
the worktree/branch setup and cleanup run outside it
(`avtt-ticket-implementer.dwf.ts:302` stem→worktree, `:319`
`worktree remove --force`, `:321` `worktree add -B`, and the post-merge
cleanup at `:505-507`). Two concurrent runs for ticket *NN* share one
stem and therefore one worktree: the second run's
`worktree remove --force` deletes the first run's active workspace
mid-flight. The workflow header's "Safe to run several tickets
concurrently" (`:13-14`) is true for *different* tickets and silent
about the same-ticket case.

## Proposal

1. **Make the steal window actually reachable:** lower `maxAgeSec`
   below the acquire timeout (e.g. 1500s, so a waiter that has waited
   25 minutes can steal a lock 25 minutes old), and state the
   invariant in a comment where both constants live: *steal age must be
   strictly less than the longest acquire wait* — the two numbers are
   one contract, not two knobs. Corrupt/unparseable lock content
   (`Get-AgeSeconds`' failure path) reads as infinitely old — stealable
   immediately — instead of age 0.
2. **Guard the per-stem setup/cleanup** the same way the main checkout
   is guarded: a per-stem lock (e.g.
   `.zcode/tools/locks/stem-<stem>.lock`) held across the
   worktree-setup and worktree-cleanup sections, acquired with a short
   timeout; a held stem lock means another run owns that ticket's
   workspace — fail fast with a plain message naming the running stem,
   never `remove --force` under it. The implementer header's safety
   claim gains the honest scope: "several *different* tickets
   concurrently; the same ticket refuses to double-start".

No change to the main-lock discipline itself (what it serializes stays
as is) — this ticket is the staleness math and the stem guard only.

## Acceptance criteria

- [ ] `maxAgeSec` is strictly less than the implementer's acquire
      timeout, with the invariant stated in a comment at both sites
      (checkable by reading `checkout-lock.ps1` and
      `avtt-ticket-implementer.dwf.ts`).
- [ ] A corrupt lock file is stealable immediately (age reads as
      stale, not 0) — checkable by reading the `Get-AgeSeconds` failure
      path; verified by a hand-run recorded in Implementation notes
      (plant garbage in `locks/main.lock`, observe a fresh acquire
      succeed after the stale threshold, not never).
- [ ] Worktree setup/cleanup for a stem runs under a per-stem lock; a
      second run for the same stem fails fast with a message naming
      the stem instead of removing the active worktree (checkable by
      reading; verified by a two-terminal collision check recorded in
      Implementation notes).
- [ ] The implementer header states the concurrency scope honestly
      (checkable by reading).

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
