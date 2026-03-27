"""Mapping layer between GRAPE suite names and pytest collection nodes.

Pytest identifies tests by file / class / function node ids such as:
`test/testReview.py::TestReview::testReview`

GRAPE historically exposed shorter suite aliases such as `Review` or
`Review.testReview`. This module preserves those aliases and also holds the
path-to-suite mapping used by `grape test --changed`.
"""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class TestSuite:
    """Metadata for one user-visible GRAPE test suite."""
    alias: str
    path: str
    class_name: str
    visible: bool = True
    include_in_all: bool = True
    serial: bool = False
    watch_paths: tuple[str, ...] = ()


SUITES = {
    "Branches": TestSuite("Branches", "test/testBranches.py", "TestBranches", watch_paths=("test/testBranches.py", "vine/branches.py")),
    "Bundle": TestSuite("Bundle", "test/testBundle.py", "TestBundle", watch_paths=("test/testBundle.py", "vine/bundle.py")),
    "Clone": TestSuite("Clone", "test/clone/aggregate.py", "TestClone", include_in_all=False, watch_paths=("test/clone", "test/testClone.py", "vine/clone.py")),
    "CloneSmoke": TestSuite("CloneSmoke", "test/clone/test_smoke.py", "TestCloneSmoke", visible=False, watch_paths=("test/clone", "test/testClone.py", "vine/clone.py")),
    "CloneSubmodule": TestSuite("CloneSubmodule", "test/clone/test_submodule.py", "TestCloneSubmodule", visible=False, watch_paths=("test/clone", "test/testClone.py", "vine/clone.py")),
    "CloneNested": TestSuite("CloneNested", "test/clone/test_nested.py", "TestCloneNested", visible=False, watch_paths=("test/clone", "test/testClone.py", "vine/clone.py")),
    "Config": TestSuite("Config", "test/testConfig.py", "TestConfig", watch_paths=("test/testConfig.py", "vine/config.py", "vine/writeConfig.py")),
    "DeleteBranch": TestSuite("DeleteBranch", "test/testDeleteBranch.py", "TestDeleteBranch", watch_paths=("test/testDeleteBranch.py", "vine/deleteBranch.py")),
    "GrapeGit": TestSuite("GrapeGit", "test/testGrapeGit.py", "TestGrapeGit", watch_paths=("test/testGrapeGit.py", "vine/grapeGit.py")),
    "MergeDown": TestSuite("MergeDown", "test/merge_down/aggregate.py", "TestMD", include_in_all=False, watch_paths=("test/merge_down", "test/testMergeDown.py", "vine/mergeDown.py", "vine/merge.py")),
    "MergeDownBasic": TestSuite("MergeDownBasic", "test/merge_down/test_basic.py", "TestMergeDownBasic", visible=False, watch_paths=("test/merge_down", "test/testMergeDown.py", "vine/mergeDown.py", "vine/merge.py")),
    "MergeDownSubmoduleNonConflict": TestSuite("MergeDownSubmoduleNonConflict", "test/merge_down/test_submodule_non_conflict.py", "TestMergeDownSubmoduleNonConflict", visible=False, watch_paths=("test/merge_down", "test/testMergeDown.py", "vine/mergeDown.py", "vine/merge.py")),
    "MergeDownSubmoduleConflict": TestSuite("MergeDownSubmoduleConflict", "test/merge_down/test_submodule_conflict.py", "TestMergeDownSubmoduleConflict", visible=False, watch_paths=("test/merge_down", "test/testMergeDown.py", "vine/mergeDown.py", "vine/merge.py")),
    "MergeDownNestedSubproject": TestSuite("MergeDownNestedSubproject", "test/merge_down/test_nested_subproject.py", "TestMergeDownNestedSubproject", visible=False, watch_paths=("test/merge_down", "test/testMergeDown.py", "vine/mergeDown.py", "vine/merge.py")),
    "ResolveConflicts": TestSuite("ResolveConflicts", "test/testResolveConflicts.py", "TestResolveConflicts", watch_paths=("test/testResolveConflicts.py", "vine/resolveConflicts.py")),
    "Review": TestSuite("Review", "test/testReview.py", "TestReview", watch_paths=("test/testReview.py", "vine/review.py", "vine/Gitlab.py")),
    "Stash": TestSuite("Stash", "test/testStash.py", "TestStash", watch_paths=("test/testStash.py", "vine/stash.py")),
    "Unbundle": TestSuite("Unbundle", "test/testUnbundle.py", "TestUnbundle", watch_paths=("test/testUnbundle.py", "vine/bundle.py")),
    "Version": TestSuite("Version", "test/testVersion.py", "TestVersion", watch_paths=("test/testVersion.py", "vine/version.py")),
    "Publish": TestSuite("Publish", "test/publish", "", include_in_all=False, watch_paths=("test/publish", "vine/publish.py")),
    "PublishFFDefault": TestSuite("PublishFFDefault", "test/publish/test_fast_forward.py", "TestPublishFFDefault", visible=False, watch_paths=("test/publish", "vine/publish.py")),
    "PublishFFMerge": TestSuite("PublishFFMerge", "test/publish/test_fast_forward.py", "TestPublishFFMerge", visible=False, watch_paths=("test/publish", "vine/publish.py")),
    "PublishFFSquash": TestSuite("PublishFFSquash", "test/publish/test_fast_forward.py", "TestPublishFFSquash", visible=False, watch_paths=("test/publish", "vine/publish.py")),
    "PublishFFCascade": TestSuite("PublishFFCascade", "test/publish/test_fast_forward.py", "TestPublishFFCascade", visible=False, watch_paths=("test/publish", "vine/publish.py")),
    "PublishFFRebase": TestSuite("PublishFFRebase", "test/publish/test_fast_forward.py", "TestPublishFFRebase", visible=False, watch_paths=("test/publish", "vine/publish.py")),
    "PublishTopicConfig": TestSuite("PublishTopicConfig", "test/publish/test_options.py", "TestPublishTopicConfig", visible=False, watch_paths=("test/publish", "vine/publish.py")),
    "PublishCustomBuild": TestSuite("PublishCustomBuild", "test/publish/test_options.py", "TestPublishCustomBuild", visible=False, watch_paths=("test/publish", "vine/publish.py")),
    "PublishCustomTest": TestSuite("PublishCustomTest", "test/publish/test_options.py", "TestPublishCustomTest", visible=False, watch_paths=("test/publish", "vine/publish.py")),
    "PublishVersionTick": TestSuite("PublishVersionTick", "test/publish/test_options.py", "TestPublishVersionTick", visible=False, watch_paths=("test/publish", "vine/publish.py")),
    "PublishStartStop": TestSuite("PublishStartStop", "test/publish/test_options.py", "TestPublishStartStop", visible=False, watch_paths=("test/publish", "vine/publish.py")),
    "PublishNestedSubprojects": TestSuite("PublishNestedSubprojects", "test/publish/test_workspace.py", "TestPublishNestedSubprojects", visible=False, watch_paths=("test/publish", "vine/publish.py")),
    "PublishFromNestedSubproject": TestSuite("PublishFromNestedSubproject", "test/publish/test_workspace.py", "TestPublishFromNestedSubproject", visible=False, watch_paths=("test/publish", "vine/publish.py")),
    "PublishNewSubmodule": TestSuite("PublishNewSubmodule", "test/publish/test_workspace.py", "TestPublishNewSubmodule", visible=False, watch_paths=("test/publish", "vine/publish.py")),
    "CO": TestSuite("CO", "test/testCO.py", "TestCheckout", watch_paths=("test/testCO.py", "vine/checkout.py")),
    "NestedSubproject": TestSuite("NestedSubproject", "test/nested_subproject/aggregate.py", "TestNestedSubproject", include_in_all=False, watch_paths=("test/nested_subproject", "test/testNestedSubproject.py", "vine/addSubproject.py", "vine/updateView.py")),
    "NestedSubprojectTopology": TestSuite("NestedSubprojectTopology", "test/nested_subproject/test_topology.py", "TestNestedSubprojectTopology", visible=False, watch_paths=("test/nested_subproject", "test/testNestedSubproject.py", "vine/addSubproject.py", "vine/updateView.py")),
    "NestedSubprojectWorkspaceSync": TestSuite("NestedSubprojectWorkspaceSync", "test/nested_subproject/test_workspace_sync.py", "TestNestedSubprojectWorkspaceSync", visible=False, watch_paths=("test/nested_subproject", "test/testNestedSubproject.py", "vine/addSubproject.py", "vine/updateView.py")),
    "NestedSubprojectProjectCommands": TestSuite("NestedSubprojectProjectCommands", "test/nested_subproject/test_project_commands.py", "TestNestedSubprojectProjectCommands", visible=False, watch_paths=("test/nested_subproject", "test/testNestedSubproject.py", "vine/addSubproject.py", "vine/updateView.py")),
    "Status": TestSuite("Status", "test/workspace_scenarios/status/aggregate.py", "TestStatusScenarios", visible=False, include_in_all=False, watch_paths=("test/workspace_scenarios", "test/testStatus.py", "test/testProjectScenarios.py", "test/gridTesting.py", "vine/status.py")),
    "StatusRepo": TestSuite("StatusRepo", "test/workspace_scenarios/status/test_repo.py", "TestStatusRepo", visible=False, watch_paths=("test/workspace_scenarios", "test/testStatus.py", "test/testProjectScenarios.py", "test/gridTesting.py", "vine/status.py")),
    "StatusSubmodule": TestSuite("StatusSubmodule", "test/workspace_scenarios/status/test_submodule.py", "TestStatusSubmodule", visible=False, watch_paths=("test/workspace_scenarios", "test/testStatus.py", "test/testProjectScenarios.py", "test/gridTesting.py", "vine/status.py")),
    "StatusTwoClients": TestSuite("StatusTwoClients", "test/workspace_scenarios/status/test_two_clients.py", "TestStatusTwoClients", visible=False, watch_paths=("test/workspace_scenarios", "test/testStatus.py", "test/testProjectScenarios.py", "test/gridTesting.py", "vine/status.py")),
    "StatusNested": TestSuite("StatusNested", "test/workspace_scenarios/status/test_nested.py", "TestStatusNested", visible=False, watch_paths=("test/workspace_scenarios", "test/testStatus.py", "test/testProjectScenarios.py", "test/gridTesting.py", "vine/status.py")),
    "GrapeUp": TestSuite("GrapeUp", "test/workspace_scenarios/grape_up/aggregate.py", "TestGrapeUpScenarios", visible=False, include_in_all=False, watch_paths=("test/workspace_scenarios", "test/testUpdateLocal.py", "test/testProjectScenarios.py", "test/gridTesting.py", "vine/updateLocal.py")),
    "GrapeUpRepo": TestSuite("GrapeUpRepo", "test/workspace_scenarios/grape_up/test_repo.py", "TestGrapeUpRepo", visible=False, watch_paths=("test/workspace_scenarios", "test/testUpdateLocal.py", "test/testProjectScenarios.py", "test/gridTesting.py", "vine/updateLocal.py")),
    "GrapeUpSubmodule": TestSuite("GrapeUpSubmodule", "test/workspace_scenarios/grape_up/test_submodule.py", "TestGrapeUpSubmodule", visible=False, watch_paths=("test/workspace_scenarios", "test/testUpdateLocal.py", "test/testProjectScenarios.py", "test/gridTesting.py", "vine/updateLocal.py")),
    "GrapeUpTwoClients": TestSuite("GrapeUpTwoClients", "test/workspace_scenarios/grape_up/test_two_clients.py", "TestGrapeUpTwoClients", visible=False, watch_paths=("test/workspace_scenarios", "test/testUpdateLocal.py", "test/testProjectScenarios.py", "test/gridTesting.py", "vine/updateLocal.py")),
    "GrapeUpNested": TestSuite("GrapeUpNested", "test/workspace_scenarios/grape_up/test_nested.py", "TestGrapeUpNested", visible=False, watch_paths=("test/workspace_scenarios", "test/testUpdateLocal.py", "test/testProjectScenarios.py", "test/gridTesting.py", "vine/updateLocal.py")),
}

COMMON_WATCH_PATHS = (
    "test/testGrape.py",
    "test/conftest.py",
    "pytest.ini",
    "vine/grapeMenu.py",
    "vine/config_parser_global.py",
    "vine/utility.py",
    "vine/option.py",
    "vine/grapeTest.py",
    "vine/test_suites.py",
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITE_ORDER_FILE = os.path.join(REPO_ROOT, "test", "suite_order.txt")


def visible_suite_names():
    return [name for name, suite in SUITES.items() if suite.visible]


def all_suite_names():
    return [name for name, suite in SUITES.items() if suite.include_in_all]


def configured_suite_order(order_path=None):
    """Load the optional broad-run suite launch order from the repository.

    The file contains one suite alias per line. Blank lines and `#` comments
    are ignored. Unlisted suites keep their default relative order and run
    after the named suites.
    """
    if order_path is None:
        order_path = SUITE_ORDER_FILE
    if not os.path.exists(order_path):
        return []

    ordered = []
    seen = set()
    with open(order_path, encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.split("#", 1)[0].strip()
            if not line or line in seen:
                continue
            if line not in SUITES:
                raise ValueError(
                    f"Invalid suite alias '{line}' in {order_path}:{line_number}"
                )
            ordered.append(line)
            seen.add(line)
    return ordered


def order_selectors(selectors, order_path=None):
    """Return selectors reordered by the repository's launch-priority file."""
    priority = {
        alias: index
        for index, alias in enumerate(configured_suite_order(order_path=order_path))
    }
    indexed = list(enumerate(selectors))
    indexed.sort(
        key=lambda item: (
            priority.get(selector_suite_name(item[1]), len(priority)),
            item[0],
        )
    )
    return [selector for _, selector in indexed]


def suite_node(alias):
    """Return the pytest node prefix for a GRAPE suite alias."""
    suite = SUITES[alias]
    if suite.class_name:
        return f"{suite.path}::{suite.class_name}"
    return suite.path


def resolve_selector(selector):
    """Convert `Review` or `Review.testReview` into a pytest node id."""
    if "." in selector:
        alias, test_name = selector.split(".", 1)
    else:
        alias, test_name = selector, None
    if alias not in SUITES:
        valid = visible_suite_names()
        raise KeyError(
            f"*** {alias} is not a valid test suite!\nValid values are:\n{dict.fromkeys(valid).keys()}"
        )

    node = suite_node(alias)
    if test_name:
        node = f"{node}::{test_name}"
    return node


def resolve_selectors(selectors):
    return [resolve_selector(selector) for selector in selectors]


def selector_suite_name(selector):
    if "." in selector:
        selector = selector.split(".", 1)[0]
    return selector


def is_serial_selector(selector):
    return SUITES[selector_suite_name(selector)].serial


def select_suites_for_changed_paths(paths):
    """Map changed files to the smallest useful GRAPE suite set.

    If a shared runner file changes, we conservatively fall back to the full
    suite because the impact is broad. Otherwise we select only suites whose
    watch lists match the changed paths.
    """
    changed = set()
    for path in paths:
        normalized = path.strip()
        if not normalized:
            continue
        if any(normalized == common or normalized.startswith(f"{common}/") for common in COMMON_WATCH_PATHS):
            return all_suite_names()
        for alias, suite in SUITES.items():
            for watch_path in suite.watch_paths:
                if normalized == watch_path or normalized.startswith(f"{watch_path}/"):
                    changed.add(alias)
                    break
    return [alias for alias in all_suite_names() if alias in changed]
