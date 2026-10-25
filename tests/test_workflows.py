"""The saved ticket workflows must not hardcode one machine (ticket 19).

``.zcode/workflows/`` carries the ticket loop AGENTS.md presents as *the*
way tickets happen, in a now-public repo: a stranger cloning it must be
able to run both scripts. They therefore derive ROOT from the runtime
environment (``git rev-parse --show-toplevel`` from the run's workspace)
and WT_BASE from ROOT's parent, and the forge probes the private
campaign-generator sibling before pointing the writer at it, degrading to
in-repo grounding when it is absent. Text-read discipline (the
tests/test_pin.py, tests/test_ci.py style): the scripts are read as text,
the grep is list-form subprocess with an explicit cwd.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".zcode" / "workflows"
FORGE = WORKFLOWS / "avtt-ticket-forge.dwf.ts"
IMPLEMENTER = WORKFLOWS / "avtt-ticket-implementer.dwf.ts"


# --- no machine path returns to the loop -------------------------------------


def test_no_machine_path_is_hardcoded_in_the_workflows():
    """`git grep -n "C:/Users" -- .zcode/workflows/` stays empty — the
    checkable criterion of ticket 19, run as stated. git grep exits 1 on
    no match, which is the pass; any other nonzero exit is an error."""
    proc = subprocess.run(
        ["git", "grep", "-n", "C:/Users", "--", ".zcode/workflows/"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert proc.returncode in (0, 1), proc.stdout + proc.stderr
    assert proc.stdout.strip() == "", \
        "a machine-specific path returned to the workflows:\n" + proc.stdout


def test_no_machine_path_in_either_script_text():
    """The literal is gone from the file contents themselves, tracked or
    not: neither script may carry any C:/Users string, and neither may
    assign ROOT or WT_BASE as a path literal."""
    for path in (FORGE, IMPLEMENTER):
        text = path.read_text(encoding="utf-8")
        assert "C:/Users" not in text, path.name + " still hardcodes a path"
        assert not re.search(r'const (?:ROOT|WT_BASE) = "C:', text), \
            path.name + " assigns ROOT/WT_BASE as a path literal"


# --- the derivation is in the scripts ----------------------------------------


def test_root_is_derived_from_the_runtime_environment():
    """ROOT comes from `git rev-parse --show-toplevel` run from the
    workspace, and the scripts abort loudly when it fails instead of
    operating on a wrong path — the failure mode ticket 19 exists to
    prevent."""
    for path in (FORGE, IMPLEMENTER):
        text = path.read_text(encoding="utf-8")
        assert '["rev-parse", "--show-toplevel"]' in text, \
            path.name + " must derive ROOT via git rev-parse --show-toplevel"
        assert 'if (ROOT === "")' in text, \
            path.name + " must abort when the root derivation fails"


def test_wt_base_derives_from_the_repo_parent():
    """WT_BASE is ROOT's parent + the worktree base name (the repo's
    sibling layout, AGENTS.md), not a literal: the implementer's per-run
    worktrees follow whatever checkout the run started from."""
    text = IMPLEMENTER.read_text(encoding="utf-8")
    assert 'ROOT.slice(0, parentSlash) + "/dcg-avtt-wt"' in text, \
        "WT_BASE must derive from ROOT's parent (the sibling layout)"


# --- the forge grounds the campaign generator only when it can read it -------


def test_forge_probes_the_sibling_before_grounding_in_it():
    """The grounding instruction is conditional: the script probes the
    sibling (git rev-parse through CG_DIR) before the writer is ever
    pointed at it, and the grounded path still names the sibling."""
    text = FORGE.read_text(encoding="utf-8")
    assert "dnd-campaign-generator" in text, \
        "the sibling repo must still be named"
    probe_at = text.find('["-C", CG_DIR, "rev-parse", "--show-toplevel"]')
    assert probe_at != -1, "the forge must probe the sibling before grounding"
    grounding_at = text.find("A claim about the campaign generator")
    assert grounding_at != -1, "the grounded path must still read the sibling"
    assert probe_at < grounding_at, \
        "the existence probe must precede the grounding instruction"


def test_forge_degrades_to_in_repo_grounding_with_a_stated_reason():
    """When the sibling is absent the writer is told to ground ONLY
    in-repo claims and to name the gap — a stranger's forge run must not
    fabricate grounding for a repo it cannot read (ticket 19)."""
    text = FORGE.read_text(encoding="utf-8")
    assert "NO readable campaign-generator checkout" in text, \
        "the degraded path must state why the sibling is unavailable"
    assert "ground ONLY in-repo claims" in text, \
        "the degraded path must restrict grounding to this repo"
    assert "named explicitly there as unverified here" in text, \
        "the degraded path must have the gap named, not silently dropped"
