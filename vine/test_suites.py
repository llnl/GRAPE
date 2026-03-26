from dataclasses import dataclass


@dataclass(frozen=True)
class TestSuite:
    alias: str
    path: str
    class_name: str
    visible: bool = True


SUITES = {
    "Branches": TestSuite("Branches", "test/testBranches.py", "TestBranches"),
    "Bundle": TestSuite("Bundle", "test/testBundle.py", "TestBundle"),
    "Clone": TestSuite("Clone", "test/testClone.py", "TestClone"),
    "Config": TestSuite("Config", "test/testConfig.py", "TestConfig"),
    "DeleteBranch": TestSuite("DeleteBranch", "test/testDeleteBranch.py", "TestDeleteBranch"),
    "GrapeGit": TestSuite("GrapeGit", "test/testGrapeGit.py", "TestGrapeGit"),
    "MergeDown": TestSuite("MergeDown", "test/testMergeDown.py", "TestMD"),
    "ResolveConflicts": TestSuite("ResolveConflicts", "test/testResolveConflicts.py", "TestResolveConflicts"),
    "Review": TestSuite("Review", "test/testReview.py", "TestReview"),
    "Stash": TestSuite("Stash", "test/testStash.py", "TestStash"),
    "Unbundle": TestSuite("Unbundle", "test/testUnbundle.py", "TestUnbundle"),
    "Version": TestSuite("Version", "test/testVersion.py", "TestVersion"),
    "Publish": TestSuite("Publish", "test/testPublish.py", "TestPublish"),
    "CO": TestSuite("CO", "test/testCO.py", "TestCheckout"),
    "NestedSubproject": TestSuite("NestedSubproject", "test/testNestedSubproject.py", "TestNestedSubproject"),
    "Status": TestSuite("Status", "test/testStatus.py", "TestStatus", visible=False),
    "GrapeUp": TestSuite("GrapeUp", "test/testUpdateLocal.py", "TestGrapeUp", visible=False),
}


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
