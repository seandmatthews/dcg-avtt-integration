# 20 — checkout-lock staleness and same-ticket worktree collisions

**Status:** completed (2026-10-24, reviewer sign-off same day)
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

- [x] `maxAgeSec` is strictly less than the implementer's acquire
      timeout, with the invariant stated in a comment at both sites
      (checkable by reading `checkout-lock.ps1` and
      `avtt-ticket-implementer.dwf.ts`).
- [x] A corrupt lock file is stealable immediately (age reads as
      stale, not 0) — checkable by reading the `Get-AgeSeconds` failure
      path; verified by a hand-run recorded in Implementation notes
      (plant garbage in `locks/main.lock`, observe a fresh acquire
      succeed after the stale threshold, not never).
- [x] Worktree setup/cleanup for a stem runs under a per-stem lock; a
      second run for the same stem fails fast with a message naming
      the stem instead of removing the active worktree (checkable by
      reading; verified by a two-terminal collision check recorded in
      Implementation notes).
- [x] The implementer header states the concurrency scope honestly
      (checkable by reading).

## Implementation notes (2026-10-24)

Landed on `feature/20-lock-and-worktree-safety` as commit `ae57816`
(2026-10-24); the reviewer signed off the same day and the branch's last
commit was amended with the status flip and this archive move. Every
criterion is proven by the recorded runs and reads below — nothing was
left for a human. Two deliberate deviations from the proposal's wording,
both documented in place: the *read*-failure path of `Get-AgeSeconds`
stays age-0 (only the *parse*-failure path goes infinitely old), and the
lock script is held to pure ASCII after the hand-run found the
powershell.exe 5.1 ANSI-parse failure.

- `checkout-lock.ps1`: `$maxAgeSec` 3600 → 1500 with the one-contract
  invariant comment at the constant; `Get-AgeSeconds` now separates two
  failure paths — unreadable-right-now (a live holder's
  `FileShare::None` write window) still reads as 0/fresh so the steal
  never races a mid-write holder, while readable-but-corrupt/empty
  content reads as `[double]::PositiveInfinity`, stealable immediately.
  `status` special-cases the infinite age instead of letting the `[int]`
  display cast throw. Deliberate narrowing of the proposal's wording:
  only the *parse*-failure path goes infinitely old; the *read*-failure
  path stays fresh, since unreadable has a live-holder cause.
- `avtt-ticket-implementer.dwf.ts`: `lockStem`/`unlockStem` acquire
  `stem-<stem>` with a 60 s timeout; the guard sits before the
  branch/worktree setup and the lock is held to the post-merge cleanup
  (released at exactly two exits: the flagged setup return and after
  cleanup), so a held stem lock means the workspace is owned for the
  whole run — a same-ticket double start fails fast naming the stem,
  never `remove --force` under it. The main-lock wait's comment states
  the invariant (1800 s wait > 1500 s steal age); the header and
  whenToUse now say "several *different* tickets concurrently; the same
  ticket refuses to double-start". The main-lock discipline itself is
  unchanged, as the proposal requires.
- Tests: `tests/test_lock_safety.py` pins all four criteria at the
  repo's text-read discipline (the two scripts are PowerShell /
  TypeScript the pytest suite cannot execute, and CI's ubuntu leg has
  neither runtime), plus `test_lock_script_is_pure_ascii`.
- Hand-runs (against the worktree's fixed script; the production main
  checkout's lock state was never touched — the old-script control ran
  on a copy in `%TEMP%`):
  - Corrupt `locks/main.lock`: with garbage planted, `status` reports
    "held (corrupt stamp - reads as infinitely old, stealable)" and a
    fresh `acquire main 30` stole it in **0.22 s** (exit 0; the file
    then holds a fresh ISO stamp; `release` returns "free"). Negative
    control, pre-fix script + same garbage + `acquire main 5`: polled
    its whole timeout, "TIMEOUT: lock 'main' still held after 5s",
    exit 1 — the old "never". (The steal is *immediate*, not merely
    "after the stale threshold": corrupt reads as infinitely old, so
    no threshold wait applies; the age threshold itself is proven by
    the next run.)
  - Threshold boundary: a 10-min-old stamp (600 s < 1500 s) is
    respected (`acquire main 3` → TIMEOUT, exit 1); a 26-min-old stamp
    (1560 s > 1500 s) is stolen by the next acquire in 0.23 s.
  - Two-terminal stem collision: terminal A `acquire
    stem-20-lock-and-worktree-safety 60` → exit 0 (holds); terminal B,
    the same acquire with the 5 s probe, polled 5 s then "TIMEOUT:
    lock 'stem-20-lock-and-worktree-safety' still held after 5s",
    exit 1 — the exact signal `lockStem` turns into the fail-fast
    abort naming the stem. (The lock is held by file existence, so two
    separate shells contend exactly as two workflow runs would.)
  - Found *by* the hand-run and fixed: an em dash inside the new
    status string broke powershell.exe 5.1's ANSI read of the BOM-less
    script (the UTF-8 bytes decode to a `"` mid-string and the parse
    dies); the script is back to pure ASCII, now pinned by
    `test_lock_script_is_pure_ascii`.
