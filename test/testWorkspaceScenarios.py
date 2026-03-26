import pytest

from test import testGrape
from test import testProjectScenarios
from test import testStatus
from test import testUpdateLocal


def _scenario_params():
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
    case = testGrape.TestGrape("runTest")
    case.setUp()
    try:
        yield case
    finally:
        case.tearDown()


@pytest.mark.scenario
@pytest.mark.slow
class TestStatusScenarios:
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
    @pytest.mark.parametrize("scenario", SCENARIO_PARAMS)
    def testGrapeUp(self, grape_case, scenario):
        scenario.reset(grape_case.defaultWorkingDirectory)
        testUpdateLocal.assert_grape_up(grape_case, scenario)
