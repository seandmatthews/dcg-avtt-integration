# 14 — broken-preset tests for every ported validator rule

**Status:** completed (implemented + reviewer sign-off 2026-10-24; this
flip and the `archive/` move are folded into the branch's single commit
by amending — pre-amend hash `c54c107`)
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

- [x] Every refusal branch listed in Problem has a deliberately-broken
      test case asserting its refusal — pinned by the new parametrized
      cases in `tests/test_presets.py` (one named case group per
      `_validate_*` function; checkable by reading the parametrize
      tables against the branch list).
- [x] The accept-as-written side is pinned for the two-sided rules
      (`see-invisible` modifier, in-range `slot`, valid `coneAngle`,
      angle ≥ 1) — same tables.
- [x] The hand monkeypatch is gone — `tests/test_presets.py` uses the
      `monkeypatch` fixture (checkable by reading).
- [x] `python run-tests.py` green with the new cases (recorded in
      Implementation notes).

## Implementation notes (2026-10-24)

What landed, all in `tests/test_presets.py` — no product-code change,
as scoped:

- Six parametrized case groups, one per `_validate_*` function named in
  the Proposal, each row a `(changes, refusal-fragment, refused)` triple
  over `valid_preset()` via the existing `broken()` helper:
  `test_grid_defaults_rules`, `test_light_preset_rules`,
  `test_sense_rules`, `test_resource_rules`, `test_widget_rules`,
  `test_vision_default_rules` (78 new rows; the file collects 136 cases,
  was 58). Refuse rows assert a fragment of the exact refusal message;
  a shared `check_case` helper asserts a refused row fails *naming* its
  fragment and an accepted row passes with zero failures.
- The two-sided rules got both directions in the same tables: a valid
  `see-invisible` modifier (id/name/description only) vs. one carrying a
  sight key; `slot` 0 and 5 vs. 6/-1/1.5; `coneAngle` 90 and the
  inclusive 360 vs. 0/361/-45/"wide"; `defaultTokenVision.angle` 1 and
  359 vs. 0.5/0/360; plus intensity 0/2 vs. 2.5/-0.5 and
  `defeatedWhenSpent` on `drains` vs. `static`.
- Bonus rows for same-function branches the Problem list did not name
  but which had no broken case either: senses entry not-an-object /
  missing id / missing name / unknown `role`; vision section
  not-an-object, entry without a usable id, senses not-a-list.
- Each refusal row was verified to trip the *intended* branch, not just
  any failure: every changes-dict was run through
  `presets.validate_preset` and the full failure messages dumped and
  read against the branch (all 78 rows matched, no surprises).
- Ride-along done: the hand-rolled `presets.pack_preset_path = lambda …`
  under try/finally in `test_invalid_pack_is_refused_before_validation`
  is replaced with the `monkeypatch` fixture.
- No port bug surfaced: every branch behaves exactly as its message
  claims.

Gates (run 2026-10-24 in the worktree, before the reviewer re-run):

- `python -m uv --directory <worktree> tool run ruff check src tests run-tests.py`
  → "All checks passed!"
- `python -m uv --directory <worktree> run python run-tests.py` →
  avtt PASS: 247 passed, 1 skipped in ~2s (the skip is pre-existing:
  `tests/test_scenes.py:428`, the genuinely-optional second golden
  capture).
- `python -m uv --directory <worktree> run python run-tests.py --all` →
  avtt PASS + avtt-golden PASS (1 passed, 1 skipped, 246 deselected).

Landed as the branch's single commit (pre-amend hash `c54c107`); the
reviewer's sign-off on 2026-10-24 accepts it, and this flip plus the
`archive/` move are folded into that commit by amending. Deviations
from the proposal: none beyond the bonus rows documented above (same
file, same sitting, per the Proposal's own scope line). Every
acceptance criterion is proven by a run recorded here — nothing is
left for a human.
