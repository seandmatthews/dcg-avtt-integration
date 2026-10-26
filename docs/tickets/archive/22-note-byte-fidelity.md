# 22 — Byte-faithful companion-note append

**Status:** completed (2026-10-25; implemented on branch
`feature/22-note-byte-fidelity`, reviewer-signed-off same day)
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

- [x] An LF note publishes with its existing bytes verbatim and
      `![[<stem>.atlasmap]]\n` appended — pinned by the byte-level LF
      test (suggested
      `tests/test_scenes.py::test_companion_note_append_is_byte_faithful_lf`,
      name final at implementation); red on Windows before the fix
      (the repro), green after on every CI leg. — [Recorded: the pin
      was reproduced red on Windows before the fix and is green after
      on this machine; green-after on the ubuntu legs is CI's to
      confirm on the merge (see implementation notes) — accepted on
      the reviewer's 2026-10-25 sign-off.]
- [x] A CRLF note stays all-CRLF, embed line and terminator included —
      pinned by the byte-level CRLF test (before the fix it would be
      red wherever the ubuntu legs run it, since the flattening
      direction fires there; green after on every leg). — [Recorded:
      pin exists and is green here; its red-before lives on the ubuntu
      legs by the ticket's own analysis and was not reproducible on
      Windows — accepted on the reviewer's 2026-10-25 sign-off, with
      the ubuntu legs' green CI's to confirm on the merge.]
- [x] Mixed endings survive verbatim and the appended line uses the
      dominant style, both dominances — pinned by the two mixed tests.
- [x] A note without a trailing newline gains its separator in the
      file's own style, both styles — pinned by the two
      no-trailing-newline tests.
- [x] An empty note gains just the embed line, LF-terminated — pinned
      by the empty-note test.
- [x] A republish never rewrites the note byte — pinned by
      `tests/test_scenes.py::test_companion_note_append_is_idempotent`
      converted to `read_bytes` comparisons.
- [x] The refusal and degrade paths stay byte-identical with their
      existing pins untouched and green —
      `::test_refusals_write_nothing`,
      `::test_refusal_of_a_150mb_file_writes_nothing`,
      `::test_incomplete_site_is_refused`,
      `::test_multiple_sites_publish_and_partial_refusal`, and
      `::test_degrade_path_to_inbox`.
- [x] `python run-tests.py` green (lint + whole suite) and
      `python run-tests.py --all` green.

## Implementation notes (2026-10-25)

Landed as proposed, with these final details:

- **Code** (`src/avtt/publish.py`, `_write_plan`): the note branch reads
  `path.read_bytes()` (empty when the note vanished between planning and
  writing — the old defensive fallback, kept), picks the ending by count
  (`b"\r\n"` only when CRLF count strictly beats bare-LF count, ties to
  LF), inserts it as separator only when the note does not already end
  in `\n` or `\r` (a lone trailing `\r` counts as terminated), and
  writes everything back with one `write_bytes`. `_note_has_line`,
  the `"same" | "missing"` plan state, refuse-on-diff and `--dry-run`
  are untouched. The docstring's byte claim now states the mechanism.
- **Tests** (`tests/test_scenes.py`): `make_campaign` gained a
  `note_raw_bytes=` kwarg (`write_bytes` when given; the `write_text`
  default path is unchanged, so no existing fixture's on-disk endings
  moved). Final names: `test_companion_note_append_is_byte_faithful_lf`,
  `test_companion_note_append_is_byte_faithful_crlf`,
  `test_companion_note_mixed_endings_survive_verbatim[lf-dominant]` /
  `[crlf-dominant]`,
  `test_companion_note_unterminated_gains_its_own_separator[lf-style]` /
  `[crlf-style]`, `test_companion_note_empty_gains_just_the_embed_line`;
  `test_companion_note_append_is_idempotent` converted to `read_bytes`
  with its fixture written as bytes. No `read_text` in any of their
  assertion chains. The link-shape/anchored tests kept their
  translated-text comparisons (detection, not fidelity); the
  refusal/degrade byte pins are untouched.
- **Red-before, recorded 2026-10-25 on Windows** (new byte tests run
  against the unfixed code): 6 failed, 2 passed — the failures were the
  LF pin, both mixed params, the unterminated LF param, the empty note
  and the converted idempotency test; the two passes were the CRLF pins
  (`byte_faithful_crlf`, `unterminated[crlf-style]`), exactly the
  ticket's prediction that pure-CRLF round-trips by accident on Windows
  and their red-before lives on the ubuntu legs.
- **How it landed (2026-10-25):** reviewer signed off the same day the
  implementation landed; the branch carries a single commit (amended
  once, to fold this status flip and the archive move in — the
  ticket-mandated one-commit shape — so the pre-amend hash is not
  quotable here; the merge into main records the final one). All eight
  acceptance criteria are ticked: six on direct local evidence, the LF
  and CRLF pins' "green after on every CI leg" clause on the
  reviewer's sign-off — the ubuntu-latest legs of
  `.github/workflows/ci.yml` were never runnable from this Windows
  machine, and that confirmation is CI's to make on the merge. That is
  the one piece of evidence recorded here without a local run behind
  it; everything else cites a command run on 2026-10-25 (listed below).
- **Deliberate deviations from the proposal, both small:** the byte
  tests write their fixtures through a `note_raw_bytes=` kwarg on
  `make_campaign` rather than overwriting the note after it returns
  (the ticket allowed either; the kwarg keeps the bytes-path explicit
  and documented); final test names as listed above. Nothing else
  moved: `_note_has_line`, plan states, refuse-on-diff, `--dry-run`
  and the refusal/degrade pins are untouched, as proposed.
- **Known stale comment, left deliberately:**
  `test_multiple_sites_publish_and_partial_refusal` still explains its
  text-mode comparison with "the append rewrites through Python text
  mode" — true when written, no longer true. The acceptance criterion
  says that test stays *untouched*, so it was; the comment is wrong
  about mechanism only, and the comparison itself (through universal
  newlines) still holds and passes. First editor after the flip may
  reword it.
- **Gates run locally (2026-10-25):** `python -m uv tool run ruff check
  src tests run-tests.py` — all checks passed; `python -m uv run python
  run-tests.py` — ruff + 289 passed; `python -m uv run python
  run-tests.py --all` — ruff + 289 + 2 integration, all suites passed.
