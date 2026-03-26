"""Compatibility layer between `grape test` and pytest.

Historically `grape test` ran a custom unittest aggregator. The current
implementation keeps the same user-facing CLI, but delegates execution to
pytest and only translates GRAPE concepts such as suite aliases, changed-file
selection, and default worker counts.
"""

from vine.option import Option
from vine import test_suites
from vine import utility
from vine.vine_logging import log_wrapper
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import os
import shutil
import subprocess
import sys
import threading
import time

import pytest
from tools.render_timing_chart import render_lines


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

            try:
                if workers > 1:
                    good = self._run_parallel(selectors, args) == 0
                else:
                    good = pytest.main(self._build_pytest_args(args, resolved)) == 0
            except ValueError as exc:
                print(f"*** {exc}")
                return True
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
        work_selectors = test_suites.order_selectors(
            selectors or test_suites.all_suite_names()
        )
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
        run_started = time.perf_counter()
        env = os.environ.copy()
        results = []
        progress_state = self._build_progress_state(work_selectors)
        live_output = self._should_render_live_progress(work_selectors)
        live_chart_width = self._chart_width_from_selectors(work_selectors)
        live_drawn = False

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    self._run_subprocess_pytest,
                    selector,
                    args,
                    env,
                    progress_state,
                ): selector
                for selector in parallel_selectors
            }
            results.extend(
                self._collect_parallel_results(
                    futures,
                    work_selectors,
                    progress_state,
                    run_started,
                    live_output,
                    live_chart_width,
                    live_drawn,
                )
            )
            live_drawn = live_output and bool(work_selectors)

            for selector in serial_selectors:
                future = executor.submit(
                    self._run_subprocess_pytest,
                    selector,
                    args,
                    env,
                    progress_state,
                )
                results.extend(
                    self._collect_parallel_results(
                        {future: selector},
                        work_selectors,
                        progress_state,
                        run_started,
                        live_output,
                        live_chart_width,
                        live_drawn,
                    )
                )
                live_drawn = live_output and bool(work_selectors)

        failed = False
        ordered = {selector: index for index, selector in enumerate(work_selectors)}
        sorted_results = sorted(results, key=lambda item: ordered[item[0]])
        chart_width = self._chart_width(sorted_results)
        chart_timings = [
            {
                "name": selector,
                "returncode": completed.returncode,
                "start": started_at - run_started,
                "end": ended_at - run_started,
            }
            for selector, completed, started_at, ended_at in sorted_results
        ]
        if not live_output:
            for line in render_lines(chart_timings, chart_width, "."):
                print(f"[grape test] {line}")
        elif chart_timings:
            self._draw_live_progress(
                chart_timings,
                live_chart_width,
                already_drawn=live_drawn,
                final=True,
            )

        for selector, completed, _, _ in sorted_results:
            should_print_stdout = completed.returncode != 0 or (
                args["--durations"] and args["--durations"] != "0"
            )
            if should_print_stdout and completed.stdout:
                print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
            failed = failed or completed.returncode != 0
        return 1 if failed else 0

    def _run_subprocess_pytest(self, selector, args, env, progress_state=None):
        """Run one GRAPE suite selector in its own pytest subprocess.

        Each subprocess keeps pytest collection, fixtures, and module globals
        isolated from the other suites. That makes the broad-run `--workers`
        mode predictable for readers who have not used pytest plugins such as
        xdist before: GRAPE is managing a pool of normal pytest processes.
        """
        cmd = [sys.executable, "-m", "pytest"]
        cmd.extend(self._build_pytest_args(args, [test_suites.resolve_selector(selector)]))
        if not args["--debug"] and (not args["--durations"] or args["--durations"] == "0"):
            cmd.append("-q")
        started = time.perf_counter()
        self._mark_suite_running(progress_state, selector, started)
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        ended = time.perf_counter()
        self._mark_suite_completed(progress_state, selector, completed.returncode, ended)
        return selector, completed, started, ended

    def _build_progress_state(self, selectors):
        """Create mutable per-suite state for the live broad-run display."""
        lock = threading.Lock()
        suites = {
            selector: {
                "start": None,
                "end": None,
                "returncode": None,
            }
            for selector in selectors
        }
        return {"lock": lock, "suites": suites}

    def _mark_suite_running(self, progress_state, selector, started):
        if not progress_state:
            return
        with progress_state["lock"]:
            progress_state["suites"][selector]["start"] = started

    def _mark_suite_completed(self, progress_state, selector, returncode, ended):
        if not progress_state:
            return
        with progress_state["lock"]:
            progress_state["suites"][selector]["end"] = ended
            progress_state["suites"][selector]["returncode"] = returncode

    def _should_render_live_progress(self, selectors):
        """Only use cursor-based redraws for interactive broad runs."""
        return (
            len(selectors) > 1
            and sys.stdout.isatty()
            and not utility.IS_NON_INTERACTIVE
        )

    def _collect_parallel_results(
        self,
        futures,
        ordered_selectors,
        progress_state,
        run_started,
        live_output,
        chart_width,
        live_drawn,
    ):
        results = []
        while futures:
            done, _ = wait(
                list(futures.keys()),
                timeout=0.1 if live_output else None,
                return_when=FIRST_COMPLETED,
            )
            if live_output:
                chart_timings = self._progress_chart_timings(
                    ordered_selectors,
                    progress_state,
                    run_started,
                )
                self._draw_live_progress(
                    chart_timings,
                    chart_width,
                    already_drawn=live_drawn,
                )
                live_drawn = True
            for future in done:
                results.append(future.result())
                del futures[future]
        return results

    def _progress_chart_timings(self, ordered_selectors, progress_state, run_started):
        """Build renderer input for the current live display snapshot."""
        now = time.perf_counter()
        timings = []
        with progress_state["lock"]:
            snapshot = {
                selector: dict(values)
                for selector, values in progress_state["suites"].items()
            }
        for selector in ordered_selectors:
            suite_state = snapshot[selector]
            started = suite_state["start"]
            ended = suite_state["end"]
            if started is None:
                timings.append(
                    {
                        "name": selector,
                        "status": "( )",
                        "start": 0.0,
                        "end": 0.0,
                        "duration_text": "0.00 seconds",
                    }
                )
                continue

            relative_start = max(0.0, started - run_started)
            if ended is None:
                relative_end = max(relative_start, now - run_started)
                status = "(...)"
            else:
                relative_end = max(relative_start, ended - run_started)
                status = f"({suite_state['returncode']})"
            timings.append(
                {
                    "name": selector,
                    "status": status,
                    "start": relative_start,
                    "end": relative_end,
                    "duration_text": f"{relative_end - relative_start:.2f} seconds",
                }
            )
        return timings

    def _draw_live_progress(self, chart_timings, chart_width, already_drawn=False, final=False):
        if not chart_timings:
            return
        span_end = max(30.0, max(item["end"] for item in chart_timings))
        lines = [
            f"[grape test] {line}"
            for line in render_lines(
                chart_timings,
                chart_width,
                ".",
                global_start=0.0,
                global_end=span_end,
            )
        ]
        if already_drawn:
            sys.stdout.write(f"\x1b[{len(lines)}F")
        for line in lines:
            sys.stdout.write("\x1b[2K")
            sys.stdout.write(line)
            sys.stdout.write("\n")
        if final:
            sys.stdout.flush()
            return
        sys.stdout.flush()

    def _chart_width_from_selectors(self, selectors):
        """Estimate chart width before subprocesses finish.

        The live display needs a width before final timings exist, so it sizes
        the numeric column pessimistically and lets the standalone renderer
        right-justify the duration text within that reserved space.
        """
        if not selectors:
            return 40
        terminal_width = shutil.get_terminal_size((120, 20)).columns
        longest_label = max(len(selector) for selector in selectors)
        reserved = len("[grape test] ") + longest_label + len(" (...) 0000.00 seconds []")
        return max(20, min(80, terminal_width - reserved))

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

    def _chart_width(self, results):
        """Choose a readable schedule-bar width for broad-run summaries."""
        if not results:
            return 40
        return self._chart_width_from_selectors(
            [selector for selector, _, _, _ in results]
        )

    def setDefaultConfig(self, config):
        pass
