# 18 — publish small hardening: note-link anchor, campaign_system equivalence, inbox note

**Status:** proposed
**Priority:** P3 — three small correctness/doc items found together;
each is a one-sitting sliver, bundled as one lane because none justifies
its own ticket
**Area:** `src/avtt/publish.py` (`_note_has_line`, `campaign_system`),
`tests/test_scenes.py`, README §5.1
**Found by:** full adversarial review, 2026-10-23

## Problem

1. **The note-link idempotency check is an unanchored substring.**
   `_note_has_line` (`publish.py:280-287`) tests
   `f"[[{stem}{_ATLASMAP_SUFFIX}" in text` — so a note containing
   `[[cave-of-doom.atlasmap-old]]` (or any link whose target merely
   *starts with* the stem's `.atlasmap` name) counts as already
   carrying the scene link, and the append is silently skipped: the
   note never gains the real embed. The false-positive shape is also
   untested.
2. **The `system:` read's non-string semantics are asserted, not
   verified, against the core.** `campaign_system`
   (`publish.py:96-99`) returns `None` for a non-string scalar
   (`system: 5` parses as int), while README §5.2's pinned read
   contract says the semantics are `str(value).strip().lower()` —
   under a literal reading of that, the core yields `"5"` where we
   yield `None`. The docstring claims this IS the shared definition;
   nothing checks the core's actual `spine.campaign_system` agrees.
   Practically harmless today (no pack is named `"5"`), but the line
   exists precisely to not drift.
3. **Stale `_inbox/` copies are undocumented.** Files dropped by the
   degrade path are never revisited: after a pin bump publishes
   `.atlasmap` scenes properly, yesterday's inbox copies linger, and a
   DM can legitimately wonder whether they still matter. One sentence
   in README §5.1's degrade paragraph closes it (inbox copies are the
   DM's to drag in or delete; a later pinned publish neither reads nor
   cleans them).

## Proposal

1. Anchor the link check: the target name must be followed by a link
   terminator — one of `]`, `|` (alias), or `#` (subpath) — so
   `[[<slug>.atlasmap]]`, `![[<slug>.atlasmap|Scene]]` and
   `[[<slug>.atlasmap#fog]]` all count, `[[<slug>.atlasmap-old]]` does
   not. A tiny helper or one regex; keep it readable over clever.
2. Verify once against the core (`dnd-campaign-generator`'s
   `spine.campaign_system`) and record the finding here in
   Implementation notes: if the core coerces non-strings
   (`str(value).strip().lower()` literally), mirror that; if the core
   also requires a string, the docstring's claim stands and gains the
   citation. Either way the two sides end the ticket provably aligned
   (cross-repo read only — contract rule 4 forbids importing it, which
   is the whole point of the check).
3. README §5.1 degrade paragraph gains the inbox-cleanup sentence.

## Acceptance criteria

- [ ] A note containing only `[[<slug>.atlasmap-old]]` does **not**
      count as carrying the link (the real line is appended);
      plain/alias/subpath shapes still count — pinned by new cases in
      `tests/test_scenes.py` (e.g.
      `::test_note_link_detection_is_anchored`).
- [ ] The core-semantics finding is recorded in Implementation notes
      with the citation (file + line in the core), and `campaign_system`
      matches it — checkable by reading; a behavior change, if any,
      lands with its own test.
- [ ] README §5.1 states the inbox-cleanup rule (checkable by reading).

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
