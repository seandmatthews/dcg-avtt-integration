# 01 — Spike: collection bootstrap semantics

**Status:** proposed
**Priority:** P1 (first in the build order, README §12)
**Area:** spike (Atlas UI experiment); output lands in `src/avtt/config.py`
and README §3.1
**Found by:** Atlas seam analysis + spec, 2026-10-09/10

## Problem

Unknown whether a collection that exists only as a folder
(`atlas-vtt/collections/<id>/maps/<stem>.json`, records written but no
collection metadata) is adopted by Atlas, or whether
`collection.json` plus the library index must exist first. README §3.1
flags this as UNKNOWN. It decides whether `publish.py scenes` needs a
config step at all: if folder-only works, `config.collection_id` can
stay `None` forever; if not, the id must be recorded per campaign.

Fallback if the answer is "needs a real collection": create it once in
the Atlas UI and record its id in the campaign's companion config. This
repo must never write `library.json` or `collection.json` either way —
those are app internals (ruling, README §3.1).

## Proposal

One experiment in the Atlas UI with a hand-written record:

1. Fresh/throwaway vault, Atlas 0.6.0 (or the current pin).
2. Hand-write a minimal valid map or scene record into
   `atlas-vtt/collections/<made-up-id>/maps/<stem>.json` — no
   `collection.json`, no library index — then open Atlas and observe:
   adopted, ignored, or error?
3. If ignored: create the collection in the UI, note the assigned id,
   and re-test adoption of the hand-written record inside it.

## Acceptance criteria

- [ ] The experiment's result is written up in this ticket's
      Implementation notes: adopted vs UI-required, with what was
      observed (checkable by reading).
- [ ] README §3.1's UNKNOWN paragraph is replaced by the answer, dated
      and tagged to the Atlas version tested.
- [ ] `src/avtt/config.py`'s `collection_id` field docstring states the
      decision (stays-None vs per-campaign) — pinned by
      `tests/test_smoke.py` importing config cleanly.

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
