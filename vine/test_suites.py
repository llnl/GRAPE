from dataclasses import dataclass


@dataclass(frozen=True)
class TestSuite:
    alias: str
    path: str
    class_name: str
    visible: bool = True
    serial: bool = False
    watch_paths: tuple[str, ...] = ()


SUITES = {
    "Branches": TestSuite("Branches", "test/testBranches.py", "TestBranches", watch_paths=("test/testBranches.py", "vine/branches.py")),
    "Bundle": TestSuite("Bundle", "test/testBundle.py", "TestBundle", watch_paths=("test/testBundle.py", "vine/bundle.py")),
    "Clone": TestSuite("Clone", "test/testClone.py", "TestClone", watch_paths=("test/testClone.py", "vine/clone.py")),
    "Config": TestSuite("Config", "test/testConfig.py", "TestConfig", watch_paths=("test/testConfig.py", "vine/config.py", "vine/writeConfig.py")),
    "DeleteBranch": TestSuite("DeleteBranch", "test/testDeleteBranch.py", "TestDeleteBranch", watch_paths=("test/testDeleteBranch.py", "vine/deleteBranch.py")),
    "GrapeGit": TestSuite("GrapeGit", "test/testGrapeGit.py", "TestGrapeGit", watch_paths=("test/testGrapeGit.py", "vine/grapeGit.py")),
    "MergeDown": TestSuite("MergeDown", "test/testMergeDown.py", "TestMD", watch_paths=("test/testMergeDown.py", "vine/mergeDown.py", "vine/merge.py")),
    "ResolveConflicts": TestSuite("ResolveConflicts", "test/testResolveConflicts.py", "TestResolveConflicts", watch_paths=("test/testResolveConflicts.py", "vine/resolveConflicts.py")),
    "Review": TestSuite("Review", "test/testReview.py", "TestReview", watch_paths=("test/testReview.py", "vine/review.py", "vine/Gitlab.py")),
    "Stash": TestSuite("Stash", "test/testStash.py", "TestStash", watch_paths=("test/testStash.py", "vine/stash.py")),
    "Unbundle": TestSuite("Unbundle", "test/testUnbundle.py", "TestUnbundle", watch_paths=("test/testUnbundle.py", "vine/bundle.py")),
    "Version": TestSuite("Version", "test/testVersion.py", "TestVersion", watch_paths=("test/testVersion.py", "vine/version.py")),
    "Publish": TestSuite("Publish", "test/testPublish.py", "TestPublish", serial=True, watch_paths=("test/testPublish.py", "vine/publish.py")),
    "CO": TestSuite("CO", "test/testCO.py", "TestCheckout", watch_paths=("test/testCO.py", "vine/checkout.py")),
    "NestedSubproject": TestSuite("NestedSubproject", "test/testNestedSubproject.py", "TestNestedSubproject", watch_paths=("test/testNestedSubproject.py", "vine/addSubproject.py", "vine/updateView.py")),
    "Status": TestSuite("Status", "test/testWorkspaceScenarios.py", "TestStatusScenarios", visible=False, watch_paths=("test/testWorkspaceScenarios.py", "test/testStatus.py", "test/testProjectScenarios.py", "test/gridTesting.py", "vine/status.py")),
    "GrapeUp": TestSuite("GrapeUp", "test/testWorkspaceScenarios.py", "TestGrapeUpScenarios", visible=False, watch_paths=("test/testWorkspaceScenarios.py", "test/testUpdateLocal.py", "test/testProjectScenarios.py", "test/gridTesting.py", "vine/updateLocal.py")),
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


def visible_suite_names():
    return [name for name, suite in SUITES.items() if suite.visible]


def all_suite_names():
    return list(SUITES.keys())


def suite_node(alias):
    suite = SUITES[alias]
    return f"{suite.path}::{suite.class_name}"


def resolve_selector(selector):
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
