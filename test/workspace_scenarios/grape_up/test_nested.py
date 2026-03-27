import pytest

from test import testUpdateLocal
from test.workspace_scenarios.shared import grape_case
from test.workspace_scenarios.shared import scenario_params


pytestmark = [pytest.mark.scenario, pytest.mark.slow]


class TestGrapeUpNested:
    """`grape up` shard for nested-subproject workspace scenarios."""

    @pytest.mark.parametrize("scenario", scenario_params("nested"))
    def testGrapeUp(self, grape_case, scenario):
        scenario.reset(grape_case.defaultWorkingDirectory)
        testUpdateLocal.assert_grape_up(grape_case, scenario)
