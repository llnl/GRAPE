import os
from test import gridTesting
from test import testGrape
from test import testProjectScenarios


class GrapeStatusTester(testGrape.TestGrape):

    def gridtestGrapeStatus(self, testProjectScenario):
        if testProjectScenario.debugging():
            self.logger.restore_sys_stdout()
            self.logger.log_to_stdout_debug()
        self.menu.set_workspace_dir(testProjectScenario.getProjectDir())
        self.assertTrue(self.menu.applyMenuChoice("status"),
                        "status Failed when no flags requesting fail codes were used.")
        ret = self.menu.applyMenuChoice("status", ["--failIfInconsistent"])
        if testProjectScenario.isConsistent():
            self.assertTrue(ret, "status thought a consistent project was inconsistent")
        else:
            self.assertFalse(ret, "status thought an inconsistent project was consistent")
        if testProjectScenario.debugging():
            self.logger.redirect_sys_stdout()

    def gridtestGrapeCheckoutOfMasterFixesGrapeStatusBranchConsistency(self, testProjectScenario):
        if testProjectScenario.debugging():
            self.logger.log_to_stdout_debug()
            self.logger.restore_sys_stdout()
        self.menu.set_workspace_dir(testProjectScenario.getProjectDir())
        ret = self.menu.applyMenuChoice("status", ["--failIfBranchesInconsistent"])
        if testProjectScenario.isStateConsistentWithBranchModel():
            self.assertTrue(ret, "grape thought consistent branch model repo was inconsistent")
        else:
            self.assertFalse(ret, "grape thought inconsistent branch model repo was consistent")
            self.menu.applyMenuChoice("checkout", ["master"])
            ret = self.menu.applyMenuChoice("status", ["--failIfBranchesInconsistent"])
            self.assertTrue(ret, "status not consistent after a grape checkout of master")
        if testProjectScenario.debugging():
            self.logger.redirect_sys_stdout()

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


TestStatus = createStatusTester()
