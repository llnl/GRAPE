"""Pytest-native scenario coverage for workspace topology tests.

These tests replace the older dynamic unittest generation for `Status` and
`GrapeUp`. If you are new to pytest, the two key ideas used here are:

- fixtures:
  reusable setup/teardown helpers injected into test functions by name
- parametrization:
  one test function can be run multiple times with different inputs, producing
  separate test cases in pytest's output
"""

import pytest

from test import testGrape
from test import testProjectScenarios
from test import testStatus
from test import testUpdateLocal


def _scenario_params():
    """Build the scenario objects that will feed pytest parametrization.

    We create one object per scenario class and reuse it across parametrized
    cases so the snapshot cache inside `ResettableProject` can survive between
    test invocations.
    """
    scenario_classes = testProjectScenarios.find_subclasses(
        testProjectScenarios, testProjectScenarios.grapeProject
    )
    scenarios = [
        scenario_class(scenario_class.__name__)
        for scenario_class in scenario_classes
    ]
    return [
        pytest.param(
            scenario,
            id=scenario.__class__.__name__,
        )
        for scenario in scenarios
    ]


SCENARIO_PARAMS = _scenario_params()


@pytest.fixture
def grape_case():
    """Provide the common `TestGrape` harness to pytest functions.

    In pytest, a fixture is a setup helper that is requested by name. Any test
    function that includes `grape_case` as an argument gets a ready-to-use
    `TestGrape` instance and pytest automatically runs the teardown after the
    test finishes.
    """
    case = testGrape.TestGrape("runTest")
    case.setUp()
    try:
        yield case
    finally:
        case.tearDown()


@pytest.mark.scenario
@pytest.mark.slow
class TestStatusScenarios:
    """Status coverage expressed as pytest parametrized tests."""

    @pytest.mark.parametrize("scenario", SCENARIO_PARAMS)
    def testGrapeStatus(self, grape_case, scenario):
        scenario.reset(grape_case.defaultWorkingDirectory)
        testStatus.assert_grape_status(grape_case, scenario)

    @pytest.mark.parametrize("scenario", SCENARIO_PARAMS)
    def testGrapeCheckoutOfMasterFixesGrapeStatusBranchConsistency(
        self, grape_case, scenario
    ):
        scenario.reset(grape_case.defaultWorkingDirectory)
        testStatus.assert_checkout_fixes_branch_consistency(grape_case, scenario)


@pytest.mark.scenario
@pytest.mark.slow
class TestGrapeUpScenarios:
    """`grape up` coverage expressed as pytest parametrized tests."""

    @pytest.mark.parametrize("scenario", SCENARIO_PARAMS)
    def testGrapeUp(self, grape_case, scenario):
        scenario.reset(grape_case.defaultWorkingDirectory)
        testUpdateLocal.assert_grape_up(grape_case, scenario)
