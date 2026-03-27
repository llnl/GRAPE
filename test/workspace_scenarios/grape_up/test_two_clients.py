import pytest

from test import testUpdateLocal
from test.workspace_scenarios.shared import grape_case
from test.workspace_scenarios.shared import scenario_params


pytestmark = [pytest.mark.scenario, pytest.mark.slow]


class TestGrapeUpTwoClients:
    """`grape up` shard for the two-client synchronization scenario."""

    @pytest.mark.parametrize("scenario", scenario_params("two_clients"))
    def testGrapeUp(self, grape_case, scenario):
        scenario.reset(grape_case.defaultWorkingDirectory)
        testUpdateLocal.assert_grape_up(grape_case, scenario)
