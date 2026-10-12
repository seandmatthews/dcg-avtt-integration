# 05 — P2: the scenes publisher (the main build)

**Status:** completed — 2026-10-12 (implemented the same day on
`feature/05-scenes-publisher` in the branch's single feat(05) commit;
reviewer sign-off and this `archive/` move are part of that change.
One criterion is honestly left for a human — the golden capture, see
Implementation notes — and was signed off as open.)
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
      (`-m integration`; discipline 1). — test written; **skips until the
      human capture** (import `sample.uvtt` in the pinned Atlas UI,
      commit `golden-<pin>/sample.atlasmap`; fixtures/README.md)
- [x] Round-trip determinism: same input twice → byte-identical —
      `tests/test_scenes.py::test_round_trip_determinism` (discipline 2).
- [x] Refusals: every limit → plain-words reason, zero writes —
      `tests/test_scenes.py::test_refusals_write_nothing` (discipline 3).
- [x] Degrade: simulated golden mismatch → `_inbox/` only —
      `tests/test_scenes.py::test_degrade_path_to_inbox` (discipline 4).
- [x] `--dry-run` prints the plan and first divergence without writing
      — `tests/test_scenes.py`.
- [x] Companion-note edit is append-only and idempotent —
      `tests/test_scenes.py`.

## Implementation notes (2026-10-12)

Landed as the branch's single feat(05) commit on
`feature/05-scenes-publisher` (this commit — the status flip and the
`archive/` move are folded into it). Gates at landing: ruff clean;
`run-tests.py --all` green — 142 passed, 2 skipped (the two golden
tests, which skip until the human capture below); the integration tier
auto-skips (`run-tests.py` finds no `fixtures/golden-*/sample.atlasmap`).
The port was written against a fresh clone of tag `0.6.0` (HEAD
`c5a99830`, per AGENTS.md's re-clone rule); the golden-test *harness*
was exercised against a temporary synthetic fixture (structural match
passes; a one-pixel perturbation and a renamed id fail; a capture-style
`background` path is exempt) and the fixture deleted — that proves the
test mechanics, not the port against the real app, which is what the
human capture pins.

**What landed (the proposal's order, all of it):** `uvtt.py` (parse +
limits + plain-words refusals — the importer's own sentences, ported
from `parseUvtt.ts`/`uvttFields.ts`/`uvttImage.ts`), `image_headers.py`
(stdlib PNG/JPEG/WebP readers, ported from `imageDimensions.ts`),
`scene.py` (`uvttToScene.ts` + `uvttClip.ts` + `newSceneFile.ts` as the
import merges it; `schema: "atlas-vtt"`, `version: 4`; JS number
semantics so the bytes match `JSON.stringify(content, null, 2)`),
`records.py` (map + scene records, no ids/timestamps/collection),
`config.py` (`<campaign>/avtt.yaml`, fed-or-refused), `publish.py
scenes` (validate → convert → plan → refuse-on-diff writes, `--dry-run`,
the `_inbox/` degrade, the companion-note line), and
`fixtures/sample.uvtt` + `sample-lit.uvtt` + `sample-nonsquare.uvtt`
(design table in fixtures/README.md). The four discipline placeholders
in `tests/test_disciplines.py` moved into `tests/test_scenes.py` with
real bodies and the file was deleted (its docstring's own rule); the
smoke pin on "scenes not built" moved with the build — the honest-stub
pin now covers `party` (ticket 06).

**Deliberate deviations from the proposal** (all checkable in the code):

- `scene.convert` takes the inline image's pixel `image_size`, not the
  stub's `image_path`: Atlas measures the image *inside the file*
  (`importUvttFile.ts`), not the site PNG. The site PNG is only copied.
- Scene records state a **top-level `mapPath`**, not `data.mapPath`: on
  disk Atlas's own writer flattens `data` into the record payload
  (`recordFile.ts`), and adoption reads the top-level key
  (`assetAdoption.ts`), falling back to the sibling `.atlasmap`. This
  resolves ticket 02's bycatch question; README §3.1 was amended in the
  same change to say exactly this (the constitution rule).
- The degrade path (installed Atlas ≠ pin, unknown included) runs
  **without requiring `avtt.yaml`**: the inbox needs only
  `atlas-vtt/_inbox/`, and the fallback must not die on adapter-path
  config. A refused (limit-breaking) `.uvtt` is not copied — it cannot
  survive the manual import either. Rule 3 holds in the inbox: an
  existing copy refuses on diff.
- `--force` republishes the **whole site set** as `<slug>-v2` (image,
  both records, `.atlasmap`, note line), not one file: a mixed
  slug/v2 set would break the records' stated paths. `--force` again on
  an already-matching v2 writes nothing.
- Refuse-on-diff for records compares meaning via `records.matches`
  (accepts Atlas's `atlasRecord` rewrite, ignores Atlas-owned fields);
  the `.atlasmap` compares as parsed JSON (a reformatted-but-equal file
  is not a divergence; a hand-tuned one still refuses); the image
  compares by bytes.
- The whole-map `wallsCrowd` guard is **not** ported (ticket 03: it is
  Atlas's manual-import path only); the publish output instead reports
  the conversion's skip counts ("left out: …"), per §5.1's "reported,
  not swallowed".

**Left for the human (criterion 1 open at sign-off):** capture the
golden fixture — import `fixtures/sample.uvtt` in the Atlas UI at the
pinned release and commit the result as
`fixtures/golden-0.6.0/sample.atlasmap` (procedure:
fixtures/README.md; optionally `sample-lit.atlasmap` from the luma
variant as a second capture). `test_golden_file` is written and skips
until then; criterion 1 stays unticked — the reviewer signed off with
it open, as ticket 03 did with its cross-repo edit. Everything the
capture needs is in place: the fixtures, the test, and the structural
comparator.
