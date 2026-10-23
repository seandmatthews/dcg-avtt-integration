# 13 — CI and run-tests.py must tell the truth about what they run

**Status:** proposed
**Priority:** P2 — CI's golden coverage is real today **by accident**;
one well-intentioned cleanup makes it vanish with no red build
**Area:** `.github/workflows/ci.yml`, `run-tests.py`, `pyproject.toml`
(marker/addopts decision), README §4 (the run-tests.py line)
**Found by:** full adversarial review, 2026-10-23

## Problem

**The documented tier separation does not exist.** `pyproject.toml:24-33`
registers the `integration` marker but no `addopts` deselects it, so the
"fast" suite (`run-tests.py:23`, plain `pytest tests -q`) collects all
153 tests **including both golden tests** (verified by running it).
Meanwhile:

- `ci.yml:10-12` claims "The integration tier (golden-file tests) needs
  the human-captured fixtures/golden-<version>/ and stays local" —
  false: the fixtures are committed and the fast tier CI runs
  (`ci.yml:44`) executes the golden tests anyway.
- `run-tests.py:5-7` claims `--all` is "no-op until
  fixtures/golden-<version>/ exists" — false for the same reason (and
  doubly stale: the capture has been automated since ticket 08).

So CI is currently golden-safe by accident, and anyone who "fixes" the
fast tier to match its documentation (`-m "not integration"`) makes CI
golden-blind while every light stays green. Under the
README-is-constitution rule this is a same-day doc/code contradiction;
it rides a ticket because the *right* resolution is a design decision,
not a comment edit.

**CI also contradicts its own pinning argument.**
`ci.yml:30-36` is titled "Install test dependencies (pinned)" and argues
"a floating install could go green on a combination never tested
locally" — then installs `pyyaml` and `ruff` completely unpinned
(`pip install pyyaml pytest==9.1.1`; `pip install ruff`), with the
pytest pin a manually duplicated constant whose comment admits the
hazard ("keep in sync when the lock moves"). No CI step ever touches
`uv.lock` (`uv sync --locked` / `uv lock --check` absent), so a
dependency edit without re-locking breaks local `uv run` while CI stays
green — pyproject is CI's truth, the lock is local's, nothing holds
them together.

**The matrix tests an EOL interpreter and nothing modern.**
`ci.yml:20-21` runs `["3.10", "3.11"]` while `requires-python =
">=3.10"` is open-ended and `uv.lock` already carries cp313–cp315
wheels. Python 3.10 reached end-of-life in October 2026; 3.12+ get zero
CI proof inside the claimed support range.

Minor: no `concurrency:` group, so pushes during a run queue duplicate
jobs.

## Proposal

1. **Embrace reality for the tiers** (recommended over re-creating the
   separation): the committed fixtures make the golden tests cheap
   (~0.1 s) and local-only rotable history — so the fast tier simply
   *is* the whole suite. Update `ci.yml`'s comment and `run-tests.py`'s
   docstring to say exactly that; keep `--all` as the explicit
   integration-only runner used by §8's procedure (its exit-nonzero
   behavior is ticket 12's scope, not here). The alternative (real
   `addopts` deselection) is explicitly **not** recommended — it is the
   change that silently deletes CI's golden coverage.
2. **Install from the lock.** Replace the pip installs with
   `astral-sh/setup-uv` + `uv sync --locked` and run the gate via
   `uv run python run-tests.py` / `uv run ruff check …`; add a
   `uv lock --check` step so lock drift is a red build, not a local
   surprise. The duplicated `pytest==9.1.1` constant disappears.
3. **Matrix refresh**: `["3.10", "3.13"]` at minimum (prove the floor
   and one modern leg; 3.10 stays until `requires-python` moves —
   Windows-first: the windows leg stays either way). Add a
   `concurrency: group: ci-${{ github.ref }}, cancel-in-progress: true`
   block.

## Acceptance criteria

- [ ] `ci.yml` and `run-tests.py` describe the tier model that actually
      runs — no comment claims the golden tier "stays local" or that
      `--all` is a no-op (checkable by reading; the golden tests run in
      CI's fast-tier step).
- [ ] CI installs via `uv sync --locked` and includes a `uv lock
      --check` step; no unpinned `pip install` of pyyaml/ruff remains
      (checkable by reading ci.yml).
- [ ] The matrix includes at least one Python ≥ 3.13 leg alongside the
      3.10 floor (checkable by reading ci.yml).
- [ ] A `concurrency` group cancels superseded runs (checkable by
      reading ci.yml).
- [ ] The pushed CI run is green in this exact shape (checkable claim;
      recorded in Implementation notes with the run link).

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
