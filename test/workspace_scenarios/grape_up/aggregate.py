import pytest

from test import testUpdateLocal
from test.workspace_scenarios.shared import ALL_SCENARIO_PARAMS
from test.workspace_scenarios.shared import grape_case


pytestmark = [pytest.mark.scenario, pytest.mark.slow]


class TestGrapeUpScenarios:
    """Aggregate grape-up suite preserved for direct `grape test GrapeUp` use."""

    @pytest.mark.parametrize("scenario", ALL_SCENARIO_PARAMS)
    def testGrapeUp(self, grape_case, scenario):
        scenario.reset(grape_case.defaultWorkingDirectory)
        testUpdateLocal.assert_grape_up(grape_case, scenario)
