# 05 — P2: the scenes publisher (the main build)

**Status:** proposed
**Priority:** P1 (the main build; gated on spikes 01–03)
**Area:** `src/avtt/uvtt.py`, `src/avtt/image_headers.py`,
`src/avtt/scene.py`, `src/avtt/records.py`, `src/avtt/config.py`,
`src/avtt/publish.py` (scenes subcommand), `fixtures/`
**Found by:** spec §5.1, 2026-10-10

## Problem

The core's maps engine emits `<campaign>/maps/sites/<slug>/
{<slug>.png, <slug>.uvtt, <slug>.md}`; Atlas needs `.atlasmap` scenes
plus adoption records under `atlas-vtt/collections/<collectionId>/`.
The conversion port, the record writers, and the CLI that drives them
are all still stubs. This is the repo's reason to exist as more than a
pack installer.

## Proposal

Implement per README §3.1–§3.3/§5.1, in this order:

1. `uvtt.py` + `image_headers.py`: parse + validate with Atlas's exact
   limits and plain-words refusals; nothing written on refusal.
2. `scene.py`: the port of `uvttToScene.ts` — deterministic ids,
   clipping math, door/light/ambient rules, byte-deterministic dumps.
   AGPL-3.0 already declared (README §10).
3. `records.py`: map + scene records in the adoption shapes (ids left
   for Atlas to recover; `data.mapPath` wiring).
4. `config.py`: shaped by spike 01's answer; fed-or-refused.
5. `publish.py scenes`: the file plan of README §5.1, idempotent per
   contract rule 3, `--dry-run` printing the plan + first divergence.
6. The degrade path: golden test red → `.uvtt` copied to
   `atlas-vtt/_inbox/` with printed instructions; nothing else written.
7. The companion-note embed line: append-only, idempotent (contract
   rule 1's licensed exception).
8. `fixtures/sample.uvtt` designed to exercise every conversion rule
   (README §7.1's list); the human captures the golden fixture.

## Acceptance criteria

- [ ] Golden-file: port output matches `fixtures/golden-<pin>/`
      structurally — pinned by `tests/test_scenes.py::test_golden_file`
      (`-m integration`; discipline 1).
- [ ] Round-trip determinism: same input twice → byte-identical —
      `tests/test_scenes.py::test_round_trip_determinism` (discipline 2).
- [ ] Refusals: every limit → plain-words reason, zero writes —
      `tests/test_scenes.py::test_refusals_write_nothing` (discipline 3).
- [ ] Degrade: simulated golden mismatch → `_inbox/` only —
      `tests/test_scenes.py::test_degrade_path_to_inbox` (discipline 4).
- [ ] `--dry-run` prints the plan and first divergence without writing
      — `tests/test_scenes.py`.
- [ ] Companion-note edit is append-only and idempotent —
      `tests/test_scenes.py`.

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
