import pytest

from test import testGrape
from test import testProjectScenarios
from test import testStatus
from test import testUpdateLocal


def _scenario_params():
    scenario_classes = testProjectScenarios.find_subclasses(
        testProjectScenarios, testProjectScenarios.grapeProject
    )
    return [
        pytest.param(scenario_class, id=scenario_class.__name__)
        for scenario_class in scenario_classes
    ]


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
    @pytest.mark.parametrize("scenario_class", _scenario_params())
    def testGrapeStatus(self, grape_case, scenario_class):
        scenario = scenario_class(scenario_class.__name__)
        scenario.reset(grape_case.defaultWorkingDirectory)
        testStatus.assert_grape_status(grape_case, scenario)

    @pytest.mark.parametrize("scenario_class", _scenario_params())
    def testGrapeCheckoutOfMasterFixesGrapeStatusBranchConsistency(
        self, grape_case, scenario_class
    ):
        scenario = scenario_class(scenario_class.__name__)
        scenario.reset(grape_case.defaultWorkingDirectory)
        testStatus.assert_checkout_fixes_branch_consistency(grape_case, scenario)


@pytest.mark.scenario
@pytest.mark.slow
class TestGrapeUpScenarios:
    @pytest.mark.parametrize("scenario_class", _scenario_params())
    def testGrapeUp(self, grape_case, scenario_class):
        scenario = scenario_class(scenario_class.__name__)
        scenario.reset(grape_case.defaultWorkingDirectory)
        testUpdateLocal.assert_grape_up(grape_case, scenario)
