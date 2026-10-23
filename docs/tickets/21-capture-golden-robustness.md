# 21 — capture-golden robustness: the CDP port collision, and lint the tools

**Status:** proposed
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

- [ ] With something already listening on the CDP port (simulated by a
      dummy listener), `capture-golden.py` exits before launching
      Obsidian, with a plain-words message naming the port — verified
      by a hand-run recorded in Implementation notes (the listener
      killed after; nothing published).
- [ ] `run-tests.py` and `ci.yml` lint `tools/` (checkable by reading;
      `ruff check src tests run-tests.py tools` clean).
- [ ] README §4's layout names `tools/` (checkable by reading).
- [ ] The next real capture (ticket 16's, or whichever lands first)
      runs green through the hardened tool — cross-referenced in that
      ticket's Implementation notes when it happens.

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
