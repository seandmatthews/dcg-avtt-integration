# 14 — broken-preset tests for every ported validator rule

**Status:** proposed
**Priority:** P2 — the validator is the only thing standing between a
pack and Atlas's silent ignore, and about a third of its rules can be
deleted without a red test
**Area:** `tests/test_presets.py`
**Found by:** full adversarial review, 2026-10-23 (grep-verified: zero
test hits for each rule listed below)

## Problem

README §7.5 promises "Preset validation port tested against
deliberately-broken presets (must be refused before Atlas ever sees
them)". The headline rules deliver (the two historic pin-bump deltas —
`unitDistance` bounds, dice `defaultRoll` widening — are covered
including inclusive boundaries, `tests/test_presets.py:128-170`). But
roughly a third of the ported checks in `src/avtt/presets.py` have **no**
deliberately-broken test; deleting or inverting any of them ships green:

- `gridDefaults.coneAngle` (presets.py:260-263) — the entire rule; and
  `abstractRangeBands` not-a-list / bad-band shapes (267-277).
- `lightPresets`: invalid `unit` (657-660), `animation` (665-667),
  `kind` (668-670), `intensity` outside 0–2 (679-686), `priority`
  (697-700), duplicate id (636-639), not-a-list (621-623).
- `senses`: `sees.bright/dim/dark/magicalDark` vocab (451-455), `look`
  (456-459), `reveals: 'all'` + `lineOfSight: false` (460-463), `range`
  (464-466), `defaultRange` (467-469), `ignores` (470-473), duplicate
  `role` (479-481), `description` non-string (443-444), duplicate id
  (424-427), not-a-list (402-404), the `see-invisible` modifier's
  keys-ignored rule (434-440).
- `resources`: `slot` outside 0–5 (517-520), `defeatedWhenSpent` on
  `static` (521-523), more than 6 (524-526), not-a-list (493-495).
- `widgets`: `order` (344-346), `color` (347-348), not-a-list (310-311),
  counter `min`/`max` non-numbers (329-331).
- `defaultTokenVision`: angle in (0,1) (558-560), a senses entry naming
  an undefined sense (582-585), duplicate entry (578-580), entry
  `range ≤ 0` (588-590), "sets nothing Atlas would use" (612-613), the
  senses-list-replaces-legacy-fields rule (596-600).

The failure these tests guard against is the repo's own named worst
case: an invalid preset reaching Atlas is silently ignored — "a knob
the DM believes is live but is not" (`presets.py:23-30`).

## Proposal

Extend the existing deliberately-broken case sets in
`tests/test_presets.py` (the parametrized tables, ticket 08/09's
pattern) so that **every** refusal branch in `presets.py`'s
`_validate_*` functions has at least one case that trips it and asserts
the refusal message. Group the new cases per validator function
(`_validate_grid_defaults`, `_validate_light_presets`,
`_validate_senses`, `_validate_resources`, `_validate_widgets`,
`_validate_vision_defaults`) rather than one monolithic table, so a
future rule maps to its test at a glance. Where a rule has two sides
(refuse vs. accept-as-written — e.g. a *valid* `see-invisible`
modifier, a `slot` inside range), add both sides; the strictness
contract ("never rejects anything Atlas would accept verbatim") needs
the false-refusal direction pinned too, not just the false-acceptance
one.

Ride-along (same file, same sitting): replace the hand-rolled
monkeypatch at `tests/test_presets.py:567-573` (`presets.pack_preset_path
= lambda …` under try/finally) with the `monkeypatch` fixture.

No product-code change is in scope — this ticket is about pinning what
the port already does. (If writing a case reveals a port bug, that is a
finding for its own change, recorded in Implementation notes.)

## Acceptance criteria

- [ ] Every refusal branch listed in Problem has a deliberately-broken
      test case asserting its refusal — pinned by the new parametrized
      cases in `tests/test_presets.py` (one named case group per
      `_validate_*` function; checkable by reading the parametrize
      tables against the branch list).
- [ ] The accept-as-written side is pinned for the two-sided rules
      (`see-invisible` modifier, in-range `slot`, valid `coneAngle`,
      angle ≥ 1) — same tables.
- [ ] The hand monkeypatch is gone — `tests/test_presets.py` uses the
      `monkeypatch` fixture (checkable by reading).
- [ ] `python run-tests.py` green with the new cases (recorded in
      Implementation notes).

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
