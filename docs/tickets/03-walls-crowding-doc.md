# 03 — Spike: walls-crowding refusal text, for the manual-import doc

**Status:** proposed
**Priority:** P3
**Area:** spike (documentation); output lands here + the core's
`docs/for-new-gms/` ATLAS tutorial (cross-repo, by hand)
**Found by:** Atlas seam analysis + spec, 2026-10-09/10

## Problem

Dense generated maps may trip Atlas's `wallsCrowd` heuristic on *its*
import path (`src/app/import/uvtt/uvttCrowding.ts` in 0.6.0). This
repo's own publisher is unaffected (it writes scenes directly, README
§12.3), but the manual-drag fallback — the degrade path's `_inbox/`
instruction (README §5.1) — lands the DM in exactly that importer. When
it refuses, the DM needs to know what the message means and what to do.

## Proposal

1. In the pinned clone, read `uvttCrowding.ts` + the importer's user-
   facing refusal strings; capture the exact text and the threshold.
2. Trigger it once in the Atlas UI with a deliberately crowded
   `fixtures/sample.uvtt` variant (confirm the source read).
3. Write the explanation into the doc that mentions manual import —
   the ATLAS tutorial lives in the *core* repo
   (`dnd-campaign-generator/docs/for-new-gms/`), so the edit there is
   made by hand as a separate cross-repo change; the captured text and
   the guidance live in this ticket.

## Acceptance criteria

- [ ] The refusal text + threshold are captured in this ticket's
      Implementation notes, tagged to the Atlas version (checkable by
      reading).
- [ ] The core tutorial's manual-import paragraph carries the
      plain-words explanation (cross-repo; note the edit here).

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
