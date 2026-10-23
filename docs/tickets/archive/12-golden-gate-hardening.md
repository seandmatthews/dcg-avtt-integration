# 12 — the golden gate must fail, never skip, when the pin's fixture is missing

**Status:** completed (implemented + reviewer-signed-off 2026-10-23, this commit, branch `feature/12-golden-gate-hardening`)
**Priority:** P1 — the §8 churn procedure's whole definition of
"breaking" is "the golden test passes or the fix is a milestone"; a gate
that can pass without running is no gate
**Area:** `tests/test_scenes.py`, `tests/test_pin.py`, `run-tests.py`,
`fixtures/golden-0.6.0/README.md` (stale line), README §7/§8 where the
mechanism is described
**Found by:** full adversarial review, 2026-10-23

## Problem

Three cooperating holes let a pin bump merge with **zero** golden
verification while every gate prints green:

1. **A missing golden is a skip, not a failure.**
   `tests/test_scenes.py:396-399` guards `test_golden_file` with
   `@pytest.mark.skipif(not GOLDEN.is_file(), …)` — the fixture's
   absence makes the load-bearing test vanish quietly (exits 0). The
   skip was honest in ticket 05's era, when the capture needed a human;
   since ticket 08 the capture is automated and lands in the same
   change, so the only state in which the skip fires is the broken one.
2. **Pin integrity accepts a placeholder.**
   `tests/test_pin.py:51-55` `test_atlas_pin_matches_fixtures` asserts
   only `golden.is_dir()` — a README-only directory passes, which is
   exactly the documented intermediate shape
   (`fixtures/golden-0.6.0/README.md` still says "Empty until a human
   captures the fixture" even though `golden-0.6.0/sample.atlasmap`
   exists and is tracked — the stale line proves how long placeholders
   live).
3. **The `--all` guard accepts any golden.**
   `run-tests.py:59-66` globs `golden-*/sample.atlasmap` — with 0.6.0
   and 0.7.1 committed, the integration tier is selected even when the
   *pin's own* fixture is missing, so `--all` reports "all suites
   passed" over a suite that skips the pin.

Concrete scenario: a bump to 0.9.x lands `golden-0.9.x/README.md` but
no capture → `test_atlas_pin_matches_fixtures` passes (dir exists),
`test_golden_file` skips, `run-tests.py --all` green, CI green. README
§8 step 3 ("Run the suite against both goldens; move the pin only when
green") is satisfiable with no golden checked — at precisely the moment
the discipline exists.

A second, smaller gap in the same mechanism: §8 step 3's "both goldens"
has no way to run the suite against the **new** fixture *before* the
pin flips (ticket 09's gate tested the old golden pre-flip and the new
one only after) — the transition relies on the flip commit's own test
run to catch a bad capture.

## Proposal

1. **Missing pin fixture = failure.** Replace `test_golden_file`'s
   `skipif` with an assert that `GOLDEN.is_file()`, failing with a
   message that names the capture command
   (`tools/capture-golden.py <pin>`). The **lit** variant keeps its
   skip — that capture is genuinely optional
   (`fixtures/README.md:44-46`) and its absence is documented.
2. **Pin integrity requires the fixture file.**
   `test_atlas_pin_matches_fixtures` asserts
   `golden-<ATLAS_PIN>/sample.atlasmap` is a file, not that the
   directory exists.
3. **`--all` checks the pin's golden specifically.** The glob becomes
   `fixtures/golden-{ATLAS_PIN}/sample.atlasmap`; missing → the
   integration tier is an error, not a silent note (exit nonzero with
   the capture command in the message).
4. **A transition handle for §8 step 3.** The golden tests resolve
   their fixture directory from an env override when present (e.g.
   `AVTT_GOLDEN_VERSION=0.9.1 python run-tests.py --all`), so a bump
   can prove the new capture green *before* flipping `ATLAS_PIN`. One
   line in README §8 step 3 names it. (If the implementer lands a
   cleaner mechanism — a `--golden` flag, a fixture-dir argument —
   fine; the criterion is that the pre-flip check is possible and
   documented, deviations recorded as usual.)
5. **Fix the stale placeholder.** `fixtures/golden-0.6.0/README.md`'s
   "Empty until…" paragraph is replaced by a line pointing at the
   committed fixture (same change; the README-is-constitution rule
   makes this a same-day item anyway — it rides here because the file
   is the evidence for hole 2).

Deliberately **not** proposed: parametrizing the golden test over every
committed `golden-*/`. Old goldens are history for a port that followed
the old pin; a future bump that legitimately changes conversion output
would make them fail against the new port. They stay as provenance
(`fixtures/README.md` already says what each row is).

## Acceptance criteria

- [x] With the pin's fixture absent (simulated in a temp copy of the
      tree), `pytest tests -m integration` **fails** (not skips) with a
      message naming the capture command — pinned by
      `tests/test_scenes.py::test_golden_file` (its new assert) and
      checkable as stated.
- [x] `tests/test_pin.py::test_atlas_pin_matches_fixtures` requires
      `golden-<ATLAS_PIN>/sample.atlasmap` to be a file (checkable by
      reading; a README-only directory fails it).
- [x] `python run-tests.py --all` exits nonzero when the pin's fixture
      is missing, with the capture command in the message (checkable
      claim; the glob is pin-scoped).
- [x] The §8 pre-flip check works: with a second golden committed and
      the env override pointing at it, the golden tests read that
      fixture — pinned by a new test asserting the override resolves
      the fixture path (e.g. `tests/test_scenes.py::test_golden_override`),
      and README §8 step 3 names the mechanism (checkable by reading).
- [x] `fixtures/golden-0.6.0/README.md` no longer claims to be empty
      (checkable by reading).
- [x] Ordering note honored: this ticket lands **before** the next pin
      bump uses the gate (ticket 16 cites it).

## Implementation notes (2026-10-23)

Landed as the branch's single feat(12) commit on
`feature/12-golden-gate-hardening` (this commit — the completed status
flip and the `archive/` move are folded into it after reviewer
sign-off, same day). No deviation from the proposal beyond the named
choice it allowed: the transition handle is the env override
`AVTT_GOLDEN_VERSION` (the proposal's own example), not a flag. All six
criteria proven by the runs below; nothing left for a human. Gates at
landing: ruff clean; `python run-tests.py --all` green — fast tier
162 passed, 1 skipped (the optional lit golden), integration tier 1
passed, 1 skipped.

Mechanism as proposed, with the env-override handle named
`AVTT_GOLDEN_VERSION`: `tests/test_scenes.py` resolves the golden
fixture directory through `golden_version()` (override when set, else
`_version.ATLAS_PIN`) / `golden_dir()`; the old module-level `GOLDEN`
/ `GOLDEN_LIT` constants are gone. `test_golden_file` lost its
`skipif` and now asserts the fixture is a file, failing with
``capture it with `tools/capture-golden.py <version>```; the lit
variant keeps its skip (genuinely optional, fixtures/README.md).
`test_pin.py::test_atlas_pin_matches_fixtures` asserts the capture
*file*, so a README-only `golden-<pin>/` fails it. `run-tests.py --all`
requires `fixtures/golden-{ATLAS_PIN}/sample.atlasmap` — the pin is
read from `src/avtt/_version.py` by text regex (`_atlas_pin()`), so
the runner stays stdlib-only and never imports the package (PyYAML
lives in the venv); with the override set, that fixture must exist
too, because the golden tests read it. Missing → per-version error
lines naming the capture command, exit 2 (distinct from a suite
failure's 1). README §7 states the file-is-the-pin rule and the
override; §8 step 3 names `AVTT_GOLDEN_VERSION=<new> python
run-tests.py --all` as the pre-flip check. `fixtures/golden-0.6.0/
README.md` now points at the committed capture (2026-10-18, table
row) instead of claiming to be empty; `_version.py`'s docstring says
"captured fixture", not "fixture directory". Nothing in `src/`
changed beyond that docstring — the holes were all in the gates.

Verification runs (2026-10-23, temp copy of the tree under the system
temp, deleted after): with `golden-0.8.0/` reduced to a README-only
placeholder — `pytest tests -m integration` → 1 failed
(`test_golden_file`, message names `tools/capture-golden.py 0.8.0`),
1 skipped (lit), exit 1, no skips of the load-bearing test;
`pytest tests/test_pin.py::test_atlas_pin_matches_fixtures` → failed
exit 1; `python run-tests.py --all` → the two error lines, exit 2.
Override end-to-end: `AVTT_GOLDEN_VERSION=0.7.1 python run-tests.py
--all` on the real tree → all suites passed (the golden test read
golden-0.7.1); the same env against a copy whose
`golden-0.7.1/sample.atlasmap` was deleted failed naming
`golden-0.7.1` and `capture-golden.py 0.7.1`, proving the read follows
the override, not the pin. Ordering: ticket 16 is still `proposed`
(docs/tickets/, not archive/) and cites this ticket — the gate exists
before the bump that will use it.
