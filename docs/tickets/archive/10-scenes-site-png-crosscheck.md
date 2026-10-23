# 10 — scenes: refuse when the site PNG disagrees with the .uvtt's image

**Status:** completed (implemented + reviewer-signed-off 2026-10-23, this commit, branch `feature/10-scenes-site-png-crosscheck`)
**Priority:** P1 — the only silent-wrong-output path found by the review:
a published scene whose walls/grid fit a different image than the one it
displays
**Area:** `src/avtt/publish.py` (`_convert_site`), `src/avtt/image_headers.py`
(already sufficient — no change expected), `tests/test_scenes.py`, README §5.1
**Found by:** full adversarial review, 2026-10-23 — reproduced live (below)

## Problem

The scene's grid and wall math are computed from the image **embedded in
the `.uvtt`** (`publish.py:202` measures `document.image_bytes` via
`image_headers.dimensions_of_bytes`), but the scene's `background` points
at the **site's PNG**, which is copied byte-for-byte without ever being
inspected (`publish.py:297` reads it; the plan at `publish.py:301-307`
states it; nothing compares the two). The two files come from the
generator as a pair, but nothing enforces the pair: a partial
regeneration, an interrupted export, or a hand swap leaves them
disagreeing, and the publisher publishes anyway.

`image_headers.pixel_dimensions` (`image_headers.py:45`) exists, is
tested (`tests/test_scenes.py:137-159`), is exported in the smoke pin
(`tests/test_smoke.py:26`) — and is called by no product code (grep over
`src/` hits only its definition). It was built for exactly this check
and never wired in.

**Live repro (2026-10-23, temp campaign, deleted after):** a site whose
`cave-of-doom.png` is 128×32 while `cave-of-doom.uvtt` embeds the 64×32
fixture image publishes cleanly — exit 0, normal success lines — and the
resulting `.atlasmap` carries `grid.size: 16` (correct for the 64px-wide
inline image, half-scale for the 128px background it references). Every
wall, door and light lands misplaced in Atlas, with no warning anywhere.
Corrupt input fares the same: a site PNG containing the literal bytes
`not a png at all` is planned for copy and referenced by the map record
(`--force --dry-run` shows it; nothing refuses).

## Proposal

In `_convert_site` (or `_site_files`, implementer's choice), before
converting:

1. Read the site PNG's real dimensions with
   `image_headers.pixel_dimensions(site.image_path)` — it already raises
   `ValueError` with a plain-words message for a truncated or
   unrecognized header, which is the corrupt-image refusal for free.
2. Refuse unless those dimensions equal the inline image's `(width,
   height)` exactly. Both files come from the same generator export;
   any difference means one of them is stale, and stale means
   misaligned walls. (Exact equality is the rule; an ±px tolerance is
   *not* proposed — the importer's ±2 px tolerance is about exporter
   rounding *inside one image*, not about two files agreeing.)
3. The refusal message says both sides in plain words, e.g. "the site
   image `<slug>.png` is W×H but the `.uvtt` embeds w×h — regenerate the
   site so the pair agrees". Nothing is written (the existing
   per-site refuse-and-continue loop at `publish.py:507-514` already
   handles this shape).
4. The degrade path is untouched: it copies the `.uvtt` only, and
   Atlas's own importer judges the pair when the DM drags it in.

README §5.1 gains one sentence under the file plan: the site PNG and the
`.uvtt`'s embedded image must agree; a disagreeing pair is refused (the
constitution rule — the README currently implies the PNG is "just
copied", which stays true only of the bytes, not the check).

## Acceptance criteria

- [x] A site whose PNG dimensions differ from the `.uvtt`'s inline image
      is refused with a plain-words reason naming both sizes, and
      nothing is written — pinned by a new
      `tests/test_scenes.py::test_site_png_disagreeing_with_uvtt_is_refused`
      (asserting the message fragment and `not atlas.exists()`).
- [x] A site PNG that is not a readable PNG/JPEG/WebP is refused with
      the plain-words header message — pinned by
      `tests/test_scenes.py::test_site_png_unreadable_is_refused`.
- [x] The live repro from Problem no longer publishes: a temp campaign
      with a 128×32 PNG beside the 64×32-embedding `sample.uvtt` exits 2
      with the refusal (recorded in Implementation notes; temp deleted).
- [x] README §5.1 states the pair-agreement rule (checkable by reading).

## Implementation notes (2026-10-23)

Landed as the branch's single feat(10) commit on
`feature/10-scenes-site-png-crosscheck` (this commit — the completed
status flip and the `archive/` move are folded into it after reviewer
sign-off, same day). Gates at landing: ruff clean;
`run-tests.py --all` green — fast tier 154 passed, 1 skipped (the
optional lit golden), integration tier 1 passed, 1 skipped. All four
criteria proven; nothing left for a human.

The check sits in `_convert_site` (`publish.py`), **after** the
importer's own image limits (`checked_cell_size`) and before
`scene.convert`. Ordering is deliberate: those limits refuse a `.uvtt`
Atlas could not import by hand either, so they fire first — the first
cut put the pair check ahead of them and two ticket-05 refusal cases
(`image-too-large`, `grid-too-small`) surfaced the pair message instead
of their own; reordered rather than touching their pins. The refusal is
a plain `ValueError` (the site-level refusal type `_site_files` already
uses), printed by the existing per-site refuse-and-continue loop; the
unreadable-PNG case is `pixel_dimensions`' own `ValueError`, unchanged.
`image_headers.py` untouched, as the ticket expected. The degrade path
is untouched — it never calls `_convert_site`.

Live repro re-run after the fix (temp campaign under the system temp,
deleted after): `cave-of-doom.png` 128×32 beside `sample.uvtt` (embeds
64×32) → exit 2, "refusing cave-of-doom: the site image
cave-of-doom.png is 128 × 32 but the .uvtt embeds 64 × 32 — regenerate
the site so the pair agrees", and `atlas-vtt/` absent after the run —
the same campaign the Problem section published cleanly.
