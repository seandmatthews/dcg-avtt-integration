# 21 — capture-golden robustness: the CDP port collision, and lint the tools

**Status:** completed (implemented + reviewer sign-off 2026-10-24 on
pre-flip commit `ed4d1e3`; this flip and the `archive/` move are folded
into the branch's single commit by amending)
**Priority:** P3 — low-probability, destructive blast radius (can drive
the owner's real Obsidian), plus silent bit-rot of the one tool the §8
procedure depends on
**Area:** `tools/capture-golden.py`, `run-tests.py` (lint command),
`.github/workflows/ci.yml` (lint step), README §4 (tools/ appears in
the layout)
**Found by:** full adversarial review, 2026-10-23

## Problem

**1. A port collision can drive the owner's live Obsidian.**
`tools/capture-golden.py:36` hardcodes `CDP_PORT = 9223`. If anything
else already binds that port — including the owner's own Obsidian
launched with remote debugging on 9223 — the isolated instance the
tool launches fails to bind it (Chromium's behavior when the debug port
is taken) and `cdp_targets()` (`:110`) then talks to the **other**
instance; the `app://` filter (`:127`) does not distinguish instances.
The tool would click the vault-trust modal, open the asset manager and
dispatch the `sample.uvtt` drop *in the owner's live vault*, then exit
4 complaining no golden appeared. The kill function only matches
processes whose command line carries `avtt-golden-capture`
(`:44-48`), so the foreign instance is never stopped. Since ticket 08
this tool is the §8 procedure's only human-free step — it runs
unattended during pin bumps, which is exactly when nobody is watching
it click things.

**2. The tool can bit-rot invisibly.** `ruff check src tests
run-tests.py` (both `run-tests.py` and `ci.yml:40-42`) omits `tools/`,
and no test executes any of `tools/` — so between pin bumps (the only
times it runs) a syntax error or an undefined name can land with every
gate green.

## Proposal

1. **Refuse a taken port before launching:** bind-test 9223 (a
   stdlib `socket` connect/listen probe) and exit with a plain-words
   message naming the port and what likely holds it, before any
   Obsidian is launched. Optionally go further and verify the CDP
   endpoint belongs to the process the tool spawned (e.g. compare the
   browser pid from `/json/version` against the launched pid) — the
   implementer picks the depth; the floor is the pre-flight refusal.
2. **Bring `tools/` under the lint gate:** add it to the ruff command
   in `run-tests.py` and `ci.yml` (`ruff check src tests run-tests.py
   tools`). No runtime test is proposed — the tool drives a real
   desktop app; its exercise is the next §8 bump, and ticket 16's
   capture run is the natural first proof after this lands.
3. README §4's layout gains the one-line `tools/` entry
   (`tools/capture-golden.py` — the golden capture automation) so the
   constitution's layout block names the directory the gates now lint.

## Acceptance criteria

- [x] With something already listening on the CDP port (simulated by a
      dummy listener), `capture-golden.py` exits before launching
      Obsidian, with a plain-words message naming the port — verified
      by a hand-run recorded in Implementation notes (the listener
      killed after; nothing published).
- [x] `run-tests.py` and `ci.yml` lint `tools/` (checkable by reading;
      `ruff check src tests run-tests.py tools` clean).
- [x] README §4's layout names `tools/` (checkable by reading).
- [ ] The next real capture (ticket 16's, or whichever lands first)
      runs green through the hardened tool — cross-referenced in that
      ticket's Implementation notes when it happens.

## Implementation notes (2026-10-24)

Landed on `feature/21-capture-golden-robustness` (worktree
`21-capture-golden-robustness`) as one commit, `ed4d1e3` pre-amend;
reviewer sign-off 2026-10-24 — this status flip and the `archive/` move
are amended into that same commit.

- **Pre-flight refusal (criterion 1).** `cdp_port_taken()` in
  `tools/capture-golden.py` connect-probes `127.0.0.1:<CDP_PORT>` after
  `cdp_kill_our_obsidian()` and its settle sleep, before `build_vault()`
  and any launch; taken → plain-words refusal naming the port, exit 2.
  Two deliberate deviations from the proposal's sketch (both documented
  in comments at the function):
  - *Connect probe, not a bind probe.* The check runs right after
    killing our own leftover instance; on Windows a just-killed listener
    can leave TIME_WAIT sockets that still block a plain bind, which
    would false-refuse the automated §8 run. A connect only succeeds on
    a live listener — exactly the collision that matters, since the
    launched Chromium binds its devtools server on 127.0.0.1 too.
  - *Floor depth; the `/json/version` pid check is not implementable as
    sketched.* The DevTools HTTP endpoint exposes no pid
    (`/json/version` carries Browser/protocol fields only), and a
    process-table cross-check would prove only that our instance is up,
    not that it holds the port (a failed-bind instance stays alive) —
    false confidence in a safety check. The refusal closes the real
    scenario (a holder present before launch); the residual race (a
    foreign process binding 9223 inside the seconds-wide launch window)
    is left open, per the ticket's "the implementer picks the depth; the
    floor is the pre-flight refusal".
  - Hand-run record (2026-10-24, this worktree): dummy stdlib listener
    bound `127.0.0.1:9223` (netstat confirmed LISTENING, pid 20844);
    `python -m uv --directory <worktree> run --with websocket-client
    tools/capture-golden.py 0.9.1` → exit 2 and on stderr: "port 9223 is
    already taken — refusing to launch anything. …" — with no
    "building vault"/"launching" lines, i.e. the exit happens before any
    Obsidian launch. The listener was killed afterwards; netstat
    confirms 9223 free again, no Obsidian.exe running, nothing
    published (no fixture written).
- **Lint gate (criterion 2).** Deviation from the problem statement:
  `run-tests.py` carried no ruff command at all (the lint line lived
  only in `ci.yml` and ad-hoc invocations), so bringing `tools/` under
  `run-tests.py` meant adding a lint suite, not extending one:
  `LINT_SUITES` runs `python -m ruff check src tests run-tests.py tools`
  first in both tiers; its docstring notes the suite needs the dev
  group's ruff (installed from the lock by every supported invocation)
  and fails loudly, never skips, under a bare interpreter. `ci.yml`'s
  lint step is now `uv run ruff check src tests run-tests.py tools`.
  `tests/test_ci.py::test_ci_lint_covers_tools` pins both files (the
  ticket proposed no runtime test of the tool; this is a config pin).
- **README §4 (criterion 3).** The layout gains the `tools/` entry; the
  `run-tests.py` layout line now mentions the lint stage (README and
  code move together — the constitution's rule).
- **Gates, run in this worktree:** `ruff check src tests run-tests.py`
  (the workflow's command) — clean; `ruff check src tests run-tests.py
  tools` — clean; `run-tests.py --all` — ruff PASS, 255 passed / 1
  skipped (the skip is the pre-existing optional `sample-lit` capture,
  unrelated), avtt-golden PASS.
- **Criterion 4 stays open for a human** — its proof is the next §8
  bump's capture run through the hardened tool, cross-referenced in that
  ticket's Implementation notes when it happens; a real capture needs
  the owner's desktop Obsidian, so an agent cannot produce it. Ticket
  16's capture (2026-10-23) predates this hardening and cannot serve.
