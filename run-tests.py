#!/usr/bin/env python3
"""Run the avtt integration test tiers from the repo root.

  python run-tests.py          fast tier: the pytest suite (seconds)
  python run-tests.py --all    reserved for the integration tier (the
                               golden-file tests, README §7.1) — no-op
                               until fixtures/golden-<version>/ exists

Stdlib only. Every subprocess is list-form args — nothing ever goes
through a shell (the family rule, kept from the campaign generator,
whose parent path contained `&`). Each suite gets a summary line and
the run exits nonzero if any suite failed.
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FAST_SUITES = [
    ("avtt", [sys.executable, "-m", "pytest", "tests", "-q"]),
]

INTEGRATION_SUITES = [
    # The golden-file tests, marked `-m integration` (README §7.1): they
    # need the human-captured fixture, and the fast tier skips them
    # until it exists.
    ("avtt-golden", [sys.executable, "-m", "pytest", "tests",
                     "-m", "integration", "-q"]),
]


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

    suites = list(FAST_SUITES)
    tier = "fast"
    if all_tiers:
        # Ready only when a real captured fixture exists — the checked-in
        # golden-<version>/ placeholder (just a README) must not select an
        # empty integration suite (pytest exits 5 on zero collected tests).
        golden = sorted((ROOT / "fixtures").glob("golden-*/sample.atlasmap"))
        if not golden:
            print("note: skipping the integration tier — no "
                  "fixtures/golden-<version>/ yet (capture procedure: "
                  "fixtures/README.md)")
        else:
            suites += INTEGRATION_SUITES
            tier = "fast + integration"
    print(f"run-tests.py: {len(suites)} suite(s), {tier} tier, root {ROOT}")

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
