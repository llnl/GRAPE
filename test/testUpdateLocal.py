import os
import sys
from test import gridTesting
from test import testGrape
from test import testProjectScenarios


class GrapeUpTester(testGrape.TestGrape):

    def gridtestGrapeUp(self, testProjectScenario):
        self.menu.set_workspace_dir(testProjectScenario.getProjectDir())
        ret = self.menu.applyMenuChoice("up", args=None, option_args=None)
        self.assertTrue(ret, "up failed to run")
        # NOTE The following counting of the number of fetches is incorrect
        #upoutput = "%s" % self.output.getvalue()
        #print upoutput.split('\n')
        #numberOfFetches = 0
        #for l in upoutput.split('\n'):
        #    if "git fetch origin" in l and "Executing" in l:
        #        numberOfFetches += 1
        #self.assertEqual(numberOfFetches, testProjectScenario.numExpectedFetches(),
        #                 "Unexpected number of fetches %d != %d\n%s" % (numberOfFetches, testProjectScenario.numExpectedFetches(),upoutput))

        #if testProjectScenario.debugging() or debugging:
        #    self.switchToHiddenOutput()

def createUpTester():
    # create a tester for all grapeProject scenarios in the testProjectScenarios module.
    scenarioClasses = testProjectScenarios.find_subclasses(testProjectScenarios, testProjectScenarios.grapeProject)
    names = [cls.__name__ for cls in scenarioClasses]
    scenarios = [cls(n) for (cls,n) in zip(scenarioClasses, names)]
    gridTesting.gridifyTestClass(scenarios, GrapeUpTester, names)
    GrapeUpTester.__test__ = False
    pytest_tester = type("TestGrapeUp", (GrapeUpTester,), {})
    pytest_tester.__test__ = True
    return pytest_tester


TestGrapeUp = createUpTester()
