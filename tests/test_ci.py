"""CI must run what it claims, from the lock, on a real matrix (ticket 13).

The tier model these tests hold ``.github/workflows/ci.yml`` to: there
is one tier — the whole suite, golden-file tests included, on the
committed captures — so CI's golden coverage is by design, not accident
(ticket 13). CI installs from ``uv.lock`` (``uv sync --locked``, guarded
by ``uv lock --check``), proves the 3.10 floor and a modern (>= 3.13)
leg, keeps its Windows leg (the repo is Windows-first, README §9), and
cancels superseded runs. ``ci.yml`` parses as YAML (PyYAML is the repo's
one dependency); pyproject.toml is read as text, the tests/test_pin.py
discipline.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CI = yaml.safe_load(
    (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
JOB = CI["jobs"]["fast-tier"]


def _run_lines() -> list[str]:
    return [line for step in JOB["steps"] if "run" in step
            for line in str(step["run"]).splitlines()]


# --- CI installs from the lock, and proves it --------------------------------


def test_ci_lint_covers_tools():
    """The lint step names tools/ (ticket 21): capture-golden.py is §8's
    only human-free step and runs only at pin bumps, so a syntax error
    landing between bumps must be a red build, not invisible bit-rot."""
    lint = [line for line in _run_lines() if "ruff check" in line]
    assert lint, "CI must have a ruff check step"
    for line in lint:
        assert re.search(r"\bruff\s+check\b.*\btools\b", line), \
            f"the lint step stopped covering tools/ (ticket 21): {line}"
    runner = (ROOT / "run-tests.py").read_text(encoding="utf-8")
    assert '"tools"' in runner, \
        "run-tests.py's lint suite must lint tools/ too (ticket 21)"


def test_ci_installs_from_the_lock():
    """`uv sync --locked` is the install and `uv lock --check` guards
    drift; no floating `pip install` of pyyaml/ruff remains — the
    pinning-argument contradiction of ticket 13."""
    runs = "\n".join(_run_lines())
    assert "uv lock --check" in runs, \
        "CI must make lock drift a red build (uv lock --check)"
    assert "uv sync --locked" in runs, "CI must install from uv.lock"
    floating = [line for line in runs.splitlines() if "pip install" in line]
    assert not floating, f"CI installs from the lock, not pip: {floating}"


# --- the matrix proves the floor, a modern leg, and Windows ------------------


def test_ci_matrix_proves_floor_modern_and_windows():
    """3.10 (the requires-python floor) and at least one >= 3.13 leg run
    alongside the Windows leg a Windows-first repo requires."""
    matrix = JOB["strategy"]["matrix"]
    versions = [str(v) for v in matrix["python-version"]]
    assert "3.10" in versions, "the requires-python floor must stay proven"
    modern = [v for v in versions
              if v.count(".") == 1 and int(v.split(".")[1]) >= 13]
    assert modern, f"no modern (>= 3.13) leg in the matrix: {versions}"
    assert any("windows" in str(os) for os in matrix["os"]), \
        "the Windows leg must stay (Windows-first, README §9)"


# --- superseded pushes cancel -------------------------------------------------


def test_ci_cancels_superseded_runs():
    """A push during a run cancels it instead of queueing duplicates."""
    concurrency = CI["concurrency"]
    assert concurrency["group"], "concurrency group missing"
    assert concurrency["cancel-in-progress"] is True


# --- the tier model: the fast tier is the whole suite -------------------------


def test_ci_runs_the_gate_not_a_filtered_pytest():
    """CI's test step runs the gate (run-tests.py) — and nothing in CI
    deselects the integration-marked golden tests."""
    runs = "\n".join(_run_lines())
    assert re.search(r"\brun-tests\.py\b", runs), \
        "CI must run the gate (run-tests.py), not a hand-rolled pytest line"
    assert "not integration" not in runs, \
        "deselecting the golden tests in CI is the golden-blind build"


def test_no_addopts_deselect_the_golden_tests():
    """The marker exists so `run-tests.py --all` / README §8 can run the
    golden tests in isolation, never to deselect them: any addopts naming
    the marker is the change that silently deletes CI's golden coverage
    (ticket 13)."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for line in text.splitlines():
        code = line.split("#", 1)[0]
        if re.match(r"\s*addopts\s*=", code):
            assert "integration" not in code, line.strip()


def test_the_plain_suite_collects_the_golden_tests():
    """The behavioral pin: `pytest tests -q` — the suite CI's fast tier
    runs, via run-tests.py — collects the integration-marked golden
    tests. If it ever stops, CI is golden-blind with every light green:
    exactly ticket 13's accident, made impossible."""
    plain = _collected([])
    golden = _collected(["-m", "integration"])
    assert golden, \
        "no integration-marked tests collected — the golden suite is empty"
    blind = golden - plain
    assert not blind, (
        "the plain suite stopped collecting the integration-marked golden "
        "tests — the fast tier CI runs would be golden-blind: "
        + ", ".join(sorted(blind)))


def _collected(marker_args: list[str]) -> set[str]:
    """Node ids `pytest tests -q --collect-only [args]` collects here.
    Collect-only: no test executes; no:cacheprovider: nothing is
    written. List-form args, explicit cwd (the subprocess rule)."""
    cmd = [sys.executable, "-m", "pytest", "tests", "-q", "--collect-only",
           "-p", "no:cacheprovider", *marker_args]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return {line.strip() for line in proc.stdout.splitlines()
            if line.strip().startswith("tests/") and "::" in line}
