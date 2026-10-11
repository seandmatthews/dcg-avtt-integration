# Ticket conventions

How tickets in this directory work — for whoever writes one (usually an
agent). The rules are inherited unchanged from
`dnd-campaign-generator/docs/tickets/CONVENTIONS.md` (same family, same
working style); this copy is the local record.

## What a ticket is

A ticket is the durable record of one unit of work from real use or the
spec. Spec sections (README §5's publishers, §12's spikes) are
converted into tickets, and then the work happens ticket-by-ticket —
the tickets are the queue and the record. Two consequences:

- A ticket must be **self-contained**: it carries its own evidence and
  must never dangle a pointer at a deleted or external doc (citing the
  README by section is fine — the README is the constitution).
- Completed tickets are **never deleted**. `archive/` is the history;
  only a ticket's status line and location change over its life.

## Rules

- **Numbering:** sequential two-digit number (`01-…`), never reused;
  gaps are fine. The number is the cross-reference id — later tickets
  cite each other by number.
- **One ticket = one lane:** sized so one agent can implement and merge
  it independently in one sitting. Spikes are tickets too — an
  experiment with a written-up result is a completed ticket.
- **Acceptance criteria are test-nameable.** Each criterion names the
  test that pins it (or is a directly checkable claim). "Works better"
  is not a criterion. Spike tickets' criteria are the written-up
  decision itself.
- **User rulings live in the ticket**, under `## Ruling (do not
  revisit)` or `## Decisions baked in`. A ruled-out approach is not
  re-proposed in a later ticket.
- **Deviations are documented, not silent.** When an implementation
  lands differently than proposed, the ticket's Implementation notes
  say so and why.
- **Status lifecycle:** `proposed` → `in-progress` → `completed`,
  `superseded`, or `abandoned`. "Parked" is not a status — write
  `proposed` with a parked note (see ticket 06). Flipping to one of the
  last three means the file moves to `archive/` in the same change.
- **No index.** There is deliberately no README or table listing the
  tickets; the status line in each file is the record.

## Template

Copy for a new ticket. The bold fields: `Status` (always, exactly one of
the five statuses), `Priority` (P1/P2/P3 or a short phrase), `Area`
(files/modules the work touches), `Found by` (what surfaced it, with
date). The three spine sections are Problem / Proposal / Acceptance
criteria; Implementation notes are added when the work lands, not up
front.

```markdown
# NN — Title in a few words

**Status:** proposed
**Priority:** P1 | P2 | P3 (or a short phrase)
**Area:** `files/modules/` the work touches
**Found by:** what surfaced it + date

## Problem

What is wrong today, with evidence. Ground it — this section must
still make sense on its own.

## Proposal

The concrete change. Enough detail that an agent can implement it
without re-deriving the design; call out anything that needs a user
ruling rather than deciding it silently.

## Acceptance criteria

- [ ] criterion — pinned by `tests/test_foo.py::test_bar`
- [ ] criterion (spikes: the written-up decision, checkable by reading)

## Implementation notes (YYYY-MM-DD)

How it actually landed: commit refs, deliberate deviations from the
proposal, follow-ups. Written when the status flips.
```
