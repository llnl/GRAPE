from vine import grapeGit as git
from vine.option import Option
from vine import test_suites
from vine.vine_logging import log_wrapper
import os

import pytest


class Test(Option):
    """
    grape test
    Runs grape's unit tests.
    Usage: grape-test [--debug] [--durations=<n>] [<suite>]...


    Arguments:
    <suite>  The name of the suite to test. The default is all.
             Enter listSuites as the suite name to list available suites.
             <suite> = <suite name>.<test> will run a particular test in a suite.

    Options:
    --debug          Disable output capture and preserve debug logging behavior.
    --durations=<n>  Show the slowest n tests in pytest output. [default: 0]

    """
    def __init__(self):
        super(Test, self).__init__()
        self._key = "test"
        self._section = "Other"

    def description(self):
        return "Test Grape."

    @log_wrapper
    def execute(self, args):
        # Allow cloning from file for testing
        git.addGitConfigFlag('-c protocol.file.allow=always')
        git.addGitConfigFlag('-c init.defaultBranch=master')

        selectors = args["<suite>"] or []
        if selectors == ["listSuites"]:
            print(dict.fromkeys(test_suites.visible_suite_names()).keys())
            return True

        pytest_args = []
        if args["--debug"]:
            pytest_args.append("-s")

        durations = args["--durations"]
        if durations and durations != "0":
            pytest_args.append(f"--durations={durations}")

        if selectors:
            try:
                pytest_args.extend(test_suites.resolve_selectors(selectors))
            except KeyError as exc:
                print(exc.args[0])
                return True
        else:
            pytest_args.append("test")

        previous_debug = os.environ.get("GRAPE_TEST_DEBUG")
        if args["--debug"]:
            os.environ["GRAPE_TEST_DEBUG"] = "1"
        else:
            os.environ.pop("GRAPE_TEST_DEBUG", None)

        good = pytest.main(pytest_args) == 0

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

    def setDefaultConfig(self, config):
        pass
