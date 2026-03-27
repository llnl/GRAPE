import pytest

from test import testStatus
from test.workspace_scenarios.shared import grape_case
from test.workspace_scenarios.shared import scenario_params


pytestmark = [pytest.mark.scenario, pytest.mark.slow]


class TestStatusSubmodule:
    """Status shard for submodule-heavy workspace scenarios."""

    @pytest.mark.parametrize("scenario", scenario_params("submodule"))
    def testGrapeStatus(self, grape_case, scenario):
        scenario.reset(grape_case.defaultWorkingDirectory)
        testStatus.assert_grape_status(grape_case, scenario)

    @pytest.mark.parametrize("scenario", scenario_params("submodule"))
    def testGrapeCheckoutOfMasterFixesGrapeStatusBranchConsistency(
        self, grape_case, scenario
    ):
        scenario.reset(grape_case.defaultWorkingDirectory)
        testStatus.assert_checkout_fixes_branch_consistency(grape_case, scenario)
