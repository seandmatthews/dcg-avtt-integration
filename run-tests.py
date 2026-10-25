#!/usr/bin/env python3
"""Run the avtt test suites from the repo root.

  python run-tests.py          the gate: the lint suite first (ruff over
                               everything Python the repo carries —
                               src, tests, this runner, tools/), then
                               the whole pytest suite (seconds) — the
                               golden-file tests (README §7.1) run in
                               it too, on the committed
                               fixtures/golden-<version>/ captures;
                               nothing is deselected (ticket 13)
  python run-tests.py --all    the same again, then the integration-only
                               golden pass (`-m integration`): the explicit runner
                               README §8's churn procedure uses. The
                               pin's golden fixture is required —
                               missing is an error naming the capture
                               command, never a quiet skip (ticket 12)

The lint suite needs the dev group's ruff; every supported invocation
(`uv run python run-tests.py`, CI's `uv sync --locked`) installs it from
the lock. With a bare interpreter that has pytest but no ruff, the lint
suite fails loudly — it never skips (the tools/ step of ticket 21 exists
because a gate member that only runs at pin bumps rots invisibly).

Stdlib only. Every subprocess is list-form args — nothing ever goes
through a shell (the family rule, kept from the campaign generator,
whose parent path contained `&`). Each suite gets a summary line and
the run exits nonzero if any suite failed.
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

GOLDEN_VERSION_ENV = "AVTT_GOLDEN_VERSION"

# The lint suite: the runtime-crash class (syntax errors, undefined
# names, unused imports/variables — pyproject.toml's ruff select) over
# everything Python the repo carries. tools/ rides here since ticket 21:
# tools/capture-golden.py is §8's only human-free step and runs only at
# pin bumps, so a syntax error there would otherwise land with every
# other gate green.
LINT_SUITES = [
    ("ruff", [sys.executable, "-m", "ruff", "check", "src", "tests",
              "run-tests.py", "tools"]),
]

# The gate's suite: plain `pytest tests -q` — the whole suite, golden
# tests included; they are never deselected (ticket 13).
FAST_SUITES = [
    ("avtt", [sys.executable, "-m", "pytest", "tests", "-q"]),
]

INTEGRATION_SUITES = [
    # The golden-file tests, marked `-m integration` (README §7.1):
    # --all runs them again as their own explicit suite — the isolated
    # pass README §8's procedure reads. They require the golden
    # fixture of the version under test (the pin's, or the
    # AVTT_GOLDEN_VERSION override's) — checked before the suite runs.
    ("avtt-golden", [sys.executable, "-m", "pytest", "tests",
                     "-m", "integration", "-q"]),
]


def _atlas_pin() -> str:
    """``ATLAS_PIN`` read from ``src/avtt/_version.py`` as text: this
    runner is stdlib-only and never imports the package, whose PyYAML
    dependency lives in the uv venv, not necessarily in this
    interpreter (the same text-read tests/test_pin.py applies to
    pyproject.toml)."""
    source = (ROOT / "src" / "avtt" / "_version.py").read_text(encoding="utf-8")
    match = re.search(r'(?m)^ATLAS_PIN = "([^"]+)"', source)
    if not match:
        raise SystemExit("run-tests.py: ATLAS_PIN not found in "
                         "src/avtt/_version.py — cannot scope the golden check")
    return match.group(1)


def run_suite(name, cmd):
    print(f"\n=== {name} ===  ({' '.join(cmd)})", flush=True)
    start = time.monotonic()
    proc = subprocess.run(cmd, cwd=str(ROOT))  # stdio streams live
    secs = time.monotonic() - start
    ok = proc.returncode == 0
    print(f"--- {name}: {'PASS' if ok else 'FAIL (rc=%d)' % proc.returncode}"
          f" in {secs:.1f}s", flush=True)
    return name, ok, secs


def main():
    args = sys.argv[1:]
    all_tiers = "--all" in args
    unknown = [a for a in args if a != "--all"]
    if unknown:
        print(f"usage: python run-tests.py [--all]  (unknown args: {unknown})")
        return 2

    suites = LINT_SUITES + list(FAST_SUITES)
    tier = "lint + whole suite"
    if all_tiers:
        # The integration tier requires the *pin's own* golden fixture
        # (ticket 12): any committed golden-*/ used to select it, which
        # let a pin bump merge with the pin's capture missing while every
        # gate printed green. A missing fixture is an error naming the
        # capture command — the capture is automated and lands in the
        # same change as the pin. With AVTT_GOLDEN_VERSION set (§8 step
        # 3's pre-flip check), that fixture must exist too, because the
        # golden tests read it.
        versions = [_atlas_pin()]
        override = os.environ.get(GOLDEN_VERSION_ENV, "")
        if override and override != versions[0]:
            versions.append(override)
        missing = [v for v in versions
                   if not (ROOT / "fixtures" / f"golden-{v}"
                           / "sample.atlasmap").is_file()]
        if missing:
            for version in missing:
                print(f"error: fixtures/golden-{version}/sample.atlasmap is "
                      f"missing — capture it with `uv run --with "
                      f"websocket-client tools/capture-golden.py {version}` "
                      "(automated, fixtures/README.md) and commit the "
                      "fixture in the same change as the pin")
            print("the integration tier requires the golden fixture above; "
                  "a pin without its capture is not a pin")
            return 2
        suites += INTEGRATION_SUITES
        tier = "lint + whole suite + integration"
    print(f"run-tests.py: {len(suites)} suite(s), {tier}, root {ROOT}")

    results = [run_suite(name, cmd) for name, cmd in suites]

    width = max(len(name) for name, _, _ in results)
    print("\n=== summary ===")
    for name, ok, secs in results:
        print(f"  {name:<{width}}  {'PASS' if ok else 'FAIL'}  {secs:6.1f}s")
    failed = [name for name, ok, _ in results if not ok]
    if failed:
        print(f"FAILED suites: {', '.join(failed)}")
        return 1
    print("all suites passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
