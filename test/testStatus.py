import os
from test import gridTesting
from test import testGrape
from test import testProjectScenarios


class GrapeStatusTester(testGrape.TestGrape):

    def gridtestGrapeStatus(self, testProjectScenario):
        assert_grape_status(self, testProjectScenario)

    def gridtestGrapeCheckoutOfMasterFixesGrapeStatusBranchConsistency(self, testProjectScenario):
        assert_checkout_fixes_branch_consistency(self, testProjectScenario)


def assert_grape_status(test_case, testProjectScenario):
    if testProjectScenario.debugging():
        test_case.logger.restore_sys_stdout()
        test_case.logger.log_to_stdout_debug()
    test_case.menu.set_workspace_dir(testProjectScenario.getProjectDir())
    test_case.assertTrue(test_case.menu.applyMenuChoice("status"),
                    "status Failed when no flags requesting fail codes were used.")
    ret = test_case.menu.applyMenuChoice("status", ["--failIfInconsistent"])
    if testProjectScenario.isConsistent():
        test_case.assertTrue(ret, "status thought a consistent project was inconsistent")
    else:
        test_case.assertFalse(ret, "status thought an inconsistent project was consistent")
    if testProjectScenario.debugging():
        test_case.logger.redirect_sys_stdout()


def assert_checkout_fixes_branch_consistency(test_case, testProjectScenario):
    if testProjectScenario.debugging():
        test_case.logger.log_to_stdout_debug()
        test_case.logger.restore_sys_stdout()
    test_case.menu.set_workspace_dir(testProjectScenario.getProjectDir())
    ret = test_case.menu.applyMenuChoice("status", ["--failIfBranchesInconsistent"])
    if testProjectScenario.isStateConsistentWithBranchModel():
        test_case.assertTrue(ret, "grape thought consistent branch model repo was inconsistent")
    else:
        test_case.assertFalse(ret, "grape thought inconsistent branch model repo was consistent")
        test_case.menu.applyMenuChoice("checkout", ["master"])
        ret = test_case.menu.applyMenuChoice("status", ["--failIfBranchesInconsistent"])
        test_case.assertTrue(ret, "status not consistent after a grape checkout of master")
    if testProjectScenario.debugging():
        test_case.logger.redirect_sys_stdout()

def createStatusTester():
    # create a tester for all grapeProject scenarios in the testProjectScenarios module.
    scenarioClasses = testProjectScenarios.find_subclasses(testProjectScenarios, testProjectScenarios.grapeProject)
    names = [cls.__name__ for cls in scenarioClasses]
    scenarios = [cls(n) for (cls,n) in zip(scenarioClasses, names)]
    gridTesting.gridifyTestClass(scenarios, GrapeStatusTester, names)
    GrapeStatusTester.__test__ = False
    pytest_tester = type("TestStatus", (GrapeStatusTester,), {})
    pytest_tester.__test__ = True
    return pytest_tester
