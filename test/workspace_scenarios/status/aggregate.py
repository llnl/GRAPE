import pytest

from test import testStatus
from test.workspace_scenarios.shared import ALL_SCENARIO_PARAMS
from test.workspace_scenarios.shared import grape_case


pytestmark = [pytest.mark.scenario, pytest.mark.slow]


class TestStatusScenarios:
    """Aggregate status suite preserved for direct `grape test Status` use."""

    @pytest.mark.parametrize("scenario", ALL_SCENARIO_PARAMS)
    def testGrapeStatus(self, grape_case, scenario):
        scenario.reset(grape_case.defaultWorkingDirectory)
        testStatus.assert_grape_status(grape_case, scenario)

    @pytest.mark.parametrize("scenario", ALL_SCENARIO_PARAMS)
    def testGrapeCheckoutOfMasterFixesGrapeStatusBranchConsistency(
        self, grape_case, scenario
    ):
        scenario.reset(grape_case.defaultWorkingDirectory)
        testStatus.assert_checkout_fixes_branch_consistency(grape_case, scenario)
