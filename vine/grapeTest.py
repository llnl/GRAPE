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
    Usage: grape-test [--debug] [--durations=<n>] [--workers=<n>] [<suite>]...


    Arguments:
    <suite>  The name of the suite to test. The default is all.
             Enter listSuites as the suite name to list available suites.
             <suite> = <suite name>.<test> will run a particular test in a suite.

    Options:
    --debug          Disable output capture and preserve debug logging behavior.
    --durations=<n>  Show the slowest n tests in pytest output. [default: 0]
    --workers=<n>    Run multiple suite selectors in parallel subprocesses. [default: 1]

    """
    def __init__(self):
        super(Test, self).__init__()
        self._key = "test"
        self._section = "Other"

    def description(self):
        return "Test Grape."

    @log_wrapper
    def execute(self, args):
        selectors = args["<suite>"] or []
        if selectors == ["listSuites"]:
            print(dict.fromkeys(test_suites.visible_suite_names()).keys())
            return True

        try:
            workers = self._parse_workers(args["--workers"])
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
        work_selectors = selectors or test_suites.all_suite_names()
        parallel_selectors = [
            selector for selector in work_selectors if not test_suites.is_serial_selector(selector)
        ]
        serial_selectors = [
            selector for selector in work_selectors if test_suites.is_serial_selector(selector)
        ]
        workers = self._parse_workers(args["--workers"])
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
            if completed.returncode != 0 and completed.stdout:
                print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
            failed = failed or completed.returncode != 0
        return 1 if failed else 0

    def _run_subprocess_pytest(self, selector, args, env):
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

    def _parse_workers(self, value):
        if value in (None, ""):
            return 1
        return max(1, int(value))

    def setDefaultConfig(self, config):
        pass
