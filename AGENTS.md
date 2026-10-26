# AGENTS.md

Repo-wide working rules for agents working in `dcg-avtt-integration`.

## The README is the constitution

`README.md` is this repo's constitution: when code and README disagree,
one of them is wrong and must be fixed the same day. Do not silently
work around a README rule — change the rule in the same change that
breaks it, with the reason stated.

## Tickets

Tickets live in `docs/tickets/` (finished ones in `docs/tickets/archive/`).
Every ticket starts with one status line, `**Status:**` followed by
exactly one of: `proposed`, `in-progress`, `superseded`, `completed`,
`abandoned` (plus a short note — dates, commit refs). When a ticket's
status becomes `superseded`, `completed`, or `abandoned`, move it into
`docs/tickets/archive/` in the same change; `proposed` and `in-progress`
tickets stay in `docs/tickets/`. There is no tickets index — the status
line in each file is the record. Format, numbering, and the template:
`docs/tickets/CONVENTIONS.md`.

## Workflows: the ticket forge and the implementer

Two saved ZCode workflows automate the ticket loop (run them by name via
the workflows hub / `CreateWorkflow` with `saved`):

- `avtt-ticket-forge` — one idea in, a grounded + reviewed ticket out;
  committed to main on the reviewer's sign-off.
- `avtt-ticket-implementer` — one existing proposed/in-progress ticket,
  implemented on its own worktree branch, gated (ruff + `run-tests.py
  --all`), reviewed; on sign-off flipped to completed, moved to
  `docs/tickets/archive/` in the same change, and merged `--no-ff` into
  main with the gates re-run (auto-revert on red). Concurrency-safe:
  per-run worktrees under `../dcg-avtt-wt/`; the shared main checkout is
  serialized by a cross-run lock (`.zcode/tools/checkout-lock.ps1`).

Both live in `.zcode/workflows/` (tracked) and are adapted from
pigeon-simulator's `pigeon-ticket-forge` / `pigeon-ticket-pipeline`.

## The Atlas source: re-clone, never vendor

The README's Atlas contract (§3) was read from a *reference clone* of
Atlas VTT at the pinned tag (see the pinned-release table, README §7).
That clone is ephemeral — before trusting any line that cites Atlas
source, re-clone and re-check the tag:

    git clone --branch <pinned-tag> https://github.com/atlas-vtt/atlas-vtt "$TEMP/atlas-vtt"

Never commit, vendor, or copy Atlas source into this repo: `scene.py`
and the preset validator are ports (derivative works — README §10), but
vendored source would change the licensing picture and the churn
procedure (§8). Cite file paths; do not carry code over.

## Atlas-side e2e: the live sitting this repo owns

The campaign generator's verification (its `docs/WORKFLOW.md`) stops at
canon — it never touches Obsidian or Atlas. This repo owns the other
half: occasionally (every few weeks of active work, and before a bundle
is handed to a real table), run the whole flow through the table
surface live — publish presets and scenes from a real campaign with the
CLI, then open the campaign vault in Obsidian desktop with the Atlas
plugin and verify what only the table can show: doors survive import,
the preset is picked up, a scene renders with sane ambient, a statblock
fence links and renders a token.

The Obsidian half is real input on the physical desktop: run it only
when the machine is free, capture a screenshot per checkpoint, and tick
the campaign generator's pending ticket boxes with that evidence — the
human spot-checks the pack instead of doing the clicks.

## Subprocess discipline

List-form args, explicit `cwd`, never `shell=True` — a rule kept from
the campaign-generator family (their parent path contained `&`).

## No long-running processes

This repo is a prep-time CLI (README §9: no server, no watcher daemon,
no runtime at the table). There is nothing to leave running — so if you
started any process while working here (a test server, a watcher), kill
it before ending the session and verify the port/process is gone.

## Windows-first

Development happens on Windows (the campaign generator's home); the CI
matrix keeps an ubuntu leg for portability, but Windows behavior wins
disputes. Paths in tests via `pathlib`; no hardcoded `/tmp`.
