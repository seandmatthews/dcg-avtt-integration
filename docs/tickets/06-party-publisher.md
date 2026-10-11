# 06 — P4: party tokens publisher

**Status:** proposed (parked — see Proposal; "parked" is not a status,
so this stays `proposed` until un-parked or abandoned)
**Priority:** parked
**Area:** would be `src/avtt/` (new records for characters/tokens),
`src/avtt/publish.py` (party subcommand)
**Found by:** spec §5.3, 2026-10-10

## Problem

Character + token records could be published from a briefing roster,
saving per-campaign UI setup. Parked (README §5.3) because one-time UI
setup costs minutes per campaign and automation only pays when the
party churns.

## Proposal (the un-park condition)

Do not start this without a fresh spike: token records
(`tokens/<id>.json` + art file) are the least-documented surface in
Atlas (README §5.3). The spike would read the 0.6.0+ source for the
token record shape and adoption path, write up the findings as ticket
02's sibling, and only then re-scope this ticket.

## Acceptance criteria

- [ ] Un-park decision recorded here with the spike ticket's number
      (checkable by reading) — or the ticket moves to `archive/` as
      `abandoned` if the UI path wins for good.

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
