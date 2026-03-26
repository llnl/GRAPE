#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time

from vine import test_suites

DEFAULT_SUITES = test_suites.all_suite_names()
HEAVY_SUITES = [
    "Status",
    "MergeDown",
    "NestedSubproject",
    "Clone",
    "Publish",
    "GrapeUp",
    "CO",
]


def run_command(cmd, cwd):
    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "seconds": round(time.perf_counter() - started, 2),
        "output": proc.stdout,
    }


def emit_markdown(results):
    print("| Target | Seconds | Return Code |")
    print("| --- | ---: | ---: |")
    for result in results:
        print(
            f"| {result['target']} | {result['seconds']:.2f} | "
            f"{result['returncode']} |"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Measure grape test suite wall-clock timings."
    )
    parser.add_argument(
        "--mode",
        choices=("full", "heavy", "all"),
        default="all",
        help="Which timing set to run.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format.",
    )
    parser.add_argument(
        "--cwd",
        default=".",
        help="Repository root to measure from.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Pass --workers to grape test.",
    )
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.cwd)
    targets = []
    if args.mode in ("full", "all"):
        targets.append(("full", ["./grape", "test"]))
    if args.mode == "heavy":
        suites = HEAVY_SUITES
    elif args.mode == "all":
        suites = DEFAULT_SUITES
    else:
        suites = []
    targets.extend((suite, ["./grape", "test", suite]) for suite in suites)

    results = []
    for target, cmd in targets:
        if args.workers != 1:
            cmd = cmd[:2] + [f"--workers={args.workers}"] + cmd[2:]
        result = run_command(cmd, cwd)
        result["target"] = target
        results.append(result)

    payload = {
        "python": sys.version.split()[0],
        "cwd": cwd,
        "results": results,
    }

    if args.format == "markdown":
        emit_markdown(results)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
