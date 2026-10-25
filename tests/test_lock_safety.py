"""The checkout lock's staleness math and the per-stem worktree guard (ticket 20).

Two failure modes made the implementer loop need human surgery exactly when it
was meant to run unattended. A crashed run's main-checkout lock was unstealable
until an hour old — past every waiter's 30-minute give-up — and a corrupt lock
file read as age 0, so it never went stale at all; and two runs of the same
ticket shared one worktree, the second run's `worktree remove --force`
deleting the first run's active workspace mid-flight. The fix lives in
`.zcode/tools/checkout-lock.ps1` and
`.zcode/workflows/avtt-ticket-implementer.dwf.ts` — PowerShell and TypeScript
the Python suite cannot execute (the CI matrix's ubuntu leg has neither), so
these tests pin the ticket's checkable-by-reading criteria with the repo's
text-read discipline (tests/test_pin.py, tests/test_workflows.py style): the
files are read as text and the invariants are asserted on exactly what a
reader would check. The behavioral hand-runs the criteria also name (a corrupt
locks/main.lock steal, a two-terminal stem collision) are recorded in the
ticket's Implementation notes.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / ".zcode" / "tools" / "checkout-lock.ps1"
IMPLEMENTER = ROOT / ".zcode" / "workflows" / "avtt-ticket-implementer.dwf.ts"


def _lock_text() -> str:
    return LOCK.read_text(encoding="utf-8")


def _impl_text() -> str:
    return IMPLEMENTER.read_text(encoding="utf-8")


def _squash(text: str) -> str:
    """Whitespace-collapsed, with the ' //' / ' #' markers of a comment line
    that a phrase was wrapped across removed, so asserted sentences survive
    any rewrapping."""
    flat = re.sub(r"\s+", " ", text)
    return re.sub(r" // | # ", " ", flat)


def _steal_age() -> int:
    m = re.search(r"^\$maxAgeSec = (\d+)$", _lock_text(), re.M)
    assert m, "checkout-lock.ps1 lost its $maxAgeSec constant"
    return int(m.group(1))


def _acquire_wait() -> int:
    m = re.search(r'"acquire", "main", "(\d+)"', _impl_text())
    assert m, "the implementer lost its main-lock acquire call"
    return int(m.group(1))


def _get_age_body() -> str:
    m = re.search(r"function Get-AgeSeconds.*?^}", _lock_text(), re.S | re.M)
    assert m, "checkout-lock.ps1 lost Get-AgeSeconds"
    return m.group(0)


# --- criterion 1: the steal window is reachable -------------------------------


def test_steal_age_is_strictly_less_than_the_acquire_wait():
    """maxAgeSec < the implementer's acquire timeout: a waiter must always be
    able to steal a crashed holder's lock before giving up itself. The old
    3600s steal age against the 1800s wait meant a crashed run's lock burned
    every implementer run's full 30-minute timeout before it could be stolen."""
    assert _steal_age() < _acquire_wait(), (
        f"steal age {_steal_age()}s is not below the implementer's "
        f"{_acquire_wait()}s acquire wait — a crashed run's lock would again "
        "outlive every waiter")
    assert _steal_age() > 0, "a zero steal age would make every live lock stale"


def test_the_invariant_is_stated_at_both_sites():
    """The two numbers are one contract, not two knobs — the comment saying so
    lives where both constants are defined, so changing one without the other
    reads as the bug it is."""
    invariant = "strictly less than the longest acquire wait"
    for name, text in (("checkout-lock.ps1", _lock_text()),
                       ("avtt-ticket-implementer.dwf.ts", _impl_text())):
        assert invariant in _squash(text), \
            name + " no longer states the steal-age invariant"
        assert "one contract, not two knobs" in _squash(text), \
            name + " no longer states the invariant's one-contract rule"


def test_the_acquire_loop_still_steals_on_age():
    """The corrupt path only helps if its age feeds the steal decision: the
    acquire loop must still steal a lock whose age exceeds $maxAgeSec."""
    text = _lock_text()
    assert "-gt $maxAgeSec" in text, "the steal-on-age check vanished"
    assert "Get-AgeSeconds $lockPath" in text, \
        "the steal decision no longer reads the lock's age"


# --- criterion 2: a corrupt lock is stealable immediately ---------------------


def test_corrupt_lock_content_reads_as_infinitely_old():
    """Get-AgeSeconds' unparseable-content path returns PositiveInfinity, not
    0: age 0 read as brand-new, so a corrupt lock never went stale and only a
    hand-deleted locks/main.lock unblocked the loop. Infinitely old is
    stealable immediately by the age check above."""
    body = _get_age_body()
    assert "return [double]::PositiveInfinity" in body, \
        "Get-AgeSeconds must read corrupt lock content as infinitely old"
    assert not re.search(r"catch\s*\{\s*return 0\s*\}", body), \
        "a bare catch returning 0 is the corrupt-lock-reads-as-fresh deadlock"


def test_status_survives_an_infinite_age():
    """`status` casts the age to [int] for display; [int] on PositiveInfinity
    throws, so the display must special-case it instead of erroring."""
    text = _lock_text()
    assert "[double]::IsInfinity" in text, \
        "status must not cast an infinite (corrupt-lock) age to [int]"


def test_lock_script_is_pure_ascii():
    """powershell.exe 5.1 reads a BOM-less script as ANSI: a multi-byte char
    inside a quoted string garbles into a quote and the whole script stops
    parsing (found by the corrupt-lock hand-run, 2026-10-24 — an em dash in
    the status message took the tool down). The script stays pure ASCII."""
    raw = LOCK.read_bytes()
    high = [b for b in raw if b >= 128]
    assert not high, \
        f"checkout-lock.ps1 must stay pure ASCII; found {len(high)} byte(s) >= 128"


# --- criterion 3: the per-stem guard ------------------------------------------


def test_stem_lock_guards_the_worktree_setup():
    """The implementer acquires stem-<stem> with a short timeout BEFORE its
    first worktree mutation: a second run of the same ticket (same stem, same
    worktree path) is refused before any `worktree remove --force` can reach
    the first run's active workspace."""
    text = _impl_text()
    assert '"acquire", "stem-" + stem, "60"' in text, \
        "the stem lock must be acquired as stem-<stem> with a short timeout"
    guard_at = text.find("if (!(await lockStem(stem)))")
    assert guard_at != -1, "the implementer lost its per-stem guard"
    force_at = text.find('"worktree", "remove", "--force"')
    assert force_at != -1, "the worktree-setup remove --force vanished"
    assert guard_at < force_at, \
        "the stem guard must precede the first `worktree remove --force`"


def test_a_held_stem_lock_fails_fast_naming_the_stem():
    """A held stem lock means another run owns that ticket's workspace: the
    abort message says so, names the running stem, and refuses to double-start
    — it is a 60s fail-fast, not a 30-minute wait and not a remove --force."""
    text = _impl_text()
    guard_at = text.find("if (!(await lockStem(stem)))")
    assert guard_at != -1
    block = _squash(text[guard_at:text.find("const existing", guard_at)])
    assert 'the per-stem lock stem-" + stem + " is held' in block, \
        "the abort message must name the held stem lock"
    assert "another implementer run for this same ticket owns worktree" in block
    assert "Refusing to double-start" in block, \
        "the abort must say the double-start is refused, not queued"


def test_stem_lock_is_held_until_cleanup():
    """'A held stem lock means another run owns that workspace' must be true
    for the whole run, so the lock is released only at the run's two exits:
    the flagged setup exit and after the post-merge cleanup — whose worktree
    remove therefore runs under the lock, not after it."""
    text = _impl_text()
    assert text.count("await unlockStem(stem);") == 2, (
        "the stem lock must be released at exactly the two exits — a third "
        "release site (or a lost one) changes what 'held' means")
    cleanup_rm = text.find('["-C", ROOT, "worktree", "remove", WT]')
    assert cleanup_rm != -1, "the post-merge worktree cleanup vanished"
    release_after = text.find("await unlockStem(stem);", cleanup_rm)
    assert release_after != -1, \
        "the post-merge cleanup must run before the stem lock is released"


# --- criterion 4: the honest header -------------------------------------------


def test_header_states_the_concurrency_scope_honestly():
    """'Safe to run several tickets concurrently' was true for different
    tickets and silent about same-ticket runs — the exact silence that let two
    runs of one ticket destroy each other's worktree. The header now scopes
    the claim to *different* tickets and states the same-ticket refusal."""
    squashed = _squash(_impl_text())
    assert "Safe to run several *different* tickets concurrently" in squashed
    assert "the same ticket refuses to double-start" in squashed, \
        "the header must state the same-ticket refusal"
    assert "Safe to run several tickets concurrently" not in squashed, \
        "the unqualified concurrency claim is back"
