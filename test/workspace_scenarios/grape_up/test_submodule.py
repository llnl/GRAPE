import pytest

from test import testUpdateLocal
from test.workspace_scenarios.shared import grape_case
from test.workspace_scenarios.shared import scenario_params


pytestmark = [pytest.mark.scenario, pytest.mark.slow]


class TestGrapeUpSubmodule:
    """`grape up` shard for submodule-heavy workspace scenarios."""

    @pytest.mark.parametrize("scenario", scenario_params("submodule"))
    def testGrapeUp(self, grape_case, scenario):
        scenario.reset(grape_case.defaultWorkingDirectory)
        testUpdateLocal.assert_grape_up(grape_case, scenario)
