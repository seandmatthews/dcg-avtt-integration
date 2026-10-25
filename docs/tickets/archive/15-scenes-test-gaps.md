# 15 — scenes-side test gaps: the note on refusal, limit boundaries, WebP/JPEG, the lit golden

**Status:** completed
**Priority:** P2 — four small gaps in README §7's delivered claims, none
of which today's suite can catch
**Area:** `tests/test_scenes.py`, `fixtures/` (two tiny new `.uvtt`
variants; optionally `sample-lit.atlasmap`), `fixtures/README.md`
**Found by:** full adversarial review, 2026-10-23

## Problem

Four independent gaps, all in the scenes lane:

1. **"Nothing is written on refusal" (§7.3) never checks the companion
   note.** Every refusal case asserts only `not atlas.exists()`
   (`tests/test_scenes.py:502`, likewise the 150 MB test at 505-515 and
   the incomplete-site test at 518-526). The companion-note append is
   the system's one write **outside** `atlas-vtt/` — the licensed
   exception to contract rule 1, and the highest-blast-radius write it
   makes (user-owned content). A pipeline reorder that appends the link
   line before conversion would mutate the user's note on every
   refusal, entirely green. Only the degrade path checks the note today
   (`test_scenes.py:570,581`).
2. **Inclusive limit boundaries are untested.** Only over-limit values
   are fed (`tests/test_scenes.py:444-489`). Exactly 20,000 segments,
   exactly 2,000 lights, exactly 4,096 cells per side, exactly
   150.0 MB, exactly 268,435,456 px, exactly 10 px per cell — the
   `>` vs `>=` behavior of `uvtt.py:112`, `scene.py:195`,
   `scene.py:201` is unasserted; an off-by-one ships green.
3. **WebP and JPEG inside a real `.uvtt` are never converted.** Every
   `.uvtt` in every test embeds PNG; the VP8L/VP8X WebP readers
   (`image_headers.py:81-87`) are reached by no test at all (only
   lossy VP8 via `pixel_dimensions`, `test_scenes.py:139-144`), and no
   JPEG-carrying `.uvtt` walks the real conversion path. A broken
   `_webp`/`_jpeg` reader ships green against a green golden.
4. **The ambient-luma branch has no golden.** `sample-lit.atlasmap` was
   never captured at any pin — `test_golden_file_lit_variant`
   (`test_scenes.py:408-416`) always skips — so `_brightness_of`
   (`scene.py:172-177`) is verified only by a unit test asserting a
   number the port computes about itself (`test_scenes.py:238-248`).
   README §7.1 lists "ambient luma" among the rules the golden
   exercises; at the pin, none does.

## Proposal

1. Add a note-untouched assertion to the refusal family: after each
   refused publish, the site's `<slug>.md` is byte-identical to what
   `make_campaign` wrote. One helper (read-before/compare-after) shared
   by `test_refusals_write_nothing`, the 150 MB test, the
   incomplete-site test, and the partial-refusal multi-site test.
2. Add boundary cases on both sides of each limit — exactly-at passes
   (a 20,000-segment file is a big parametrize case but cheap to build
   programmatically; the 150 MB boundary case can use a monkeypatched
   or minimal-payload file of exactly the limit bytes — implementer's
   choice, documented if the construction is unusual) and one-past
   refuses (mostly already present).
3. Add two tiny fixtures: `sample-webp.uvtt` (VP8L image, the
   least-covered reader) and `sample-jpeg.uvtt`, each a minimal variant
   of `sample.uvtt` with the image swapped; convert them end-to-end in
   tests (refusal-free happy path through `publish.py` or the
   converter, whichever the existing style favors). The fixture design
   table in `fixtures/README.md` gains their rows.
4. Capture `sample-lit.atlasmap` at the pin — one more run of the
   capture tool (`tools/capture-golden.py` supports the second capture;
   `fixtures/README.md:44-46` already describes it). If the capture
   cannot land in the same change, the fallback is honest wording:
   README §7.1 and `fixtures/README.md` say the luma branch is
   unit-tested only until the capture exists — deviation recorded, not
   silent. (If ticket 16's bump lands first, capture at the new pin;
   either way the fixture directory and the pin agree.)

## Acceptance criteria

- [x] Every refusal test leaves the companion note byte-identical —
      pinned by the shared assertion in
      `tests/test_scenes.py::test_refusals_write_nothing`,
      `::test_refusal_of_a_150mb_file_writes_nothing`,
      `::test_incomplete_site_is_refused`, and the multi-site
      partial-refusal test.
- [x] Exactly-at-limit files pass and one-past files refuse for the six
      §3.3 limits — pinned by new boundary cases in the refusal tables
      (`tests/test_scenes.py`).
- [x] A VP8L-WebP `.uvtt` and a JPEG `.uvtt` convert end-to-end green —
      pinned by new tests over `fixtures/sample-webp.uvtt` and
      `fixtures/sample-jpeg.uvtt` (names final at implementation);
      `fixtures/README.md` carries their design rows.
- [x] `sample-lit.atlasmap` captured at the pin and
      `test_golden_file_lit_variant` runs (not skips) via
      `python run-tests.py --all` — or the honest-wording fallback is
      landed in README §7.1 + fixtures/README.md with the deviation
      recorded here (checkable either way).
- [x] `python run-tests.py` (and `--all` if the capture landed) green.

## Implementation notes (2026-10-24)

Landed as the branch's single `test(15)` commit on
`feature/15-scenes-test-gaps` (this commit — the status flip and the
archive move amend it). All five criteria proved green in the
implementer's own runs; the reviewer signed off 2026-10-24.

- **The capture tool did not support the second capture yet.** The
  ticket said it did; it hard-coded `sample.uvtt`. `--fixture` is added
  (`tools/capture-golden.py`): the vault copies the named fixture and
  the drop script reads it; the captured `.atlasmap` takes the fixture's
  stem. The lit capture landed the same session:
  `python -m uv run --with websocket-client python tools/capture-golden.py
  0.9.1 --fixture sample-lit.uvtt` →
  `fixtures/golden-0.9.1/sample-lit.atlasmap` (ambient 0.26, lights not
  hidden, no non-import state keys; isolated instance stopped, port 9223
  free afterwards). The real app's import matches the port's luma branch
  — `test_golden_file_lit_variant` runs and passes.
- **The 150 MB exactly-at case is monkeypatched, as the ticket allows:**
  `FILE_BYTES_LIMIT` is patched to 1 MiB and the file padded to exactly
  the limit with JSON whitespace. That pins the `>` comparison at its
  boundary without building and parsing 150 MB of JSON; the real
  constant and its one-past refuse stay with the existing 150 MB test.
  Documented in the test's docstring.
- **Wall-segment boundaries count every source together** (lines +
  outlines + portals share one budget), so the exactly-at case carries
  the one 20,000-segment line and empties the rest; one-past is 20,001.
- **The new image fixtures are header skeletons**, not decodable
  pixels — there is no WebP/JPEG encoder on the stdlib and the pipeline
  reads image headers only (README §4; the scene background is the site
  PNG). They still walk the real publish path and must produce a scene
  byte-identical to the PNG sample's (same design, same geometry).
  fixtures/README.md says exactly this in their rows.
- **Boundary images are header-only PNGs** for the same reason — the
  16384 × 16384 exactly-at case would otherwise be a quarter-gigabyte
  of pixels nothing decodes.
- **Observed, not changed:** the companion-note append rewrites the file
  through Python text mode, so on Windows the note's on-disk line
  endings become CRLF (content preserved; every note test compares
  through the same translation). Refused notes are never rewritten —
  that is the byte-identical pin. Changing the append's byte fidelity
  is not this ticket's; noting it here for a future one.
- Gates: ruff clean; `run-tests.py` and `run-tests.py --all` green
  (82+ passed, 0 skipped in the scenes file; the integration tier ran
  both golden tests).
