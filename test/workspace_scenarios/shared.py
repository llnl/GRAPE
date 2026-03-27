"""Shared pytest helpers for split workspace-scenario suites.

If you are new to pytest, two patterns matter here:

- a fixture is a setup helper that tests request by naming an argument
- parametrization lets one test function run once per scenario object

The broad runner can only schedule work at the file or class level, so these
helpers define explicit scenario groups instead of discovery-order slices.
That keeps the shard membership stable as new scenario classes are added.
"""

import pytest

from test import testGrape
from test import testProjectScenarios


SCENARIO_GROUPS = {
    "repo": (
        "singleRepo",
        "repoWithLocalGitflowBranches",
        "repoWithLocalAndOriginGitflowBranches",
        "singleRepoWithMissingLocalPublicBranches",
    ),
    "submodule": (
        "validRepoWithSubmodule",
        "WorkspaceWithSubmoduleOnDevelop",
        "WorkspaceOnDevelopSubmoduleOnDevelop",
        "WorkspaceOnTopicSubmoduleOnMaster",
        "WorkspaceOnTopicSubmoduleOnTopic",
        "WorkspaceWithDetachedSubmodule",
    ),
    "two_clients": (
        "WorkspaceOnTopicSubmoduleOnTopicTwoClients",
    ),
    "nested": (
        "ValidRepoWithNestedSubproject",
        "WorkspaceWithNestedOnDevelop",
    ),
}


def _scenario_classes_by_name():
    classes = testProjectScenarios.find_subclasses(
        testProjectScenarios, testProjectScenarios.grapeProject
    )
    return {scenario_class.__name__: scenario_class for scenario_class in classes}


SCENARIO_CLASSES = _scenario_classes_by_name()
SCENARIO_OBJECTS = {
    class_name: SCENARIO_CLASSES[class_name](class_name)
    for group in SCENARIO_GROUPS.values()
    for class_name in group
}


def scenario_params(group_name):
    """Return stable pytest parameters for one explicit scenario shard."""
    return SCENARIO_PARAM_GROUPS[group_name]


SCENARIO_PARAM_GROUPS = {
    group_name: [
        pytest.param(SCENARIO_OBJECTS[class_name], id=class_name)
        for class_name in class_names
    ]
    for group_name, class_names in SCENARIO_GROUPS.items()
}


ALL_SCENARIO_PARAMS = [
    pytest.param(SCENARIO_OBJECTS[class_name], id=class_name)
    for group in SCENARIO_GROUPS.values()
    for class_name in group
]


@pytest.fixture
def grape_case():
    """Provide the shared `TestGrape` harness to pytest shard functions."""
    case = testGrape.TestGrape("runTest")
    case.setUp()
    try:
        yield case
    finally:
        case.tearDown()
