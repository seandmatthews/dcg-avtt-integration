# 12 — the golden gate must fail, never skip, when the pin's fixture is missing

**Status:** proposed
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

- [ ] With the pin's fixture absent (simulated in a temp copy of the
      tree), `pytest tests -m integration` **fails** (not skips) with a
      message naming the capture command — pinned by
      `tests/test_scenes.py::test_golden_file` (its new assert) and
      checkable as stated.
- [ ] `tests/test_pin.py::test_atlas_pin_matches_fixtures` requires
      `golden-<ATLAS_PIN>/sample.atlasmap` to be a file (checkable by
      reading; a README-only directory fails it).
- [ ] `python run-tests.py --all` exits nonzero when the pin's fixture
      is missing, with the capture command in the message (checkable
      claim; the glob is pin-scoped).
- [ ] The §8 pre-flip check works: with a second golden committed and
      the env override pointing at it, the golden tests read that
      fixture — pinned by a new test asserting the override resolves
      the fixture path (e.g. `tests/test_scenes.py::test_golden_override`),
      and README §8 step 3 names the mechanism (checkable by reading).
- [ ] `fixtures/golden-0.6.0/README.md` no longer claims to be empty
      (checkable by reading).
- [ ] Ordering note honored: this ticket lands **before** the next pin
      bump uses the gate (ticket 16 cites it).

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
