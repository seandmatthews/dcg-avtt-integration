# 22 — Byte-faithful companion-note append

**Status:** proposed
**Priority:** P2 — a guarantee the docstring already makes and the code
breaks on every first publish, on the system's highest-blast-radius write
**Area:** `src/avtt/publish.py` (`_write_plan`'s companion-note branch),
`tests/test_scenes.py` (the companion-note test family)
**Found by:** ticket 15's "Observed, not changed" deferral
(docs/tickets/archive/15-scenes-test-gaps.md) + the owner's ask,
2026-10-25

## Problem

The companion-note append promises byte preservation and does not
deliver it. `_write_plan`'s docstring (src/avtt/publish.py:336-341) says
the note is "append-only: existing note text is kept byte for byte",
but the code rewrites the whole file through Python text mode
(src/avtt/publish.py:347-350): `read_text(encoding="utf-8")` applies
universal-newline translation on the way in (every `\r\n`/`\r` becomes
`\n` in memory), and `write_text(..., encoding="utf-8")` translates
every `\n` to `os.linesep` on the way out. On Windows that promotes an
LF note to CRLF throughout; on POSIX the same pair flattens a CRLF note
to LF. Content is preserved; bytes are not.

Reproduced 2026-10-25 through the real CLI (repo venv runner, since
`uv` is not on this shell's PATH; script under %TEMP%, never in the
repo): a campaign whose note was written as raw bytes
`b'Site briefing from the core.\nSecond line.\n'`, then
`python src/avtt/publish.py <campaign> scenes` (exit 0, published):

    BEFORE: b'Site briefing from the core.\nSecond line.\n'
    AFTER:  b'Site briefing from the core.\r\nSecond line.\r\n![[demo.atlasmap]]\r\n'

In-process probes of the same read/write pair the code uses: a
pure-CRLF note happens to round-trip byte-identically on Windows (the
read strips the CRs, the write puts them back); a mixed LF/CRLF note
comes out all-CRLF. Which style survives is the platform's choice, not
the file's — and the CI matrix runs the whole suite on ubuntu-latest
too (.github/workflows/ci.yml:30-33), where the write side has no
`\r\n` to restore and the flattening direction is the one that fires.

Nothing pins byte fidelity, because every companion-note test compares
through the same translation the code uses: `make_campaign` writes the
fixture note via `write_text` (tests/test_scenes.py:126), and the note
family asserts via `read_text` —
`test_companion_note_append_is_idempotent` (tests/test_scenes.py:940-951),
`test_companion_note_preserves_content_without_trailing_newline`
(tests/test_scenes.py:954-959), and the link-shape/anchored-detection
tables (tests/test_scenes.py:962-996). The only byte-level pins are the
refusal and degrade paths — `note_bytes()` (tests/test_scenes.py:139-146),
the refusal family (tests/test_scenes.py:580-622) and the `_inbox/`
degrade pin (tests/test_scenes.py:810-825) — and those are green
because refused and degraded publishes never touch the note.

The note is the one write this repo makes outside `atlas-vtt/`
(contract rule 1's licensed exception, README §2/§9) — user-owned
content, the highest-blast-radius write the system makes (ticket 15's
words). Ticket 15 saw the rewrite, left it alone, and recorded it "for
a future one"; the docstring, not the README, is where the byte claim
lives, and the constitution's own rule (a claim and the code disagree →
fix the same day) is what this ticket executes: the code is made to
match the claim, not the claim lowered to the code.

## Proposal

Make `_write_plan`'s note branch byte-faithful, in
`src/avtt/publish.py`:

1. Read once as bytes: `data = path.read_bytes() if path.is_file()
   else b""` (keeps today's defensive fallback at publish.py:347 for a
   note that vanished between planning and writing).
2. Pick the note's own ending **by count**, the core's convention for
   this exact problem (dnd-campaign-generator/studio/places.py:273-288,
   `_page_snapshot`: the dominant newline "by COUNT, not mere presence
   — one pasted CRLF line in an LF page must not flip the whole file";
   ties go to LF):

       ending = b"\r\n" if data.count(b"\r\n") > data.count(b"\n") - data.count(b"\r\n") else b"\n"

   An empty or all-LF note gets `b"\n"`; a CRLF-dominant note gets
   `b"\r\n"`. Detection, not assumption, is required: the generator
   itself writes these notes via `write_text` with no `newline`
   argument (dnd-campaign-generator/studio/routers/maps.py:355-366), so
   their on-disk style is platform-dependent.
3. Assemble bytes and write them back untranslated:

       new = data                                    # verbatim, mixed endings and all
       if data and data[-1:] not in (b"\n", b"\r"):
           new += ending                             # the file's own style, so the
                                                     # embed line starts on its own line
       path.write_bytes(new + str(payload).encode("utf-8") + ending)

   A lone trailing `\r` counts as terminated (no separator inserted).
   The file always ends newline-terminated, matching today's
   content-level behavior (publish.py:348-350).
4. Everything else is untouched by design: `_note_has_line`
   (publish.py:299-311) keeps its translated-text detection (line
   endings are invisible to the link regex; a non-UTF-8 note raises
   exactly as today); the note's plan state stays `"same" | "missing"`
   (publish.py:324), so idempotency, refuse-on-diff, and `--dry-run`
   output do not change; refused and degraded publishes still never
   touch the note.

No user ruling needed — the owner's ask fixes the direction (make the
code byte-faithful; the docstring's intent stands and becomes true).
README needs no edit: §2 rule 1 and §5.1 promise "append-only", never a
byte contract, and they remain true. Whether the byte tests write their
fixtures via a `note_raw_bytes=` kwarg on `make_campaign` or by
overwriting the note after it returns is implementer's choice — keep
the churn small.

Tests (`tests/test_scenes.py`) — the load-bearing rule: byte-fidelity
tests write fixture notes with `write_bytes` and assert with
`read_bytes()`; no `read_text` anywhere in their assertion chain
(today `make_campaign`'s `write_text` makes even the fixture CRLF on
Windows on disk). Suggested names, final at implementation:

- LF note stays LF: `b"Site briefing from the core.\nSecond line.\n"`
  → existing bytes verbatim + `b"![[demo.atlasmap]]\n"`. This is the
  red-on-Windows-before pin (the repro above fails it today); it is
  green on ubuntu before and after, which is why the CRLF pin below
  exists too.
- CRLF note stays CRLF: `b"alpha\r\nbeta\r\n"` →
  `b"alpha\r\nbeta\r\n![[demo.atlasmap]]\r\n"` — the pin that catches
  the ubuntu direction.
- Mixed, both dominances: `b"lf line\nmore lf\nlast\r\n"` (2 LF vs 1
  CRLF → LF dominant) → original bytes verbatim +
  `b"![[demo.atlasmap]]\n"`; `b"a\r\nb\r\nc\n"` (2 CRLF vs 1 bare LF →
  CRLF dominant) → verbatim + `b"![[demo.atlasmap]]\r\n"`.
- No trailing newline, both styles: `b"no trailing newline"` →
  `b"no trailing newline\n![[demo.atlasmap]]\n"`; `b"alpha\r\nbeta"` →
  `b"alpha\r\nbeta\r\n![[demo.atlasmap]]\r\n"`.
- Empty note (a zero-byte `demo.md` is a legal site — `_site_files`
  asks only for existence, publish.py:189-195): becomes just
  `b"![[demo.atlasmap]]\n"`.
- Idempotency at byte level: convert
  `test_companion_note_append_is_idempotent` (tests/test_scenes.py:940-951)
  to `read_bytes` comparisons (fixture note written as bytes).
- The link-shape/anchored tests (tests/test_scenes.py:962-996) may keep
  their translated-text comparisons; their subject is detection, not
  fidelity.
- The refusal/degrade byte pins (tests/test_scenes.py:139-146, 580-622,
  810-825) stay exactly as they are — this ticket must not weaken the
  guarantee they pin.

Gate: ruff clean and `python run-tests.py` green; `--all` too, per the
house habit (the note append is unit-tier; the integration tier should
be unaffected).

## Acceptance criteria

- [ ] An LF note publishes with its existing bytes verbatim and
      `![[<stem>.atlasmap]]\n` appended — pinned by the byte-level LF
      test (suggested
      `tests/test_scenes.py::test_companion_note_append_is_byte_faithful_lf`,
      name final at implementation); red on Windows before the fix
      (the repro), green after on every CI leg.
- [ ] A CRLF note stays all-CRLF, embed line and terminator included —
      pinned by the byte-level CRLF test (before the fix it would be
      red wherever the ubuntu legs run it, since the flattening
      direction fires there; green after on every leg).
- [ ] Mixed endings survive verbatim and the appended line uses the
      dominant style, both dominances — pinned by the two mixed tests.
- [ ] A note without a trailing newline gains its separator in the
      file's own style, both styles — pinned by the two
      no-trailing-newline tests.
- [ ] An empty note gains just the embed line, LF-terminated — pinned
      by the empty-note test.
- [ ] A republish never rewrites the note byte — pinned by
      `tests/test_scenes.py::test_companion_note_append_is_idempotent`
      converted to `read_bytes` comparisons.
- [ ] The refusal and degrade paths stay byte-identical with their
      existing pins untouched and green —
      `::test_refusals_write_nothing`,
      `::test_refusal_of_a_150mb_file_writes_nothing`,
      `::test_incomplete_site_is_refused`,
      `::test_multiple_sites_publish_and_partial_refusal`, and
      `::test_degrade_path_to_inbox`.
- [ ] `python run-tests.py` green (lint + whole suite) and
      `python run-tests.py --all` green.

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
