"""Compatibility layer between `grape test` and pytest.

Historically `grape test` ran a custom unittest aggregator. The current
implementation keeps the same user-facing CLI, but delegates execution to
pytest and only translates GRAPE concepts such as suite aliases, changed-file
selection, and default worker counts.
"""

from vine.option import Option
from vine import test_suites
from vine.vine_logging import log_wrapper
from concurrent.futures import ThreadPoolExecutor
import os
import subprocess
import sys

import pytest


class Test(Option):
    """
    grape test
    Runs grape's unit tests.
    Usage: grape-test [--debug] [--durations=<n>] [--workers=<n>] [--changed] [--base=<ref>] [<suite>]...


    Arguments:
    <suite>  The name of the suite to test. The default is all.
             Enter listSuites as the suite name to list available suites.
             <suite> = <suite name>.<test> will run a particular test in a suite.

    Options:
    --debug          Disable output capture and preserve debug logging behavior.
    --durations=<n>  Show the slowest n tests in pytest output. Pytest prints
                     a summary of the slowest individual tests at the end of
                     the run. [default: 0]
    --workers=<n>    Run multiple suite selectors in parallel subprocesses.
                     This is GRAPE-level parallelism: each selected suite is
                     handed to a separate pytest process rather than using a
                     pytest plugin such as xdist. [default: 1]
    --changed        Run suites mapped from files changed since --base.
                     This is intended for local developer loops where a full
                     suite run would be unnecessarily broad.
    --base=<ref>     Base ref for --changed selection. [default: origin/master]

    """
    def __init__(self):
        super(Test, self).__init__()
        self._key = "test"
        self._section = "Other"

    def description(self):
        return "Test Grape."

    @log_wrapper
    def execute(self, args):
        """Resolve GRAPE-style arguments and execute the matching pytest run."""
        selectors = args["<suite>"] or []
        if selectors == ["listSuites"]:
            print(dict.fromkeys(test_suites.visible_suite_names()).keys())
            return True

        if args["--changed"] and not selectors:
            selectors = self._selectors_from_changed_files(args["--base"])
            if not selectors:
                print("No changed suites matched the current diff.")
                return True

        try:
            workers = self._parse_workers(
                args["--workers"],
                selectors=selectors,
                debug=args["--debug"],
            )
        except ValueError:
            print("*** --workers must be an integer >= 1")
            return True

        try:
            resolved = test_suites.resolve_selectors(selectors) if selectors else None
        except KeyError as exc:
            print(exc.args[0])
            return True

        previous_debug = os.environ.get("GRAPE_TEST_DEBUG")
        try:
            if args["--debug"]:
                os.environ["GRAPE_TEST_DEBUG"] = "1"
                workers = 1
            else:
                os.environ.pop("GRAPE_TEST_DEBUG", None)

            if workers > 1:
                good = self._run_parallel(selectors, args) == 0
            else:
                good = pytest.main(self._build_pytest_args(args, resolved)) == 0
        finally:
            if previous_debug is not None:
                os.environ["GRAPE_TEST_DEBUG"] = previous_debug
            elif "GRAPE_TEST_DEBUG" in os.environ:
                del os.environ["GRAPE_TEST_DEBUG"]

        if not good:
            print("*"*80)
            print("*"*80)
            print("Hey, a test has failed")
            print("*"*80)
            print("*"*80)
            exit(1)
        return True

    def _build_pytest_args(self, args, resolved_selectors):
        """Translate GRAPE options into the subset of pytest arguments we use."""
        pytest_args = []
        if args["--debug"]:
            pytest_args.append("-s")

        durations = args["--durations"]
        if durations and durations != "0":
            pytest_args.append(f"--durations={durations}")

        if resolved_selectors:
            pytest_args.extend(resolved_selectors)
        else:
            pytest_args.append("test")
        return pytest_args

    def _run_parallel(self, selectors, args):
        """Run broad GRAPE suite selections in parallel subprocesses.

        We parallelize at the GRAPE suite layer instead of inside pytest so we
        can keep explicit control over:
        - which suites must remain serial
        - how output is summarized
        - environments that do not have pytest-xdist installed
        """
        work_selectors = selectors or test_suites.all_suite_names()
        parallel_selectors = [
            selector for selector in work_selectors if not test_suites.is_serial_selector(selector)
        ]
        serial_selectors = [
            selector for selector in work_selectors if test_suites.is_serial_selector(selector)
        ]
        workers = self._parse_workers(
            args["--workers"],
            selectors=work_selectors,
            debug=args["--debug"],
        )
        env = os.environ.copy()
        results = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(self._run_subprocess_pytest, selector, args, env)
                for selector in parallel_selectors
            ]
            for future in futures:
                results.append(future.result())

        for selector in serial_selectors:
            results.append(self._run_subprocess_pytest(selector, args, env))

        failed = False
        ordered = {selector: index for index, selector in enumerate(work_selectors)}
        for selector, completed in sorted(results, key=lambda item: ordered[item[0]]):
            print(f"[grape test] {selector} ({completed.returncode})")
            should_print_stdout = completed.returncode != 0 or (
                args["--durations"] and args["--durations"] != "0"
            )
            if should_print_stdout and completed.stdout:
                print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
            failed = failed or completed.returncode != 0
        return 1 if failed else 0

    def _run_subprocess_pytest(self, selector, args, env):
        """Run one GRAPE suite selector in its own pytest subprocess."""
        cmd = [sys.executable, "-m", "pytest"]
        cmd.extend(self._build_pytest_args(args, [test_suites.resolve_selector(selector)]))
        if not args["--debug"] and (not args["--durations"] or args["--durations"] == "0"):
            cmd.append("-q")
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        return selector, completed

    def _parse_workers(self, value, *, selectors, debug):
        """Choose a worker count when the user does not specify one.

        Broad runs default to 4 workers because that is the best measured point
        in this repository so far. Narrow runs stay serial by default so simple
        one-suite invocations preserve readable pytest output and avoid
        subprocess overhead.
        """
        if value in (None, ""):
            if debug:
                return 1
            if selectors and len(selectors) <= 1:
                return 1
            return 4
        return max(1, int(value))

    def _selectors_from_changed_files(self, base_ref):
        """Map git-changed files to GRAPE suite aliases."""
        changed_paths = self._changed_paths(base_ref)
        return test_suites.select_suites_for_changed_paths(changed_paths)

    def _changed_paths(self, base_ref):
        """Return the union of committed, staged, and unstaged changed paths."""
        commands = [
            ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
            ["git", "diff", "--name-only", "--cached"],
            ["git", "diff", "--name-only"],
        ]
        changed = []
        seen = set()
        for cmd in commands:
            completed = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if completed.returncode != 0:
                continue
            for line in completed.stdout.splitlines():
                if line and line not in seen:
                    seen.add(line)
                    changed.append(line)
        return changed

    def setDefaultConfig(self, config):
        pass
